"""Sound for the videos, made in code so there is nothing to license: a music bed composed for each video (see
composer.py), a whoosh for transitions and a low hit for figures, plus the ffmpeg mix that ducks the music under the voice and masters
the result to YouTube loudness."""
import os
import wave
from typing import List, Optional, Tuple

import numpy as np

SR = 48000

def _write(path: str, stereo: np.ndarray) -> None:
    pcm = (np.clip(stereo, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.reshape(-1).tobytes())


def _reverb_lowpass(x: np.ndarray, cutoff: float, seconds: float = 1.8, wet: float = 0.35, seed: int = 3) -> np.ndarray:
    """A gentle low-pass and, added to it at `wet` of its own level, a soft room reverb (decaying noise impulse),
    both done in one FFT pass. (The bed's reverb used to be louder than the music itself: a wash that sounded like an
    echo under the voice.)"""
    rng = np.random.default_rng(seed)
    n_ir = int(seconds * SR)
    ir = rng.normal(0, 1, n_ir) * np.exp(-np.arange(n_ir) / (SR * seconds / 5))
    ir = ir / np.sqrt((ir ** 2).sum())
    size = 1 << int(np.ceil(np.log2(len(x) + n_ir)))
    freqs = np.fft.rfftfreq(size, 1 / SR)
    lp = 1 / (1 + (freqs / cutoff) ** 4)
    X = np.fft.rfft(x, size) * lp
    y = np.fft.irfft(X * np.fft.rfft(ir, size), size)[:len(x)]
    dry = np.fft.irfft(X, size)[:len(x)]
    return dry + y * wet


def music(seconds: float, path: str, seed: str = "", mood: str = "", sections=None) -> dict:
    """The music bed of one video, composed for it (composer.py): its mode, key, tempo and instrument come from the
    mood and title, its chords change with the shots, and how much music there is follows the story. `sections` is
    [(start s, end s, kind of shot)]. Returns what was composed (mode, key, tempo...) for the log."""
    from . import composer
    try:
        out, note = composer.compose(seconds, seed, mood, sections)
    except Exception as exc:        # the music must never cost a finished video: a plainer score, then none at all
        try:
            out, note = composer.compose(seconds, seed, "", None)
            note = {**note, "fallback": f"{type(exc).__name__}: {str(exc)[:120]}"}
        except Exception as exc2:
            out, note = np.zeros((2, int((seconds + 2) * SR)), dtype="float32"), {"silent": f"{type(exc2).__name__}: {str(exc2)[:120]}"}
    _write(path, out.T)
    return note


def whoosh(path: str) -> None:
    """Filtered noise that rises and falls while panning across: the sound of a transition."""
    n = int(0.8 * SR)
    t = np.arange(n) / n
    noise = np.random.default_rng(5).normal(0, 1, n)
    alpha = 0.02 + 0.25 * np.sin(np.pi * t) ** 2      # the filter opens in the middle of the sweep
    y = noise
    for _ in range(3):                                # three poles in a row: a soft "whoom", with none of the hissy
        out = np.zeros(n)                             # top that one pole leaves (that read as static under speech)
        acc = 0.0
        for i in range(n):
            acc += alpha[i] * (y[i] - acc)
            out[i] = acc
        y = out
    # nothing above ~1.5 kHz at all: a whoosh falls into the silence between two lines, and any noise up there is
    # heard as hiss (measured: 31 dB under the voice, 68 times in a ten-minute video, was what "many hiss" was made of)
    freqs = np.fft.rfftfreq(n, 1 / SR)
    y = np.fft.irfft(np.fft.rfft(y) / (1 + (freqs / 1500.0) ** 8), n)
    y *= np.sin(np.pi * t ** 0.8) ** 3
    y /= np.abs(y).max() + 1e-9
    _write(path, np.stack([y * (1 - 0.6 * t), y * (0.4 + 0.6 * t)], axis=1) * 0.7)


def hit(path: str, root_hz: float = 40.0) -> None:
    """A low, short impact with a falling pitch (settling on the video's own key): lands under a figure as it appears."""
    n = int(1.0 * SR)
    t = np.arange(n) / SR
    pitch = root_hz + 70 * np.exp(-t * 12)
    body = np.sin(2 * np.pi * np.cumsum(pitch) / SR) * np.exp(-t * 4.5)
    click = np.random.default_rng(9).normal(0, 1, n) * np.exp(-t * 90) * 0.4
    y = body + click
    y /= np.abs(y).max() + 1e-9
    _write(path, np.stack([y, y], axis=1) * 0.8)


BED_DEFAULT = 0.16           # measured: 0.34 left the music only 8 dB under the voice in every pause (heard as loud, messy, pumping)


def bed_level() -> float:
    """The music's volume under the narration (repository variable MUSIC_LEVEL; 0 = no music)."""
    try:
        return max(0.0, min(1.0, float(os.environ.get("MUSIC_LEVEL") or BED_DEFAULT)))
    except ValueError:
        return BED_DEFAULT


def whoosh_level() -> float:
    """The volume of the transition whoosh (repository variable WHOOSH_LEVEL; 0 = none). It was switched off when a
    "radio signal lost" sound was suspected, but that sound was the voice model's own hiss after sentences (see
    clone_voice.speech_end), and the owner asked for the whoosh back."""
    try:
        return max(0.0, min(1.0, float(os.environ.get("WHOOSH_LEVEL") or 0.12)))
    except ValueError:
        return 0.12


# Every voice line loses everything above ~10.5 kHz before the mix. The cloned voice is 24 kHz, and its leftover hiss
# sits at 11-12 kHz, just under that rate's ceiling: on the "Types of data" video (2026-11-13) the hissy quiz lines
# were 12 dB louder there than clean lines, while 6-11 kHz (all that voicecheck.hiss_ratio measures) was the same, so
# the hiss was never caught. Clean speech has nothing up there (-104 dB), so the cut is inaudible on a clean line. A
# linear-phase FIR: flat to 10.2 kHz, -87 dB from 10.8 kHz. It delays by a fixed 20 ms AND shifts the timestamps, so
# the timestamps are first rebuilt from the sample count and then exactly 960 samples (20 ms at 48 kHz) are cut:
# every word stays where the captions put it (measured at three placements: 0.02 ms; a time-based trim was 20 ms off).
VOICE_TOP_CUT = ("firequalizer=gain='if(lt(f,10200),0,-90)':delay=0.02:zero_phase=on,"
                 "asetpts=N/SR/TB,atrim=start_sample=960,asetpts=N/SR/TB")


def mix_filter(voice_at: List[float], whoosh_at: List[float], hit_at: List[float],
               tempos: Optional[List[float]] = None, final: bool = True, music_gain: float = 1.0,
               stems: bool = False) -> Tuple[str, int]:
    """ffmpeg filtergraph for inputs [voice clips..., music, whoosh, hit] -> [out]. The voice is cleaned up,
    the music ducks under it, the effects are placed, and the whole is mastered to -14 LUFS (YouTube).
    No "|" anywhere: on Windows the npx shim would read it as a pipe."""
    v = len(voice_at)
    m, w, h = v, v + 1, v + 2
    speed = lambda k: f"atempo={tempos[k]:.3f}," if tempos and tempos[k] > 1.005 else ""
    parts = [f"[{k}:a]aresample=48000,{VOICE_TOP_CUT},{speed(k)}adelay=delays={int(t * 1000)}:all=1[v{k}]"
             for k, t in enumerate(voice_at)]
    parts.append("".join(f"[v{k}]" for k in range(v)) + f"amix=inputs={v}:normalize=0,aformat=channel_layouts=stereo,"
                 "highpass=f=80,acompressor=threshold=-20dB:ratio=3:attack=5:release=150:makeup=2,"
                 "equalizer=f=3500:t=q:w=1.2:g=1.5,apad,asplit=2[voice][key]")   # apad: music runs past the last word
    # the music is a faint floor under the narration, never a second thing to listen to: about 20 dB under the
    # voice (master() measures the real mix and lowers the bed until the pauses are at least PAUSE_FLOOR_DB under it) (a cloned voice is less loud and more dynamic than a synthetic one, so the old level was heard as
    # background noise), pushed down further while the voice speaks. MUSIC_LEVEL=0 removes it altogether.
    parts.append(f"[{m}:a]highpass=f=110,volume={bed_level() * music_gain:.3f}[bedraw]")   # no rumble: small speakers cannot play it
    parts.append("[bedraw][key]sidechaincompress=threshold=0.02:ratio=6:attack=20:release=900[bed]")
    if stems:                       # the narration and the music bed on their own: how loud is the bed in the pauses?
        parts += ["[voice]aresample=48000[outv]", "[bed]aresample=48000[outb]"]
        return ";".join(parts), 3
    sfx = []
    for name, idx, times, vol in (("w", w, whoosh_at if whoosh_level() > 0 else [], whoosh_level()), ("h", h, hit_at, 0.18)):
        if not times:
            continue
        outs = "".join(f"[{name}{k}r]" for k in range(len(times)))
        parts.append(f"[{idx}:a]volume={vol},asplit={len(times)}{outs}" if len(times) > 1 else f"[{idx}:a]volume={vol}[{name}0r]")
        for k, t in enumerate(times):
            parts.append(f"[{name}{k}r]adelay=delays={max(0, int(t * 1000))}:all=1[{name}{k}]")
            sfx.append(f"[{name}{k}]")
    parts.append(f"[voice][bed]{''.join(sfx)}amix=inputs={2 + len(sfx)}:normalize=0,"
                 + ("loudnorm=I=-14:TP=-1.5:LRA=11," if final else "") + "aresample=48000[out]")
    return ";".join(parts), 3


def two_pass_filter(report: str) -> str:
    """The loudnorm filter for a second pass, fed with what the first pass measured (read from its report): the whole
    soundtrack is then raised or lowered by one fixed amount, instead of loudnorm's single-pass habit of riding the
    gain, which lifts the room tone after every sentence (a breathing, echoing sound). Plain loudnorm if the report
    cannot be read."""
    import json
    import re as _re
    plain = "loudnorm=I=-14:TP=-1.5:LRA=11"
    m = _re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", report or "", _re.S)
    try:
        d = json.loads(m.group(0))
        vals = {k: float(d[k]) for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")}
    except (AttributeError, KeyError, TypeError, ValueError):
        return plain
    if any(v != v or abs(v) == float("inf") for v in vals.values()):
        return plain
    return (f"{plain}:measured_I={vals['input_i']}:measured_TP={vals['input_tp']}:measured_LRA={vals['input_lra']}"
            f":measured_thresh={vals['input_thresh']}:offset={vals['target_offset']}:linear=true")


PAUSE_FLOOR_DB = 18.0       # the music in a pause must sit at least this far under the narration (300-3400 Hz level)


def band_db(x: np.ndarray, sr: int, lo: float = 300.0, hi: float = 3400.0) -> float:
    """RMS level (dB, relative to full scale) of the lo..hi Hz part of a mono signal."""
    if len(x) < 64:
        return -120.0
    spec = np.fft.rfft(x.astype("float64") * np.hanning(len(x)))
    f = np.fft.rfftfreq(len(x), 1 / sr)
    spec[(f < lo) | (f > hi)] = 0
    y = np.fft.irfft(spec, len(x))
    return float(20 * np.log10(np.sqrt((y ** 2).mean()) / 0.612 + 1e-9))      # 0.612: the Hann window's own loss


def _read_mono(path: str):
    with wave.open(path, "rb") as w:
        sr, ch = w.getframerate(), w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype("float32") / 32768
    return sr, (x.reshape(-1, ch).mean(1) if ch > 1 else x)


def pause_margin(voice: str, bed: str, spans: List[Tuple[float, float]]) -> Optional[Tuple[float, float, int]]:
    """How far under the narration the music sits in the pauses: (speech level dB, music level in the pauses dB,
    number of pauses measured), or None if there is nothing to compare. `voice` and `bed` are the two stems of the
    mix (see mix_filter's stems), `spans` the (start s, end s) of the spoken lines. A pause is the stretch between
    two lines at least half a second long, measured from 0.1 s after a line to 0.05 s before the next."""
    try:
        sr, v = _read_mono(voice)
        _, b = _read_mono(bed)
    except (OSError, wave.Error, EOFError):
        return None
    seg = lambda x, a, c: x[max(0, int(a * sr)):max(0, int(c * sr))]       # noqa: E731
    speech = [band_db(seg(v, s + 0.2, e - 0.2), sr) for s, e in spans if e - s > 1.2]
    pauses = [band_db(seg(b, spans[i][1] + 0.1, spans[i + 1][0] - 0.05), sr)
              for i in range(len(spans) - 1) if spans[i + 1][0] - spans[i][1] >= 0.5]
    if not speech or not pauses:
        return None
    return float(np.median(speech)), float(np.median(pauses)), len(pauses)
