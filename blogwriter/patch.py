"""Fix one thing in a finished video, and get the whole video back in minutes instead of three hours.

The make job saves the video's working folder (the picture script long.json, every shot's narration clip, the music) next
to the finished video in the storage bucket (videos/<run>/state.zip). This tool takes the newest video (or the one named),
changes only what you ask, redraws only the shots that changed, and puts them back into the finished video:

  edits (JSON, one object per change):  [{"shot": 12, "narration": "new text"},
                                        {"at": "3:12", "headline": "Fixed title", "replace": {"colour": "color"}}]
  shot       the shot number (1 = the first shot); or  at  a time like "3:12" inside that shot
  narration  the new spoken text of the shot (spoken again in the owner's voice, fitted into the same time)
  headline / kicker / label   the shot's on-screen words
  replace    {"old": "new"} in every on-screen word of the shot (a typo in a diagram label, a formula)

Only the changed shots are rendered again; the rest of the picture is cut from the old video, so the length of every shot
stays the same (a new narration is fitted into its shot: shorter is padded, up to 30% longer is sped up). The sound is mixed
again (it takes about two minutes) when a narration changed. The Short and the thumbnail are not touched.
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from typing import List, Optional, Tuple

from . import sfx, storage, video
from .config import Settings

FPS, LEAD = video.FPS, video.LEAD
JOB = os.path.join(video.VIDEO_APP, "public", "job")


# ------------------------------------------------------------------------------------------ finding and changing shots
def locate(starts: List[int], frames: List[int], edit: dict) -> int:
    """The index (from 0) of the shot an edit names: `shot` (1-based) or `at` ("3:12" or seconds)."""
    n = len(starts)
    if edit.get("shot") is not None:
        k = int(edit["shot"]) - 1
    elif edit.get("at") is not None:
        raw = str(edit["at"]).strip()
        secs = sum(float(p) * 60 ** i for i, p in enumerate(reversed(raw.split(":"))))
        f = int(secs * FPS)
        k = max((i for i in range(n) if starts[i] <= f), default=0)
    else:
        raise ValueError(f"an edit needs a shot or an at: {edit}")
    if not 0 <= k < n:
        raise ValueError(f"there is no shot {k + 1} (the video has {n})")
    return k


def _swap(value, old: str, new: str):
    """`old` replaced by `new` in every string inside the value (lists and dicts included)."""
    if isinstance(value, str):      # any case; a capital stays a capital
        return re.sub(re.escape(old), lambda m: new[:1].upper() + new[1:] if m.group()[:1].isupper() else new, value, flags=re.I)
    if isinstance(value, list):
        return [_swap(v, old, new) for v in value]
    if isinstance(value, dict):
        return {k: (v if k in ("narration", "kind", "type", "src", "image", "images") else _swap(v, old, new)) for k, v in value.items()}
    return value


def apply_text_edit(scene: dict, edit: dict) -> bool:
    """headline, kicker, label and replace of one edit applied to the scene (changed in place); True if anything changed."""
    before = json.dumps(scene, sort_keys=True)
    for key in ("headline", "kicker", "label"):
        if edit.get(key) is not None:
            scene[key] = str(edit[key])
    for old, new in (edit.get("replace") or {}).items():
        for key in list(scene):
            if key not in ("narration", "kind", "frames", "cam", "images", "src"):
                scene[key] = _swap(scene[key], str(old), str(new))
    return json.dumps(scene, sort_keys=True) != before


# ------------------------------------------------------------------------------------------------- captions and subtitles
def recaption(captions: List[dict], start: int, frames: int, words: list) -> List[dict]:
    """The caption lines of one shot replaced by lines made from its new words (frames counted from the video's start)."""
    keep = [c for c in captions if not (start + LEAD - 2 <= c["from"] < start + frames)]
    new = [{"from": start + LEAD + round(a * FPS), "to": start + LEAD + round(b * FPS), "text": line}
           for a, b, line in video.word_lines(words, 0, 42)]
    return sorted(keep + new, key=lambda c: c["from"])


def patch_srt(text: str, start: int, frames: int, words: list) -> str:
    """The subtitle file with the cues of one shot replaced (the file's cues are whole seconds-based blocks)."""
    def secs(ts):
        h, m, rest = ts.split(":")
        s, ms = rest.split(",")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        rows = block.splitlines()
        if len(rows) >= 3 and "-->" in rows[1]:
            a, b = (secs(x.strip()) for x in rows[1].split("-->"))
            cues.append((a, b, " ".join(rows[2:])))
    lo, hi = (start + LEAD) / FPS - 0.05, (start + frames) / FPS
    cues = [c for c in cues if not lo <= c[0] < hi]
    base = (start + LEAD) / FPS
    cues += [(base + a, base + b, t) for a, b, t in video.word_lines(words, 0, 84)]
    return video.srt(sorted(cues))


# -------------------------------------------------------------------------------------------------------- the splice itself
def ranges(edited: List[int], starts: List[int], frames: List[int]) -> List[Tuple[int, int]]:
    """The frame ranges (first, last inclusive) to draw again: each edited shot, neighbours merged."""
    out: List[Tuple[int, int]] = []
    for k in sorted(set(edited)):
        a, b = starts[k], starts[k] + frames[k] - 1
        if out and a <= out[-1][1] + 1:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def splice_filter(spans: List[Tuple[int, int]], total_frames: int) -> str:
    """ffmpeg filter graph: the old video's frames outside the spans, the new segments (inputs 1..n) inside them."""
    parts, order, prev = [], [], 0
    for i, (a, b) in enumerate(spans):
        if a > prev:
            parts.append(f"[0:v]trim=start_frame={prev}:end_frame={a},setpts=PTS-STARTPTS[o{i}]")
            order.append(f"[o{i}]")
        parts.append(f"[{i + 1}:v]setpts=PTS-STARTPTS[n{i}]")
        order.append(f"[n{i}]")
        prev = b + 1
    if prev < total_frames:
        parts.append(f"[0:v]trim=start_frame={prev},setpts=PTS-STARTPTS[tail]")
        order.append("[tail]")
    return ";".join(parts + [f"{''.join(order)}concat=n={len(order)}:v=1:a=0[v]"])


def video_frames(path: str) -> int:
    out = subprocess.run([video.ffmpeg_exe(), "-hide_banner", "-i", path, "-map", "0:v:0", "-c", "copy", "-f", "null", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    return int(re.findall(r"frame=\s*(\d+)", out)[-1])


# ----------------------------------------------------------------------------------------------------------- the whole job
def fit(words: list, wav: str, frames: int) -> list:
    """A new narration clip fitted into its shot: sped up (at most 30%, pitch kept) when it runs past the shot, else left
    as it is (the picture simply holds). Returns the words' timings, moved to match."""
    seconds = words[-1][1] + 0.3
    room = (frames - LEAD - 4) / FPS
    if seconds <= room:
        return words
    tempo = seconds / room
    if tempo > video.MAX_TEMPO:
        raise ValueError(f"the new narration is {seconds:.1f}s but the shot has {room:.1f}s (at most {room * video.MAX_TEMPO:.1f}s "
                         "with a faster delivery): shorten it")
    tmp = wav + ".fast.wav"
    video.ffmpeg(["-i", wav, "-filter:a", f"atempo={tempo:.4f}", "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", tmp])
    os.replace(tmp, wav)
    return [(a / tempo, b / tempo, w) for a, b, w in words]


def pick_folder(client, bucket: str, want: str = "") -> str:
    keys = [o for o in client.list_objects_v2(Bucket=bucket, Prefix="videos/").get("Contents", []) if o["Key"].endswith("/state.zip")]
    if want:
        keys = [o for o in keys if want in o["Key"]]
    if not keys:
        raise RuntimeError("no saved video state found (a video made before this feature has none; make a new one)")
    return max(keys, key=lambda o: o["LastModified"])["Key"].rsplit("/", 1)[0]


def main() -> int:
    log = print
    s = Settings.from_env()
    edits = json.loads(os.environ.get("PATCH_EDITS") or "[]")
    if not edits:
        log("no edits given")
        return 1
    c = storage._client(s)
    folder = pick_folder(c, s.s3_bucket, os.environ.get("PATCH_RUN", "").strip())
    log(f"patching {folder}")
    work = tempfile.mkdtemp(prefix="patch_")
    shutil.rmtree(JOB, ignore_errors=True)
    os.makedirs(JOB)
    zpath = os.path.join(work, "state.zip")
    c.download_file(s.s3_bucket, f"{folder}/state.zip", zpath)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(JOB)
    old = os.path.join(work, "old.mp4")
    c.download_file(s.s3_bucket, f"{folder}/long_video_en.mp4", old)
    with open(os.path.join(JOB, "long.json"), encoding="utf-8") as f:
        props = json.load(f)
    with open(os.path.join(JOB, "patch.json"), encoding="utf-8") as f:
        meta = json.load(f)
    scenes, starts, total = props["scenes"], meta["starts"], meta["total"]
    frames = [sc["frames"] for sc in scenes]
    edited, spoken_new = [], {}
    for e in edits:
        k = locate(starts, frames, e)
        changed = apply_text_edit(scenes[k], e)
        if e.get("narration"):
            text = " ".join(str(e["narration"]).split())
            path = os.path.join(JOB, f"en_long{k}.wav")
            got = video.speak_cloned([(text, video.VOICES["en"], path)], s, JOB, log)[0]
            if not got:
                raise RuntimeError(f"shot {k + 1}: the new narration could not be spoken")
            words = video.tighten(path, got)
            words = fit(words, path, frames[k])
            scenes[k]["narration"] = text
            props["captions"] = recaption(props["captions"], starts[k], frames[k], words)
            spoken_new[k] = words
            changed = True
        if changed:
            edited.append(k)
            log(f"shot {k + 1}: changed")
    if not edited:
        log("nothing changed")
        return 1
    with open(os.path.join(JOB, "long.json"), "w", encoding="utf-8") as f:
        json.dump(props, f, ensure_ascii=False)

    # the sound again, when a narration changed
    audio = old
    if spoken_new:
        assets = {n: os.path.join(JOB, f"{n}.wav") for n in ("music", "whoosh", "hit")}
        silence = os.path.join(JOB, "silence.wav")
        clips = [os.path.join(JOB, f"en_long{i}.wav") if os.path.exists(os.path.join(JOB, f"en_long{i}.wav")) else silence
                 for i in range(len(scenes))]
        audio = os.path.join(work, "soundtrack.mp3")
        video.master(clips, starts, [sc["kind"] for sc in scenes], total, assets, audio, log, meta.get("tempos"),
                     sfx.cues(scenes, starts, FPS), meta.get("root_hz", 65.0))

    # only the changed shots are drawn again
    spans = ranges(edited, starts, frames)
    segs = []
    for i, (a, b) in enumerate(spans):
        seg = os.path.join(work, f"seg{i}.mp4")
        log(f"drawing frames {a}-{b}")
        video.remotion(["render", "src/index.jsx", "Long", seg, "--props=public/job/long.json", f"--frames={a}-{b}",
                        *video.QUALITY, f"--scale={video.LONG_SCALE}", "--timeout=120000"], log)
        segs.append(seg)
    new = os.path.join(work, "long_video_en.mp4")
    encoder, args = video.CODECS["h264"]
    graph = splice_filter(spans, video_frames(old))
    cmd = ["-i", old, *sum((["-i", sg] for sg in segs), []), *(["-i", audio] if audio != old else []),
           "-filter_complex", graph, "-map", "[v]", "-map", f"{len(segs) + 1}:a" if audio != old else "0:a",
           "-c:v", encoder, *args, "-preset", "fast", "-c:a", "aac" if audio != old else "copy", *(["-b:a", "192k", "-ar", "48000"] if audio != old else []),
           "-movflags", "+faststart", new]
    log("joining the old picture and the new shots")
    video.ffmpeg(cmd, timeout=4 * 3600)
    check = video.playback_check(new)
    log("playback check: " + check["summary"])
    if check.get("problems"):      # never replace a good stored video with a broken one
        log("the fixed video has playback problems; nothing was uploaded: " + "; ".join(check["problems"])[:300])
        return 1

    # upload: the original is kept beside, the same names carry the fix, the state follows so a next fix builds on this one
    key = f"{folder}/long_video_en.mp4"
    if not c.list_objects_v2(Bucket=s.s3_bucket, Prefix=key.replace(".mp4", ".orig.mp4")).get("Contents"):
        c.copy_object(Bucket=s.s3_bucket, CopySource={"Bucket": s.s3_bucket, "Key": key}, Key=key.replace(".mp4", ".orig.mp4"))
    c.upload_file(new, s.s3_bucket, key, ExtraArgs={"ContentType": "video/mp4"})
    srt_key = f"{folder}/subtitles_en.srt"
    try:
        text = c.get_object(Bucket=s.s3_bucket, Key=srt_key)["Body"].read().decode("utf-8")
        for k, words in spoken_new.items():
            text = patch_srt(text, starts[k], frames[k], words)
        c.put_object(Bucket=s.s3_bucket, Key=srt_key, Body=text.encode("utf-8"), ContentType="text/plain; charset=utf-8")
    except Exception as exc:        # the subtitles are a nicety; the video is fixed
        log(f"subtitles not updated: {type(exc).__name__}")
    video.upload_state(s, JOB, folder, log)
    link = storage.link_for(s, key, c)
    from .mailer import send_email
    send_email(s, "[Video fixed] " + folder.split("/")[-1][:80], f"The video was fixed in shots {', '.join(str(k + 1) for k in edited)}.\n\n{link}\n\n"
               "The Short and the thumbnail are as they were. The upload button of the first email now uploads the fixed video.", [], log)
    log(f"done: {link}")
    return 0


def commit() -> str:
    """The git commit the video was made with ("" when unknown); the Fix a video workflow draws with that code."""
    s = Settings.from_env()
    c = storage._client(s)
    try:
        folder = pick_folder(c, s.s3_bucket, os.environ.get("PATCH_RUN", "").strip())
        return c.get_object(Bucket=s.s3_bucket, Key=f"{folder}/commit.txt")["Body"].read().decode().strip()
    except Exception:
        return ""


if __name__ == "__main__":
    if sys.argv[1:] == ["commit"]:
        print(commit())
        sys.exit(0)
    sys.exit(main())
