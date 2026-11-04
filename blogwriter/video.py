"""Turn a finished report into videos for review: one long video whose pictures carry no sentences (so the
English, Hindi and Telugu narrations all fit the same picture track), an audio track and subtitles per extra
language for YouTube's multi-language audio, one Short per language and a thumbnail. Nothing is posted: the files
are stored and emailed, and a person uploads them.

    python -m blogwriter.video output/<run folder>      # (re)make the videos of a saved run"""
import asyncio
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from typing import Callable, Dict, List, Optional
from urllib.parse import quote, unquote

import requests

from .config import Settings
from .llm import LLMClient, LLMError
from .mailer import send_email
from .research import domain
from .storage import prune_prefix, upload_run
from .web import UA
from .writer import LANGS, strip_unsupported_numbers

VIDEO_APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "video")
VOICES = {"en": "en-US-AndrewNeural", "hi": "hi-IN-MadhurNeural", "te": "te-IN-MohanNeural",
          "kn": "kn-IN-GaganNeural", "ta": "ta-IN-ValluvarNeural"}
FPS = 30
LEAD = 8                  # frames between a card's arrival and its narration (the Board starts audio here)
MP3_BYTES_PER_SECOND = 6000   # edge-tts speaks 24 kHz, 48 kbit/s mono MP3
SHORT_MAX_SECONDS = 58
KEEP_DAYS = 14            # videos are deleted from object storage after this; review and post before then

SCRIPT_PROMPT = """You write the narration of a YouTube explainer video built ONLY from these verified facts.

Story: {title}

Verified facts (number, source, claim, supporting quote):
{facts}

Return JSON:
{{"title": "YouTube title, at most 70 characters, specific, no clickbait words",
  "thumb_text": "2 to 4 punchy words for the thumbnail",
  "description": "2 or 3 plain sentences saying what the video covers",
  "tags": ["6 to 10 search tags"],
  "scenes": [{{"kind": "hook | fact | quote",
              "narration": "what the narrator says",
              "number": "the one headline figure of this scene WITH its unit or symbol, e.g. $115B, 46%, 4.5x, 2028, or empty",
              "subjects": ["2 or 3 exact English Wikipedia article titles to illustrate the scene: the people, places or organisations in it, and one visual thing it is about (e.g. Data center, Optical fiber, Strait of Hormuz)"],
              "facts": [fact numbers used]}}],
  "short": [{{"scene": scene index, "narration": "one or two short sentences"}}]}}

Rules:
- 9 to 13 scenes. Scene 0 is the hook: at most 30 words, open with the most striking verified fact and the question it raises.
- Every other scene: 40 to 70 words, one idea, taken only from the facts listed. Name the source in the sentence ("Reuters reports ...").
- A "quote" scene repeats a supporting quote word for word and says who said it.
- No predictions, opinions or advice. No facts that are not listed. Plain spoken English, short sentences.
- Write figures the way a narrator reads them aloud ("115 billion dollars", "46 percent"); the "number" field keeps the short form.
- Do not end with a call to action; the closing scene is added separately.
- "short": 3 or 4 items for a vertical Short under 50 seconds: the hook first, then the strongest facts, at most 22 words each."""

OUTRO = ("That is the short version. The full report, with {facts} verified facts and every source linked, "
         "is in the description. Subscribe for one researched story every day.")
SHORT_OUTRO = "The full story, with every source, is linked on this channel."


def mp3_seconds(path: str) -> float:
    return os.path.getsize(path) / MP3_BYTES_PER_SECOND


async def _speak(text: str, voice: str, path: str, gate: asyncio.Semaphore) -> List[tuple]:
    """Write the narration to `path`; returns its sentences as (start s, end s, text)."""
    import edge_tts
    async with gate:
        for attempt in range(5):           # the free voice service drops connections now and then
            try:
                sentences, audio = [], bytearray()
                async for chunk in edge_tts.Communicate(text, voice, boundary="SentenceBoundary").stream():
                    if chunk["type"] == "audio":
                        audio += chunk["data"]
                    elif chunk["type"] == "SentenceBoundary":
                        start = chunk["offset"] / 1e7
                        sentences.append((start, start + chunk["duration"] / 1e7, chunk["text"]))
                if not audio:
                    raise RuntimeError("no audio returned")
                with open(path, "wb") as f:
                    f.write(audio)
                return sentences or [(0.0, len(audio) / MP3_BYTES_PER_SECOND, text)]
            except Exception:
                if attempt == 4:
                    raise
                await asyncio.sleep(5 * (attempt + 1))


def speak_all(jobs: List[tuple]) -> List[List[tuple]]:
    """jobs: (text, voice, path). Spoken a few at a time, so the free voice service is not hammered."""
    async def run():
        gate = asyncio.Semaphore(3)
        return await asyncio.gather(*(_speak(t, v, p, gate) for t, v, p in jobs))
    return asyncio.run(run())


COMMONS = "https://commons.wikimedia.org/w/api.php"


def _credit(name: str, ext: dict) -> dict:
    artist = re.sub(r"<[^>]+>", "", ext.get("Artist", {}).get("value", "")).strip()
    return {"file": f"https://commons.wikimedia.org/wiki/File:{quote(name.replace(' ', '_'))}",
            "license": ext.get("LicenseShortName", {}).get("value", "see file page"), "author": artist[:80]}


def _download(url: str, dest: str) -> bool:
    img = requests.get(url, headers=UA, timeout=20)
    if img.ok and img.headers.get("content-type", "").startswith("image/"):
        with open(dest, "wb") as f:
            f.write(img.content)
        return True
    return False


def free_image(subject: str, dest: str) -> Optional[dict]:
    """A freely licensed photo of `subject`, saved to `dest`; returns its credit (author, licence, file page).
    First the lead image of the English Wikipedia article, when that is a Wikimedia Commons file (non-free logos
    and posters live on Wikipedia itself and are skipped); otherwise the best Commons search hit. Commons only
    hosts free files, but most need the credit, which goes into the video description."""
    try:
        r = requests.get("https://en.wikipedia.org/api/rest_v1/page/summary/" + quote(subject.replace(" ", "_")),
                         headers=UA, timeout=15)
        page = r.json() if r.ok else {}
        thumb = (page.get("thumbnail") or {}).get("source", "")
        if page.get("type") != "disambiguation" and "/wikipedia/commons/" in thumb:
            if _download(re.sub(r"/\d+px-", "/960px-", thumb), dest) or _download(thumb, dest):
                name = unquote((page.get("originalimage") or {}).get("source", thumb).split("?")[0].split("/")[-1])
                name = re.sub(r"^\d+px-", "", name)        # a thumbnail's file name carries its width
                meta = requests.get(COMMONS, headers=UA, timeout=15, params={
                    "action": "query", "titles": f"File:{name}", "prop": "imageinfo", "iiprop": "extmetadata",
                    "format": "json"}).json()
                info = next(iter(meta.get("query", {}).get("pages", {}).values()), {}).get("imageinfo", [{}])[0]
                return _credit(name, info.get("extmetadata", {}))
        hits = requests.get(COMMONS, headers=UA, timeout=15, params={
            "action": "query", "generator": "search", "gsrsearch": f"{subject} filetype:bitmap", "gsrnamespace": 6,
            "gsrlimit": 8, "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 960,
            "format": "json"}).json().get("query", {}).get("pages", {})
        terms = {w for w in re.findall(r"[a-z]{3,}", subject.lower()) if w not in ("the", "and", "inc", "ltd")}
        for hit in sorted(hits.values(), key=lambda h: h.get("index", 99)):
            info = (hit.get("imageinfo") or [{}])[0]
            name = hit.get("title", "").removeprefix("File:")
            # search also matches file descriptions; a hit must name the subject, or it is often off-topic
            if (terms & set(re.findall(r"[a-z]{3,}", name.lower()))
                    and info.get("mime") in ("image/jpeg", "image/png") and info.get("width", 0) >= 640
                    and "logo" not in name.lower() and _download(info.get("thumburl") or info["url"], dest)):
                return _credit(name, info.get("extmetadata", {}))
    except (requests.RequestException, ValueError, KeyError, IndexError):
        pass
    return None


def chunks(text: str, start: float, end: float, limit: int) -> List[tuple]:
    """Split one spoken sentence into caption lines of at most `limit` characters, timed by length."""
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > limit:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    total = sum(len(l) for l in lines) or 1
    out, t = [], start
    for line in lines:
        span = (end - start) * len(line) / total
        out.append((t, t + span, line))
        t += span
    return out


def srt(cues: List[tuple]) -> str:
    def ts(s):
        ms = int(round(s * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    return "\n".join(f"{i}\n{ts(a)} --> {ts(b)}\n{t}\n" for i, (a, b, t) in enumerate(cues, 1))


def remotion(args: List[str], log: Callable[[str], None], timeout: int = 3600) -> None:
    """Run the Remotion CLI in the video app (`ffmpeg` runs the ffmpeg that Remotion ships, so the machine
    needs only Node.js)."""
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        raise RuntimeError("Node.js (npx) is not installed")
    extra = [] if args[0] == "ffmpeg" else ["--log=error"]
    r = subprocess.run([npx, "remotion", *args, *extra], cwd=VIDEO_APP, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"remotion {args[0]} failed: {(r.stderr or r.stdout)[-600:]}")


def audio_track(clips: List[str], at: List[float], total: float, dest: str, log: Callable[[str], None]) -> None:
    """One MP3 with each clip starting at its second in `at`, padded to `total` seconds: the narration of one
    language laid on the long video's timeline (its length must match the video for YouTube)."""
    inputs, chains = [], []
    for k, (clip, t) in enumerate(zip(clips, at)):
        inputs += ["-i", clip]
        # "delays=..:all=1" rather than "ms|ms": a "|" would be read as a pipe by the Windows npx shim
        chains.append(f"[{k}:a]aresample=48000,adelay=delays={int(t * 1000)}:all=1[a{k}]")
    mix = "".join(f"[a{k}]" for k in range(len(clips)))
    remotion(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex",
              ";".join(chains) + f";{mix}amix=inputs={len(clips)}:normalize=0,apad[out]", "-map", "[out]",
              "-t", f"{total:.3f}", "-ac", "2", "-b:a", "128k", dest], log, timeout=600)


def render_video(composition: str, props: str, clips: List[str], at: List[float], total: float, dest: str,
                 log: Callable[[str], None]) -> None:
    """Render the pictures silently, then lay the narration on with ffmpeg: rendering with the audio attached
    is three to four times slower in Remotion."""
    silent, voice = dest + ".silent.mp4", dest + ".voice.mp3"
    remotion(["render", "src/index.jsx", composition, silent, f"--props={props}", "--muted", "--crf=20"], log)
    audio_track(clips, at, total, voice, log)
    remotion(["ffmpeg", "-y", "-v", "error", "-i", silent, "-i", voice, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
              "-c:a", "aac", "-b:a", "160k", "-shortest", dest], log, timeout=600)
    for tmp in (silent, voice):
        os.remove(tmp)


class VideoMaker:
    def __init__(self, settings: Settings, llm: Optional[LLMClient] = None, log: Callable[[str], None] = print):
        self.s = settings
        self.llm = llm or LLMClient(settings, log)
        self.log = log

    # ---- script ---------------------------------------------------------------------------------------
    def script(self, title: str, facts: List[dict], sources: List[dict]) -> dict:
        lines = []
        for i, f in enumerate(facts, 1):
            src = sources[int(f["source"]) - 1] if str(f.get("source", "")).isdigit() else {}
            lines.append(f"{i}. [{domain(src.get('url', ''))}] {f['claim']} | \"{f.get('quote', '')[:240]}\"")
        plan = self.llm.complete_json(SCRIPT_PROMPT.format(title=title, facts="\n".join(lines)), max_tokens=5000)
        allowed = " ".join(f"{f['claim']} {f.get('quote', '')}" for f in facts)
        scenes = []
        for sc in plan.get("scenes", [])[:13]:
            narration = strip_unsupported_numbers(str(sc.get("narration", "")).strip(), allowed)
            if not narration:
                continue
            number = str(sc.get("number") or "").strip()[:12]
            digits = re.findall(r"\d[\d,.]*", number)
            if digits and not all(d.rstrip(".").replace(",", "") in allowed.replace(",", "") for d in digits):
                number = ""      # a headline figure must be one of the verified numbers
            if re.fullmatch(r"[\d,.]+", number) and not re.fullmatch(r"(19|20)\d\d", number):
                number = ""      # and must say what it counts ("4.5" alone means nothing; "4.5x" or "$4.5B" does)
            used = [int(n) for n in sc.get("facts", []) if str(n).isdigit() and 0 < int(n) <= len(facts)]
            src = ""
            if used and str(facts[used[0] - 1].get("source", "")).isdigit():
                src = domain(sources[int(facts[used[0] - 1]["source"]) - 1]["url"])
            scenes.append({"kind": sc.get("kind") if sc.get("kind") in ("hook", "fact", "quote") else "fact",
                           "narration": narration, "number": number, "source": src,
                           "subjects": [str(x) for x in sc.get("subjects", [])][:3]})
        if len(scenes) < 4:
            raise LLMError("the video script came back too short")
        scenes.append({"kind": "outro", "narration": OUTRO.format(facts=len(facts)), "number": "", "source": "",
                       "subjects": []})
        short = []
        for item in plan.get("short", [])[:4]:
            idx = item.get("scene")
            text = strip_unsupported_numbers(str(item.get("narration", "")).strip(), allowed)
            if isinstance(idx, int) and 0 <= idx < len(scenes) - 1 and text:
                short.append({"scene": idx, "narration": text})
        short = short or [{"scene": 0, "narration": scenes[0]["narration"]}]
        short.append({"scene": len(scenes) - 1, "narration": SHORT_OUTRO})
        return {"title": str(plan.get("title", title))[:100], "thumb_text": str(plan.get("thumb_text", ""))[:40],
                "description": str(plan.get("description", "")), "tags": [str(t) for t in plan.get("tags", [])][:12],
                "scenes": scenes, "short": short}

    def translate_lines(self, lines: List[str], lang: str) -> Optional[List[str]]:
        """Translate the narration line by line (same count, same order), or None if the model will not."""
        name = LANGS[lang]
        prompt = (f"Translate each string of this JSON array into {name}, for a narrator to read aloud. Keep the "
                  f"order and return a JSON array with exactly {len(lines)} strings. Keep numbers as digits. Write "
                  f"names of people, places and companies in {name} script. Translate faithfully: add or drop "
                  f"nothing.\n\n{json.dumps(lines, ensure_ascii=False)}")
        for _ in range(2):
            try:
                out = self.llm.complete_json(prompt, max_tokens=max(1500, sum(len(l) for l in lines) * 3),
                                             temperature=0.2)
            except LLMError:
                continue
            if isinstance(out, list) and len(out) == len(lines) and all(isinstance(x, str) and x.strip() for x in out):
                return [x.strip() for x in out]
        self.log(f"[video] {name} translation failed; that language is skipped")
        return None

    # ---- assembly ---------------------------------------------------------------------------------------
    def make(self, run_dir: str, email: bool = True) -> Dict[str, str]:
        t0 = time.time()
        with open(os.path.join(run_dir, "research.json"), encoding="utf-8") as f:
            research = json.load(f)
        with open(os.path.join(run_dir, "metadata.json"), encoding="utf-8") as f:
            meta = json.load(f)
        facts, sources = research["facts"], research["sources"]
        title = meta.get("title", meta.get("topic", ""))
        self.log("\n=== Video: script, voices, pictures, render ===")
        plan = self.script(title, facts, sources)
        self.log(f"[video] {len(plan['scenes'])} scenes, short of {len(plan['short'])} beats")

        out = os.path.abspath(os.path.join(run_dir, "video"))
        job = os.path.join(VIDEO_APP, "public", "job")
        shutil.rmtree(job, ignore_errors=True)
        os.makedirs(job)
        os.makedirs(out, exist_ok=True)

        # pictures: free Wikimedia Commons photos of what each scene is about, credited in the description
        credits, pictures = [], {}
        for sc in plan["scenes"]:
            sc["images"] = []
            for subject in sc.pop("subjects"):
                if subject not in pictures:
                    dest = os.path.join(job, f"img{len(pictures)}.jpg")
                    credit = free_image(subject, dest)
                    pictures[subject] = f"job/img{len(pictures)}.jpg" if credit else ""
                    if credit:
                        credits.append({"subject": subject, **credit})
                if pictures[subject]:
                    sc["images"].append(pictures[subject])
        self.log(f"[video] {len(credits)} free photo(s) from Wikimedia Commons")

        # narration in every language: the long-video lines, the Short lines, then the title and description
        langs = [l for l in self.s.video_langs if l in VOICES] or ["en"]
        english = ([sc["narration"] for sc in plan["scenes"]] + [b["narration"] for b in plan["short"]] +
                   [plan["title"], plan["description"]])
        texts = {"en": english}
        for lang in langs:
            if lang != "en":
                done = self.translate_lines(english, lang)
                if done:
                    texts[lang] = done
        n_long, n_short = len(plan["scenes"]), len(plan["short"])
        jobs, keys = [], []
        for lang, lines in texts.items():
            for i, line in enumerate(lines[:n_long + n_short]):
                kind, idx = ("long", i) if i < n_long else ("short", i - n_long)
                jobs.append((line, VOICES[lang], os.path.join(job, f"{lang}_{kind}{idx}.mp3")))
                keys.append((lang, kind, idx))
        spoken = dict(zip(keys, speak_all(jobs)))
        self.log(f"[video] {len(jobs)} narration clips spoken in {', '.join(texts)}")

        # long video: each card stays up for the longest language, so every track fits the same pictures
        frames = []
        for i in range(n_long):
            longest = max(mp3_seconds(os.path.join(job, f"{l}_long{i}.mp3")) for l in texts)
            frames.append(math.ceil(longest * FPS) + LEAD + int(0.6 * FPS))
        starts = [sum(frames[:i]) for i in range(n_long)]
        visuals = [{k: sc[k] for k in ("kind", "number", "source", "images")} for sc in plan["scenes"]]
        files = {}
        for lang in texts:
            props = {"fps": FPS, "thumbText": plan["thumb_text"], "captions": [],
                     "scenes": [{**v, "frames": frames[i], "audio": f"job/{lang}_long{i}.mp3"} for i, v in enumerate(visuals)]}
            path = os.path.join(job, f"long_{lang}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(props, f, ensure_ascii=False)
            cues = []
            for i in range(n_long):
                base = (starts[i] + LEAD) / FPS
                for a, b, text in spoken[(lang, "long", i)]:
                    cues += chunks(text, base + a, base + b, 84)
            with open(os.path.join(out, f"subtitles_{lang}.srt"), "w", encoding="utf-8") as f:
                f.write(srt(cues))
            files[f"subtitles_{lang}.srt"] = "subtitles"
            clips = [os.path.join(job, f"{lang}_long{i}.mp3") for i in range(n_long)]
            at = [(st + LEAD) / FPS for st in starts]
            if lang == "en":
                self.log("[video] rendering the long video (English audio)")
                render_video("Long", path, clips, at, sum(frames) / FPS, os.path.join(out, "long_video_en.mp4"),
                             self.log)
                files["long_video_en.mp4"] = "video"
                remotion(["still", "src/index.jsx", "Thumb", os.path.join(out, "thumbnail.png"), f"--props={path}"],
                         self.log)
                files["thumbnail.png"] = "thumbnail"
            else:     # the same timeline, audio only: an extra audio track for YouTube's multi-language audio
                self.log(f"[video] mixing the {LANGS[lang]} audio track")
                audio_track(clips, at, sum(frames) / FPS, os.path.join(out, f"audio_track_{lang}.mp3"), self.log)
                files[f"audio_track_{lang}.mp3"] = "audio"

        # one Short per language, captions burned in (a Short is posted per language, so its words can show)
        for lang in texts:
            beats = list(range(n_short))
            secs = lambda bs: sum(mp3_seconds(os.path.join(job, f"{lang}_short{b}.mp3")) + 0.6 for b in bs)
            while secs(beats) > SHORT_MAX_SECONDS and len(beats) > 2:
                beats.pop(-2)               # drop the weakest middle beat, keep the hook and the ending
            scenes, captions, t, clips, at = [], [], 0, [], []
            for b in beats:
                clip = os.path.join(job, f"{lang}_short{b}.mp3")
                clips.append(clip)
                at.append((t + LEAD) / FPS)
                n = math.ceil(mp3_seconds(clip) * FPS) + LEAD + int(0.35 * FPS)
                scenes.append({**visuals[plan["short"][b]["scene"]], "frames": n, "audio": f"job/{lang}_short{b}.mp3"})
                for a, z, text in spoken[(lang, "short", b)]:
                    for ca, cz, line in chunks(text, a, z, 38):
                        captions.append({"from": t + LEAD + round(ca * FPS), "to": t + LEAD + round(cz * FPS), "text": line})
                t += n
            path = os.path.join(job, f"short_{lang}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"fps": FPS, "scenes": scenes, "captions": captions, "thumbText": ""}, f, ensure_ascii=False)
            self.log(f"[video] rendering the {LANGS[lang]} Short ({t / FPS:.0f}s)")
            render_video("Short", path, clips, at, t / FPS, os.path.join(out, f"short_{lang}.mp4"), self.log)
            files[f"short_{lang}.mp4"] = "short"

        product = (meta.get("gumroad") or {}).get("url", "")
        with open(os.path.join(out, "posting_guide.txt"), "w", encoding="utf-8") as f:
            f.write(posting_guide(plan, texts, n_long + n_short, credits, product, meta))
        with open(os.path.join(out, "video_script.json"), "w", encoding="utf-8") as f:
            json.dump({"plan": plan, "texts": texts, "credits": credits}, f, indent=2, ensure_ascii=False)
        shutil.rmtree(job, ignore_errors=True)
        self.log(f"[video] done in {time.time() - t0:.0f}s: {', '.join(files)}")
        self.deliver(run_dir, out, files, plan, email)
        return {name: os.path.join(out, name) for name in files}

    def deliver(self, run_dir: str, out: str, files: Dict[str, str], plan: dict, email: bool) -> None:
        """Store the videos (deleted after KEEP_DAYS) and email the links plus the small files. Never posts."""
        names = list(files) + ["posting_guide.txt"]
        prune_prefix(self.s, "videos/", KEEP_DAYS, self.log)
        links = upload_run(self.s, out, names, self.log,
                           prefix=f"videos/{os.path.basename(os.path.normpath(run_dir))}")
        if not email:
            return
        listing = "\n".join(f"  {n}: {links[n]}" for n in names if n in links) or f"  saved in {out}"
        body = (f"Your videos for \"{plan['title']}\" are ready to review. Nothing has been posted.\n\n"
                f"DOWNLOAD (links work for 7 days; the files are deleted from storage after {KEEP_DAYS} days):\n"
                f"{listing}\n\nHOW TO POST: see the attached posting_guide.txt (titles, descriptions and tags in "
                f"every language, photo credits, and the steps to add the extra audio tracks in YouTube Studio).\n")
        small = [os.path.join(out, n) for n in names if n.endswith((".txt", ".srt", ".png"))]
        send_email(self.s, f"[Video] {plan['title'][:120]}", body, small, self.log)


def posting_guide(plan: dict, texts: Dict[str, List[str]], n_lines: int, credits: List[dict], product: str,
                  meta: dict) -> str:
    credit_lines = "\n".join(f"- {c['subject']}: {c['author'] or 'see file page'}, {c['license']}, {c['file']}"
                             for c in credits) or "- none (no photos used)"
    report = f"Full report: {product}\n" if product else ""
    parts = [f"POSTING GUIDE - {plan['title']}\n", "Nothing was posted automatically. Review the videos first.\n",
             "LONG VIDEO (YouTube)",
             "1. YouTube Studio > Create > Upload videos > long_video_en.mp4. Use the English title and description "
             "below and thumbnail.png. Upload subtitles_en.srt under Subtitles.",
             "2. After it is processed: Studio > Subtitles > Add language (Hindi, Telugu, ...). For each language: "
             "Audio > Add > upload audio_track_<lang>.mp3; Subtitles > Upload file > subtitles_<lang>.srt; "
             "Title & description > add the translated text below.",
             "3. Viewers then hear the video in their own language from one video and one view count.\n",
             "SHORTS: upload short_<lang>.mp4 as separate Shorts with that language's title.\n"]
    for lang, lines in texts.items():
        title, desc = lines[n_lines], lines[n_lines + 1]
        parts.append(f"===== {LANGS[lang].upper()} =====\nTitle: {title}\nDescription:\n{desc}\n\n{report}"
                     f"Sources: {meta.get('sources', '?')} sources, {meta.get('verified_facts', '?')} verified facts.\n"
                     f"Photo credits (required by the licences):\n{credit_lines}\n")
    parts.append("Tags: " + ", ".join(plan["tags"]))
    return "\n".join(parts) + "\n"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python -m blogwriter.video output/<run folder> [--no-email]")
    VideoMaker(Settings.from_env()).make(sys.argv[1], email="--no-email" not in sys.argv)
