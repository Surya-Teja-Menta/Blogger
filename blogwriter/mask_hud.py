"""One-off repair: blur the HUD readout (the "SHOT 06 / 74" text and the ruler on the right edge) out of the newest stored
video, in place. Downloads long_video_en.mp4 and short_en.mp4 of the newest videos/ folder, covers those two small
areas with a blurred copy of the background beside them, keeps the original beside it as *.orig.mp4 and
uploads the repaired file under the same key, so the emailed link keeps working. Run by .github/workflows/mask-hud.yml."""
import os
import subprocess
import sys
import tempfile

from .config import Settings
from . import storage

# boxes (x, y, w, h) in the composition's own pixels: Long is 2560 wide, Short 1080 wide (video/src/skeleton.jsx put the
# readout at right: inset+18, top 60 (Long) / 132 (Short); the ruler at width - inset - 8, from 30% to 70% of the height)
LONG = [(2140, 44, 400, 82), (2440, 410, 100, 630)]
SHORT = [(750, 116, 310, 72), (985, 560, 85, 800)]


def size(path: str):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0",
                          path], capture_output=True, text=True, check=True).stdout.strip().split(",")
    return int(out[0]), int(out[1])


def mask(src: str, dst: str) -> None:
    w, h = size(src)
    boxes, base = (LONG, 2560) if w > h else (SHORT, 1080)
    k = w / base
    chain = ",".join("delogo=x=%d:y=%d:w=%d:h=%d" % tuple(round(v * k) for v in box) for box in boxes)      # filled from the surroundings
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-vf", chain, "-c:v", "libx264", "-preset", "fast", "-crf", "14",
                    "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", dst], check=True)


def main() -> int:
    s = Settings.from_env()
    c = storage._client(s)
    keys = [o for o in c.list_objects_v2(Bucket=s.s3_bucket, Prefix="videos/").get("Contents", []) if o["Key"].endswith("long_video_en.mp4")]
    if not keys:
        print("no video found")
        return 1
    newest = max(keys, key=lambda o: o["LastModified"])["Key"].rsplit("/", 1)[0]
    print("newest folder:", newest)
    with tempfile.TemporaryDirectory() as tmp:
        for name in ("long_video_en.mp4", "short_en.mp4"):
            key = f"{newest}/{name}"
            try:
                c.head_object(Bucket=s.s3_bucket, Key=key)
            except Exception:
                print("skip (not there):", key)
                continue
            src, dst = os.path.join(tmp, name), os.path.join(tmp, "fixed_" + name)
            c.download_file(s.s3_bucket, key, src)
            c.upload_file(src, s.s3_bucket, key.replace(".mp4", ".orig.mp4"), ExtraArgs={"ContentType": "video/mp4"})
            mask(src, dst)
            c.upload_file(dst, s.s3_bucket, key, ExtraArgs={"ContentType": "video/mp4"})
            print("repaired and uploaded:", key, round(os.path.getsize(dst) / 1e6), "MB")
            os.remove(src)
            os.remove(dst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
