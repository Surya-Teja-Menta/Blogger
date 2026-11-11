"""The voice farm: the narration in the owner's cloned voice, spoken on many GitHub machines at once.

One machine clones a 10-minute narration in about two hours (the free runners have no graphics card). So the
narration's lines are split into contiguous chunks of about equal length and each chunk is cloned on its own machine
in parallel: about a quarter of an hour for the lot.

The machines are jobs of the same workflow run as the make job (the "voice" job of .github/workflows/make.yml: a
matrix of CHUNKS machines that start with the run, install the cloning environment while the script is being
written, and wait). A separate workflow started by the make job would be held by GitHub for approval; jobs of the
run itself are never held. The make job stays the one process that holds the video (script, pictures, timings), so
nothing has to be resumed: it puts each chunk's lines in the private storage bucket, waits for the audio to appear
there, and takes it from there. The lines and the audio travel through the private bucket (the repository is public)
and are deleted afterwards. Anything that goes wrong (no machine came, one died, one is too slow) returns the chunk
as missing and the caller clones it on its own machine, or speaks it with the standard voice: a video is never lost.
"""
import hashlib
import json
import os
import time
import zipfile
from typing import Callable, List, Optional

from .config import Settings

CHUNKS = 12                  # machines per video: the size of the "voice" job's matrix in make.yml (keep equal)
WAIT_MINUTES = 150           # how long the make job waits for the audio before cloning what is missing itself (every sentence is
                             # chosen from several checked takes: slow on purpose)
HELLO_MINUTES = 6            # a machine that has not said it is there this long after its lines were put out is not coming
POLL_SECONDS = 20


def run_prefix(topic: str, lesson: str = "") -> str:
    """The bucket folder this run's make job and its voice machines share (several topics can run in one workflow
    run, so the topic is part of it)."""
    tag = hashlib.sha1(f"{topic}|{lesson}".encode("utf-8")).hexdigest()[:8]
    return f"voice-farm/{os.environ.get('GITHUB_RUN_ID', 'local')}-{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}-{tag}"


def available(settings: Settings) -> bool:
    """True where the farm can run: inside a GitHub run, with the private bucket."""
    off = os.environ.get("VOICE_FARM", "on").strip().lower() in ("off", "0", "no", "false")
    return bool(not off and settings.storage_configured and os.environ.get("GITHUB_RUN_ID") and os.environ.get("RUN_TOPIC"))


def split(sizes: List[int], n: int) -> List[range]:
    """n contiguous runs of lines whose total sizes are about equal (never an empty run)."""
    n = max(1, min(n, len(sizes)))
    total = sum(sizes) or 1
    out: List[range] = []
    start, acc = 0, 0
    for i, size in enumerate(sizes):
        acc += size
        lines_after = len(sizes) - i - 1
        runs_after = n - len(out) - 1                     # runs still to open once the current one closes
        if len(out) < n - 1 and (acc >= total * (len(out) + 1) / n or lines_after == runs_after):
            out.append(range(start, i + 1))
            start = i + 1
    if start < len(sizes):
        out.append(range(start, len(sizes)))
    return out


def _keys(s3, bucket: str, prefix: str) -> List[str]:
    return [o["Key"] for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix)
            for o in page.get("Contents", [])]


def clone(texts: List[str], settings: Settings, job: str, log: Callable[[str], None],
          sleep: Callable[[float], None] = time.sleep) -> Optional[List[dict]]:
    """Every line cloned on the farm. One entry per line: {"ok", "out" (a WAV), "words", "match"} when its machine
    delivered, {"missing": True} when its whole chunk did not. None when the farm could not be used at all."""
    from .storage import _client, prune_prefix
    chunks = split([len(t) for t in texts], CHUNKS)
    wait = float(os.environ.get("VOICE_FARM_WAIT_MINUTES") or WAIT_MINUTES) * 60
    hello = float(os.environ.get("VOICE_FARM_HELLO_MINUTES") or HELLO_MINUTES) * 60
    prefix = run_prefix(os.environ.get("RUN_TOPIC", ""), os.environ.get("RUN_LESSON", ""))
    bucket = settings.s3_bucket
    t0 = time.time()
    s3 = None
    try:
        s3 = _client(settings)
        for k in range(CHUNKS):                           # every machine gets its lines (or an empty chunk)
            lines = chunks[k] if k < len(chunks) else range(0)
            body = json.dumps([{"text": texts[i]} for i in lines], ensure_ascii=False).encode("utf-8")
            s3.put_object(Bucket=bucket, Key=f"{prefix}/spec-{k}.json", Body=body)
        log(f"[voice] farm: {len(texts)} lines in {len(chunks)} chunks put out for the voice machines")
        ready, failed, pending, last = set(), set(), set(range(len(chunks))), t0
        while pending and time.time() - t0 < wait:
            seen = set(_keys(s3, bucket, prefix + "/"))
            for k in sorted(pending):
                if f"{prefix}/out-{k}.zip" in seen:
                    ready.add(k)
                elif f"{prefix}/err-{k}.txt" in seen:
                    failed.add(k)
                elif time.time() - t0 > hello and f"{prefix}/alive-{k}.txt" not in seen:
                    failed.add(k)                       # no machine came for this chunk (the runner queue was full)
            pending -= ready | failed
            if pending:
                if time.time() - last > 300:
                    log(f"[voice] farm: {len(ready)} of {len(chunks)} chunks done after {(time.time() - t0) / 60:.0f} min")
                    last = time.time()
                sleep(POLL_SECONDS)
        items: List[dict] = [{"missing": True} for _ in texts]
        delivered = 0
        for k in sorted(ready):
            folder = os.path.join(job, f"farm_{k}")
            os.makedirs(folder, exist_ok=True)
            try:
                s3.download_file(bucket, f"{prefix}/out-{k}.zip", os.path.join(folder, "out.zip"))
                with zipfile.ZipFile(os.path.join(folder, "out.zip")) as z:
                    z.extractall(folder)
                with open(os.path.join(folder, "jobs.json"), encoding="utf-8") as f:
                    done = json.load(f)
            except Exception as exc:                    # a corrupt hand-over: that chunk is cloned here instead
                log(f"[voice] farm: chunk {k}'s audio could not be read ({type(exc).__name__})")
                continue
            delivered += 1
            for j, i in enumerate(chunks[k]):
                it = done[j] if j < len(done) else {}
                items[i] = {"ok": bool(it.get("ok")), "words": it.get("words") or [], "match": it.get("match", 0),
                            "checks": it.get("checks") or {},
                            "out": os.path.join(folder, f"{j}.wav")}
        log(f"[voice] farm: {delivered} of {len(chunks)} chunks delivered in {(time.time() - t0) / 60:.0f} min"
            + ("; the lines of the others are cloned here" if delivered < len(chunks) else ""))
        return items if delivered else None
    except Exception as exc:                            # the bucket, the network ...: the caller clones on its own
        log(f"[voice] farm: unavailable ({type(exc).__name__}: {str(exc)[:120]})")
        return None
    finally:
        try:        # tell the machines still waiting that there is nothing more to do; the lines and audio are not kept
            s3 = s3 or _client(settings)
            keys = _keys(s3, bucket, prefix + "/")
            for i in range(0, len(keys), 1000):
                s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in keys[i:i + 1000]]})
            s3.put_object(Bucket=bucket, Key=f"{prefix}/done.txt", Body=b"done")
            prune_prefix(settings, "voice-farm/", 2, lambda m: None)
        except Exception:
            pass


def release(settings: Settings) -> None:
    """Tell this run's voice machines there is nothing more for them to do (the make job ended, well or not)."""
    if not (settings.storage_configured and os.environ.get("GITHUB_RUN_ID") and os.environ.get("RUN_TOPIC")):
        return
    try:
        from .storage import _client
        prefix = run_prefix(os.environ.get("RUN_TOPIC", ""), os.environ.get("RUN_LESSON", ""))
        _client(settings).put_object(Bucket=settings.s3_bucket, Key=f"{prefix}/done.txt", Body=b"done")
    except Exception:
        pass
