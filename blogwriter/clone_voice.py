"""Speak narration lines in the channel owner's own voice (Chatterbox, MIT licence: zero-shot cloning from a short
recording), and time every spoken word (faster-whisper, MIT). Runs in its own Python environment, because the
models pin their own library versions; the pipeline calls it as a separate process:

    python clone_voice.py jobs.json reference.wav

jobs.json: [{"text": "...", "out": "path.wav"}, ...]. For each job it writes the WAV and adds "words":
[[start s, end s, word], ...] as heard, plus "ok". The file is rewritten with the results. A job that fails keeps
ok=false, and the pipeline speaks that line with its usual voice instead (never a missing line).
Settings (environment): CLONE_EXAGGERATION (0.25-2, default 0.6: livelier delivery), CLONE_CFG (0-1, default 0.4:
lower is slower and more deliberate), CLONE_WHISPER (faster-whisper model, default "base.en").
"""
import json
import os
import re
import sys
import time


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


def dry(x, sr, rt60=0.6, strength=1.1, floor=0.3, delay=0.045):
    """Take the room out of a voice: late-reverberation suppression (after Lebart et al.). The part of each frame that
    is the decaying tail of what was said `delay` seconds earlier is estimated from the spectrum then and taken
    away, so words end where they end. The owner's recording carries some room (the haze between its words), and a
    cloned voice repeats the room it was given: it sounded like an echo."""
    import numpy as np
    n = 1024 if sr >= 20000 else 512
    hop = n // 4
    win = np.hanning(n + 1)[:-1]
    pad = np.concatenate([np.zeros(n), x, np.zeros(2 * n)])
    count = 1 + (len(pad) - n) // hop
    idx = np.arange(n)[None, :] + hop * np.arange(count)[:, None]
    X = np.fft.rfft(pad[idx] * win, axis=1)
    P = np.abs(X) ** 2 + 1e-12
    d = max(1, int(round(delay * sr / hop)))
    R = np.zeros_like(P)
    R[d:] = np.exp(-13.8155 * (d * hop / sr) / rt60) * P[:-d]
    G = np.sqrt(np.clip(1 - strength * R / P, floor ** 2, 1.0))
    k = np.ones(5) / 5                                    # smooth across frequency; the gain rises at once, falls slowly
    G = np.apply_along_axis(lambda r: np.convolve(r, k, mode="same"), 1, G)
    for t in range(1, count):
        G[t] = np.maximum(G[t], G[t - 1] * 0.6)
    Y = np.fft.irfft(X * G, n=n, axis=1) * win
    out, norm = np.zeros(len(pad)), np.zeros(len(pad))
    for t in range(count):
        out[t * hop:t * hop + n] += Y[t]
        norm[t * hop:t * hop + n] += win ** 2
    return (out / np.maximum(norm, 1e-6))[n:n + len(x)].astype("float32")


def main() -> int:
    jobs_path, reference = sys.argv[1], sys.argv[2]
    with open(jobs_path, encoding="utf-8") as f:
        jobs = json.load(f)
    import torch
    import torchaudio
    from faster_whisper import WhisperModel

    torch.set_num_threads(os.cpu_count() or 4)
    t0 = time.time()
    drying = os.environ.get("CLONE_DRY", "1").strip() != "0"
    if drying:                          # the recording with its room taken out: the clone then speaks in a dry room
        wav, sr_ref = torchaudio.load(reference)
        reference = reference + ".dry.wav"
        torchaudio.save(reference, torch.from_numpy(dry(wav.mean(0).numpy(), sr_ref))[None], sr_ref)
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
    asr = WhisperModel(os.environ.get("CLONE_WHISPER", "base.en"), device="cpu", compute_type="int8")
    exaggeration = float(os.environ.get("CLONE_EXAGGERATION", "0.6"))
    cfg = float(os.environ.get("CLONE_CFG", "0.4"))
    if turbo:     # the sample is already loudness-normalised; Turbo's own normalisation trips a dtype bug
        tts.prepare_conditionals(reference, exaggeration=exaggeration, norm_loudness=False)
    else:
        tts.prepare_conditionals(reference, exaggeration=exaggeration)
    speak = (lambda s: tts.generate(s)) if turbo else (lambda s: tts.generate(s, exaggeration=exaggeration, cfg_weight=cfg))
    print(f"[clone] models ready in {time.time() - t0:.0f}s", flush=True)
    gap = torch.zeros(1, int(tts.sr * 0.18))           # a breath between sentences
    # how closely a line must say its script: a clean take scores ~1.0, one misheard word ~0.95, a garbled take
    # with invented words ~0.85 (measured on real takes)
    need = float(os.environ.get("CLONE_MATCH", "0.92"))
    tries = int(os.environ.get("CLONE_TRIES", "3"))

    def say(text):
        """One take of a line: its audio and the words heard in it (timed from the samples themselves: reading the
        file back would go through PyAV, whose newer versions refuse an option faster-whisper passes)."""
        pieces = []
        for s in sentences(text):
            pieces += [speak(s), gap]
        audio = torch.cat(pieces[:-1], dim=1)
        if drying:
            audio = torch.from_numpy(dry(audio.squeeze(0).numpy(), tts.sr))[None]
        mono16 = torchaudio.functional.resample(audio, tts.sr, 16000).squeeze(0).numpy().astype("float32")
        segs, _ = asr.transcribe(mono16, language="en", word_timestamps=True, beam_size=1,
                                 vad_filter=False, condition_on_previous_text=False)
        words = [[round(w.start, 3), round(w.end, 3), w.word.strip()]
                 for seg in segs for w in (seg.words or []) if w.word.strip()]
        return audio, words

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
        print(f"[clone] {k + 1}/{len(jobs)} {'ok' if job['ok'] else 'FAILED ' + job.get('error', '')} "
              f"match {job.get('match', 0):.2f} ({time.time() - t0:.0f}s)", flush=True)
        with open(jobs_path, "w", encoding="utf-8") as f:   # progress is kept even if the process dies later
            json.dump(jobs, f, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
