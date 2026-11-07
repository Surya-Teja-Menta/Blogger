"""Sound for the videos, made in code so there is nothing to license: a calm music bed, a whoosh for
transitions and a low hit for figures, plus the ffmpeg mix that ducks the music under the voice and masters
the result to YouTube loudness."""
import hashlib
import os
import wave
from typing import List, Optional, Tuple

import numpy as np

SR = 48000

# chord progressions (Hz of the triads); one is picked per video so channels do not sound identical
PROGRESSIONS = [
    [(220.00, 261.63, 329.63), (174.61, 220.00, 261.63), (130.81, 164.81, 196.00), (196.00, 246.94, 293.66)],  # Am F C G
    [(146.83, 174.61, 220.00), (116.54, 146.83, 174.61), (174.61, 220.00, 261.63), (130.81, 164.81, 196.00)],  # Dm Bb F C
    [(164.81, 196.00, 246.94), (130.81, 164.81, 196.00), (196.00, 246.94, 293.66), (146.83, 185.00, 220.00)],  # Em C G D
]


def _write(path: str, stereo: np.ndarray) -> None:
    pcm = (np.clip(stereo, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.reshape(-1).tobytes())


def _reverb_lowpass(x: np.ndarray, cutoff: float, seconds: float = 1.8, wet: float = 0.35) -> np.ndarray:
    """Soft room reverb (decaying noise impulse) and a gentle low-pass, both done in one FFT pass."""
    rng = np.random.default_rng(3)
    n_ir = int(seconds * SR)
    ir = rng.normal(0, 1, n_ir) * np.exp(-np.arange(n_ir) / (SR * seconds / 5))
    ir = ir / np.sqrt((ir ** 2).sum())
    size = 1 << int(np.ceil(np.log2(len(x) + n_ir)))
    freqs = np.fft.rfftfreq(size, 1 / SR)
    lp = 1 / (1 + (freqs / cutoff) ** 4)
    X = np.fft.rfft(x, size) * lp
    y = np.fft.irfft(X * np.fft.rfft(ir, size), size)[:len(x)]
    dry = np.fft.irfft(X, size)[:len(x)]
    return dry * (1 - wet) + y * wet * 3


def music(seconds: float, path: str, seed: str = "") -> None:
    """An ambient bed: slow chords, a soft eighth-note pulse and a low heartbeat, in one of a few keys. One
    32-second progression is made with its reverb tail wrapped around, so it loops without a seam."""
    loop = _bed(seed)
    n = int((seconds + 2) * SR)
    out = np.tile(loop, (n // len(loop) + 1, 1))[:n]
    t = np.arange(n) / SR
    fade = np.minimum(1, np.minimum(t / 2.5, (t[-1] - t) / 3))[:, None]
    _write(path, out * fade)


def _bed(seed: str) -> np.ndarray:
    pick = int(hashlib.md5(seed.encode()).hexdigest(), 16)
    chords = PROGRESSIONS[pick % len(PROGRESSIONS)]
    period = 32.0
    bar = 8.0                                   # one chord every 8 seconds
    n = int((period + bar + 4) * SR)            # one more chord and room for the reverb tail, wrapped round below
    t = np.arange(n) / SR
    left, right = np.zeros(n), np.zeros(n)
    for k in range(1, int(period / bar) + 1):   # chord 4 is chord 0 again: its body wraps to the loop's start
        a, b = k * bar - 1.5, (k + 1) * bar + 1.5          # each chord fades over its neighbours
        i0, i1 = max(0, int(a * SR)), min(n, int(b * SR))
        if i0 >= i1:
            continue
        seg = t[i0:i1]
        env = np.sin(np.pi * np.clip((seg - a) / (b - a), 0, 1)) ** 2
        for f in chords[k % len(chords)]:
            left[i0:i1] += 0.05 * env * (np.sin(2 * np.pi * f * seg) + 0.25 * np.sin(4 * np.pi * f * seg))
            right[i0:i1] += 0.05 * env * (np.sin(2 * np.pi * f * 1.003 * seg) + 0.25 * np.sin(4 * np.pi * f * 1.003 * seg))
        root = chords[k % len(chords)][0] / 2
        left[i0:i1] += 0.06 * env * np.sin(2 * np.pi * root * seg)
        right[i0:i1] += 0.06 * env * np.sin(2 * np.pi * root * seg)
    beat = 60 / 96                              # 96 bpm
    pluck_len = int(0.5 * SR)
    pl_t = np.arange(pluck_len) / SR
    for j in range(int(period / (beat / 2))):
        start = j * beat / 2
        chord = chords[int(start // bar) % len(chords)]
        f = chord[j % 3] * 2
        i0 = int(start * SR)
        i1 = min(n, i0 + pluck_len)
        tone = 0.03 * np.exp(-pl_t * 7)[: i1 - i0] * np.sin(2 * np.pi * f * pl_t[: i1 - i0])
        pan = 0.5 + 0.3 * np.sin(j)
        left[i0:i1] += tone * (1 - pan)
        right[i0:i1] += tone * pan
        if j % 2 == 0:                          # heartbeat on every beat
            thump = 0.09 * np.exp(-pl_t * 9)[: i1 - i0] * np.sin(2 * np.pi * (48 + 30 * np.exp(-pl_t * 30)[: i1 - i0]) * pl_t[: i1 - i0])
            left[i0:i1] += thump
            right[i0:i1] += thump
    left, right = _reverb_lowpass(left, 2600), _reverb_lowpass(right, 2600)
    out = np.stack([left, right], axis=1)
    p = int(period * SR)
    loop = out[:p].copy()
    loop[: n - p] += out[p:]                    # the tail of the last chord rings into the first: no seam
    return loop / (np.abs(loop).max() + 1e-9) * 0.5


def whoosh(path: str) -> None:
    """Filtered noise that rises and falls while panning across: the sound of a transition."""
    n = int(0.8 * SR)
    t = np.arange(n) / n
    noise = np.random.default_rng(5).normal(0, 1, n)
    alpha = 0.02 + 0.25 * np.sin(np.pi * t) ** 2      # the filter opens in the middle of the sweep
    y = np.zeros(n)
    acc = 0.0
    for i in range(n):
        acc += alpha[i] * (noise[i] - acc)
        y[i] = acc
    y *= np.sin(np.pi * t ** 0.8) ** 3
    y /= np.abs(y).max() + 1e-9
    _write(path, np.stack([y * (1 - 0.6 * t), y * (0.4 + 0.6 * t)], axis=1) * 0.7)


def hit(path: str) -> None:
    """A low, short impact with a falling pitch: lands under a figure as it appears."""
    n = int(1.0 * SR)
    t = np.arange(n) / SR
    pitch = 40 + 70 * np.exp(-t * 12)
    body = np.sin(2 * np.pi * np.cumsum(pitch) / SR) * np.exp(-t * 4.5)
    click = np.random.default_rng(9).normal(0, 1, n) * np.exp(-t * 90) * 0.4
    y = body + click
    y /= np.abs(y).max() + 1e-9
    _write(path, np.stack([y, y], axis=1) * 0.8)


def bed_level() -> float:
    """The music's volume under the narration (repository variable MUSIC_LEVEL; 0 = no music)."""
    try:
        return max(0.0, min(1.0, float(os.environ.get("MUSIC_LEVEL") or 0.12)))
    except ValueError:
        return 0.12


def mix_filter(voice_at: List[float], whoosh_at: List[float], hit_at: List[float],
               tempos: Optional[List[float]] = None) -> Tuple[str, int]:
    """ffmpeg filtergraph for inputs [voice clips..., music, whoosh, hit] -> [out]. The voice is cleaned up,
    the music ducks under it, the effects are placed, and the whole is mastered to -14 LUFS (YouTube).
    No "|" anywhere: on Windows the npx shim would read it as a pipe."""
    v = len(voice_at)
    m, w, h = v, v + 1, v + 2
    speed = lambda k: f"atempo={tempos[k]:.3f}," if tempos and tempos[k] > 1.005 else ""
    parts = [f"[{k}:a]aresample=48000,{speed(k)}adelay=delays={int(t * 1000)}:all=1[v{k}]" for k, t in enumerate(voice_at)]
    parts.append("".join(f"[v{k}]" for k in range(v)) + f"amix=inputs={v}:normalize=0,aformat=channel_layouts=stereo,"
                 "highpass=f=80,acompressor=threshold=-20dB:ratio=3:attack=5:release=150:makeup=2,"
                 "equalizer=f=3500:t=q:w=1.2:g=2.5,apad,asplit=2[voice][key]")   # apad: music runs past the last word
    # the music is a faint floor under the narration, never a second thing to listen to: about 20 dB under the
    # voice (a cloned voice is less loud and more dynamic than a synthetic one, so the old level was heard as
    # background noise), pushed down further while the voice speaks. MUSIC_LEVEL=0 removes it altogether.
    parts.append(f"[{m}:a]volume={bed_level():.3f}[bedraw]")
    parts.append("[bedraw][key]sidechaincompress=threshold=0.02:ratio=8:attack=15:release=900[bed]")
    sfx = []
    for name, idx, times, vol in (("w", w, whoosh_at, 0.12), ("h", h, hit_at, 0.22)):
        if not times:
            continue
        outs = "".join(f"[{name}{k}r]" for k in range(len(times)))
        parts.append(f"[{idx}:a]volume={vol},asplit={len(times)}{outs}" if len(times) > 1 else f"[{idx}:a]volume={vol}[{name}0r]")
        for k, t in enumerate(times):
            parts.append(f"[{name}{k}r]adelay=delays={max(0, int(t * 1000))}:all=1[{name}{k}]")
            sfx.append(f"[{name}{k}]")
    parts.append(f"[voice][bed]{''.join(sfx)}amix=inputs={2 + len(sfx)}:normalize=0,"
                 "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[out]")
    return ";".join(parts), 3
