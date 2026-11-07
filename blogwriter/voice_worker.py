"""One machine of the voice farm (see voicefarm.py): clones one chunk of a narration in the owner's voice.

    python -m blogwriter.voice_worker          (FARM_PREFIX and FARM_INDEX in the environment)

It starts with the workflow run, so it first says it is there (<prefix>/alive-<n>.txt) and waits for its lines
(<prefix>/spec-<n>.json) to appear in the private bucket, as the make job writes the script. Then it reads the
owner's recording from the same bucket, clones every line with the cloning tool (checked against its script, timed
word by word), and puts <prefix>/out-<n>.zip back (the WAVs and jobs.json). If it cannot, it puts
<prefix>/err-<n>.txt, so the make job stops waiting for it. It leaves quietly when <prefix>/done.txt appears (the
make job needs no more voices) or after WORKER_WAIT_MINUTES.
"""
import json
import os
import re
import shutil
import sys
import tempfile
import time
import zipfile

from .config import Settings


def main(argv=None, sleep=time.sleep) -> int:
    prefix, index = os.environ.get("FARM_PREFIX", ""), os.environ.get("FARM_INDEX", "")
    if not re.fullmatch(r"voice-farm/[\w-]{3,64}", prefix) or not index.isdigit():
        print("[worker] bad inputs")
        return 2
    from . import video
    from .storage import _client
    settings = Settings.from_env()
    s3 = _client(settings)
    bucket = settings.s3_bucket
    work = tempfile.mkdtemp(prefix="voice_")
    try:
        s3.put_object(Bucket=bucket, Key=f"{prefix}/alive-{index}.txt", Body=b"here")
        deadline = time.time() + float(os.environ.get("WORKER_WAIT_MINUTES") or 100) * 60
        lines = None
        while lines is None:
            keys = {o["Key"] for o in s3.list_objects_v2(Bucket=bucket, Prefix=prefix + "/").get("Contents", [])}
            if f"{prefix}/done.txt" in keys:
                print("[worker] nothing to do")
                return 0
            if f"{prefix}/spec-{index}.json" in keys:
                body = s3.get_object(Bucket=bucket, Key=f"{prefix}/spec-{index}.json")["Body"].read()
                lines = json.loads(body.decode("utf-8"))
            elif time.time() > deadline:
                print("[worker] no lines came")
                return 0
            else:
                sleep(15)
        try:
            done = []
            if lines:
                python = os.environ.get("VOICE_PYTHON", "")
                if not python or not os.path.exists(python):
                    raise RuntimeError("the cloning environment did not install")
                ref = video.voice_sample(settings, work, print)
                if not ref:
                    raise RuntimeError("no voice sample")
                spec = os.path.join(work, "jobs.json")
                with open(spec, "w", encoding="utf-8") as f:
                    json.dump([{"text": it["text"], "out": os.path.join(work, f"{j}.wav")} for j, it in enumerate(lines)],
                              f, ensure_ascii=False)
                if video.clone_with_budget(python, spec, ref, [it["text"] for it in lines], print):
                    raise RuntimeError("cloning would take too long on this machine")
                os.remove(ref)
                with open(spec, encoding="utf-8") as f:
                    done = json.load(f)
                for it in done:                          # the lines stay in the bucket's spec, not in the hand-over
                    it.pop("text", None)
            out = os.path.join(work, "out.zip")
            with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
                z.writestr("jobs.json", json.dumps(done, ensure_ascii=False))
                for j in range(len(done)):
                    wav = os.path.join(work, f"{j}.wav")
                    if os.path.exists(wav):
                        z.write(wav, f"{j}.wav")
            s3.upload_file(out, bucket, f"{prefix}/out-{index}.zip")
            print(f"[worker] chunk {index}: {sum(bool(it.get('ok')) for it in done)} of {len(done)} lines delivered")
            return 0
        except Exception as exc:
            print(f"[worker] chunk {index} failed: {type(exc).__name__}: {str(exc)[:200]}")
            try:
                s3.put_object(Bucket=bucket, Key=f"{prefix}/err-{index}.txt",
                              Body=f"{type(exc).__name__}: {str(exc)[:200]}".encode("utf-8"))
            except Exception:
                pass
            return 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
