"""A small sound under every picture that appears: a soft pop when a box, label, icon or graphic node lands, a tick for
a drawn line or a dot, a thump for a stamp. All of it is synthesized (nothing to license), made only of pure tones
with a short attack and no noise, so it cannot add hiss (see sound.whoosh for why that matters). The pops are tuned to
the video's own key and climb a pentatonic scale within a shot, so a build of five boxes plays a little rising
phrase instead of the same click five times. Every sound is timed from the frame the picture appears on, which the
timing code (diagram.timed, graphics.timed) already knows, so it lands with the picture and the spoken word."""
from typing import Dict, List

import numpy as np

from . import sound

SCALE = (1.0, 9 / 8, 5 / 4, 3 / 2, 5 / 3)        # major pentatonic: any run of these notes sounds right in the key
MAX_PER_SHOT = 6                                   # a shot is mostly the narrator's: a few sounds at most
MIN_GAP = 0.3                                      # seconds between two sounds of one shot
TICKS = ("dot", "dots", "arrow", "line", "curve")  # drawn, not placed: a tick
THUMPS = ("stamp",)


def pop(hz: float) -> np.ndarray:
    """A soft bubble: a pure tone with a quick downward chirp, a 4 ms attack and a fast decay."""
    t = np.arange(int(0.25 * sound.SR)) / sound.SR
    phase = 2 * np.pi * np.cumsum(hz * (1 + 0.5 * np.exp(-t * 70))) / sound.SR
    y = (np.sin(phase) + 0.25 * np.sin(2 * phase) * np.exp(-t * 30)) * np.exp(-t * 24) * np.minimum(1, t / 0.004)
    return y / (np.abs(y).max() + 1e-9)


def tick() -> np.ndarray:
    """A soft wooden tick: 1.5 kHz, 40 ms."""
    t = np.arange(int(0.06 * sound.SR)) / sound.SR
    y = np.sin(2 * np.pi * 1500 * t) * np.exp(-t * 140) * np.minimum(1, t / 0.001)
    return y / (np.abs(y).max() + 1e-9)


def cues(scenes: List[dict], starts: List[int], fps: int = 30) -> Dict[str, list]:
    """When the sounds fall, in seconds: {"pops": five lists (one per note of SCALE), "ticks": [...], "hits": [...]}.
    From each shot's timed diagram elements and motion graphic: the frame (`at`, counted from the shot's start) each
    piece appears on."""
    pops: List[List[float]] = [[] for _ in SCALE]
    ticks: List[float] = []
    hits: List[float] = []
    for s, st in zip(scenes, starts):
        found = []                                  # (frame, kind)
        g = s.get("graphic") or {}
        for part in ([g["center"]] if g.get("center") else []) + list(g.get("nodes") or []):
            if "at" in part:
                found.append((part["at"], "pop"))
        if "at" in g and not g.get("nodes") and not g.get("center"):
            found.append((g["at"], "pop"))          # a library graphic is one picture
        for el in (s.get("diagram") or {}).get("elements", []):
            if el.get("at") is not None:
                found.append((el["at"], "hit" if el.get("type") in THUMPS else "tick" if el.get("type") in TICKS else "pop"))
        last, note, used = -9.0, 0, 0
        for at, kind in sorted(found):
            when = (st + at) / fps
            if when - last < MIN_GAP or used >= MAX_PER_SHOT:
                continue
            last, used = when, used + 1
            if kind == "pop":
                pops[min(note, len(SCALE) - 1)].append(when)
                note += 1
            else:
                (ticks if kind == "tick" else hits).append(when)
    return {"pops": pops, "ticks": ticks, "hits": hits}


def render(path: str, seconds: float, found: Dict[str, list], root_hz: float) -> int:
    """The pops and ticks as one stereo track `seconds` long (the stamps' thumps go through the mix's own hit sound);
    returns how many sounds it holds. The pops are tuned to four octaves above the video's low key note."""
    out = np.zeros((int(seconds * sound.SR) + sound.SR, 2), dtype="float32")
    n = 0

    def put(wave: np.ndarray, when: float, pan: float) -> None:
        nonlocal n
        i = int(max(0.0, when) * sound.SR)
        if i + len(wave) < len(out):
            wave = wave * 0.6                              # headroom: two sounds may overlap
            out[i:i + len(wave), 0] += wave * (1 - 0.35 * max(0.0, pan))
            out[i:i + len(wave), 1] += wave * (1 + 0.35 * min(0.0, pan))
            n += 1
    for k, times in enumerate(found["pops"]):
        wave = pop(root_hz * 4 * SCALE[k])
        for j, when in enumerate(times):
            put(wave, when, 0.5 if j % 2 else -0.5)       # alternate a little left and right
    wave = tick()
    for j, when in enumerate(found["ticks"]):
        put(wave, when, 0.5 if j % 2 else -0.5)
    sound._write(path, out)
    return n
