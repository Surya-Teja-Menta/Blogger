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


def main() -> int:
    jobs_path, reference = sys.argv[1], sys.argv[2]
    with open(jobs_path, encoding="utf-8") as f:
        jobs = json.load(f)
    import torch
    import torchaudio
    from faster_whisper import WhisperModel

    torch.set_num_threads(os.cpu_count() or 4)
    t0 = time.time()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # Turbo (the default) is the smaller, much faster model: it ignores the expressiveness settings
    turbo = os.environ.get("CLONE_MODEL", "turbo").strip().lower() != "standard"
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
    for k, job in enumerate(jobs):
        job["ok"] = False
        try:
            pieces = []
            for s in sentences(job["text"]):
                wav = speak(s)
                pieces += [wav, gap]
            audio = torch.cat(pieces[:-1], dim=1)
            torchaudio.save(job["out"], audio, tts.sr)
            # the words are timed from the audio itself, handed over as 16 kHz samples (reading the file back would
            # go through PyAV, whose newer versions refuse an option faster-whisper passes)
            mono16 = torchaudio.functional.resample(audio, tts.sr, 16000).squeeze(0).numpy().astype("float32")
            segs, _ = asr.transcribe(mono16, language="en", word_timestamps=True, beam_size=1,
                                     vad_filter=False, condition_on_previous_text=False)
            job["words"] = [[round(w.start, 3), round(w.end, 3), w.word.strip()]
                            for seg in segs for w in (seg.words or []) if w.word.strip()]
            job["ok"] = bool(job["words"])
        except Exception as exc:                        # one line must not sink the rest
            job["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        print(f"[clone] {k + 1}/{len(jobs)} {'ok' if job['ok'] else 'FAILED ' + job.get('error', '')} "
              f"({time.time() - t0:.0f}s)", flush=True)
        with open(jobs_path, "w", encoding="utf-8") as f:   # progress is kept even if the process dies later
            json.dump(jobs, f, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
