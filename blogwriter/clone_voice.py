"""Speak narration lines in the channel owner's own voice (Chatterbox, MIT licence: zero-shot cloning from a short
recording), and time every spoken word (faster-whisper, MIT). Runs in its own Python environment, because the
models pin their own library versions; the pipeline calls it as a separate process:

    python clone_voice.py jobs.json reference.wav

jobs.json: [{"text": "...", "out": "path.wav"}, ...]. For each job it writes the WAV and adds "words":
[[start s, end s, word], ...] as heard, plus "ok". The file is rewritten with the results. A job that fails keeps
ok=false, and the pipeline speaks that line with its usual voice instead (never a missing line).
Settings (environment): CLONE_EXAGGERATION (0.25-2, default 0.6: livelier delivery), CLONE_CFG (0-1, default 0.4:
lower is slower and more deliberate), CLONE_WHISPER (faster-whisper model, default "small.en"), CLONE_TAKES (the most
takes tried of one sentence, default 6).

Every sentence is spoken until a take is clean (voicecheck.py: no lost or garbled word, no hole in the middle, no
noise between words), the best take is mended, trimmed at its real edges, and listened to once more after trimming, so
no step can lose a word.
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voicecheck as vc  # noqa: E402


def sentences(text: str):
    """Short pieces Chatterbox speaks steadily (a long paragraph in one go can drift or cut off)."""
    parts = [p.strip() for p in re.split(r"(?<=[.!?…])\s+", text.strip()) if p.strip()]
    out = []
    for p in parts:                       # an overlong sentence is split at commas
        while len(p.split()) > 40 and "," in p:
            cut = p.rfind(",", 0, len(p) // 2 + 40)
            if cut <= 0:
                break
            out.append(p[:cut + 1].strip())
            p = p[cut + 1:].strip()
        out.append(p)
    return out


SMALL = {w: k for k, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                                    "fourteen fifteen sixteen seventeen eighteen nineteen".split())}
TENS = {w: 10 * k for k, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if k > 1}


def tokens(text: str):
    """Words for comparing a script with what was heard: lower case, no punctuation, numbers as digits."""
    out = []
    for w in re.findall(r"[a-z0-9']+", text.lower().replace("-", " ")):
        if w in SMALL or w in TENS:
            v = SMALL.get(w, TENS.get(w, 0))
            if out and out[-1].isdigit() and int(out[-1]) % 10 == 0 and int(out[-1]) >= 20 and v < 10:
                out[-1] = str(int(out[-1]) + v)       # "forty two" -> 42
            else:
                out.append(str(v))
        else:
            out.append(w)
    return out


def match(script: str, heard: str) -> float:
    """How closely what was heard follows the script (1 = word for word)."""
    import difflib
    return difflib.SequenceMatcher(None, tokens(script), tokens(heard), autojunk=False).ratio()


def _box(a, kt, kf):
    """A moving average over time (kt frames) and frequency (kf bins) of a spectrogram, numpy only."""
    import numpy as np
    out = a
    for axis, k in ((0, kt), (1, kf)):
        if k > 1:
            pad = [(0, 0), (0, 0)]
            pad[axis] = (k // 2, k - 1 - k // 2)
            c = np.cumsum(np.pad(out, pad, mode="edge"), axis=axis)
            c = np.concatenate([np.zeros_like(np.take(c, [0], axis=axis)), c], axis=axis)
            hi = np.take(c, range(k, c.shape[axis]), axis=axis)
            lo = np.take(c, range(0, c.shape[axis] - k), axis=axis)
            out = (hi - lo) / k
    return out


def dry(x, sr, rt60=0.6, strength=0.8, floor=0.5, delay=0.045):
    """Take the room out of a voice: late-reverberation suppression (after Lebart et al.). The part of each frame that
    is the decaying tail of what was said `delay` seconds earlier is estimated from the spectrum then and taken
    away, so words end where they end. Power and gain are both smoothed, so no granular speckle is left behind."""
    import numpy as np
    n = 1024 if sr >= 20000 else 512
    hop = n // 4
    win = np.hanning(n + 1)[:-1]
    pad = np.concatenate([np.zeros(n), x, np.zeros(2 * n)])
    count = 1 + (len(pad) - n) // hop
    idx = np.arange(n)[None, :] + hop * np.arange(count)[:, None]
    X = np.fft.rfft(pad[idx] * win, axis=1)
    P = np.maximum(_box(np.abs(X) ** 2 + 1e-12, 3, 9), 1e-10)           # (a running sum can cancel to nothing)
    d = max(1, int(round(delay * sr / hop)))
    R = np.zeros_like(P)
    R[d:] = np.exp(-13.8155 * (d * hop / sr) / rt60) * P[:-d]
    G = _box(np.sqrt(np.clip(1 - strength * R / P, floor ** 2, 1.0)), 5, 15)
    for t in range(1, count):
        G[t] = np.maximum(G[t], G[t - 1] * 0.7)
    Y = np.fft.irfft(X * G, n=n, axis=1) * win
    out, norm = np.zeros(len(pad)), np.zeros(len(pad))
    for t in range(count):
        out[t * hop:t * hop + n] += Y[t]
        norm[t * hop:t * hop + n] += win ** 2
    return (out / np.maximum(norm, 1e-6))[n:n + len(x)].astype("float32")


def best_window(x, sr, seconds=10.0):
    """(start, end) samples of the cleanest `seconds` of a recording: where speech stands furthest above the quiet
    between words, with plenty of speech in it. Chatterbox listens to only the first ~10 s of a reference, so those
    seconds are what a clone's voice (and its room, hiss, hum and clicks) is made of: the start of a recording is
    often its worst part, and the clone then speaks with that hiss now and then."""
    import numpy as np
    n = int(0.03 * sr)
    fr = x[:len(x) // n * n].reshape(-1, n)
    db = 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9)
    per = int(seconds / 0.03)
    if len(db) <= per:
        return 0, len(x)
    best, at = -1e9, 0
    for a in range(0, len(db) - per, 5):
        w = db[a:a + per]
        top = np.percentile(w, 90)
        speech = float(np.mean(w > top - 20))
        if not 0.4 <= speech <= 0.9:
            continue
        quiet = w[w <= top - 20]                  # how noisy the pauses get: any hissy stretch counts against the window
        score = top - (np.percentile(quiet, 75) if len(quiet) > 5 else top) - 40 * abs(speech - 0.65)
        if score > best:
            best, at = score, a
    return at * n, min(len(x), (at + per) * n)


def speech_end(x, sr, word_end, reach=0.5):
    """Sample where a spoken sentence really ends. After its last word the model sometimes adds a burst of hiss (a
    breath, an "sss" that is not a word), a fraction of a second after a gap of true silence: heard as a radio losing
    its signal before the line goes dead. The speech ends at the first true silence after the recogniser's last word.
    Silence means 40 dB under the sentence's own loud parts: a word's final "s", "v" or "f" decays slowly through
    -20 to -35 dB (measured on real takes, and the recogniser ends the word before that tail is over), so a looser
    threshold bit those last sounds off ("times" heard as "time", "curve" as "cub"). No silence within `reach`
    seconds: 0.3 s past the word, which is longer than the tails measured."""
    import numpy as np
    step = max(1, int(0.01 * sr))
    frames = len(x) // step
    if frames < 5:
        return len(x)
    rms = np.sqrt((x[:frames * step].reshape(frames, step) ** 2).mean(1))
    at = min(frames - 1, int(word_end * 100))
    ref = float(np.percentile(rms[:at + 1], 75)) if at > 0 else float(rms.max())
    quiet = rms < ref * 0.01                                    # 40 dB under the sentence's own loud parts
    for i in range(at + 2, min(frames - 3, at + int(reach * 100))):
        if quiet[i:i + 4].all():
            return min(len(x), (i + 2) * step)
    return min(len(x), int((word_end + 0.3) * sr))


LEAD_ALLOW = 0.18            # an unpitched start ("sh", "str", "f") never takes longer than this before the vowel
FRICATIVE_END = re.compile(r"(s|z|x|f|v|th|sh|ch|ce|se|ze|ve|fe|ge)$")
STOP_END = re.compile(r"(p|t|k|c)$")


def speech_span(x, sr, word_start, word_end, last_word=""):
    """(start, end) samples of the real speech in one spoken sentence. The model puts a burst of noise (a breath, an
    "sss") before the first word of many lines and after the last one: heard as a radio losing its signal, and
    measured at 0.15 to 0.4 s long in a fifth to a third of the lines after the last word (the burst comes after a
    short dip, and is about as loud as the word's own final "s"). A word's own unpitched edges are short: an initial
    "sh" or "str" is under 0.18 s, a final "s" about 0.12 s, a final "t" under 0.07 s. So the line keeps everything
    from 0.18 s before its first pitched sound to the end of its last pitched sound plus the time its last letter
    needs, but never less than the recogniser's own span of the words, and never past the first real dip after them.
    Nothing is trimmed if no pitch is found (a whisper, a very short line)."""
    import numpy as np
    step, win = max(1, int(0.01 * sr)), max(8, int(0.032 * sr))
    frames = (len(x) - win) // step
    if frames < 12:
        return 0, len(x)
    idx = np.arange(win)[None, :] + step * np.arange(frames)[:, None]
    f = x[idx]
    f = f - f.mean(1, keepdims=True)
    rms = np.sqrt((f ** 2).mean(1))
    # pitch is judged on the voice's low frequencies only (70 Hz to 1 kHz): hiss lives high up, and a narrow band of
    # hiss would otherwise correlate with itself and pass for a voice
    power = np.abs(np.fft.rfft(f, 2 * win, axis=1)) ** 2
    freq = np.fft.rfftfreq(2 * win, 1 / sr)
    power[:, (freq < 70) | (freq > 1000)] = 0
    ac = np.fft.irfft(power, axis=1)[:, :win]
    lo, hi = max(1, int(sr / 400)), min(win - 1, int(sr / 70))
    ratio = ac[:, lo:hi].max(1) / np.maximum(ac[:, 0], 1e-12)
    low = np.sqrt(np.maximum(ac[:, 0], 0))
    voiced = (ratio > 0.5) & (low > float(np.percentile(low, 75)) * 0.05)
    ref = float(np.percentile(rms, 75))
    hits = np.where(voiced)[0]
    if len(hits) < 8:
        return 0, len(x)
    first, last = int(hits[0]), int(hits[-1])
    start = max(0, int(first * step - LEAD_ALLOW * sr))
    start = min(start, int(0.8 * sr))     # the recogniser's first-word time is no guide: it often sits inside the noise
    word = re.sub(r"[^a-z]", "", (last_word or "").lower())
    allow = 0.12 if FRICATIVE_END.search(word) else 0.07 if STOP_END.search(word) else 0.04
    tail = int((last * step + win) + allow * sr)
    at = min(frames - 1, max(0, int(word_end * 100) - 5))
    gap = len(x)                       # the first real dip after the words: a burst of hiss comes after it, not before
    for i in range(at, frames - 3):
        if (rms[i:i + 4] < ref * 0.07).all():            # 23 dB under the line's loud parts, for 40 ms
            gap = (i + 1) * step
            break
    end = max(min(gap, tail), int((word_end + 0.06) * sr))
    return start, min(len(x), end)


def main() -> int:
    jobs_path, reference = sys.argv[1], sys.argv[2]
    with open(jobs_path, encoding="utf-8") as f:
        jobs = json.load(f)
    import torch
    import torchaudio
    from faster_whisper import WhisperModel

    torch.set_num_threads(max(1, (os.cpu_count() or 4) - 1))     # one core stays free for the CI runner's own agent (a starved runner "loses communication" and the whole run is lost)
    t0 = time.time()
    drying = os.environ.get("CLONE_DRY", "1").strip() != "0"
    if drying:       # the recording's cleanest ten seconds, with its room taken out: the clone then speaks in a dry room
        wav, sr_ref = torchaudio.load(reference)
        mono = wav.mean(0).numpy()
        a, b = best_window(mono, sr_ref)
        print(f"[clone] reference: seconds {a / sr_ref:.1f} to {b / sr_ref:.1f} of {len(mono) / sr_ref:.1f}", flush=True)
        import atexit
        import shutil
        import tempfile
        scratch = tempfile.mkdtemp(prefix="ref_")          # never next to the recording: that folder may be kept
        atexit.register(shutil.rmtree, scratch, True)
        reference = os.path.join(scratch, "reference.wav")
        torchaudio.save(reference, torch.from_numpy(dry(mono[a:b], sr_ref))[None], sr_ref)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # Turbo (the default) is the smaller, much faster model: it ignores the expressiveness settings
    # the standard model (default) says the script word for word; Turbo is ~2.5x faster but garbles some words
    turbo = os.environ.get("CLONE_MODEL", "standard").strip().lower() == "turbo"
    if turbo:
        from chatterbox.tts_turbo import ChatterboxTurboTTS
        tts = ChatterboxTurboTTS.from_pretrained(device=device)
    else:
        from chatterbox.tts import ChatterboxTTS
        tts = ChatterboxTTS.from_pretrained(device=device)
    asr = WhisperModel(os.environ.get("CLONE_WHISPER", "small.en"), device="cpu", compute_type="int8")
    exaggeration = float(os.environ.get("CLONE_EXAGGERATION", "0.6"))
    cfg = float(os.environ.get("CLONE_CFG", "0.4"))
    if turbo:     # the sample is already loudness-normalised; Turbo's own normalisation trips a dtype bug
        tts.prepare_conditionals(reference, exaggeration=exaggeration, norm_loudness=False)
    else:
        tts.prepare_conditionals(reference, exaggeration=exaggeration)
    temperature = float(os.environ.get("CLONE_TEMPERATURE", "0.7"))     # cooler than the default 0.8: fewer wild takes
    speak = ((lambda s: tts.generate(s)) if turbo else
             (lambda s: tts.generate(s, exaggeration=exaggeration, cfg_weight=cfg, temperature=temperature, min_p=0.08)))
    print(f"[clone] models ready in {time.time() - t0:.0f}s", flush=True)
    gap = torch.zeros(1, int(tts.sr * 0.18))           # a breath between sentences
    # how closely a line must say its script: a clean take scores ~1.0, one misheard word ~0.95, a garbled take
    # with invented words ~0.85 (measured on real takes)
    need = float(os.environ.get("CLONE_MATCH", "0.92"))
    tries = int(os.environ.get("CLONE_TRIES", "1"))     # whole-line retries: every sentence already chooses among takes
    takes = max(1, int(os.environ.get("CLONE_TAKES", "6")))
    sr = tts.sr

    def recognise(x):
        """The words heard in a take, timed from the samples themselves (reading a file back would go through PyAV,
        whose newer versions refuse an option faster-whisper passes)."""
        m16 = torchaudio.functional.resample(torch.from_numpy(x)[None], sr, 16000).squeeze(0).numpy().astype("float32")
        segs, _ = asr.transcribe(m16, language="en", word_timestamps=True, beam_size=5,
                                 vad_filter=False, condition_on_previous_text=False)
        return [[round(w.start, 3), round(w.end, 3), w.word.strip()]
                for seg in segs for w in (seg.words or []) if w.word.strip()]

    def best_take(piece, stats):
        """The best of up to `takes` takes of one piece of script: the first clean one, else the lowest score."""
        best = None
        for _ in range(takes):
            audio = speak(piece).squeeze(0).numpy()
            if drying:
                audio = dry(audio, sr)
            heard = recognise(audio)
            verdict = vc.judge(piece, audio, sr, heard)
            stats["takes"] += 1
            if best is None or verdict["score"] < best[2]["score"]:
                best = (audio, heard, verdict)
            if verdict["clean"]:
                break
        return best

    def finish(piece, audio, heard, verdict, stats):
        """Mend the take (holes shortened, noise between words faded out), cut it at its real edges, and listen again:
        the cut may not cost a word that the take had. -> (audio, words)."""
        import numpy as np
        if verdict["holes"] or verdict["junk"]:
            audio, heard = vc.mend(audio, sr, heard)
            stats["mended"] += len(verdict["holes"]) + len(verdict["junk"])
        want = vc.fidelity(piece, " ".join(w[2] for w in heard))[0]
        options = []
        if heard:
            options.append(speech_span(audio, sr, heard[0][0], heard[-1][1], heard[-1][2]))   # the tight cut
            options.append((max(0, int((heard[0][0] - 0.25) * sr)), min(len(audio), int((heard[-1][1] + 0.35) * sr))))
        options.append((0, len(audio)))                                                       # no cut at all
        for begin, cut in options:
            part = audio[begin:cut].copy()
            if len(part) < int(0.15 * sr):
                continue
            shift = begin / sr
            words = [[max(0.0, round(a - shift, 3)), max(0.0, round(b - shift, 3)), w] for a, b, w in heard]
            lead, fade = min(len(part), int(0.015 * sr)), min(len(part), int(0.03 * sr))
            part[:lead] *= np.linspace(0, 1, lead, dtype="float32")
            part[len(part) - fade:] *= np.linspace(1, 0, fade, dtype="float32")
            if (begin, cut) == options[-1] or vc.fidelity(piece, " ".join(w[2] for w in recognise(part)))[0] <= want:
                return part, words
        return audio, heard

    def halves(piece):
        """A long sentence in two parts at the comma nearest its middle (None when it has no comma worth splitting at)."""
        parts = piece.split(",")
        if len(piece.split()) < 9 or len(parts) < 2:
            return None
        cuts = [len(",".join(parts[:i + 1])) for i in range(len(parts) - 1)]
        at = min(cuts, key=lambda c: abs(c - len(piece) / 2))
        return piece[:at + 1].strip(), piece[at + 1:].strip()

    def say(text):
        """A line: its audio and the words heard in it. Every sentence is the best of several takes, dried, mended,
        cut where its speech really ends and listened to again, so no junk sound is left after it and no word is
        missing. A long sentence that stays wrong is spoken in two halves, each chosen on its own."""
        import numpy as np
        pieces, words, offset = [], [], 0.0
        stats = {"takes": 0, "mended": 0, "bad": 0, "split": 0}
        for sentence in sentences(text):
            audio, heard, verdict = best_take(sentence, stats)
            part = None
            two = halves(sentence) if verdict["bad"] else None
            if two:
                t1, t2 = best_take(two[0], stats), best_take(two[1], stats)
                if t1[2]["bad"] + t2[2]["bad"] < verdict["bad"]:
                    stats["split"] += 1
                    a1, h1 = finish(two[0], *t1, stats)
                    a2, h2 = finish(two[1], *t2, stats)
                    pause = np.zeros(int(0.22 * sr), "float32")
                    shift = (len(a1) + len(pause)) / sr
                    part = np.concatenate([a1, pause, a2])
                    wds = h1 + [[a + shift, b + shift, w] for a, b, w in h2]
                    verdict = {**verdict, "bad": t1[2]["bad"] + t2[2]["bad"]}
            if part is None:
                part, wds = finish(sentence, audio, heard, verdict, stats)
            stats["bad"] += verdict["bad"]
            pieces += [torch.from_numpy(part)[None], gap]
            words += [[a + offset, b + offset, w] for a, b, w in wds]
            offset += len(part) / sr + gap.shape[1] / sr
        say.stats = stats
        return torch.cat(pieces[:-1], dim=1), [[round(a, 3), round(b, 3), w] for a, b, w in words]

    for k, job in enumerate(jobs):
        job["ok"] = False
        try:
            best = None                 # a take that garbles or adds words is spoken again; the closest is kept
            for attempt in range(max(1, tries)):
                audio, words = say(job["text"])
                score = match(job["text"], " ".join(w[2] for w in words))
                if best is None or score > best[0]:
                    best = (score, audio, words)
                if score >= need:
                    break
            score, audio, words = best
            torchaudio.save(job["out"], audio, tts.sr)
            job.update(words=words, match=round(score, 3), ok=bool(words))
        except Exception as exc:                        # one line must not sink the rest
            job["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        st = getattr(say, "stats", {})
        job["checks"] = dict(st)                    # what the checking found, for the pipeline's log
        print(f"[clone] {k + 1}/{len(jobs)} {'ok' if job['ok'] else 'FAILED ' + job.get('error', '')} "
              f"match {job.get('match', 0):.2f} takes {st.get('takes', 0)} mended {st.get('mended', 0)} "
              f"split {st.get('split', 0)} unfixed {st.get('bad', 0)} ({time.time() - t0:.0f}s)", flush=True)
        with open(jobs_path, "w", encoding="utf-8") as f:   # progress is kept even if the process dies later
            json.dump(jobs, f, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
