"""The voice farm: the narration in the owner's cloned voice, spoken on many GitHub machines at once.

One machine clones a 10-minute narration in about two hours (the free runners have no graphics card). So the
narration's lines are split into contiguous chunks of about equal length and each chunk is cloned on its own machine
(workflow "Voice farm worker", blogwriter/voice_worker.py) in parallel: about a quarter of an hour for the lot.

The make job stays the one process that holds the video (script, pictures, timings), so nothing has to be resumed:
it writes each chunk's lines to the private storage bucket, asks GitHub to start one worker per chunk, waits for
their audio to appear in the bucket, and takes it from there. The workers get nothing but a random folder name and a
chunk number as inputs (the repository is public); the lines and the audio travel through the private bucket and are
deleted afterwards. Anything that goes wrong (no token, a worker that never starts or dies) returns the chunk as
missing and the caller clones it on its own machine, or speaks it with the standard voice: a video is never lost.
"""
import json
import os
import secrets
import time
import zipfile
from typing import Callable, List, Optional

import requests

from .config import Settings

WORKFLOW = "voice.yml"
CHUNKS = 12                  # machines per video (the free plan runs 20 jobs at a time; the make job is one)
WAIT_MINUTES = 75            # how long the make job waits for the workers before cloning what is missing itself
POLL_SECONDS = 20


def available(settings: Settings) -> bool:
    """True where the farm can run: on GitHub (a token and the repository's name), with the private bucket."""
    off = os.environ.get("VOICE_FARM", "on").strip().lower() in ("off", "0", "no", "false")
    return bool(not off and settings.storage_configured and os.environ.get("ACTIONS_TOKEN")
                and os.environ.get("GITHUB_REPOSITORY"))


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


def dispatch(prefix: str, index: int) -> Optional[str]:
    """Ask GitHub to start one worker; None when it was accepted, else why not."""
    url = f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/actions/workflows/{WORKFLOW}/dispatches"
    ref = os.environ.get("VOICE_FARM_REF") or os.environ.get("GITHUB_REF_NAME") or "main"
    headers = {"Authorization": f"Bearer {os.environ['ACTIONS_TOKEN']}", "Accept": "application/vnd.github+json"}
    why = "no answer"
    for _ in range(2):
        try:
            r = requests.post(url, headers=headers, timeout=30,
                              json={"ref": ref, "inputs": {"prefix": prefix, "index": str(index)}})
            if r.status_code == 204:
                return None
            why = f"HTTP {r.status_code} {r.text[:120]}"
            if r.status_code < 500:
                break
        except requests.RequestException as exc:
            why = type(exc).__name__
        time.sleep(3)
    return why


def _keys(s3, bucket: str, prefix: str) -> List[str]:
    return [o["Key"] for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix)
            for o in page.get("Contents", [])]


def clone(texts: List[str], settings: Settings, job: str, log: Callable[[str], None],
          sleep: Callable[[float], None] = time.sleep) -> Optional[List[dict]]:
    """Every line cloned on the farm. One entry per line: {"ok", "out" (a WAV), "words", "match"} when its machine
    delivered, {"missing": True} when its whole chunk did not. None when the farm could not be started at all."""
    from .storage import _client
    chunks = split([len(t) for t in texts], int(os.environ.get("VOICE_FARM_CHUNKS") or CHUNKS))
    wait = float(os.environ.get("VOICE_FARM_WAIT_MINUTES") or WAIT_MINUTES) * 60
    prefix = f"voice-farm/{secrets.token_hex(5)}"
    bucket = settings.s3_bucket
    t0 = time.time()
    s3 = None
    try:
        s3 = _client(settings)
        for k, lines in enumerate(chunks):
            body = json.dumps([{"text": texts[i]} for i in lines], ensure_ascii=False).encode("utf-8")
            s3.put_object(Bucket=bucket, Key=f"{prefix}/spec-{k}.json", Body=body)
        started: List[int] = []
        for k in range(len(chunks)):
            why = dispatch(prefix, k)
            if why:
                log(f"[voice] farm: machine {k} was not started ({why})")
            else:
                started.append(k)
        if not started:
            return None
        log(f"[voice] farm: {len(texts)} lines on {len(started)} machines")
        ready, failed, pending, last = set(), set(), set(started), t0
        while pending and time.time() - t0 < wait:
            seen = set(_keys(s3, bucket, prefix + "/"))
            for k in sorted(pending):
                if f"{prefix}/out-{k}.zip" in seen:
                    ready.add(k)
                elif f"{prefix}/err-{k}.txt" in seen:
                    failed.add(k)
            pending -= ready | failed
            if pending:
                if time.time() - last > 300:
                    log(f"[voice] farm: {len(ready)} of {len(started)} machines done after {(time.time() - t0) / 60:.0f} min")
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
                log(f"[voice] farm: machine {k}'s audio could not be read ({type(exc).__name__})")
                continue
            delivered += 1
            for j, i in enumerate(chunks[k]):
                it = done[j] if j < len(done) else {}
                items[i] = {"ok": bool(it.get("ok")), "words": it.get("words") or [], "match": it.get("match", 0),
                            "out": os.path.join(folder, f"{j}.wav")}
        log(f"[voice] farm: {delivered} of {len(chunks)} machines delivered in {(time.time() - t0) / 60:.0f} min"
            + ("; the lines of the others are cloned here" if delivered < len(chunks) else ""))
        return items
    except Exception as exc:                            # the bucket, the network ...: the caller clones on its own
        log(f"[voice] farm: unavailable ({type(exc).__name__}: {str(exc)[:120]})")
        return None
    finally:
        try:                                            # the lines and audio are not kept in the bucket
            s3 = s3 or _client(settings)
            keys = _keys(s3, bucket, prefix + "/")
            for i in range(0, len(keys), 1000):
                s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in keys[i:i + 1000]]})
        except Exception:
            pass
