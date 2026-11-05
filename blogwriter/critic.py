"""Looks at a finished video before a person does: a contact sheet of frames scored by the vision model, and a
measurement of how long the picture stands still. The verdict goes into the review email."""
import io
import subprocess
from typing import List

import numpy as np

from .config import Settings
from .footage import ffmpeg_exe, frame_jpeg, vision

RUBRIC = """These are 12 frames, in order, from a documentary-style explainer video for YouTube (a contact sheet).
Judge it like a demanding video editor. Return
{"score": 1-10 (10 = looks like a professional documentary channel, 1 = looks like a slideshow),
 "slideshow": true or false (does it feel like static slides rather than video?),
 "issues": ["frame N: concrete problem", ...] (unreadable or overlapping text, empty or dark frames, repeated
           layouts, off-topic pictures, awkward cropping), at most 6,
 "best": "what works best, one line"}"""


def contact_sheet(video: str, seconds: float, path: str, n: int = 12) -> bytes:
    from PIL import Image
    times = [1.5 + (seconds - 4) * k / (n - 1) for k in range(n)]
    grabs = [g for g in (frame_jpeg(video, t, 480) for t in times) if g]     # a seek past the end gives nothing
    tiles = [Image.open(io.BytesIO(g)).convert("RGB") for g in grabs]
    w, h = tiles[0].size
    sheet = Image.new("RGB", (w * 4, h * 3), (0, 0, 0))
    for k, tile in enumerate(tiles):
        sheet.paste(tile.resize((w, h)), ((k % 4) * w, (k // 4) * h))
    sheet.save(path, "JPEG", quality=85)
    with open(path, "rb") as f:
        return f.read()


def still_spans(video: str, min_seconds: float = 3.0) -> List[tuple]:
    """Stretches where the picture barely changes for min_seconds or more: the clearest sign of a slideshow."""
    w, h, fps = 96, 54, 4
    raw = subprocess.run([ffmpeg_exe(), "-v", "error", "-i", video, "-vf", f"fps={fps},scale={w}:{h},format=gray",
                          "-f", "rawvideo", "-"], capture_output=True, timeout=600).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.int16)
    if len(frames) < 2:
        return []
    moving = np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2)) > 0.6
    spans, start = [], None
    for k, m in enumerate(list(moving) + [True]):
        if not m and start is None:
            start = k
        elif m and start is not None:
            if (k - start) / fps >= min_seconds:
                spans.append((round(start / fps, 1), round(k / fps, 1)))
            start = None
    return spans


def review(settings: Settings, video: str, seconds: float, sheet_path: str) -> dict:
    sheet = contact_sheet(video, seconds, sheet_path)
    verdict = vision(settings, RUBRIC, [sheet]) or {}
    verdict["still"] = still_spans(video)
    return verdict


def summary(verdict: dict) -> str:
    if not verdict:
        return "QUALITY CHECK: not available."
    lines = [f"QUALITY CHECK: {verdict.get('score', '?')}/10"
             + (" - looks like a slideshow, review carefully" if verdict.get("slideshow") else "")]
    lines += [f"  - {i}" for i in verdict.get("issues", [])[:6]]
    if verdict.get("best"):
        lines.append(f"  + {verdict['best']}")
    if verdict.get("still"):
        lines.append("  still picture at: " + ", ".join(f"{a}-{b}s" for a, b in verdict["still"][:8]))
    return "\n".join(lines)
