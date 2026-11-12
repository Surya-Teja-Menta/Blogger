"""How good is one take of a spoken line? The cloning model is a sampler: any take of a sentence can drop or garble a
word, leave a long hole in the middle, or sprinkle breath and static between words. Instead of hoping, every take is
listened to (a speech recogniser's words, plus the samples themselves) and scored; the best of several is kept, and a
take that is nearly right is mended (a hole shortened, the noise between words faded out).

Pure numpy, no models: clone_voice.py (which runs in the voice environment) imports this file from its own folder, and
the tests run it on synthetic signals.

A take is a mono float array `x` at `sr`, the script it was meant to say, and `heard`: [[start s, end s, word], ...]
from the recogniser."""
import difflib
import re
from typing import Dict, List, Tuple

import numpy as np

HOP = 0.01                    # seconds between measurements
HOLE = 0.45                   # a silence inside a line longer than this is a hole (a comma lasts 0.2 to 0.35 s)
HOLE_TO = 0.28                # a hole is shortened to this
WORDS_PER_SECOND = (1.7, 4.4)  # slower or faster than this is a dragged or a rushed take
HISS_MAX = -34.0              # hiss_ratio above this is a hissy take (measured on a finished video: clean lines -43 +/- 3, the worst clean one -36.5, a hissy one -28)
HISS_FIX_TO = -38.0           # a repaired line should get under this
SIMILAR = 0.86                # a heard word this close to the script's word is the same word (recogniser noise)

SMALL = {w: k for k, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                                    "fourteen fifteen sixteen seventeen eighteen nineteen".split())}
TENS = {w: 10 * k for k, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if k > 1}


def tokens(text: str) -> List[str]:
    """Words for comparing a script with what was heard: lower case, no punctuation, numbers as digits."""
    out: List[str] = []
    for w in re.findall(r"[a-z0-9']+", str(text).lower().replace("-", " ").replace("‑", " ")):
        w = w.replace("'", "")
        if w in SMALL or w in TENS:
            v = SMALL.get(w, TENS.get(w, 0))
            if out and out[-1].isdigit() and int(out[-1]) % 10 == 0 and int(out[-1]) >= 20 and v < 10:
                out[-1] = str(int(out[-1]) + v)
            else:
                out.append(str(v))
        else:
            out.append(w)
    return out


def _skeleton(word: str) -> str:
    """A word with its vowels flattened and doubled letters merged: names are heard in many spellings that sound alike."""
    return re.sub(r"(.)\1+", r"\1", re.sub(r"[aeiouy]+", "a", word.lower()))


def _names(script: str) -> set:
    """The capitalised words inside sentences (not the first word of one): names, which a recogniser spells at will."""
    out = set()
    for m in re.finditer(r"[A-Za-z][A-Za-z']*", str(script)):
        before = str(script)[:m.start()].rstrip()
        if m.group(0)[0].isupper() and before and before[-1] not in ".!?…\"“":
            out.update("".join(tokens(m.group(0))) for _ in [0])
    return out


def fidelity(script: str, heard_text: str) -> Tuple[int, List[str]]:
    """How many script words a take lost, garbled or invented, and what: (count, ["lost 'x'", ...]). Blocks that sound
    alike once joined ("check out" / "checkout", "x i" / "xi") count as the same words, and so do a recogniser's usual
    slips ("calculator" heard as "calculators"): only blocks that are really different count."""
    a, b = tokens(script), tokens(heard_text)
    names = _names(script)
    notes: List[str] = []
    bad = 0
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        want, got = "".join(a[i1:i2]), "".join(b[j1:j2])
        if want and got and difflib.SequenceMatcher(None, want, got).ratio() >= SIMILAR:
            continue
        if want in names and got and difflib.SequenceMatcher(None, _skeleton(want), _skeleton(got)).ratio() >= 0.8:
            continue                       # a name, heard in another spelling ("Adyora" as "Adiora")
        n = max(i2 - i1, j2 - j1)
        bad += n
        notes.append(f"{' '.join(a[i1:i2]) or '-'} -> {' '.join(b[j1:j2]) or '-'}")
    return bad, notes


def frames_db(x: np.ndarray, sr: int, window: float = 0.025) -> np.ndarray:
    """Level of every HOP seconds (dB, relative to full scale) over a `window`-long frame."""
    step, win = max(1, int(HOP * sr)), max(8, int(window * sr))
    if len(x) < win:
        return np.full(1, -120.0)
    n = (len(x) - win) // step + 1
    idx = np.arange(win)[None, :] + step * np.arange(n)[:, None]
    return 20 * np.log10(np.sqrt((x[idx] ** 2).mean(1)) + 1e-9)


def band_db(x: np.ndarray, sr: int, lo: float, hi: float, window: float = 0.025) -> np.ndarray:
    """Level of the lo..hi Hz band, at the same moments as frames_db."""
    step, win = max(1, int(HOP * sr)), max(8, int(window * sr))
    if len(x) < win:
        return np.full(1, -120.0)
    n = (len(x) - win) // step + 1
    idx = np.arange(win)[None, :] + step * np.arange(n)[:, None]
    spec = np.abs(np.fft.rfft(x[idx] * np.hanning(win), axis=1)) ** 2
    f = np.fft.rfftfreq(win, 1 / sr)
    return 10 * np.log10(spec[:, (f >= lo) & (f < hi)].mean(1) / win + 1e-12)


def speech_bounds(db: np.ndarray, rel: float = -32.0) -> Tuple[int, int, float]:
    """(first frame, last frame, level) of the speech: frames within `rel` dB of the line's loud parts."""
    level = float(np.percentile(db, 90))
    on = np.where(db > level + rel)[0]
    if len(on) == 0:
        return 0, len(db) - 1, level
    return int(on[0]), int(on[-1]), level


def holes(x: np.ndarray, sr: int, rel: float = -32.0, longer: float = HOLE) -> List[Tuple[float, float]]:
    """Silences inside the speech (not its ends) longer than `longer` s: [(start s, end s)]."""
    db = frames_db(x, sr)
    a, b, level = speech_bounds(db, rel)
    quiet = db < level + rel
    out, start = [], None
    for i in range(a, b + 1):
        if quiet[i] and start is None:
            start = i
        elif not quiet[i] and start is not None:
            if (i - start) * HOP > longer:
                out.append((start * HOP, i * HOP))
            start = None
    return out


def junk(x: np.ndarray, sr: int, heard: List[list], pad: Tuple[float, float] = (0.06, 0.14), rel: float = -30.0,
         longer: float = 0.06) -> List[Tuple[float, float]]:
    """Sounds that are not words: stretches of audible sound (within `rel` dB of the loud parts) outside every
    recognised word (padded: a word's soft start and its tail run past the recogniser's times). Breath, static, a
    stray "sss": [(start s, end s)]."""
    db = frames_db(x, sr)
    level = float(np.percentile(db, 90))
    covered = np.zeros(len(db), bool)
    for s, e, _ in heard:
        covered[max(0, int((s - pad[0]) / HOP)):int((e + pad[1]) / HOP) + 1] = True
    loud = (db > level + rel) & ~covered
    out, start = [], None
    for i in range(len(db) + 1):
        if i < len(db) and loud[i] and start is None:
            start = i
        elif (i == len(db) or not loud[i]) and start is not None:
            if (i - start) * HOP >= longer:
                out.append((start * HOP, i * HOP))
            start = None
    return out


def hiss_ratio(x: np.ndarray, sr: int) -> float:
    """How much of the speech is high-frequency noise: the level of 6-11 kHz against 0.3-3 kHz, over the line's
    voiced frames (dB; lower is cleaner; measured on a finished video, clean lines sit near -43 (the worst clean one -36), a hissy take near -28). Sibilants lift single
    frames, so the median over the loud frames is used."""
    if sr < 16000:
        return -99.0
    db = frames_db(x, sr)
    hf, mid = band_db(x, sr, 6000, min(11000, sr / 2 - 100)), band_db(x, sr, 300, 3000)
    n = min(len(db), len(hf), len(mid))
    loud = db[:n] > float(np.percentile(db, 90)) - 14
    return float(np.median((hf[:n] - mid[:n])[loud])) if loud.any() else -99.0


def judge(script: str, x: np.ndarray, sr: int, heard: List[list]) -> Dict[str, object]:
    """Everything about one take that matters. `bad`: script words lost or garbled; `holes`, `junk`: see above;
    `rate`: words per second; `clip`: share of samples at full scale; `hiss`: see hiss_ratio. `score`: lower is
    better, 0 is a clean take."""
    got = " ".join(w[2] for w in heard)
    bad, notes = fidelity(script, got)
    hs, js = holes(x, sr), junk(x, sr, heard)
    hiss = hiss_ratio(x, sr)
    span = (heard[-1][1] - heard[0][0]) if heard else 0.0
    words = len(tokens(script))
    rate = words / span if span > 0.3 else 0.0
    clip = float((np.abs(x) > 0.995).mean()) if len(x) else 0.0
    odd_rate = 0.0 if WORDS_PER_SECOND[0] <= rate <= WORDS_PER_SECOND[1] or words < 4 else 1.0
    score = (10.0 * bad + 4.0 * sum(min(2.0, e - s) for s, e in hs) + 3.0 * sum(min(1.0, e - s) for s, e in js)
             + 4.0 * odd_rate + 100.0 * min(clip * 100, 1.0) + 8.0 * max(0.0, hiss - HISS_MAX))
    return {"bad": bad, "notes": notes, "holes": hs, "junk": js, "rate": round(rate, 2), "clip": round(clip, 5),
            "hiss": round(hiss, 1), "score": round(score, 2),
            "clean": bad == 0 and not hs and not js and not odd_rate and clip < 1e-4 and hiss <= HISS_MAX}


def mend(x: np.ndarray, sr: int, heard: List[list]) -> Tuple[np.ndarray, List[list]]:
    """The take with its holes shortened to HOLE_TO and its non-word noise faded out (a 20 ms fade each side, to 3% of
    the level: quiet, not a dead digital silence that would make the room tone jump). Word times move with the cuts."""
    out = x.astype("float32").copy()
    # noise between words: attenuate, with fades
    gain = np.ones(len(out), "float32")
    for s, e in junk(out, sr, heard):
        a, b = max(0, int(s * sr)), min(len(out), int(e * sr))
        gain[a:b] = 0.03
    if (gain < 1).any():
        k = max(1, int(0.02 * sr))
        gain = np.convolve(gain, np.ones(k, "float32") / k, mode="same")
        out *= gain
    # holes: cut the middle of the silence, keep both edges (they hold the word tails)
    cuts = [(s, e) for s, e in holes(out, sr)]
    if not cuts:
        return out, [list(w) for w in heard]
    pieces, last, removed = [], 0, []
    for s, e in cuts:
        keep = HOLE_TO / 2
        a, b = int((s + keep) * sr), int((e - keep) * sr)
        if b - a < int(0.02 * sr):
            continue
        pieces.append(out[last:a])
        fade = int(0.01 * sr)
        pieces[-1][-fade:] *= np.linspace(1, 0, fade, dtype="float32")
        last = b
        out2 = out[last:last + fade]
        out2 *= np.linspace(0, 1, len(out2), dtype="float32")
        removed.append((s + keep, e - keep))
    pieces.append(out[last:])
    mended = np.concatenate(pieces)
    shifted = []
    for s, e, w in heard:
        shift = lambda t: t - sum(min(max(0.0, t - a), b - a) for a, b in removed)
        shifted.append([round(shift(s), 3), round(shift(e), 3), w])
    return mended, shifted
