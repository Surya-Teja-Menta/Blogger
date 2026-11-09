"""The music of one video, composed in code (so there is nothing to license) for that video alone.

Nothing is a fixed loop. The mood the planner wrote for the video (and its tone and title) decides the mode (minor,
dorian, lydian...), the tempo, the brightness, the instrument of the plucks and how much it drives; the title picks the
key and the chord pattern. The chords change where the story changes (at the shots and chapters), the amount of music
follows the story (a breath at a chapter card, a ticking suspense under a quiz that resolves when the answer lands, a
build towards the middle, a resolution in the outro), and the little themes are written for this video.

The notes sit in the middle of the spectrum (200-1600 Hz), where a phone or a laptop speaker can play them: a bed made
of low chords alone is there on the file but cannot be heard on small speakers."""
import hashlib
import re
from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import sound

SR = sound.SR
SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11], "lydian": [0, 2, 4, 6, 7, 9, 11], "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "dorian": [0, 2, 3, 5, 7, 9, 10], "minor": [0, 2, 3, 5, 7, 8, 10], "phrygian": [0, 1, 3, 5, 7, 8, 10],
}
# chord roots (scale degrees) in the patterns that move people: one set for minor-third scales, one for major
PATTERNS_MINOR = [[0, 5, 2, 6], [0, 3, 6, 2], [0, 6, 5, 6], [0, 2, 3, 6], [5, 6, 0, 0], [0, 3, 5, 4]]
PATTERNS_MAJOR = [[0, 4, 5, 3], [0, 5, 3, 4], [0, 3, 4, 3], [5, 3, 0, 4], [0, 2, 3, 4], [3, 0, 4, 5]]
# (words in the mood, votes for modes, tempo shift in bpm, brightness -1..1, drive 0..1)
FEELS = [
    (r"dark|tense|ominous|grim|danger|fear|threat|crisis|war|collapse|myster|noir|secret|conspir|shadow|dread|risk",
     {"phrygian": 2, "minor": 2, "dorian": 1}, -4, -0.6, 0.3),
    (r"sad|loss|lonely|melanchol|nostalg|reflect|wistful|grief|elegy|bittersweet|quiet|somber|sombre",
     {"minor": 2, "dorian": 2}, -10, -0.2, 0.0),
    (r"calm|gentle|soft|patient|slow|peace|serene|sooth|relax|cozy|cosy|warm|tender",
     {"major": 1, "mixolydian": 1, "lydian": 1, "dorian": 1}, -10, 0.1, 0.0),
    (r"curious|wonder|discover|magic|dream|cosmic|space|universe|glass|awe|explor|myster",
     {"lydian": 2, "dorian": 1}, -2, 0.5, 0.1),
    (r"bright|hope|uplift|cheer|joy|optimis|sunny|fresh|friendly|inspir|clear",
     {"major": 2, "lydian": 1, "mixolydian": 1}, 4, 0.7, 0.4),
    (r"playful|fun|quirk|witty|sarcas|deadpan|cheeky|humou?r|light|teas|wry",
     {"mixolydian": 2, "major": 1, "dorian": 1}, 8, 0.4, 0.5),
    (r"urgent|fast|energ|punch|intens|driv|race|thrill|dynamic|bold|epic|power|bustl",
     {"minor": 1, "dorian": 2, "mixolydian": 1}, 18, 0.2, 0.9),
    (r"scien|math|logic|analy|precis|data|technic|engineer|code|algorithm|number|statist",
     {"dorian": 2, "lydian": 1}, 0, 0.2, 0.3),
    (r"histor|ancient|old|classic|story|legend|tradition|empire",
     {"minor": 1, "dorian": 1, "mixolydian": 1}, -6, -0.1, 0.1),
]
# how much music each kind of shot carries (0 = none): a chapter card is a breath, a figure lands with weight
ENERGY = {"hook": 0.55, "chapter": 0.12, "check": 0.3, "outro": 0.4, "stat": 0.62, "compare": 0.55, "bars": 0.55,
          "line": 0.55, "donut": 0.55, "kpis": 0.6, "timeline": 0.5, "steps": 0.5, "map": 0.5, "list": 0.45,
          "quote": 0.35, "equation": 0.5, "plot": 0.52, "graph": 0.52, "derive": 0.56, "surface": 0.56,
          "diagram": 0.5, "photo": 0.45}
TARGET_RMS = 0.085          # of the finished bed: the mix sets how far under the voice it sits (MUSIC_LEVEL)


def _pick(seed: str) -> int:
    return int(hashlib.md5(seed.encode()).hexdigest(), 16)


def feel(mood: str, seed: str = "") -> Dict:
    """What this video's music should be, from its mood words and its title."""
    pick = _pick(seed)
    votes: Dict[str, float] = {k: 0.0 for k in SCALES}
    shift = bright = drive = 0.0
    hits = 0
    for words, scales, bpm, b, d in FEELS:
        n = len(re.findall(words, mood.lower()))
        if not n:
            continue
        hits += 1
        for k, v in scales.items():
            votes[k] += v * min(n, 2)
        shift, bright, drive = shift + bpm, bright + b, drive + d
    if hits:
        shift, bright, drive = shift / hits, bright / hits, drive / hits
    else:                                   # no words to go on: the title alone makes the choice
        bright, drive = ((pick >> 4) % 100) / 100 - 0.3, 0.3
    scale = sorted(SCALES, key=lambda k: (-votes[k], _pick(seed + k)))[0]
    bpm = float(np.clip(66 + (pick >> 12) % 23 + shift, 56, 112))
    timbres = (["bell", "harp"] if bright > 0.45 else ["marimba", "harp"] if drive > 0.55 else ["harp", "bell"]
               if bright > -0.1 else ["harp", "marimba"])
    return {"scale": scale, "root": 48 + (pick >> 24) % 12, "bpm": round(bpm, 1), "bright": round(float(np.clip(bright, -1, 1)), 2),
            "drive": round(float(np.clip(drive, 0, 1)), 2), "timbre": timbres[(pick >> 40) % 2],
            "pattern": (pick >> 48) % 6, "arp": (pick >> 56) % 4, "hits": hits}


def hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


@lru_cache(maxsize=256)
def _pluck(midi: int, kind: str) -> np.ndarray:
    """One plucked or struck note (mono), ringing out in 1.8 s."""
    n = int(1.8 * SR)
    t = np.arange(n) / SR
    f = hz(midi)
    if kind == "bell":
        parts = [(1.0, 1.0, 2.2), (2.756, 0.38, 4.0), (5.404, 0.14, 7.0)]
    elif kind == "marimba":
        parts = [(1.0, 1.0, 5.0), (3.9, 0.35, 13.0), (9.2, 0.08, 30.0)]
    else:                                                       # harp
        parts = [(k, 1.0 / k, 2.5 + 1.8 * k) for k in range(1, 6)]
    y = sum(a * np.sin(2 * np.pi * f * r * t) * np.exp(-d * t) for r, a, d in parts if f * r < 9000)
    y = y * np.minimum(1, t / 0.004)
    return (y / (np.abs(y).max() + 1e-9)).astype("float32")


def _pad(midi: float, seconds: float) -> np.ndarray:
    """One sustained voice of the pad: a soft attack that opens over a second or two, a slow shimmer, a long release."""
    n = int((seconds + 2.0) * SR)
    t = np.arange(n) / SR
    f = hz(midi)
    att = min(1.6, max(0.3, seconds * 0.4))
    env = np.minimum(1, t / att) ** 1.5 * np.where(t < seconds, 1.0, np.exp(-(t - seconds) * 2.2))
    y = np.sin(2 * np.pi * f * t) + 0.28 * np.sin(4 * np.pi * f * t) + 0.09 * np.sin(6 * np.pi * f * t)
    y = y * (1 + 0.06 * np.sin(2 * np.pi * 0.21 * t + midi))
    return (y * env).astype("float32")


def _smooth(x, a, b):
    t = np.clip((np.asarray(x, dtype=float) - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


class _Bus:
    """A stereo buffer notes are laid into."""
    def __init__(self, n: int):
        self.buf = np.zeros((2, n), dtype="float32")

    def put(self, at: float, sig: np.ndarray, gain: float, pan: float = 0.5) -> None:
        i = int(round(at * SR))
        n = self.buf.shape[1]
        if i < 0:                           # a note that would start before the video: only its later part is kept
            sig, i = sig[-i:], 0
        if i >= n or gain <= 0 or len(sig) == 0:
            return
        seg = sig[:n - i]
        self.buf[0, i:i + len(seg)] += seg * (gain * np.cos(pan * np.pi / 2))
        self.buf[1, i:i + len(seg)] += seg * (gain * np.sin(pan * np.pi / 2))


def _wash(buf: np.ndarray, cutoff: float, seconds: float, wet: float) -> np.ndarray:
    """A low-pass and a soft room tail, block by block (a whole video at once would not fit in memory)."""
    out = np.zeros_like(buf)
    block, tail = 1 << 19, int(seconds * SR)
    for c in (0, 1):
        for i in range(0, buf.shape[1], block):
            chunk = buf[c, i:i + block].astype("float64")
            if np.abs(chunk).max() < 1e-7:
                continue
            x = np.zeros(len(chunk) + tail)
            x[:len(chunk)] = chunk
            y = sound._reverb_lowpass(x, cutoff, seconds, wet, seed=3 + c)
            m = min(len(y), buf.shape[1] - i)
            out[c, i:i + m] += y[:m].astype("float32")
    return out


def chord_tones(scale: Sequence[int], degree: int, root: int, low: int, high: int) -> List[int]:
    """The notes (MIDI) of the triad on a scale degree, every octave that falls between `low` and `high`."""
    base = [root + scale[(degree + s) % 7] + 12 * ((degree + s) // 7) for s in (0, 2, 4)]
    notes = [n + 12 * k for n in base for k in range(-5, 6) if low <= n + 12 * k <= high]
    return sorted(set(notes))


def _voicing(scale, degree, root, extra):
    """Three or four voices close together around G3-D5 (the middle of what a small speaker plays)."""
    out = []
    for s in [0, 2, 4] + ([8] if extra else []):
        n = root + scale[(degree + s) % 7] + 12 * ((degree + s) // 7)
        while n < 52:
            n += 12
        while n > 74:
            n -= 12
        out.append(n)
    return sorted(out)


def sections_for(seconds: float, sections: Optional[Sequence[Tuple[float, float, str]]]):
    if sections:
        return [(float(a), float(b), str(k)) for a, b, k in sections if b > a]
    return [(0.0, seconds, "")]


def energy_curve(seconds: float, sections, rate: int = 20) -> np.ndarray:
    """How much music there is, second by second: the weight of each shot, shaped by a build towards two thirds of the
    video and a settling at the end, with the steps between shots smoothed over a few seconds."""
    n = int(seconds * rate) + 2
    e = np.full(n, 0.4)
    for a, b, kind in sections:
        frac = (a + b) / 2 / max(seconds, 1)
        arc = 0.72 + 0.28 * np.exp(-((frac - 0.62) / 0.3) ** 2)
        base = ENERGY.get(kind, 0.45)
        e[int(a * rate):int(b * rate) + 1] = base * arc
    k = int(3.5 * rate) | 1
    pad = np.pad(e, (k // 2, k // 2), mode="edge")
    c = np.cumsum(np.insert(pad, 0, 0))
    return np.clip((c[k:] - c[:-k])[:n] / k, 0, 1)


def compose(seconds: float, seed: str = "", mood: str = "", sections=None) -> Tuple[np.ndarray, Dict]:
    """The bed, (2, samples) float32, and the description of the music (for the log)."""
    f = feel(mood, seed)
    pick = _pick(seed)
    rng = np.random.default_rng(pick % (2 ** 32))
    scale = SCALES[f["scale"]]
    minor = scale[2] == 3
    pattern = (PATTERNS_MINOR if minor else PATTERNS_MAJOR)[f["pattern"] % 6]
    beat = 60.0 / f["bpm"]
    bar = 4 * beat
    secs = sections_for(seconds, sections)
    n = int((seconds + 2) * SR)
    energy = energy_curve(seconds + 2, secs)
    at = lambda t: float(energy[min(len(energy) - 1, max(0, int(t * 20)))])
    kind_at = lambda t: next((k for a, b, k in secs if a <= t < b), secs[-1][2])
    wet, dry = _Bus(n), _Bus(n)

    # where the chords change: at the shots (on the bar grid), and every couple of bars inside a long one
    marks = [0.0]
    for a, b, k in secs:
        t = round(a / bar) * bar
        if t - marks[-1] >= (1.0 if k in ("chapter", "check", "outro") else 1.9) * bar and t < seconds - bar:
            marks.append(t)
    changes = []
    for c0, c1 in zip(marks, marks[1:] + [seconds + 2]):
        t = c0
        changes.append(t)
        while c1 - t > 4.5 * bar:
            t += 2 * bar
            changes.append(t)
    last_start = secs[-1][0]
    shift = 0
    chords = []
    for i, c0 in enumerate(changes):
        c1 = changes[i + 1] if i + 1 < len(changes) else seconds + 2
        if kind_at(c0) == "chapter" and (not chords or kind_at(chords[-1][0]) != "chapter"):
            shift += 1                      # a new part of the story: the harmony moves on
        degree = pattern[(i + shift) % len(pattern)]
        if secs[-1][2] == "outro" and c0 >= last_start and c1 >= seconds:
            degree = 0                      # the outro comes home
        chords.append((c0, c1, degree))

    motif_len = [4, 6, 5, 7][(pick >> 5) % 4]
    pent = [i for i in range(7) if i not in (3, 6)]
    motifs = []
    for _ in range(2):
        steps, cur = [], int(rng.integers(0, 5))
        for _ in range(motif_len):
            cur = int(np.clip(cur + rng.choice([-2, -1, -1, 0, 1, 1, 2]), 0, 9))
            steps.append((cur, float(rng.choice([1, 1, 2, 0.5, 0.5, 1.5]))))
        motifs.append(steps)
    melody_n = 0

    for i, (c0, c1, deg) in enumerate(chords):
        span = c1 - c0
        kind = kind_at(c0)
        e0 = at(c0 + 0.5)
        # pad: a few close voices spread across the stereo field, and a quiet root underneath
        voices = _voicing(scale, deg, f["root"], f["bright"] > 0.3 or (pick >> 9) % 3 == 0)
        for j, m in enumerate(voices):
            wet.put(c0 - 0.6, _pad(m, span + 0.9), (0.8 + 0.2 * e0) * 0.95, 0.2 + 0.6 * ((j * 0.37 + i * 0.11) % 1.0))
        bass = f["root"] + scale[deg % 7] - 12
        while bass > 47:
            bass -= 12
        dry.put(c0 - 0.3, _pad(bass, span + 0.6), 0.45)

        tones = chord_tones(scale, deg, f["root"], 60, 84)
        steps = beat / 2 if f["drive"] > 0.4 else beat
        order = [[0, 1, 2, 1], [0, 1, 2, 3], [2, 1, 0, 1], [0, 2, 1, 2]][f["arp"]]
        k = 0
        t = c0
        while t < c1 - 0.05:
            if kind == "check":
                break                                 # the quiz has its own ticking, below
            e = at(t)
            level = float(_smooth(e, 0.28, 0.6))
            if level > 0.02 and rng.random() > 0.16 + 0.2 * (1 - level):
                note = tones[order[k % len(order)] % len(tones)] + (12 if k % 8 == 7 else 0)
                wet.put(t + float(rng.normal(0, 0.006)), _pluck(int(note), f["timbre"]),
                        0.5 * level * (0.8 + 0.4 * rng.random()), 0.3 + 0.4 * ((k * 0.29) % 1.0))
            k += 1
            t += steps

        # a theme for this video, now and then, when the music is full enough: it comes back, never the same twice
        if kind not in ("chapter", "check") and at(c0 + beat) > 0.42 and span >= bar * 1.4 and rng.random() < 0.75:
            motif = motifs[melody_n % 2]
            melody_n += 1
            pos = c0 + beat * float(rng.choice([0, 0, 1]))
            anchor = min(chord_tones(scale, deg, f["root"], 72, 84), key=lambda m: abs(m - 78))
            base = sorted(set(f["root"] + scale[d % 7] for d in pent))
            line = sorted(m + 12 * o for m in base for o in range(-2, 4) if 66 <= m + 12 * o <= 91)
            idx = min(range(len(line)), key=lambda j: abs(line[j] - anchor))
            for step, dur in motif:
                if pos >= min(c1 - beat, c0 + 2.2 * bar):
                    break
                j = int(np.clip(idx + step - 2 + (1 if melody_n % 3 == 0 else 0), 0, len(line) - 1))
                wet.put(pos, _pluck(int(line[j]), "bell" if f["bright"] > -0.3 else f["timbre"]),
                        0.62 * float(_smooth(at(pos), 0.4, 0.7)) * (0.85 + 0.3 * rng.random()), 0.65)
                pos += dur * beat

        # a soft pulse under a driving, full passage
        if f["drive"] > 0.5 and at(c0 + beat) > 0.55 and kind not in ("chapter", "check"):
            tt = np.arange(int(0.5 * SR)) / SR
            kick = np.sin(2 * np.pi * (52 + 40 * np.exp(-tt * 28)) * tt) * np.exp(-tt * 9) * 0.5
            kick += 0.12 * np.sin(2 * np.pi * 104 * tt) * np.exp(-tt * 14)
            q = c0
            while q < c1 - 0.2:
                dry.put(q, kick.astype("float32"), 0.5, 0.5)
                q += beat * (2 if f["drive"] <= 0.8 else 1)

    # a quiz: a clock-like pair of notes while the viewer thinks, a bright rising chord when the answer lands
    tonic = chord_tones(scale, 0, f["root"], 60, 84)
    for a, b, kind in secs:
        if kind != "check":
            continue
        t = a + 0.4
        k = 0
        while t < a + 0.6 * (b - a):
            wet.put(t, _pluck(int(tonic[0] + (7 if k % 2 else 0) + 12), "marimba"), 0.34, 0.35 if k % 2 else 0.65)
            t += 0.5
            k += 1
        for j, m in enumerate(chord_tones(scale, 0, f["root"], 64, 88)[:4]):
            wet.put(a + 0.6 * (b - a) + 0.12 * j, _pluck(int(m), "bell"), 0.55, 0.3 + 0.13 * j)
    if secs[-1][2] == "outro":                      # and a last bell to close the video
        wet.put(max(secs[-1][0] + 0.4, seconds - 6.0), _pluck(int(tonic[len(tonic) // 2]), "bell"), 0.7, 0.5)

    out = _wash(wet.buf, 4200, 1.6, 0.3) + dry.buf
    t = np.arange(n) / SR
    fade = np.minimum(1, np.minimum(t / 2.5, (t[-1] - t) / 3)).astype("float32")
    out *= fade
    rms = float(np.sqrt((out[:, :int(seconds * SR)] ** 2).mean()) + 1e-9)
    out *= TARGET_RMS / rms
    peak = float(np.abs(out).max())
    if peak > 0.95:
        out *= 0.95 / peak
    note = {"mode": f["scale"], "key": f["root"] % 12, "bpm": f["bpm"], "timbre": f["timbre"], "bright": f["bright"],
            "drive": f["drive"], "chords": len(chords)}
    return out, note
