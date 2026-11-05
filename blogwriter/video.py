"""Turn a finished report into videos for review: a documentary-style long video (English picture track, with
the Hindi and Telugu narrations as extra audio tracks for YouTube's multi-language audio), one Short per
language with on-screen text and captions in that language, subtitles and a thumbnail. Nothing is posted: the
files are stored and emailed, and a person reviews and uploads them.

    python -m blogwriter.video output/<run folder> [--no-email]     # (re)make the videos of a saved run"""
import asyncio
import hashlib
import unicodedata
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List, Optional
from urllib.parse import quote, unquote

import requests

from . import sound
from .config import Settings
from .critic import review, summary
from .footage import CLIP_SECONDS, find_clip, photo_fits
from .llm import LLMClient, LLMError
from .mailer import send_email
from . import design, graphics, mathexpr
from .research import domain
from .storage import prune_prefix, upload_run
from .web import UA
from .writer import LANGS, strip_unsupported_numbers

VIDEO_APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "video")
VOICES = {"en": "en-US-AndrewNeural", "hi": "hi-IN-MadhurNeural", "te": "te-IN-MohanNeural",
          "kn": "kn-IN-GaganNeural", "ta": "ta-IN-ValluvarNeural"}
FPS = 30
TRANSITION = 15           # frames two scenes overlap; must equal TRANSITION in video/src/theme.js
LEAD = 6                  # frames after a shot starts before its narration begins
GAP = 4                   # frames of breath after the narration (clips are trimmed to the words, see tighten)
MP3_BYTES_PER_SECOND = 6000   # edge-tts speaks 24 kHz, 48 kbit/s mono MP3
SHORT_MAX_SECONDS = 58
MAX_TEMPO = 1.3           # a dubbed track may be sped up this much (pitch kept) to fit the English picture
KEEP_DAYS = 14            # videos are deleted from object storage after this; review and post before then
KINDS = ("hook", "photo", "stat", "compare", "bars", "line", "donut", "kpis", "timeline", "steps", "map", "list",
         "quote", "equation", "plot", "graph", "derive")
MATH_KINDS = ("equation", "plot", "graph", "derive")      # lesson shots drawn from maths, not from facts or photos
PLOTS = ("scatter", "fit", "residuals", "squares", "descent")
FIGURE_KINDS = {"compare": (2, 3), "bars": (3, 6), "line": (3, 8), "donut": (2, 4), "kpis": (3, 4)}  # items (min, max)
CHART_KINDS = ("stat", "hook", "compare", "bars", "line", "donut", "kpis")      # a hit sound lands under these
ORDINALS = ("ONE", "TWO", "THREE", "FOUR", "FIVE")
ROMAN = ("I", "II", "III", "IV", "V")
# how a video numbers its parts; chosen per video so the stings differ too
KICKERS = (lambda k: f"PART {ORDINALS[k]}", lambda k: f"{k + 1:02d}", lambda k: f"CHAPTER {ROMAN[k]}",
           lambda k: f"{ROMAN[k]}.", lambda k: f"STEP {k + 1}")
VIDEO_STYLES = ("news", "story", "education", "concept")
# the voice of each style; the structure of every video is planned fresh by the model (BRIEF_PROMPT)
STYLES = {
    "news": "a documentary news channel (Vox, Johnny Harris, ColdFusion): calm authority, real tension, every "
            "claim sourced",
    "story": "a narrative storytelling channel (Lemmino, Real Stories, Barely Sociable): a true story told in "
             "scenes, with people, stakes, suspense and a turn, never a list of facts",
    "education": "an educational channel (3Blue1Brown, StatQuest, Veritasium): builds real understanding step by "
                 "step, intuition first, then precision, never dumbed down",
    "concept": "a concept explainer channel (Kurzgesagt, Wendover, Vox explainers): one big idea made vivid with "
               "analogies and visual metaphors",
}

BRIEF_PROMPT = """You are the showrunner of a YouTube channel. Before anything is written, plan ONE video on this
subject so it feels made for it: no stock formula, no fixed "three acts". Decide the shape this particular subject
needs (for example: a mystery told clue by clue; a problem, the failed fixes and the breakthrough; an everyday
question, the model, the maths, the uses; a day-by-day countdown; a myth and its debunking).

Subject: {title}
Style: {style}
Facts available (short):
{facts}

Reply with JSON:
{{"style": one of {styles} ({style_rule}),
  "structure": "one sentence naming the shape you chose and why it suits this subject",
  "acts": [{{"title": "2 to 4 words", "job": "what this part does for the viewer"}}] (2 to 5 parts),
  "opening": "how the first 10 seconds hook the viewer",
  "ending": "how the last shot lands (the answer, a twist, a callback to the opening)",
  "tone": "3 to 5 words",
  "mood": "4 to 6 words about how the video should look and feel",
  "minutes": a number from 2 to 5,
  "maths": true if the subject has formulas worth teaching, else false}}"""

SHAPE = """You are the head writer of {persona}. Write the script and direct the visuals of a {minutes} minute
video built ONLY from these verified facts.

Subject: {title}

Verified facts (number, [source], claim | supporting quote):
{facts}

THE PLAN FOR THIS VIDEO (follow it; it was made for this subject)
- Shape: {structure}
- Parts, in order: {acts}
- Opening: {opening} At most 28 words. No greeting, no "in this video".
- Ending: {ending} This is the last shot before the outro.
- Tone: {tone}
- Teach or tell one idea per shot and build each shot on the one before. Analogies are welcome, but every number
  and every factual claim must come from the facts.
- Show any process as a "steps" shot and any set of numbers as a chart."""

MATHS_RULES = r"""
- The MATHS INTUITION is the heart of this video: at least half of all shots are maths shots ("equation", "graph",
  "derive", "plot"), with at least 3 "equation" or "derive" shots and at least 2 "graph" shots. Always picture
  first, then the formula that says the same thing. Use "graph" to SHOW behaviour: sweep a parameter to show what
  it does, a tangent for rates and gradients, the area for integrals, totals and probabilities. Use "derive" for
  algebra a viewer should follow step by step, each step with a note on what changed. For fitting a
  line, teach in this order: the data (scatter), the idea of a line through it (fit), the model formula, each
  point's error (residuals), why we square the errors (squares), the cost formula (e.g.
  J = \frac{1}{n}\sum (y_i - \hat{y}_i)^2), how the cost is minimised (descent), and the update rule (e.g.
  w \leftarrow w - \alpha \frac{\partial J}{\partial w}).
- Narration of a maths shot (20 to 40 words) describes what the viewer is watching move ("watch the line tilt
  until...") and names each symbol in the order it appears, in plain words ("w, the slope, says how steep the
  line is"). Never use a technical word (affine, conditional mean, regressor) without saying what it means in the
  same sentence. Standard formulas and their symbols are allowed even if not in the facts."""

SCRIPT_PROMPT = """{shape}
- Mark the first shot of every act after the opening with "act": a 2 to 4 word act title ("The deal", "Why now");
  every other shot has "act": "". The title flashes on screen while the narration runs on, so do NOT write
  "Part one" lines and do not make separate title shots.
- {shots} scenes ("shots") in total. One shot is ONE spoken sentence of 8 to 24 words, 3 to 8 seconds on
  screen: the picture changes with every sentence, which is what makes it feel like video and not slides.
  End each act so it leads into the next ("But that was only half of it.").
- The narration is read aloud by a voice: write maths in words ("y hat equals w times x plus b"), never LaTeX
  or symbols in the narration.
- Spoken style: short sentences, plain words, contrast and stakes. Name sources naturally ("Reuters reports").
  No predictions, opinions, advice or facts that are not listed. Write figures as they are said aloud
  ("115 billion dollars"); on-screen fields keep the short form ("$115B").
- "outro": 1 or 2 closing sentences in this video's own voice that say the full report, with every source,
  is linked in the description, and invite the viewer to subscribe. Not a slogan; make it fit the story.

VISUALS: pick a "kind" per shot, never the same kind twice in a row, at least 7 different kinds overall.
About a third of shots are "photo" shots; the rest are graphics. Whenever the facts hold several comparable
numbers, show them as a chart (bars, line, donut, kpis, compare). Never invent or estimate a number to fill a
chart: every figure on screen must be in the facts, written the same way.
- "hook":     photo background + headline (+ optional number). Only scene 0.
- "photo":    full-screen photo of the people, company or place, with a headline.
- "stat":     one verified figure, huge.        Needs "number" (with unit) and "label" (what it counts, max 6 words).
- "compare":  2 or 3 figures of the same unit as horizontal bars.
              Needs "items": [{{"label": max 3 words, "display": "$115B"}}].
- "bars":     3 to 6 figures of the same unit as a column chart. Needs "items" like compare.
- "line":     a trend: 3 to 8 values of one measure in time order. Needs "items": [{{"label": "2023" or "Q2 2025",
              "display": "$5.9B"}}].
- "donut":    shares of a whole: 2 to 4 percentages adding up to 100 or less.
              Needs "items": [{{"label": max 3 words, "display": "46%"}}].
- "kpis":     3 or 4 headline figures of different kinds side by side.
              Needs "items": [{{"label": max 4 words, "display": "$1B"}}].
- "steps":    a process or chain of cause and effect, 3 to 5 steps in order.
              Needs "items": [{{"label": max 5 words}}].
- "timeline": 3 to 5 dated events.               Needs "events": [{{"date": "2024" or "Mar 2025", "label": max 4 words}}].
- "map":      countries involved.                Needs "countries": [English country names, 1 to 3].
- "list":     3 parallel points.                 Needs "items": [{{"label": max 6 words}}] (exactly 3).
- "quote":    a supporting quote, word for word. Needs "quote" (max 25 words, copied exactly) and "speaker".
- "equation": (lessons) a formula built piece by piece. Needs "parts": [{{"tex": KaTeX LaTeX of one piece,
              "label": plain name of that symbol, max 3 words, or ""}}], 2 to 8 pieces that read as one formula
              left to right, e.g. [{{"tex": "\\\\hat{{y}}", "label": "prediction"}}, {{"tex": "=", "label": ""}},
              {{"tex": "w", "label": "slope"}}, {{"tex": "x", "label": "input"}}, {{"tex": "+", "label": ""}},
              {{"tex": "b", "label": "intercept"}}]. Label at most 4 pieces; keep \\\\frac and \\\\sum inside one piece.
- "graph":    (lessons) an animated graph of 1 to 3 functions of x. Needs "graph": {{"curves": [{{"fn": the function
              in plain maths using only x, a, numbers, + - * / ^, brackets, sin cos tan exp log sqrt abs, pi, e
              (always write * for multiplication: "a*x^2", "exp(-x^2/2)"), "tex": its KaTeX label, e.g.
              "y = ax^2"}}], "x": [xmin, xmax], "param": {{"from": 0.5, "to": 3}} (only if a curve uses a: a then
              slides between these values while the narration says what it does), "mark": "tangent" (a point slides
              along the first curve with its tangent and slope), "area" (the area under it fills in, with its value),
              "point" (a point traces it with its coordinates) or ""}}; plus "xlabel" and "ylabel" (max 3 words).
- "derive":   (lessons) a working written out line by line. Needs "steps": [{{"tex": one full KaTeX line,
              "note": what this step did, max 5 words, e.g. "take the derivative"}}], 2 to 5 steps.
- "plot":     (lessons on fitting data) an animated plot of sample data. Needs "plot": one of "scatter" (the data
              points), "fit" (a line turning into the best fit), "residuals" (each point's error to the line),
              "squares" (each error drawn as a square, their total shrinking as the line improves), "descent"
              (gradient descent: a ball stepping down the error curve while the line improves); "xlabel" and
              "ylabel" (axis names, max 3 words, e.g. "House size", "Price").
Every scene also has: "headline" (max 7 punchy words, NOT a copy of the narration), "kicker" (max 3 words,
e.g. "THE DEAL"), "highlight" (1 or 2 words of the headline to mark), "subjects" (2 or 3 exact English Wikipedia
article titles to illustrate it: organisations, places, products or buildings, plus one visual thing like
"Data center"; never people, whose photos cannot be checked),
"footage" (for hook, photo, stat and list shots: a 2 to 4 word search phrase for real stock footage that fits
behind the sentence, concrete and filmable, e.g. "server racks", "container ship", "stock exchange floor",
"rocket launch"; empty for the other kinds), "act" (see above), and "facts" (the fact numbers used).

Return JSON:
{{"title": "YouTube title, max 70 characters, specific and curious, no clickbait words or ALL CAPS",
  "thumb_text": "3 or 4 words for the thumbnail", "thumb_highlight": "1 word of thumb_text",
  "description": "2 or 3 plain sentences on what the video covers",
  "tags": ["8 to 12 search tags"],
  "scenes": [{{"kind": "...", "narration": "...", "headline": "...", "kicker": "...", "highlight": "...",
              "number": "", "label": "", "items": [], "events": [], "countries": [], "quote": "", "speaker": "",
              "subjects": [], "footage": "", "act": "", "facts": []}}],
  "outro": "...", "short": [{{"scene": scene index, "narration": "..."}}]}}

"short": 4 or 5 beats for a vertical Short under 50 seconds, reusing scenes' visuals by index. Beat 1 stops the
scroll in at most 14 words; then the strongest facts, at most 20 words each. Charts make strong Short beats."""

OUTRO = ("That's the short version. The full report has {facts} verified facts, and every source is linked. "
         "It's in the description. And if you want one story like this, researched properly, every day, subscribe.")
SHORT_OUTRO = "Full story, with every source, on the channel."
ATLAS = os.path.join(VIDEO_APP, "node_modules", "world-atlas", "countries-50m.json")
COUNTRY_ALIASES = {"united states": "United States of America", "usa": "United States of America",
                   "us": "United States of America", "uk": "United Kingdom", "britain": "United Kingdom",
                   "great britain": "United Kingdom", "uae": "United Arab Emirates", "czech republic": "Czechia",
                   "south korea": "South Korea", "north korea": "North Korea", "drc": "Dem. Rep. Congo",
                   "democratic republic of the congo": "Dem. Rep. Congo", "ivory coast": "Côte d'Ivoire"}


def mp3_seconds(path: str) -> float:
    return os.path.getsize(path) / MP3_BYTES_PER_SECOND


async def _speak(text: str, voice: str, path: str, gate: asyncio.Semaphore) -> List[tuple]:
    """Write the narration to `path`; returns its words as (start s, end s, word), so captions and on-screen
    reveals can land on the exact spoken word."""
    import edge_tts
    async with gate:
        for attempt in range(5):           # the free voice service drops connections now and then
            try:
                sentences, audio = [], bytearray()
                stream = edge_tts.Communicate(text, voice, rate="+6%" if voice.startswith("en") else "+0%",
                                              boundary="WordBoundary").stream()
                async for chunk in stream:
                    if chunk["type"] == "audio":
                        audio += chunk["data"]
                    elif chunk["type"] == "WordBoundary":
                        start = chunk["offset"] / 1e7
                        sentences.append((start, start + chunk["duration"] / 1e7, chunk["text"]))
                if not audio:
                    raise RuntimeError("no audio returned")
                with open(path, "wb") as f:
                    f.write(audio)
                return sentences or [(0.0, len(audio) / MP3_BYTES_PER_SECOND, text)]
            except Exception as exc:
                if attempt == 4:                # one unspeakable line must not sink the whole video
                    print(f"[video] no voice for {text[:60]!r}: {type(exc).__name__}")
                    return None
                await asyncio.sleep(5 * (attempt + 1))


def speak_all(jobs: List[tuple]) -> List[List[tuple]]:
    """jobs: (text, voice, path). Spoken a few at a time, so the free voice service is not hammered."""
    async def run():
        gate = asyncio.Semaphore(3)
        return await asyncio.gather(*(_speak(t, v, p, gate) for t, v, p in jobs))
    return asyncio.run(run())


def tighten(path: str, words: List[tuple]) -> List[tuple]:
    """Cut the voice service's silence before the first word and after the last, so shots follow each other at
    the pace of speech; returns the word timings moved to match. Re-encoded at the service's own bitrate, so
    mp3_seconds still holds."""
    if not words:
        return words
    a = max(0.0, words[0][0] - 0.04)
    b = words[-1][1] + 0.12
    tmp = path + ".tmp.mp3"
    try:
        ffmpeg(["-ss", f"{a:.3f}", "-i", path, "-t", f"{b - a:.3f}", "-ac", "1", "-ar", "24000", "-b:a", "48k", tmp])
        os.replace(tmp, path)
    except RuntimeError:
        return words
    return [(s - a, e - a, w) for s, e, w in words]


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
            if _download(re.sub(r"/\d+px-", "/1280px-", thumb), dest) or _download(thumb, dest):
                name = unquote((page.get("originalimage") or {}).get("source", thumb).split("?")[0].split("/")[-1])
                name = re.sub(r"^\d+px-", "", name)        # a thumbnail's file name carries its width
                meta = requests.get(COMMONS, headers=UA, timeout=15, params={
                    "action": "query", "titles": f"File:{name}", "prop": "imageinfo", "iiprop": "extmetadata",
                    "format": "json"}).json()
                info = next(iter(meta.get("query", {}).get("pages", {}).values()), {}).get("imageinfo", [{}])[0]
                return _credit(name, info.get("extmetadata", {}))
        hits = requests.get(COMMONS, headers=UA, timeout=15, params={
            "action": "query", "generator": "search", "gsrsearch": f"{subject} filetype:bitmap", "gsrnamespace": 6,
            "gsrlimit": 8, "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1280,
            "format": "json"}).json().get("query", {}).get("pages", {})
        terms = {w for w in re.findall(r"[a-z]{3,}", subject.lower()) if w not in ("the", "and", "inc", "ltd")}
        for hit in sorted(hits.values(), key=lambda h: h.get("index", 99)):
            info = (hit.get("imageinfo") or [{}])[0]
            name = hit.get("title", "").removeprefix("File:")
            # search also matches file descriptions; a hit must name the subject, or it is often off-topic
            if (terms & set(re.findall(r"[a-z]{3,}", name.lower()))
                    and info.get("mime") in ("image/jpeg", "image/png") and info.get("width", 0) >= 800
                    and "logo" not in name.lower() and _download(info.get("thumburl") or info["url"], dest)):
                return _credit(name, info.get("extmetadata", {}))
        # Openverse: openly licensed photos from Flickr and other collections, no key needed
        found = requests.get("https://api.openverse.org/v1/images/", headers=UA, timeout=15, params={
            "q": subject, "license_type": "commercial,modification", "page_size": 10, "mature": "false"}).json()
        for hit in found.get("results", []):
            if ((hit.get("width") or 0) >= 1000 and terms & set(re.findall(r"[a-z]{3,}", (hit.get("title") or "").lower()))
                    and _download(hit.get("url", ""), dest)):
                lic = str(hit.get("license", "")).upper()
                return {"file": hit.get("foreign_landing_url", ""), "author": str(hit.get("creator") or "")[:80],
                        "license": "Public domain" if lic in ("PDM", "CC0") else f"CC {lic} {hit.get('license_version', '')}".strip()}
    except (requests.RequestException, ValueError, KeyError, IndexError):
        pass
    return None


def word_lines(words: List[tuple], offset: float, limit: int) -> List[tuple]:
    """Caption lines from spoken words: at most `limit` characters, also broken at a pause, each timed from its
    first word's start to its last word's end."""
    lines, cur = [], []
    for w in words:
        pause = cur and w[0] - cur[-1][1] > 0.35
        if cur and (pause or len(" ".join(x[2] for x in cur + [w])) > limit):
            lines.append(cur)
            cur = []
        cur.append(w)
    if cur:
        lines.append(cur)
    return [(offset + l[0][0], offset + l[-1][1], " ".join(x[2] for x in l)) for l in lines]


def cue(words: List[tuple], target: str) -> Optional[int]:
    """Frames from the narration's start to the first spoken word that carries `target` (a figure's digits or a
    highlighted word), or None."""
    keys = re.findall(r"\d+", target) or [w.lower() for w in re.findall(r"[^\W\d_]{3,}", target)]
    for start, _, word in words:
        low = word.lower()
        if keys and any(k in low for k in keys[:1]):
            return LEAD + round(start * FPS)
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
    if args[0] in ("render", "still"):
        extra.append("--timeout=120000")
    for attempt in range(2):             # the headless browser occasionally fails to start; once more then
        r = subprocess.run([npx, "remotion", *args, *extra], cwd=VIDEO_APP, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        if r.returncode == 0:
            return
        log(f"[video] remotion {args[0]} failed (attempt {attempt + 1}): {(r.stderr or r.stdout)[-200:].strip()}")
    if r.returncode != 0:
        raise RuntimeError(f"remotion {args[0]} failed: {(r.stderr or r.stdout)[-600:]}")


def ffmpeg(args: List[str], timeout: int = 900) -> None:
    """A full ffmpeg (from the imageio-ffmpeg wheel): the one Remotion ships lacks the audio filters used here."""
    import imageio_ffmpeg
    r = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-y", "-v", "error", *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {r.stderr[-600:]}")


def timeline(seconds: List[float], kinds: List[str]) -> tuple:
    """Scene lengths in frames and the frame each scene starts at. Scenes overlap by TRANSITION frames, so
    each one lasts its narration plus the lead-in, a breath and the overlap; a silent chapter card gets 2.5 s."""
    frames = [max(75 if k == "chapter" else 60, math.ceil(s * FPS) + LEAD + GAP + TRANSITION)
              for s, k in zip(seconds, kinds)]
    starts = [sum(frames[:i]) - i * TRANSITION for i in range(len(frames))]
    return frames, starts, sum(frames) - TRANSITION * (len(frames) - 1)


def master(clips: List[str], starts: List[int], kinds: List[str], total: int, assets: dict, dest: str,
           log: Callable[[str], None], tempos: Optional[List[float]] = None) -> None:
    """The finished soundtrack of one language: narration (cleaned up), music ducked under it, a whoosh on
    every transition and a hit under every figure, mastered to YouTube loudness."""
    voice_at = [(st + LEAD) / FPS for st in starts]
    whoosh_at = [st / FPS - 0.25 for st in starts[1:]]
    hit_at = [(st + 14) / FPS for st, k in zip(starts, kinds) if k in CHART_KINDS]
    graph, _ = sound.mix_filter(voice_at, whoosh_at, hit_at, tempos)
    inputs = sum((["-i", c] for c in clips), []) + ["-i", assets["music"], "-i", assets["whoosh"], "-i", assets["hit"]]
    ffmpeg([*inputs, "-filter_complex", graph, "-map", "[out]", "-t", f"{total / FPS:.3f}", "-ac", "2",
            "-b:a", "192k", dest])


def render(composition: str, props: str, soundtrack: str, dest: str, log: Callable[[str], None]) -> None:
    """Render the pictures silently, then put the soundtrack on: rendering with audio attached is three to
    four times slower in Remotion."""
    silent = dest + ".silent.mp4"
    remotion(["render", "src/index.jsx", composition, silent, f"--props={props}", "--muted", "--crf=19",
              "--x264-preset=medium"], log)
    ffmpeg(["-i", silent, "-i", soundtrack, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
            "-b:a", "192k", "-shortest", "-movflags", "+faststart", dest])
    os.remove(silent)


def country_names() -> Dict[str, str]:
    try:
        with open(ATLAS, encoding="utf-8") as f:
            atlas = json.load(f)
        return {g["properties"]["name"].lower(): g["properties"]["name"]
                for g in atlas["objects"]["countries"]["geometries"]}
    except (OSError, ValueError, KeyError):
        return {}


def _verified(text: str, allowed: str) -> bool:
    """Every number in `text` appears in the verified material."""
    flat = allowed.replace(",", "")
    return all(d.rstrip(".").replace(",", "") in flat for d in re.findall(r"\d[\d,.]*", text or ""))


def _figure(text: str, allowed: str) -> str:
    """A short on-screen figure, kept only if verified and if it says what it counts ($115B, 46%, 4.5x, 2028)."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()           #   and friends become plain spaces
    for word, short in (("trillion", "T"), ("billion", "B"), ("million", "M"), ("thousand", "K")):
        text = re.sub(rf"(\d)\s*{word}\b", rf"\1{short}", text, flags=re.I)
    if len(text) > 12:                 # cutting would leave "241.62 billi" on screen
        return ""
    if not re.search(r"\d", text) or not _verified(text, allowed):
        return ""
    if re.fullmatch(r"[\d,.]+", text) and not re.fullmatch(r"(19|20)\d\d", text):
        return ""
    return text


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", (text or "").lower())).strip()


def check_scene(sc: dict, allowed: str, quotes: str, countries: Dict[str, str]) -> dict:
    """Keep what the scene's visual needs and is verified; a visual whose data does not hold up becomes a photo."""
    words = lambda v, n: " ".join(str(v or "").split()[:n])
    kind = sc.get("kind") if sc.get("kind") in KINDS else "photo"
    out = {"kind": kind, "headline": words(sc.get("headline"), 8), "kicker": words(sc.get("kicker"), 3).upper(),
           "number": "", "label": "", "items": [], "events": [], "countries": [], "quote": "", "speaker": ""}
    out["highlight"] = " ".join(w for w in str(sc.get("highlight", "")).split() if w.lower() in out["headline"].lower())
    if kind in ("stat", "hook", "photo"):
        out["number"] = _figure(sc.get("number"), allowed)
        out["label"] = words(sc.get("label"), 7)
        if kind == "stat" and not out["number"]:
            out["kind"] = "photo"
    elif kind in FIGURE_KINDS:
        items = []
        for it in sc.get("items") or []:
            if not isinstance(it, dict):
                continue
            shown = _figure(it.get("display"), allowed)
            m = re.search(r"\d[\d,]*\.?\d*", shown)
            label = words(it.get("label"), 4)
            if shown and m and label and _verified(label, allowed):
                items.append({"label": label, "display": shown, "value": float(m.group().replace(",", ""))})
        out["kind"], out["items"] = chart_kind(kind, items)
    elif kind == "timeline":
        events = [{"date": str(e.get("date", ""))[:12], "label": words(e.get("label"), 5)}
                  for e in sc.get("events") or [] if isinstance(e, dict)]
        out["events"] = [e for e in events if e["date"] and re.search(r"\d", e["date"]) and _verified(e["date"], allowed)
                         and e["label"]][:5]
        if len(out["events"]) < 3:
            out["kind"] = "photo"
    elif kind == "map":
        names = []
        for c in sc.get("countries") or []:
            key = str(c).strip().lower()
            name = countries.get(key) or countries.get(COUNTRY_ALIASES.get(key, "").lower())
            if name and name not in names:
                names.append(name)
        out["countries"] = names[:3]
        if not names:
            out["kind"] = "photo"
    elif kind == "steps":
        out["items"] = [{"label": words((it or {}).get("label") if isinstance(it, dict) else it, 6)}
                        for it in sc.get("items") or []][:5]
        if len(out["items"]) < 3 or not all(i["label"] and _verified(i["label"], allowed) for i in out["items"]):
            out["kind"], out["items"] = "photo", []
    elif kind == "list":
        out["items"] = [{"label": words((it or {}).get("label") if isinstance(it, dict) else it, 7)}
                        for it in sc.get("items") or []][:3]
        if len(out["items"]) < 3 or not all(i["label"] and _verified(i["label"], allowed) for i in out["items"]):
            out["kind"] = "photo"
    elif kind == "quote":
        q = str(sc.get("quote", "")).strip().strip('"“”')
        if q and len(_norm(q)) > 12 and _norm(q) in quotes:
            out["quote"], out["speaker"] = " ".join(q.split()[:30]), words(sc.get("speaker"), 5)
        else:
            out["kind"] = "photo"
    elif kind == "equation":
        parts = []
        for p in sc.get("parts") or []:
            p = p if isinstance(p, dict) else {"tex": p, "label": ""}     # a piece sent as plain TeX
            tex = fix_tex(str(p.get("tex", "")).strip())
            if not tex or len(tex) > 80 or re.search(r"\\(href|url|includegraphics|html)", tex):
                parts = []
                break
            parts.append({"tex": tex, "label": words(p.get("label"), 3)})
        if parts and not tex_complete(" ".join(p["tex"] for p in parts)):
            parts = []
        out["parts"] = parts[:8]
        if not out["parts"]:              # one piece is fine: the whole formula, named once
            out["kind"] = "photo"
    elif kind == "plot":
        out["plot"] = sc.get("plot") if sc.get("plot") in PLOTS else "fit"
        out["xlabel"], out["ylabel"] = words(sc.get("xlabel"), 3) or "x", words(sc.get("ylabel"), 3) or "y"
    elif kind == "graph":
        graph = mathexpr.check_graph(sc.get("graph"))
        if graph:
            out["graph"] = graph
            out["xlabel"], out["ylabel"] = words(sc.get("xlabel"), 3) or "x", words(sc.get("ylabel"), 3) or "y"
        else:
            out["kind"] = "photo"
    elif kind == "derive":
        steps = []
        for st in (sc.get("steps") or [])[:5]:
            st = st if isinstance(st, dict) else {"tex": st, "note": ""}
            tex = fix_tex(str(st.get("tex", "")).strip())
            if tex and len(tex) <= 120 and tex_complete(tex) and \
                    not re.search(r"\\(href|url|includegraphics|html)", tex):
                steps.append({"tex": tex, "note": words(st.get("note"), 5)})
        out["steps"] = steps
        if len(steps) == 1:               # a one-line working is just a formula
            out["kind"], out["parts"] = "equation", [{"tex": steps[0]["tex"], "label": steps[0]["note"]}]
            del out["steps"]
        elif not steps:
            out["kind"] = "photo"
    elif kind == "chapter" and not out["headline"]:
        out["kind"] = "photo"
    if not _verified(out["headline"], allowed):
        out["headline"] = re.sub(r"\S*\d\S*", "", out["headline"]).strip()   # no unverified figure in a headline
    return out


def chart_kind(kind: str, items: List[dict]) -> tuple:
    """The chart a set of verified figures can honestly be drawn as. Columns and lines need one unit throughout,
    a line no negative values, a donut percentages that fit in a whole; otherwise a simpler chart, or a photo."""
    unit = lambda d: re.sub(r"[\d,.\s-]", "", d)
    units = {unit(i["display"]) for i in items}
    ok = {"compare": 2 <= len(items) and len(units) == 1,
          "bars": 3 <= len(items) and len(units) == 1,
          "line": 3 <= len(items) and len(units) == 1 and not any(i["display"].lstrip().startswith("-") for i in items),
          "donut": 2 <= len(items) and units == {"%"} and sum(i["value"] for i in items[:4]) <= 100.5,
          "kpis": 3 <= len(items)}
    for k in (kind, "kpis", "compare"):
        if ok[k]:
            return k, items[:FIGURE_KINDS[k][1]]
    return "photo", []


def fix_tex(tex: str) -> str:
    r"""Repair a hat a model typed as a character (betâ, ŷ) instead of \hat{...}."""
    tex = unicodedata.normalize("NFD", tex)
    return re.sub(r"(\\[a-zA-Z]+|[a-zA-Z])\u0302", r"\\hat{\1}", tex)


GREEK = ("alpha", "beta", "gamma", "delta", "epsilon", "theta", "lambda", "mu", "sigma", "pi", "rho", "omega", "nabla")


def speakable(text: str) -> str:
    r"""Narration is read aloud: LaTeX a model slipped into it becomes words (\hat{y} -> "y hat", \beta -> "beta")."""
    text = unicodedata.normalize("NFD", text)
    text = re.sub(r"\\hat\s*\{?\\?([A-Za-z]+)\}?|\\?([A-Za-z]+)\u0302(?![A-Za-z])", lambda m: f"{m.group(1) or m.group(2)} hat", text)
    text = re.sub(r"\\(" + "|".join(GREEK) + r")\b", r"\1", text)
    text = re.sub(r"\\partial", "d", text)
    text = re.sub(r"\\[A-Za-z]+", "", text)
    text = re.sub(r"[{}\\$]", "", text)
    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", text)).strip()


def tex_complete(tex: str) -> bool:
    r"""False for a formula a model left unfinished: unbalanced braces, an empty group, a derivative with nothing
    to differentiate (\frac{\partial}{\partial}), or a line that ends on an operator."""
    depth = 0
    for ch in tex:
        depth += {"{": 1, "}": -1}.get(ch, 0)
        if depth < 0:
            return False
    t = tex.strip()
    return (depth == 0 and "{}" not in t.replace(" ", "") and not re.search(r"\\partial\s*}", t)
            and not re.search(r"(=|\+|-|\\leftarrow|\\to|\\cdot|\\times|\^|_)$", t))


def typeset_errors(texs: List[str]) -> set:
    """The LaTeX pieces KaTeX rejects (checked with the video app's own KaTeX)."""
    if not texs:
        return set()
    node = shutil.which("node") or shutil.which("node.exe")
    script = ("const k=require('katex');let d='';process.stdin.on('data',c=>d+=c).on('end',()=>{"
              "const bad=JSON.parse(d).filter(t=>{try{k.renderToString(t,{throwOnError:true});return false}"
              "catch(e){return true}});console.log(JSON.stringify(bad))})")
    try:
        r = subprocess.run([node, "-e", script], cwd=VIDEO_APP, input=json.dumps(texs), capture_output=True,
                           text=True, encoding="utf-8", timeout=60)
        return set(json.loads(r.stdout))
    except (OSError, ValueError, subprocess.SubprocessError, TypeError):
        return set()


def shape_prompt(brief: dict, style: str, title: str, facts: str) -> tuple:
    """The writer's brief: the style's voice plus the plan made for this subject (braces escaped for the
    script prompt), and the number of shots that fits the planned length."""
    acts = "; ".join(f"{a['title']} ({a['job']})" for a in brief["acts"])
    minutes = brief["minutes"]
    text = SHAPE.format(persona=STYLES[style], minutes=f"{minutes:g}", title=title, facts=facts, acts=acts,
                        structure=brief["structure"], opening=brief["opening"], ending=brief["ending"],
                        tone=brief["tone"])
    if brief.get("maths"):
        text += MATHS_RULES
    shots = f"{max(14, round(minutes * 7))} to {max(20, round(minutes * 10))}"
    return text.replace("{", "{{").replace("}", "}}"), shots


def check_brief(raw, style: str) -> dict:
    """The plan as the writer can use it; anything missing gets a neutral default, never a fixed template."""
    raw = raw if isinstance(raw, dict) else {}
    if style not in VIDEO_STYLES:
        style = raw.get("style") if raw.get("style") in VIDEO_STYLES else "concept"
    acts = []
    for a in raw.get("acts") or []:
        if isinstance(a, dict) and str(a.get("title", "")).strip():
            acts.append({"title": " ".join(str(a["title"]).split()[:4]), "job": str(a.get("job", ""))[:160]})
    try:
        minutes = min(5.0, max(2.0, float(raw.get("minutes", 3))))
    except (TypeError, ValueError):
        minutes = 3.0

    def s(k, d):
        return str(raw.get(k) or d)[:300]
    return {"style": style, "acts": acts[:5] or [{"title": "The story", "job": "tell it from start to finish"}],
            "structure": s("structure", "whatever shape makes this subject clearest"),
            "opening": s("opening", "a question or a surprising fact the viewer already half-wonders about."),
            "ending": s("ending", "answer the opening question in one sentence."),
            "tone": s("tone", "clear, curious, warm"), "mood": s("mood", ""), "minutes": minutes,
            "maths": bool(raw.get("maths"))}


def on_screen(scene: dict) -> List[str]:
    """The words a scene shows, in a fixed order (so a translation can be put back in place)."""
    return ([scene["headline"], scene["kicker"], scene["label"], scene.get("quote", "")] +
            [i["label"] for i in scene.get("items", [])] + [e["label"] for e in scene.get("events", [])] +
            graphics.labels(scene.get("graphic")) + [p["label"] for p in scene.get("parts", [])] +
            [st["note"] for st in scene.get("steps", [])] +
            ([scene["xlabel"], scene["ylabel"]] if scene["kind"] in ("plot", "graph") else []))


def with_text(scene: dict, texts: List[str]) -> dict:
    s = json.loads(json.dumps(scene))
    s["headline"], s["kicker"], s["label"], s["quote"] = texts[:4]
    rest = texts[4:]
    for i in s.get("items", []):
        i["label"], rest = rest[0], rest[1:]
    for e in s.get("events", []):
        e["label"], rest = rest[0], rest[1:]
    if s.get("graphic"):
        rest = graphics.relabel(s["graphic"], rest)
    for p in s.get("parts", []):
        p["label"], rest = rest[0], rest[1:]
    for st in s.get("steps", []):
        st["note"], rest = rest[0], rest[1:]
    if s["kind"] in ("plot", "graph"):
        s["xlabel"], s["ylabel"] = rest[:2]
    s["highlight"] = ""          # the marked word cannot be matched across languages
    s.pop("chapter", None)       # act titles belong to the long video
    return s


class VideoMaker:
    def __init__(self, settings: Settings, llm: Optional[LLMClient] = None, log: Callable[[str], None] = print):
        self.s = settings
        self.llm = llm or LLMClient(settings, log)
        self.log = log

    # ---- script ---------------------------------------------------------------------------------------
    def brief(self, title: str, facts: List[dict], style: str) -> dict:
        """Plan this video's own shape (structure, parts, opening, ending, tone, mood) before writing it."""
        short = "\n".join(f"- {f['claim'][:160]}" for f in facts[:30])
        rule = "pick the style that suits this subject best" if style not in VIDEO_STYLES else f'keep "{style}"'
        try:
            raw = self.llm.complete_json(BRIEF_PROMPT.format(title=title, style=style, facts=short, style_rule=rule,
                                                             styles=", ".join(VIDEO_STYLES)),
                                         max_tokens=1500, temperature=0.9)
        except LLMError as exc:
            self.log(f"[video] no plan from the model ({exc}); writing without one")
            raw = {}
        b = check_brief(raw, style)
        self.log(f"[video] plan ({b['style']}, {b['minutes']:g} min{', maths' if b['maths'] else ''}): "
                 f"{b['structure'][:140]} | {' / '.join(a['title'] for a in b['acts'])}")
        return b

    def script(self, title: str, facts: List[dict], sources: List[dict], style: str = "news",
               brief: Optional[dict] = None) -> dict:
        lines = []
        for i, f in enumerate(facts, 1):
            src = sources[int(f["source"]) - 1] if str(f.get("source", "")).isdigit() else {}
            lines.append(f"{i}. [{domain(src.get('url', ''))}] {f['claim']} | \"{f.get('quote', '')[:240]}\"")
        brief = brief or check_brief({}, style)
        shape, shots = shape_prompt(brief, brief["style"], title, "\n".join(lines))
        prompt = SCRIPT_PROMPT.replace("{shape}", shape).replace("{shots}", shots)
        prompt = prompt.replace("{{", "{").replace("}}", "}")
        plan = self.llm.complete_json(prompt, max_tokens=12000)
        kicker = KICKERS[int(hashlib.md5(title.encode()).hexdigest(), 16) % len(KICKERS)]
        allowed = " ".join(f"{f['claim']} {f.get('quote', '')}" for f in facts)
        quotes = " ".join(_norm(f.get("quote", "")) for f in facts)
        countries = country_names()

        def maths(p) -> int:
            return sum(1 for sc in (p.get("scenes") or [] if isinstance(p, dict) else [])
                       if isinstance(sc, dict) and check_scene(sc, allowed, quotes, countries)["kind"] in MATH_KINDS)
        def spoken_words(p) -> int:
            return sum(len(str(sc.get("narration", "")).split())
                       for sc in (p.get("scenes") or [] if isinstance(p, dict) else []) if isinstance(sc, dict))

        def score(p) -> tuple:
            return (min(maths(p), need), min(spoken_words(p), words_needed))

        # a lesson without its maths, or a 4 minute plan narrated in 90 seconds, is not the video; ask once more
        need = max(5, len(plan.get("scenes") or []) * 2 // 5) if brief.get("maths") else 0
        words_needed = round(brief["minutes"] * 150 * 0.75)      # ~150 spoken words a minute
        notes = []
        if need and maths(plan) < need:
            notes.append(f"it had only {maths(plan)} maths shots; this lesson needs at least {need} \"equation\", "
                         f"\"graph\", \"derive\" or \"plot\" shots, each with its required fields filled in exactly")
        if spoken_words(plan) < words_needed:
            notes.append(f"its narration was only {spoken_words(plan)} words; the planned {brief['minutes']:g} minutes "
                         f"need at least {words_needed} words, so give each shot a full sentence or two and explain "
                         f"each idea properly")
        if notes:
            self.log(f"[video] first draft too thin ({'; '.join(n.split(';')[0] for n in notes)}); rewriting the script")
            try:
                again = self.llm.complete_json(prompt + "\n\nIMPORTANT: a first draft fell short: " + "; and ".join(notes)
                                               + ".", max_tokens=14000)
            except LLMError:
                again = {}
            if score(again) > score(plan) and len((again or {}).get("scenes") or []) >= 5:
                plan = again
        scenes, act, acts = [], "", 0
        for sc in plan.get("scenes", [])[:32]:
            if not isinstance(sc, dict):
                continue
            if sc.get("kind") == "chapter":        # an old-style title shot becomes the next shot's act sting
                act = str(sc.get("headline") or "")
                continue
            act = str(sc.get("act") or "").strip() or act
            narration = strip_unsupported_numbers(speakable(str(sc.get("narration", "")).strip()), allowed)
            if not narration:
                continue
            scene = check_scene(sc, allowed, quotes, countries)
            used = [int(n) for n in sc.get("facts", []) if str(n).isdigit() and 0 < int(n) <= len(facts)]
            src = ""
            if used and str(facts[used[0] - 1].get("source", "")).isdigit():
                src = domain(sources[int(facts[used[0] - 1]["source"]) - 1]["url"])
            scene.update(narration=narration, source="" if scene["kind"] == "chapter" else src,
                         subjects=[str(x) for x in sc.get("subjects", [])][:3],
                         footage=str(sc.get("footage") or "")[:40] if scene["kind"] in ("hook", "photo", "stat", "list")
                         else "")
            if act and scenes and acts < len(ORDINALS):
                title_words = " ".join(act.split()[:4])
                if _verified(title_words, allowed):
                    scene["chapter"] = {"kicker": kicker(acts), "title": title_words}
                    acts += 1
            act = ""
            scenes.append(scene)
        if len(scenes) < 5:
            raise LLMError("the video script came back too short")
        def texs(sc):
            return [p["tex"] for p in sc.get("parts", []) + sc.get("steps", []) +
                    (sc.get("graph") or {}).get("curves", []) if p["tex"]]
        bad = typeset_errors([t for sc in scenes for t in texs(sc)])
        for sc in scenes:             # a formula KaTeX cannot typeset turns the shot into a plain one
            if any(t in bad for t in texs(sc)):
                self.log(f"[video] formula skipped ({sc['kind']}): {' | '.join(texs(sc))[:100]}")
                sc["kind"], sc["parts"], sc["steps"] = "photo", [], []
                sc.pop("graph", None)
        scenes[0]["kind"] = "hook" if scenes[0]["kind"] in ("photo", "hook", "stat") else scenes[0]["kind"]
        outro = strip_unsupported_numbers(str(plan.get("outro") or "").strip(), allowed)
        if not 8 <= len(outro.split()) <= 60:
            outro = OUTRO.format(facts=len(facts))
        scenes.append({"kind": "outro", "narration": outro, "kicker": "Full report below",
                       "headline": str(plan.get("thumb_text") or title)[:40], "highlight": "report",
                       "label": f"{len(facts)} verified facts · {len(sources)} sources", "number": "", "items": [],
                       "events": [], "countries": [], "quote": "", "speaker": "", "source": "", "subjects": []})
        short = []
        for item in plan.get("short", [])[:5]:
            idx = item.get("scene")
            text = strip_unsupported_numbers(str(item.get("narration", "")).strip(), allowed)
            if isinstance(idx, int) and 0 <= idx < len(scenes) - 1 and text:
                short.append({"scene": idx, "narration": text})
        short = short or [{"scene": 0, "narration": scenes[0]["narration"]}]
        short.append({"scene": len(scenes) - 1, "narration": SHORT_OUTRO})
        return {"title": str(plan.get("title", title))[:100], "thumb_text": str(plan.get("thumb_text", ""))[:40],
                "thumb_highlight": str(plan.get("thumb_highlight", ""))[:20],
                "description": str(plan.get("description", "")), "tags": [str(t) for t in plan.get("tags", [])][:12],
                "scenes": scenes, "short": short}

    def translate_lines(self, lines: List[str], lang: str) -> Optional[List[str]]:
        """Translate the lines (same count, same order; empty lines stay empty), or None if the model will not."""
        name = LANGS[lang]
        todo = [i for i, l in enumerate(lines) if l.strip()]
        src = [lines[i] for i in todo]
        prompt = (f"Translate each string of this JSON array into {name}, for a narrator to read aloud and for "
                  f"on-screen titles. Keep the order and return a JSON array with exactly {len(src)} strings. Keep "
                  f"numbers as digits and symbols like $ and %. Write names of people, places and companies in {name} "
                  f"script. Keep titles short. Translate faithfully: add or drop nothing.\n\n"
                  f"{json.dumps(src, ensure_ascii=False)}")
        for _ in range(2):
            try:
                out = self.llm.complete_json(prompt, max_tokens=max(2000, sum(len(l) for l in src) * 3),
                                             temperature=0.2)
            except LLMError:
                continue
            if isinstance(out, list) and len(out) == len(src) and all(isinstance(x, str) and x.strip() for x in out):
                done = list(lines)
                for i, text in zip(todo, out):
                    done[i] = text.strip()
                return done
        self.log(f"[video] {name} translation failed; that language is skipped")
        return None

    # ---- assembly ---------------------------------------------------------------------------------------
    def make(self, run_dir: str, email: bool = True, style: str = "") -> Dict[str, str]:
        t0 = time.time()
        with open(os.path.join(run_dir, "research.json"), encoding="utf-8") as f:
            research = json.load(f)
        with open(os.path.join(run_dir, "metadata.json"), encoding="utf-8") as f:
            meta = json.load(f)
        facts, sources = research["facts"], research["sources"]
        title = meta.get("title", meta.get("topic", ""))
        self.log("\n=== Video: script, pictures, voices, sound, render ===")
        style = {"explainer": "education"}.get(style, style) or meta.get("style") or \
            ("news" if meta.get("source") != "topic" else "auto")
        brief = self.brief(title, facts, style)
        plan = self.script(title, facts, sources, brief["style"], brief)
        scenes, beats = plan["scenes"], plan["short"]
        theme = design.design(self.llm.complete_json, plan["title"], brief["style"],
                              f"{brief['mood']} {brief['tone']}", self.log)
        self.log(f"[video] {len(scenes)} scenes ({', '.join(s['kind'] for s in scenes)}), Short of {len(beats)} beats")
        self.art_direct(scenes)
        if brief["style"] in ("education", "concept"):
            n = graphics.no_stock_photos(scenes)
            if n:
                self.log(f"[graphics] {n} picture shot(s) shown as animated type, not stock photos")

        out = os.path.abspath(os.path.join(run_dir, "video"))
        job = os.path.join(VIDEO_APP, "public", "job")
        shutil.rmtree(job, ignore_errors=True)
        os.makedirs(job)
        os.makedirs(out, exist_ok=True)

        # pictures: free Wikimedia Commons photos, credited in the description; a photo is not repeated
        # in consecutive scenes
        credits, pictures = [], {}
        for k, sc in enumerate(scenes):
            sc["images"] = []
            if sc.get("graphic") or sc["kind"] in MATH_KINDS:
                sc.pop("subjects", None)
                sc.pop("footage", None)
            for subject in sc.pop("subjects", []):
                if subject not in pictures:
                    dest = os.path.join(job, f"img{len(pictures)}.jpg")
                    credit = free_image(subject, dest)
                    if credit and not photo_fits(self.s, subject, dest, self.log, sc.get("narration", "")):
                        credit = None
                    pictures[subject] = f"job/img{len(pictures)}.jpg" if credit else ""
                    if credit:
                        credits.append({"subject": subject, **credit})
                previous = scenes[k - 1].get("images", []) if k else []
                if pictures[subject] and pictures[subject] not in previous:
                    sc["images"].append(pictures[subject])
        self.log(f"[video] {len(credits)} free photo(s) (Wikimedia Commons, Openverse)")
        wanted = [(k, sc["footage"], sc["narration"]) for k, sc in enumerate(scenes) if sc.get("footage")]
        with ThreadPoolExecutor(max_workers=4) as pool:
            found = list(pool.map(lambda w: (w[0], find_clip(w[1], w[2], os.path.join(job, f"clip{w[0]}.mp4"),
                                                             self.s, self.log)), wanted))
        for k, credit in found:
            if credit:
                scenes[k].update(video=f"job/clip{k}.mp4", clipSeconds=CLIP_SECONDS)
                credits.append(credit)
        self.log(f"[video] {sum(1 for _, c in found if c)} of {len(wanted)} shots got real footage")

        # everything spoken or shown, in every language: long narration, Short narration, Short on-screen text,
        # title and description
        langs = [l for l in self.s.video_langs if l in VOICES] or ["en"]
        n_long, n_short = len(scenes), len(beats)
        shown = [on_screen(scenes[b["scene"]]) for b in beats]
        english = ([s["narration"] for s in scenes] + [b["narration"] for b in beats] + sum(shown, []) +
                   [plan["title"], plan["description"]])
        texts = {"en": english}
        for lang in langs:
            if lang != "en":
                done = self.translate_lines(english, lang)
                if done:
                    texts[lang] = done
        jobs, keys = [], []
        for lang, lines in texts.items():
            for i, line in enumerate(lines[:n_long + n_short]):
                if not line.strip():
                    continue
                kind, idx = ("long", i) if i < n_long else ("short", i - n_long)
                jobs.append((line, VOICES[lang], os.path.join(job, f"{lang}_{kind}{idx}.mp3")))
                keys.append((lang, kind, idx))
        spoken = {k: v for k, v in zip(keys, speak_all(jobs)) if v is not None}
        with ThreadPoolExecutor(max_workers=6) as pool:
            trimmed = list(pool.map(lambda kv: tighten(jobs[keys.index(kv[0])][2], kv[1]), spoken.items()))
        spoken = dict(zip(spoken, trimmed))
        self.log(f"[video] {len(jobs)} narration clips spoken in {', '.join(texts)}")

        def clip(lang, kind, idx):
            path = os.path.join(job, f"{lang}_{kind}{idx}.mp3")
            return path if (lang, kind, idx) in spoken else None

        def silence():
            path = os.path.join(job, "silence.wav")
            if not os.path.exists(path):
                import numpy as np
                sound._write(path, np.zeros((SR_SILENCE, 2)))
            return path

        # sound assets, made once per video
        assets = {"music": os.path.join(job, "music.wav"), "whoosh": os.path.join(job, "whoosh.wav"),
                  "hit": os.path.join(job, "hit.wav")}
        sound.whoosh(assets["whoosh"])
        sound.hit(assets["hit"])

        # long video: the pictures follow the English narration. A dubbed line that runs longer is sped up (at
        # most MAX_TEMPO, pitch kept), and only what still does not fit lengthens the shot, so the English video
        # has no silent waits and every language still fits the pictures
        kinds = [s["kind"] for s in scenes]
        secs = {(l, i): mp3_seconds(clip(l, "long", i)) for l in texts for i in range(n_long) if clip(l, "long", i)}
        longest = []
        for i in range(n_long):
            en = secs.get(("en", i), 0.0)
            dub = max((v for (l, k), v in secs.items() if k == i and l != "en"), default=0.0)
            longest.append(max(en, dub / MAX_TEMPO) if en else dub)
        tempo = {key: max(1.0, v / longest[key[1]]) if longest[key[1]] else 1.0 for key, v in secs.items()}
        frames, starts, total = timeline(longest, kinds)
        sound.music(total / FPS + 1, assets["music"], seed=title)
        long_scenes = [{**s, "frames": frames[i], "cue": cue(spoken.get(("en", "long", i), []), s.get("number", "")),
                        "hcue": cue(spoken.get(("en", "long", i), []), s.get("highlight", "")),
                        "graphic": graphics.timed(s.get("graphic"), s.get("headline", ""), spoken.get(("en", "long", i), []),
                                                  frames[i], FPS, LEAD),
                        "parts": graphics.timed_parts(s.get("parts", []), spoken.get(("en", "long", i), []), frames[i],
                                                      FPS, LEAD),
                        "steps": graphics.timed_steps(s.get("steps", []), spoken.get(("en", "long", i), []), frames[i],
                                                      FPS, LEAD)}
                       for i, s in enumerate(scenes)]
        # the English captions are part of the picture: short lines, timed to the spoken words
        long_captions = []
        for i in range(n_long):
            for ca, cz, line in word_lines(spoken.get(("en", "long", i), []), 0, 42):
                long_captions.append({"from": starts[i] + LEAD + round(ca * FPS),
                                      "to": starts[i] + LEAD + round(cz * FPS), "text": line})
        props = os.path.join(job, "long.json")
        with open(props, "w", encoding="utf-8") as f:
            json.dump({"scenes": long_scenes, "captions": long_captions, "channel": self.s.channel_name, "theme": theme,
                       "thumbText": plan["thumb_text"], "thumbHighlight": plan["thumb_highlight"]}, f, ensure_ascii=False)
        files = {}
        for lang in texts:
            cues = []
            for i in range(n_long):
                base = (starts[i] + LEAD) / FPS
                t = tempo.get((lang, i), 1.0)
                cues += word_lines([(a / t, b / t, w) for a, b, w in spoken.get((lang, "long", i), [])], base, 84)
            with open(os.path.join(out, f"subtitles_{lang}.srt"), "w", encoding="utf-8") as f:
                f.write(srt(cues))
            files[f"subtitles_{lang}.srt"] = "subtitles"
            track = os.path.join(out, f"audio_track_{lang}.mp3") if lang != "en" else os.path.join(job, "long_en.mp3")
            self.log(f"[video] mastering the {LANGS[lang]} soundtrack")
            master([clip(lang, "long", i) or silence() for i in range(n_long)], starts, kinds, total, assets, track,
                   self.log, [tempo.get((lang, i), 1.0) for i in range(n_long)])
            if lang != "en":
                files[f"audio_track_{lang}.mp3"] = "audio"
        self.log(f"[video] rendering the long video ({total / FPS:.0f}s)")
        render("Long", props, os.path.join(job, "long_en.mp3"), os.path.join(out, "long_video_en.mp4"), self.log)
        files["long_video_en.mp4"] = "video"
        remotion(["still", "src/index.jsx", "Thumb", os.path.join(out, "thumbnail.png"), f"--props={props}"], self.log)
        files["thumbnail.png"] = "thumbnail"
        self.log("[video] quality check (contact sheet + stillness)")
        try:
            verdict = review(self.s, os.path.join(out, "long_video_en.mp4"), total / FPS, os.path.join(out, "contact_sheet.jpg"))
        except Exception as exc:          # the check must never cost the videos
            verdict = {}
            self.log(f"[video] quality check failed: {type(exc).__name__}: {str(exc)[:120]}")
        if os.path.exists(os.path.join(out, "contact_sheet.jpg")):
            files["contact_sheet.jpg"] = "review"
        self.log("[video] " + summary(verdict).replace("\n", "\n[video] "))

        # one Short per language: its own timing, on-screen text and karaoke captions in that language
        per_beat = [len(x) for x in shown]
        for lang, lines in texts.items():
            screen = lines[n_long + n_short:n_long + n_short + sum(per_beat)]
            order = list(range(n_short))
            secs = lambda bs: sum(mp3_seconds(clip(lang, "short", b)) + 0.4 for b in bs if clip(lang, "short", b))
            while secs(order) > SHORT_MAX_SECONDS and len(order) > 2:
                order.pop(-2)               # drop the weakest middle beat, keep the hook and the ending
            order = [b for b in order if clip(lang, "short", b)]
            seconds = [mp3_seconds(clip(lang, "short", b)) for b in order]
            sk = [scenes[beats[b]["scene"]]["kind"] for b in order]
            fr, st, tot = timeline(seconds, sk)
            short_scenes, captions = [], []
            for j, b in enumerate(order):
                offset = sum(per_beat[:b])
                visual = with_text(scenes[beats[b]["scene"]], screen[offset:offset + per_beat[b]]) if lang != "en" \
                    else scenes[beats[b]["scene"]]
                short_scenes.append({**visual, "frames": fr[j]})
                words = spoken[(lang, "short", b)]
                short_scenes[-1].update(cue=cue(words, visual.get("number", "")),
                                        hcue=cue(words, visual.get("highlight", "")),
                                        graphic=graphics.timed(visual.get("graphic"), visual.get("headline", ""), words,
                                                               fr[j], FPS, LEAD),
                                        parts=graphics.timed_parts(visual.get("parts", []), words, fr[j], FPS, LEAD),
                                        steps=graphics.timed_steps(visual.get("steps", []), words, fr[j], FPS, LEAD))
                for ca, cz, line in word_lines(words, 0, 30):
                    captions.append({"from": st[j] + LEAD + round(ca * FPS), "to": st[j] + LEAD + round(cz * FPS),
                                     "text": line})
            path = os.path.join(job, f"short_{lang}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"scenes": short_scenes, "captions": captions, "channel": self.s.channel_name, "theme": theme},
                          f, ensure_ascii=False)
            track = os.path.join(job, f"short_{lang}.mp3")
            master([clip(lang, "short", b) for b in order], st, sk, tot, assets, track, self.log)
            self.log(f"[video] rendering the {LANGS[lang]} Short ({tot / FPS:.0f}s)")
            render("Short", path, track, os.path.join(out, f"short_{lang}.mp4"), self.log)
            files[f"short_{lang}.mp4"] = "short"

        product = (meta.get("gumroad") or {}).get("url", "")
        n_lines = n_long + n_short + sum(per_beat)
        with open(os.path.join(out, "posting_guide.txt"), "w", encoding="utf-8") as f:
            f.write(summary(verdict) + "\n\n" + posting_guide(plan, texts, n_lines, credits, product, meta))
        with open(os.path.join(out, "video_script.json"), "w", encoding="utf-8") as f:
            json.dump({"plan": plan, "texts": texts, "credits": credits, "review": verdict}, f, indent=2,
                      ensure_ascii=False)
        shutil.rmtree(job, ignore_errors=True)
        self.log(f"[video] done in {time.time() - t0:.0f}s: {', '.join(files)}")
        self.deliver(run_dir, out, files, plan, email, verdict)
        return {name: os.path.join(out, name) for name in files}

    def art_direct(self, scenes: List[dict]) -> None:
        """Motion graphics for the shots without a strong picture; any failure leaves the templates in place."""
        try:
            reply = self.llm.complete_json(graphics.prompt(scenes), max_tokens=4000, temperature=0.6)
        except LLMError as exc:
            self.log(f"[graphics] no art direction: {str(exc)[:120]}")
            return
        n = graphics.assign(scenes, reply, _verified, self.log)
        kinds = ", ".join(s["graphic"]["type"] for s in scenes if s.get("graphic"))
        self.log(f"[graphics] {n} motion graphic(s): {kinds}")

    def deliver(self, run_dir: str, out: str, files: Dict[str, str], plan: dict, email: bool,
                verdict: Optional[dict] = None) -> None:
        """Store the videos (deleted after KEEP_DAYS) and email the links plus the small files. Never posts."""
        names = list(files) + ["posting_guide.txt"]
        prune_prefix(self.s, "videos/", KEEP_DAYS, self.log)
        links = upload_run(self.s, out, names, self.log,
                           prefix=f"videos/{os.path.basename(os.path.normpath(run_dir))}")
        if not email:
            return
        listing = "\n".join(f"  {n}: {links[n]}" for n in names if n in links) or f"  saved in {out}"
        body = (f"Your videos for \"{plan['title']}\" are ready to review. Nothing has been posted.\n\n"
                f"{summary(verdict or {})}\n(contact_sheet.jpg shows 12 frames at a glance)\n\n"
                f"DOWNLOAD (links work for 7 days; the files are deleted from storage after {KEEP_DAYS} days):\n"
                f"{listing}\n\nHOW TO POST: see the attached posting_guide.txt (titles, descriptions and tags in "
                f"every language, photo credits, and the steps to add the extra audio tracks in YouTube Studio).\n")
        small = [os.path.join(out, n) for n in names if n.endswith((".txt", ".srt", ".png", ".jpg"))]
        send_email(self.s, f"[Video] {plan['title'][:120]}", body, small, self.log)


SR_SILENCE = sound.SR // 2


def posting_guide(plan: dict, texts: Dict[str, List[str]], n_lines: int, credits: List[dict], product: str,
                  meta: dict) -> str:
    credit_lines = "\n".join(f"- {c['subject']}: {c['author'] or 'see file page'}, {c['license']}, {c['file']}"
                             for c in credits) or "- none (no photos used)"
    report = f"Full report: {product}\n" if product else ""
    parts = [f"POSTING GUIDE - {plan['title']}\n", "Nothing was posted automatically. Review the videos first.\n",
             "LONG VIDEO (YouTube)",
             "1. YouTube Studio > Create > Upload videos > long_video_en.mp4. Use the English title and description "
             "below and thumbnail.png. English captions are already in the picture; subtitles_en.srt is optional (CC).",
             "2. After it is processed: Studio > Subtitles > Add language (Hindi, Telugu, ...). For each language: "
             "Audio > Add > upload audio_track_<lang>.mp3; Subtitles > Upload file > subtitles_<lang>.srt; "
             "Title & description > add the translated text below.",
             "3. Viewers then hear the video in their own language from one video and one view count.\n",
             "SHORTS: upload short_<lang>.mp4 as separate Shorts with that language's title.\n",
             "Music and sound effects are generated by the pipeline itself: no licence or credit needed.\n"
             "Credits below cover the photos and video clips (Wikimedia Commons, NASA, Pixabay).\n"]
    for lang, lines in texts.items():
        title, desc = lines[n_lines], lines[n_lines + 1]
        parts.append(f"===== {LANGS[lang].upper()} =====\nTitle: {title}\nDescription:\n{desc}\n\n{report}"
                     f"Sources: {meta.get('sources', '?')} sources, {meta.get('verified_facts', '?')} verified facts.\n"
                     f"Photo and footage credits (required by the licences):\n{credit_lines}\n")
    parts.append("Tags: " + ", ".join(plan["tags"]))
    return "\n".join(parts) + "\n"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python -m blogwriter.video output/<run folder> [--no-email] [--style=auto|news|story|education|concept]")
    VideoMaker(Settings.from_env()).make(sys.argv[1], email="--no-email" not in sys.argv,
                                         style=next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--style=")), ""))
