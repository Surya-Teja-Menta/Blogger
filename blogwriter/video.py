"""Turn a finished report into videos for review: a documentary-style long video (English picture track, with
the Hindi and Telugu narrations as extra audio tracks for YouTube's multi-language audio), one Short per
language with on-screen text and captions in that language, subtitles and a thumbnail. Nothing is posted: the
files are stored and emailed, and a person reviews and uploads them.

    python -m blogwriter.video output/<run folder> [--no-email]     # (re)make the videos of a saved run"""
import asyncio
import glob
import hashlib
from concurrent.futures import ThreadPoolExecutor
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
from .footage import CLIP_SECONDS, find_clip, gemini_json, photo_fits
from .llm import LLMClient, LLMError
from .mailer import send_email
from . import design, diagram, graphics, mathexpr
from .research import domain
from .storage import prune_prefix, upload_run
from .web import UA
from .writer import LANGS, strip_unsupported_numbers

VIDEO_APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "video")
VOICES = {"en": "en-US-BrianMultilingualNeural", "hi": "hi-IN-MadhurNeural", "te": "te-IN-MohanNeural",
          "kn": "kn-IN-GaganNeural", "ta": "ta-IN-ValluvarNeural"}
FPS = 30
TRANSITION = 15           # frames two scenes overlap; must equal TRANSITION in video/src/theme.js
LEAD = 6                  # frames after a shot starts before its narration begins
GAP = 4                   # frames of breath after the narration (clips are trimmed to the words, see tighten)
MP3_BYTES_PER_SECOND = 6000   # edge-tts speaks 24 kHz, 48 kbit/s mono MP3
SHORT_MAX_SECONDS = 58
MAX_TEMPO = 1.3           # a dubbed track may be sped up this much (pitch kept) to fit the English picture
LONG_MINUTES = 6          # from this length a script is written part by part (one request comes back too short)
MAX_SCENES = 110          # shots in one video
DIAGRAM_MAX = 18          # bespoke diagrams per video (each costs several vision-model calls) ...
DIAGRAM_MAX_LONG = 30     # ... and in a long video, where most shots are pictures of the idea
CHECK_PAUSE = 3.0         # seconds of silence in a "check" shot for the viewer to think before the answer
REVIEWERS = 4             # diagram critiques run side by side (each is a slow vision-model call)
KEEP_DAYS = 14            # videos are deleted from object storage after this; review and post before then
KINDS = ("hook", "photo", "stat", "compare", "bars", "line", "donut", "kpis", "timeline", "steps", "map", "list",
         "quote", "equation", "plot", "graph", "derive", "surface", "check", "diagram")
MATH_KINDS = ("equation", "plot", "graph", "derive", "surface")   # lesson shots drawn from maths, not facts or photos
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
    "education": "an educational channel with the pictures of 3Blue1Brown, the hooks of Veritasium and the timing of "
                 "a film, narrated with dry, deadpan wit: builds real understanding step by step in simple everyday "
                 "words, every idea grounded in real life, intuition first, then precision, never dumbed down",
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
  "narrator": "the voice of this video in one sentence: HOW it talks to the viewer (its stance, rhythm and
    humour), e.g. a patient teacher thinking out loud with you; a sceptic testing every claim; a guide who keeps
    asking 'but why?'; a deadpan, sarcastic guide who teases the obvious wrong answer (for a lesson: dry, sarcastic
    and warm). It is the channel's narrator, never a character: no invented name, job, place,
    possessions or personal experiences.",
  "device": "the storytelling device that carries the whole video (e.g. one running example that grows each
    shot; a question the viewer is asked to guess before each reveal; a wrong answer that gets corrected; a
    countdown; a letter; a then-and-now contrast)",
  "mood": "4 to 6 words about how the video should look and feel",
  "examples": "2 to 4 everyday real-life situations the viewer has lived that make this subject concrete (from food,
    phones, traffic, sport, exams, shopping, queues, weather...), the first one strong enough to run through the
    whole video",
  "minutes": a number: 8 to 12 for an education lesson (every idea taught properly, with pictures, a worked
    example and a check), 3 to 8 otherwise,
  "maths": true if the subject has formulas worth teaching, else false}}"""

SHAPE = """You are the head writer of {persona}. Write the script and direct the visuals of a {minutes} minute
video built ONLY from these verified facts. This video has its own voice: {narrator} Keep that voice in every
line, and carry the whole video with this device: {device}

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
- Show any process as a "steps" shot and any set of numbers as a chart.
- Honesty: the narrator never claims personal experiences, credentials, a location or things it did ("I'm in my
  lab", "in my years as an engineer", "my students"). "We" and "let's" for working something out together are
  fine, and an analogy is framed as one ("imagine ...")."""

TEACHING = r"""
- This is a LESSON: it TEACHES, it does not only explain. In this order: (1) open on a question or a problem the
  viewer cares about; (2) recall, in a shot or two, what the viewer needs from before; (3) intuition first: SHOW
  the idea with a picture that moves (a diagram, "graph", "surface" or "plot") before any formula; (4) then the
  formula, naming every symbol; (5) a worked example with small concrete numbers, step by step ("derive" lines
  such as "\hat{y} = 2 \cdot 3 + 1 = 7"), every number shown on screen and the arithmetic exactly right, then a
  sanity check of the answer; (6) a common mistake and why it fails; (7) one or two "check" shots, each a
  question the viewer answers before the reveal, testing the idea just taught (a prediction, a direction, a small
  calculation), never trivia; (8) a recap "list" of the three things to remember; (9) one line on what is next.
- Show, do not just tell: most shots are pictures of the idea (diagram, graph, surface, plot, derive, equation);
  talk over a plain title is rare. Numbers in a worked example or a check are illustrative and allowed when that
  shot shows them on screen."""

VOICE = r"""
- VOICE: dry, deadpan, sarcastic wit, like a teacher who has heard every wrong answer and still finds them funny.
  About every third or fourth line carries a playful jab: at the obvious-but-wrong intuition, at jargon, at the
  subject's scary reputation, at everyday absurdities. Never at the viewer, never mean, never about real people or
  groups, and a joke never replaces the explanation: the line still teaches.
- WORDS: simple everyday words a 12-year-old knows, short sentences. A technical term only once the idea is already
  clear, and explained in the same sentence ("this is called the standard error: how much the average wobbles").
- REAL LIFE: show every idea first in a real-life situation the viewer has lived, then generalise it. Use these, and
  keep the first one running through the whole video, coming back to it as the ideas grow: [examples].
- CINEMA: open cold on a real-life moment, never on a definition; raise a question, hold it, then reveal; vary the
  rhythm (a few quick punchy lines, then one slow reveal shot); end every part on a hook into the next.
- PICTURES: most shots are "diagram" shots or maths shots (graph, surface, derive, equation, check). A "diagram"
  shot is an animated picture of the idea built for that sentence, described in its "picture". Simulate whatever
  can be simulated instead of describing it: chance, averages and spread as live random samples falling into a
  histogram; many small random pushes adding up as balls bouncing through pegs into bins; shares and odds as a crowd
  of icons with some lit up; totals as counters; one idea turning into another as a shape that morphs. In a lesson,
  "photo" shots are rare (at most 1 shot in 10), whatever the general rule above says."""

LESSON = """
- This video is lesson {number} of {total} in the course "{course}"{module}. Its learning goal: {goal}
  It must cover: {ideas}. Pictures worth showing: {visuals}.
  The viewer has already learned: {before}. Recall only what this lesson needs; do not teach it again.
  {after}"""

MATHS_RULES = r"""
- The MATHS INTUITION is the heart of this video: at least half of all shots are maths shots ("equation", "graph",
  "derive", "plot"), with at least 3 "equation" or "derive" shots and at least 2 "graph" shots. Always picture
  first, then the formula that says the same thing. Use "graph" to SHOW behaviour: sweep a parameter to show what
  it does, a tangent for rates and gradients, the area for integrals, totals and probabilities. Use "derive" for
  algebra a viewer should follow step by step, each step with a note on what changed. Use "surface" whenever a
  quantity depends on TWO inputs (a cost over two weights, a loss landscape, a valley or a saddle, a plane fitted
  to two features): seeing it in 3D is the moment it clicks, so a lesson with such an idea has at least one. For fitting a
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
- "outro": 1 or 2 closing sentences in this video's own voice that say {outro_ask} linked in the description,
  and invite the viewer to subscribe to {channel} (say the channel's name). Not a slogan; make it fit the story.

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
- "diagram":  an animated picture drawn for this sentence from moving parts (shapes that morph, arrows, curves,
              labelled boxes, icons, crowds of icons, counters, live random samples falling into a histogram, real
              physics with balls bouncing through pegs into bins, short formulas); the camera follows each part as
              it is said and a hand-drawn pen rings or underlines the key one. Needs "picture": what it shows and
              what moves, in one sentence (max 35 words), e.g. "single delivery times fall into a lopsided
              histogram, then averages of 30 orders pile into a narrow bell".
- "check":    (lessons) a question for the viewer to answer before the reveal. Needs "question" (max 14
              words), "options": 2 to 4 short answers (max 6 words each, maths in plain words or short like
              "w = 3"), "answer": the index of the right option (0 = first), "why": max 10 words. Its narration
              asks the question (ending with "?"), then gives the answer and why: the video pauses after the "?"
              for the viewer to think.
- "derive":   (lessons) a working written out line by line. Needs "steps": [{{"tex": one full KaTeX line,
              "note": what this step did, max 5 words, e.g. "take the derivative"}}], 2 to 5 steps.
- "plot":     (lessons on fitting data) an animated plot of sample data. Needs "plot": one of "scatter" (the data
              points), "fit" (a line turning into the best fit), "residuals" (each point's error to the line),
              "squares" (each error drawn as a square, their total shrinking as the line improves), "descent"
              (gradient descent: a ball stepping down the error curve while the line improves); "xlabel" and
              "ylabel" (axis names, max 3 words, e.g. "House size", "Price").
- "surface":  (lessons) a 3D surface z = f(x, y) that rises out of the floor while the camera orbits it. Needs
              "surface": {{"fn": the function in plain maths using only x, y, numbers, + - * / ^, brackets, sin cos
              tan exp log sqrt abs, pi, e (write * for multiplication: "x^2 + 3*y^2", "0.4*x + 0.2*y + 1"), "tex":
              its KaTeX label, e.g. "J(w, b) = w^2 + 3b^2", "x": [xmin, xmax], "y": [ymin, ymax], "mark": "descent" (a
              ball takes real gradient-descent steps from "start" down to the bottom), "minimum" (the lowest point
              is ringed), "residuals" (3D data points with sticks to the surface; give "points": 6 to 20 [x, y, z]
              near the surface, e.g. houses around a fitted plane) or "", "start": [x, y] (for descent: a high
              point)}}; plus "xlabel", "ylabel" and "zlabel" (axis names, max 3 words, e.g. "w", "b", "cost").
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
         "It's in the description. And if you want one story like this, researched properly, every day, subscribe "
         "to {channel}.")
OUTRO_SOURCES = ("Every one of the {facts} facts in this video was checked, and every source is linked in the "
                 "description. If you want more like this, explained properly, subscribe to {channel}.")
SHORT_OUTRO = "Full story, with every source, on {channel}."
# a long video is planned as an outline, then written part by part (placeholders are filled with fill())
OUTLINE = """

THIS IS A LONG VIDEO, so plan it before writing it: about [minutes] minutes, [words] spoken words, [shots] shots.
Break it into the parts of the plan, in order, and each part into beats. One beat is one thing the viewer SEES and
learns (it becomes one or two shots), written as its shot kind and what it shows, e.g. "graph: the cost as w
slides, its lowest point marked" or "check: which way does w move if the slope is negative?". About [shots] beats.
Reply with JSON: {"title": "YouTube title, max 70 characters, specific and curious, no clickbait words or ALL CAPS",
 "thumb_text": "3 or 4 words for the thumbnail", "thumb_highlight": "1 word of thumb_text",
 "description": "2 or 3 plain sentences on what the video covers", "tags": ["8 to 12 search tags"],
 "outro": "the closing sentences described above",
 "parts": [{"title": "2 to 4 words", "beats": ["kind: what this beat shows and teaches", "..."]}]}"""
ACT = """

THE OUTLINE OF THE WHOLE VIDEO:
[outline]

Now write ONLY part [k] of [n], "[title]", shot by shot. Its beats:
[beats]
Write [lo] to [hi] shots for these beats (a beat may take several shots: one sentence and one picture each),
about [words] spoken words in all. [first]
[prev]
Reply with JSON: {"scenes": [{"kind": "...", "narration": "...", "headline": "...", "kicker": "...",
 "highlight": "...", "act": "", "facts": [], plus every field that shot's kind needs, exactly as described above}]}"""
SHORT_PICK = """These are the shots of a video (index | kind | narration). Pick 4 or 5 beats for a vertical Short
under 50 seconds that reuse these shots' pictures: beat 1 stops the scroll in at most 14 words; then the strongest
moments, at most 20 words each (pictures of the idea make strong beats). Each beat's narration is a new line for
the Short, saying only what that shot says.
[rows]
Reply with JSON: {"short": [{"scene": index, "narration": "..."}]}"""


def fill(template: str, **values) -> str:
    """str.format for prompts that also contain JSON braces: [name] placeholders."""
    for k, v in values.items():
        template = template.replace(f"[{k}]", str(v))
    return template
EXPAND = """These are the narration lines of an explainer video, one per shot, in order. The video is too short:
together they should run about {total} spoken words, but they have {have}. Rewrite every line so it explains more:
say what the viewer is watching, why it matters and what it means, in the same voice. Keep each line's meaning
and its place in the story, keep every symbol and term it names (in the same order), and add no new numbers,
names or facts. The first line stays a hook of at most 28 words; no line is longer than 55 words.
Lines (JSON): {lines}
Reply with JSON: {{"lines": [exactly {n} strings, in the same order]}}"""
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


def join_pause(first: str, second: str, pause: float, dest: str) -> float:
    """first, then `pause` seconds of silence, then second, as one clip at the voice's own format (so
    mp3_seconds holds); returns the second the second part starts."""
    mono = "aresample=24000,aformat=channel_layouts=mono"
    ffmpeg(["-i", first, "-f", "lavfi", "-t", f"{pause:.2f}", "-i", "anullsrc=r=24000:cl=mono", "-i", second,
            "-filter_complex", f"[0:a]{mono}[a];[2:a]{mono}[c];[a][1:a][c]concat=n=3:v=0:a=1[out]", "-map", "[out]",
            "-ac", "1", "-ar", "24000", "-b:a", "48k", dest])
    return mp3_seconds(first) + pause


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


LONG_SCALE = "1.3333333333333333"   # 1920x1080 layout rendered at 2560x1440: YouTube streams 1440p uploads at a
                                    # far higher bitrate, so text, formulas and thin lines stay crisp


QUALITY = ["--muted", "--crf=16", "--x264-preset=slow", "--jpeg-quality=100"]   # quality over speed
CHUNK_FRAMES = 2700       # one render machine's share of a long video (90 s of video, ~40 min of rendering)
SOUNDTRACK = "soundtrack_en.mp3"


def render(composition: str, props: str, soundtrack: str, dest: str, log: Callable[[str], None]) -> None:
    """Render the pictures silently, then put the soundtrack on: rendering with audio attached is three to
    four times slower in Remotion. Quality over speed: full-quality frames, low CRF, slow preset."""
    silent = dest + ".silent.mp4"
    scale = [f"--scale={LONG_SCALE}"] if composition == "Long" else []
    remotion(["render", "src/index.jsx", composition, silent, f"--props={props}", *QUALITY, *scale], log,
             timeout=5 * 3600)
    ffmpeg(["-i", silent, "-i", soundtrack, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
            "-b:a", "192k", "-shortest", "-movflags", "+faststart", dest])
    os.remove(silent)


def render_parts(total: int) -> List[tuple]:
    """A long video's frame ranges, one per render machine (inclusive, as Remotion's --frames takes them)."""
    n = max(1, math.ceil(total / CHUNK_FRAMES))
    size = math.ceil(total / n)
    return [(k * size, min(total, (k + 1) * size) - 1) for k in range(n)]


def part_args(first: int, last: int, dest: str) -> List[str]:
    """The Remotion command for one part, run in the video app with the job folder in public/job."""
    return ["render", "src/index.jsx", "Long", dest, "--props=public/job/long.json", f"--frames={first}-{last}",
            *QUALITY, f"--scale={LONG_SCALE}", "--log=error", "--timeout=120000"]


def join_parts(parts: List[str], soundtrack: str, dest: str) -> None:
    """The long video from its separately rendered parts (same encoder settings, each starting on a key frame,
    so they join without re-encoding), with the soundtrack laid on."""
    listing = dest + ".parts.txt"
    with open(listing, "w", encoding="utf-8") as f:
        f.write("".join(f"file '{os.path.abspath(p)}'\n" for p in parts))
    ffmpeg(["-f", "concat", "-safe", "0", "-i", listing, "-i", soundtrack, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", dest], timeout=3600)
    os.remove(listing)


def crop_to_content(path: str, bg: str, margin: float = 0.05) -> Optional[float]:
    """Cut a clean frame down to what is drawn on it: on a transparent frame everything clearly opaque, otherwise
    everything that differs clearly from the background."""
    try:
        from PIL import Image
        import numpy as np
        im = Image.open(path)
        if im.mode in ("RGBA", "LA") and im.getchannel("A").getextrema()[0] < 128:
            im = im.convert("RGBA")
            mask = np.asarray(im.getchannel("A")).astype(int) > 60
        else:
            im = im.convert("RGB")
            a = np.asarray(im).astype(int)
            ref = np.array([int(bg[i:i + 2], 16) for i in (1, 3, 5)])
            mask = np.abs(a - ref).max(axis=2) > 48
        ys, xs = np.nonzero(mask)
        if len(xs) < 50:
            return None
        h, w = mask.shape
        x0, x1 = np.percentile(xs, [0.5, 99.5]).astype(int)
        y0, y1 = np.percentile(ys, [0.5, 99.5]).astype(int)
        mx, my = int((x1 - x0) * margin) + 10, int((y1 - y0) * margin) + 10
        box = (max(0, x0 - mx), max(0, y0 - my), min(w, x1 + mx), min(h, y1 + my))
        im.crop(box).save(path)
        return (box[2] - box[0]) / max(1, box[3] - box[1])
    except (OSError, ValueError, ImportError):
        pass
    return None


def subscribe_at(starts: List[int], kinds: List[str], total: int) -> Optional[int]:
    """The frame the subscribe card appears in the long video: a second into the first shot that starts after
    about 30% of the video (so it lands on a settled picture, never on a cut), and never in the outro."""
    if total < 40 * FPS:
        return None
    for st, kind in zip(starts, kinds):
        if st >= total * 0.3 and kind != "outro" and st + 30 + 150 < total:
            return st + 30
    return None


HERO_ORDER = ("surface", "graph", "equation", "derive", "plot", "diagram", "bars", "line", "donut", "compare", "kpis", "stat", "map")


def hero_shot(scenes: List[dict], starts: List[int]) -> Optional[int]:
    """The frame of the video's strongest visual for the thumbnail: a graph, formula or chart fully built (just
    before the shot ends), or a motion graphic; None if the video has neither."""
    best = None
    for i, s in enumerate(scenes):
        kind = "diagram" if s.get("diagram") else s["kind"]
        rank = HERO_ORDER.index(kind) if kind in HERO_ORDER else (len(HERO_ORDER) if s.get("graphic") and
                                                                  s["graphic"]["type"] != "kinetic" else None)
        if rank is not None and (best is None or rank < best[0]):
            best = (rank, i)
    if best is None:
        return None
    i = best[1]
    return starts[i] + max(1, scenes[i]["frames"] - TRANSITION - 12)


def country_names() -> Dict[str, str]:
    try:
        with open(ATLAS, encoding="utf-8") as f:
            atlas = json.load(f)
        return {g["properties"]["name"].lower(): g["properties"]["name"]
                for g in atlas["objects"]["countries"]["geometries"]}
    except (OSError, ValueError, KeyError):
        return {}


_UNITS = {w: k for k, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                                       "fourteen fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * k for k, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if k > 1}
_SCALES = {"hundred": 100, "thousand": 1000, "million": 1_000_000}


def spelled_numbers(text: str) -> List[str]:
    """Numbers said in words, as digits: "forty" -> "40", "six hundred and fifty" -> "650"."""
    out, total, cur, on = [], 0, 0, False
    for w in re.findall(r"[a-z]+", (text or "").lower().replace("-", " ")) + ["."]:
        if w in _UNITS or w in _TENS:
            cur, on = cur + _UNITS.get(w, _TENS.get(w, 0)), True
        elif w in _SCALES and on:
            if _SCALES[w] == 100:
                cur *= 100
            else:
                total, cur = total + cur * _SCALES[w], 0
        elif w == "and" and on:
            continue
        elif on:
            out.append(str(total + cur))
            total, cur, on = 0, 0, False
    return out


def _verified(text: str, allowed: str) -> bool:
    """Every number in `text` appears in the verified material (written in digits or said in words)."""
    flat = allowed.replace(",", "")
    digits = re.findall(r"\d[\d,.]*", text or "")
    if digits and not all(d.rstrip(".").replace(",", "") in flat for d in digits):
        flat += " " + " ".join(spelled_numbers(allowed))
    return all(d.rstrip(".").replace(",", "") in flat for d in digits)


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


PERSONA = re.compile(r"\b(I'?m|I am) (in|at|sitting|standing|back in)\b|\bmy (lab|garage|desk|office|kitchen|notebook|"
                     r"students?|class(room)?|studio|workshop|career|job|years)\b|\bwhen I was\b|\bI remember\b|"
                     r"\bI'?ve (spent|worked|taught|been teaching)\b|\bin my (years|career|experience|work)\b", re.I)


def strip_persona(text: str) -> str:
    """Drop every sentence in which the narrator claims a life it does not have (a lab, a career, students)."""
    return " ".join(s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s and not PERSONA.search(s))


def maths_shown(scene: dict) -> str:
    """Everything mathematical a shot shows on screen (its numbers may be spoken in its narration)."""
    bits = [p["tex"] for p in scene.get("parts", [])] + [st["tex"] for st in scene.get("steps", [])]
    bits += [c["fn"] + " " + c.get("tex", "") for c in (scene.get("graph") or {}).get("curves", [])]
    if scene.get("surface"):
        bits.append(scene["surface"]["fn"] + " " + scene["surface"].get("tex", ""))
    if scene["kind"] == "check":
        bits += [scene["question"], scene["why"], *scene["options"]]
    return " ".join(bits)


def _plain(tex: str) -> str:
    """TeX arithmetic as plain maths (a TeX fraction becomes ((a)/(b)), a TeX dot or times becomes *), for
    checking worked examples."""
    t = re.sub(r"\\(left|right|,|;|!|quad|qquad)", " ", tex)
    t = re.sub(r"\\(cdot|times)", "*", t).replace("\\div", "/").replace("\u2212", "-")
    for _ in range(4):
        t = re.sub(r"\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"((\1)/(\2))", t)
    t = t.replace("{", "(").replace("}", ")")
    return re.sub(r"(\d|\))\s*\(", r"\1*(", t)


def arithmetic_ok(lines: List[str]) -> bool:
    """False if any purely numeric step of a worked example is wrong ("2 * 3 + 1 = 8"). Steps with symbols
    are not judged. Allows the rounding a displayed decimal implies."""
    for line in lines:
        sides = re.split(r"=|\\approx", _plain(line))
        approx = "\\approx" in line
        for a, b in zip(sides, sides[1:]):
            a, b = a.strip(), b.strip()
            if not (re.fullmatch(r"[\d.+\-*/^() ]+", a) and re.fullmatch(r"[\d.+\-*/^() ]+", b)
                    and re.search(r"\d", a) and re.search(r"\d", b)):
                continue
            try:
                x, y = mathexpr.compile_expr(a)(0, 0), mathexpr.compile_expr(b)(0, 0)
            except (ValueError, ZeroDivisionError, OverflowError, TypeError):
                continue
            decimals = max((len(d) for d in re.findall(r"\.(\d+)", b)), default=0)
            slack = 0.5 * 10 ** -decimals + 1e-9 + (0.02 * abs(y) if approx else 0)
            if not (isinstance(x, float) and isinstance(y, float)) or abs(x - y) > slack:
                return False
    return True


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
    elif kind == "diagram":
        out["picture"] = words(sc.get("picture"), 40)
    elif kind == "steps":
        out["items"] = [{"label": words((it or {}).get("label") if isinstance(it, dict) else it, 6)}
                        for it in sc.get("items") or []][:5]
        if len(out["items"]) < 3 or not all(i["label"] and _verified(i["label"], allowed) for i in out["items"]):
            out["kind"], out["items"] = "photo", []
    elif kind == "list":
        out["items"] = [{"label": words((it or {}).get("label") if isinstance(it, dict) else it, 7)}
                        for it in sc.get("items") or []][:3]
        if len(out["items"]) < 3 or not all(i["label"] and _verified(i["label"], allowed) for i in out["items"]):
            out["kind"], out["items"] = "photo", []
    elif kind == "quote":
        q = str(sc.get("quote", "")).strip().strip('"“”')
        speaker = str(sc.get("speaker", ""))
        # a quote is someone's words; a line lifted from an encyclopedia is not a quote (the shot gets a picture)
        if q and len(_norm(q)) > 12 and _norm(q) in quotes and not re.search(r"wiki|encyclop|britannica|dictionary",
                                                                                speaker, re.I):
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
    elif kind == "surface":
        surface = mathexpr.check_surface(sc.get("surface"))
        if surface:
            out["surface"] = surface
            out["xlabel"], out["ylabel"] = words(sc.get("xlabel"), 3) or "x", words(sc.get("ylabel"), 3) or "y"
            out["zlabel"] = words(sc.get("zlabel"), 3) or "z"
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
    elif kind == "check":
        options = [words(o, 7) for o in (sc.get("options") or [])[:4] if words(o, 7)]
        try:
            answer = int(sc.get("answer"))
        except (TypeError, ValueError):
            answer = -1
        out.update(question=words(sc.get("question"), 16), options=options, answer=answer, why=words(sc.get("why"), 12))
        if not out["question"] or len(options) < 2 or not 0 <= answer < len(options):
            out["kind"] = "photo"
    elif kind == "chapter" and not out["headline"]:
        out["kind"] = "photo"
    if out["kind"] in ("derive", "equation") and not arithmetic_ok(
            [st["tex"] for st in out.get("steps", [])] + [" ".join(p["tex"] for p in out.get("parts", []))]):
        out["kind"] = "photo"             # a worked example with wrong arithmetic is worse than none
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


def lesson_text(lesson: Optional[dict]) -> str:
    """Where this video sits in its course (empty for a standalone video)."""
    if not lesson:
        return ""
    before = "; ".join(f"{p['title']} ({', '.join(p.get('key_ideas', [])[:3])})" for p in lesson.get("previous", [])[-3:])
    nxt = lesson.get("next") or ""
    return LESSON.format(number=lesson.get("number", 1), total=lesson.get("total", 1), course=lesson.get("course", ""),
                         module=f", module \"{lesson['module']}\"" if lesson.get("module") else "",
                         goal=lesson.get("goal", ""), ideas="; ".join(lesson.get("key_ideas", [])) or "-",
                         visuals="; ".join(lesson.get("visuals", [])) or "-", before=before or "nothing yet, this is the start",
                         after=f'The last shot before the outro says the next lesson is "{nxt}".' if nxt
                         else "This is the last lesson: close the whole course.")


def shape_prompt(brief: dict, style: str, title: str, facts: str, lesson: Optional[dict] = None) -> tuple:
    """The writer's brief: the style's voice plus the plan made for this subject (braces escaped for the
    script prompt), and the number of shots that fits the planned length."""
    acts = "; ".join(f"{a['title']} ({a['job']})" for a in brief["acts"])
    minutes = brief["minutes"]
    text = SHAPE.format(persona=STYLES[style], minutes=f"{minutes:g}", title=title, facts=facts, acts=acts,
                        narrator=brief["narrator"], device=brief["device"],
                        structure=brief["structure"], opening=brief["opening"], ending=brief["ending"],
                        tone=brief["tone"])
    if brief.get("maths"):
        text += MATHS_RULES
    if style == "education":
        text += TEACHING + VOICE.replace("[examples]", brief.get("examples") or "everyday situations the viewer knows")
    text += lesson_text(lesson)
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
        minutes = min(12.0, max(2.0, float(raw.get("minutes", 9 if style == "education" else 4))))
    except (TypeError, ValueError):
        minutes = 9.0 if style == "education" else 4.0

    def s(k, d):
        return str(raw.get(k) or d)[:300]
    narrator = s("narrator", "a curious guide who works things out alongside the viewer.")
    if style == "education" and not re.search(r"sarcas|deadpan|dry wit|wry", narrator, re.I):
        narrator = narrator.rstrip(". ") + ". Dry, deadpan and sarcastic in tone, but warm."    # the lesson voice
    return {"style": style, "acts": acts[:5] or [{"title": "The story", "job": "tell it from start to finish"}],
            "structure": s("structure", "whatever shape makes this subject clearest"),
            "opening": s("opening", "a question or a surprising fact the viewer already half-wonders about."),
            "ending": s("ending", "answer the opening question in one sentence."),
            "tone": s("tone", "clear, curious, warm"), "mood": s("mood", ""), "minutes": minutes,
            "narrator": narrator,
            "device": s("device", "one running example that grows with every shot."),
            "examples": s("examples", "an everyday situation the viewer has lived, chosen for this subject"),
            "maths": bool(raw.get("maths"))}


def on_screen(scene: dict) -> List[str]:
    """The words a scene shows, in a fixed order (so a translation can be put back in place)."""
    return ([scene["headline"], scene["kicker"], scene["label"], scene.get("quote", "")] +
            [i["label"] for i in scene.get("items", [])] + [e["label"] for e in scene.get("events", [])] +
            graphics.labels(scene.get("graphic")) + [p["label"] for p in scene.get("parts", [])] +
            [st["note"] for st in scene.get("steps", [])] + diagram.texts(scene.get("diagram")) +
            ([scene["question"], scene["why"], *scene["options"]] if scene["kind"] == "check" else []) +
            ([scene["xlabel"], scene["ylabel"]] if scene["kind"] in ("plot", "graph", "surface") else []) +
            ([scene["zlabel"]] if scene["kind"] == "surface" else []))


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
    if s.get("diagram"):
        rest = diagram.retext(s["diagram"], rest)
    if s["kind"] == "check":
        s["question"], s["why"] = rest[:2]
        s["options"], rest = rest[2:2 + len(s["options"])], rest[2 + len(s["options"]):]
    if s["kind"] in ("plot", "graph", "surface"):
        s["xlabel"], s["ylabel"] = rest[:2]
        if s["kind"] == "surface":
            s["zlabel"] = rest[2]
    s["highlight"] = ""          # the marked word cannot be matched across languages
    s.pop("chapter", None)       # act titles belong to the long video
    return s


class VideoMaker:
    def __init__(self, settings: Settings, llm: Optional[LLMClient] = None, log: Callable[[str], None] = print):
        self.s = settings
        self.llm = llm or LLMClient(settings, log)
        self.log = log

    # ---- script ---------------------------------------------------------------------------------------
    def brief(self, title: str, facts: List[dict], style: str, lesson: Optional[dict] = None) -> dict:
        """Plan this video's own shape (structure, parts, opening, ending, tone, mood) before writing it. A course
        lesson brings its goal, what it must cover and its planned length."""
        short = "\n".join(f"- {f['claim'][:160]}" for f in facts[:30]) + lesson_text(lesson)
        rule = "pick the style that suits this subject best" if style not in VIDEO_STYLES else f'keep "{style}"'
        try:
            raw = self.llm.complete_json(BRIEF_PROMPT.format(title=title, style=style, facts=short, style_rule=rule,
                                                             styles=", ".join(VIDEO_STYLES)),
                                         max_tokens=1500, temperature=0.9)
        except LLMError as exc:
            self.log(f"[video] no plan from the model ({exc}); writing without one")
            raw = {}
        b = check_brief(raw, style)
        if lesson and lesson.get("minutes"):
            b["minutes"] = min(12.0, max(6.0, float(lesson["minutes"])))
            b["maths"] = b["maths"] or bool(lesson.get("maths"))
        self.log(f"[video] plan ({b['style']}, {b['minutes']:g} min{', maths' if b['maths'] else ''}): "
                 f"{b['structure'][:140]} | {' / '.join(a['title'] for a in b['acts'])}")
        self.log(f"[video] narrator: {b['narrator'][:140]} | device: {b['device'][:140]}")
        return b

    def long_plan(self, rules: str, brief: dict, words_needed: int) -> Optional[dict]:
        """A long video written part by part: an outline of the whole video first, then each part in its own
        request (one request for 10 minutes comes back far too short). The Short is picked later, from the
        finished shots. None if no outline came back."""
        n_shots = round(brief["minutes"] * 7)
        try:
            outline = self.llm.complete_json(rules + fill(OUTLINE, minutes=f"{brief['minutes']:g}", words=words_needed,
                                                          shots=n_shots), max_tokens=6000, temperature=0.6)
        except LLMError as exc:
            self.log(f"[video] no outline ({str(exc)[:80]}); writing in one go")
            return None
        parts = [p for p in (outline.get("parts") or [] if isinstance(outline, dict) else [])
                 if isinstance(p, dict) and isinstance(p.get("beats"), list) and p["beats"]]
        if not parts:
            return None
        total = sum(len(p["beats"]) for p in parts)
        listing = "\n".join(f"{k + 1}. {p.get('title', '')}: " + " | ".join(str(b) for b in p["beats"])
                             for k, p in enumerate(parts))
        if total < n_shots * 0.75:
            self.log(f"[video] the outline has {total} beats for about {n_shots} shots: each part is written longer")
        scenes = []
        words_of = lambda shots: sum(len(str(s.get("narration", "")).split()) for s in shots)      # noqa: E731
        for k, part in enumerate(parts):
            beats = [str(b) for b in part["beats"]][:16]
            name = " ".join(str(part.get("title") or f"Part {k + 1}").split()[:4])
            # the part's share of the planned length, however thin its outline: a beat may need several shots
            lo = max(len(beats), round(n_shots * len(beats) / total))
            target = round(words_needed * len(beats) / total)
            ask = rules + fill(ACT, outline=listing, k=k + 1, n=len(parts), title=name,
                               beats="\n".join(f"- {b}" for b in beats), lo=lo, hi=lo + max(3, lo // 3),
                               words=target,
                               first='Its first shot is the opening (see "Opening") and has "act": "".' if k == 0 else
                               f'Its first shot has "act": "{name}"; every other shot has "act": "".',
                               prev=f'The part before ended with: "{scenes[-1].get("narration", "")}"' if scenes else "")
            got, note = [], ""
            for _ in range(3):            # a part that comes back empty or far too short is asked for again
                try:
                    reply = self.llm.complete_json(ask + note, max_tokens=8000, temperature=0.7)
                except LLMError:
                    continue
                new = [sc for sc in (reply.get("scenes") if isinstance(reply, dict) else reply) or []
                       if isinstance(sc, dict) and str(sc.get("narration", "")).strip()]
                if words_of(new) > words_of(got):
                    got = new
                if len(got) >= lo * 0.75 and words_of(got) >= target * 0.75:
                    break
                if got:
                    note = (f"\n\nYour last version of this part was far too short: {len(got)} shots and "
                            f"{words_of(got)} words. Write {lo} to {lo + max(3, lo // 3)} shots and about {target} "
                            "words: split each beat into several shots, one sentence and one picture each.")
            if got and k:
                got[0]["act"] = name
            scenes += got
            self.log(f"[video] part {k + 1}/{len(parts)} \"{name}\": {len(got)} shots, "
                     f"{sum(len(str(s['narration']).split()) for s in got)} words")
        if len(scenes) < 5:
            return None
        return {**{k: outline[k] for k in ("title", "thumb_text", "thumb_highlight", "description", "tags", "outro")
                   if outline.get(k) is not None}, "scenes": scenes, "short": None}     # a missing field is left out

    def pick_short(self, scenes: List[dict], allowed: str) -> List[dict]:
        """The Short's beats, chosen from the finished shots (their index is final, so the pictures match)."""
        rows = "\n".join(f"{i} | {s['kind']} | {s['narration'][:140]}" for i, s in enumerate(scenes))
        try:
            reply = self.llm.complete_json(fill(SHORT_PICK, rows=rows), max_tokens=1500, temperature=0.5)
        except LLMError:
            reply = {}
        beats = []
        for item in (reply.get("short") if isinstance(reply, dict) else None) or []:
            idx = item.get("scene") if isinstance(item, dict) else None
            text = strip_unsupported_numbers(str((item or {}).get("narration", "")).strip(), allowed)
            if isinstance(idx, int) and 0 <= idx < len(scenes) and text:
                beats.append({"scene": idx, "narration": text})
        return beats[:5]

    def script(self, title: str, facts: List[dict], sources: List[dict], style: str = "news",
               brief: Optional[dict] = None, report: bool = False, lesson: Optional[dict] = None) -> dict:
        """report: a full report is for sale and linked; otherwise the outro points to the sources only.
        lesson: this video's place in a course (its goal, what it covers, what came before and after)."""
        lines = []
        for i, f in enumerate(facts, 1):
            src = sources[int(f["source"]) - 1] if str(f.get("source", "")).isdigit() else {}
            lines.append(f"{i}. [{domain(src.get('url', ''))}] {f['claim']} | \"{f.get('quote', '')[:240]}\"")
        brief = brief or check_brief({}, style)
        shape, shots = shape_prompt(brief, brief["style"], title, "\n".join(lines), lesson)
        prompt = SCRIPT_PROMPT.replace("{shape}", shape).replace("{shots}", shots).replace(
            "{outro_ask}", "the full report, with every source, is" if report else "every source is").replace(
            "{channel}", self.s.channel_name)
        prompt = prompt.replace("{{", "{").replace("}}", "}")
        words_needed = round(brief["minutes"] * 160)      # the voice speaks ~170 words a minute; pauses take the rest
        plan = None
        if brief["minutes"] >= LONG_MINUTES:
            plan = self.long_plan(prompt.split("\nReturn JSON:")[0], brief, words_needed)
        written_long = plan is not None
        plan = plan or self.llm.complete_json(prompt, max_tokens=12000)
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
        for attempt in range(0 if written_long else 2):   # a one-go draft is rewritten up to twice while short
            notes = []
            if need and maths(plan) < need:
                notes.append(f"it had only {maths(plan)} maths shots; this lesson needs at least {need} \"equation\", "
                             f"\"graph\", \"derive\" or \"plot\" shots, each with its required fields filled in exactly")
            if spoken_words(plan) < words_needed:
                notes.append(f"its narration was only {spoken_words(plan)} words; the planned {brief['minutes']:g} "
                             f"minutes need at least {words_needed} words, so give each shot a full sentence or two "
                             f"and explain each idea properly")
            if not notes:
                break
            self.log(f"[video] draft {attempt + 1} too thin ({'; '.join(n.split(';')[0] for n in notes)}); "
                     "rewriting the script")
            try:
                again = self.llm.complete_json(prompt + "\n\nIMPORTANT: a draft fell short: " + "; and ".join(notes)
                                               + ".", max_tokens=14000)
            except LLMError:
                again = {}
            if score(again) > score(plan) and len((again or {}).get("scenes") or []) >= 5:
                plan = again
        if spoken_words(plan) < words_needed * 0.9:        # still short: the same shots, each explained more
            plan = self.expand(plan, words_needed)
        scenes, act, acts = [], "", 0
        for sc in plan.get("scenes", [])[:MAX_SCENES]:
            if not isinstance(sc, dict):
                continue
            if sc.get("kind") == "chapter":        # an old-style title shot becomes the next shot's act sting
                act = str(sc.get("headline") or "")
                continue
            act = str(sc.get("act") or "").strip() or act
            scene = check_scene(sc, allowed, quotes, countries)
            # a fact's number must be in the research; a worked example's numbers must be on screen in the shot
            narration = strip_persona(strip_unsupported_numbers(speakable(str(sc.get("narration", "")).strip()),
                                                                f"{allowed} {maths_shown(scene)}"))
            if not narration:
                continue
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
                    (sc.get("graph") or {}).get("curves", []) + [sc.get("surface") or {"tex": ""}] if p["tex"]]
        bad = typeset_errors([t for sc in scenes for t in texs(sc)])
        for sc in scenes:             # a formula KaTeX cannot typeset turns the shot into a plain one
            if any(t in bad for t in texs(sc)):
                self.log(f"[video] formula skipped ({sc['kind']}): {' | '.join(texs(sc))[:100]}")
                sc["kind"], sc["parts"], sc["steps"] = "photo", [], []
                sc.pop("graph", None)
                sc.pop("surface", None)
        scenes[0]["kind"] = "hook" if scenes[0]["kind"] in ("photo", "hook", "stat") else scenes[0]["kind"]
        outro = strip_persona(strip_unsupported_numbers(str(plan.get("outro") or "").strip(), allowed))
        if not 8 <= len(outro.split()) <= 60 or (not report and "report" in outro.lower()):
            outro = (OUTRO if report else OUTRO_SOURCES).format(facts=len(facts), channel=self.s.channel_name)
        scenes.append({"kind": "outro", "narration": outro, "kicker": "Full report below" if report else "Sources below",
                       "card": "Documentary report" if report else "Checked facts", "channel": self.s.channel_name,
                       "headline": str(plan.get("thumb_text") or title)[:40],
                       "highlight": "report" if report else "sources",
                       "label": f"{len(facts)} verified facts · {len(sources)} sources", "number": "", "items": [],
                       "events": [], "countries": [], "quote": "", "speaker": "", "source": "", "subjects": []})
        if plan.get("short") is None:      # a long video's Short is picked from its finished shots
            plan["short"] = self.pick_short(scenes[:-1], allowed)
        short = []
        for item in plan.get("short", [])[:5]:
            idx = item.get("scene")
            text = strip_unsupported_numbers(str(item.get("narration", "")).strip(), allowed)
            if isinstance(idx, int) and 0 <= idx < len(scenes) - 1 and text:
                short.append({"scene": idx, "narration": text})
        short = short or [{"scene": 0, "narration": scenes[0]["narration"]}]
        short.append({"scene": len(scenes) - 1, "narration": SHORT_OUTRO.format(channel=self.s.channel_name)})
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
    def make(self, run_dir: str, email: bool = True, style: str = "", lesson: Optional[dict] = None) -> Dict[str, str]:
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
        style = "education" if lesson else style
        brief = self.brief(title, facts, style, lesson)
        plan = self.script(title, facts, sources, brief["style"], brief,
                           report=bool((meta.get("gumroad") or {}).get("url")), lesson=lesson)
        scenes, beats = plan["scenes"], plan["short"]
        theme = design.design(self.llm.complete_json, plan["title"], brief["style"],
                              f"{brief['mood']} {brief['tone']}", self.log)
        self.log(f"[video] {len(scenes)} scenes ({', '.join(s['kind'] for s in scenes)}), Short of {len(beats)} beats")
        self.art_direct(scenes)
        bare = {i for i, s in enumerate(scenes) if s["kind"] in graphics.ELIGIBLE and not s.get("graphic")
                and not s.get("video") and i > 0}
        if brief["style"] in ("education", "concept") and bare:
            self.art_direct(scenes, only=bare)      # in a lesson every idea gets a picture, not just its words
        self.draw_diagrams(scenes, brief, plan["title"])
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
            if sc.get("graphic") or sc.get("diagram") or sc["kind"] in MATH_KINDS:
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
                path = os.path.join(job, f"{lang}_{kind}{idx}.mp3")
                ask = line.find("?") + 1 if kind == "long" and scenes[idx]["kind"] == "check" else 0
                if 0 < ask < len(line.rstrip()):   # a check: question and answer spoken apart, a pause between
                    jobs += [(line[:ask].strip(), VOICES[lang], path[:-4] + "_q.mp3"),
                             (line[ask:].strip(), VOICES[lang], path[:-4] + "_a.mp3")]
                    keys += [(lang, kind, idx, "q"), (lang, kind, idx, "a")]
                    continue
                jobs.append((line, VOICES[lang], path))
                keys.append((lang, kind, idx))
        spoken = {k: v for k, v in zip(keys, speak_all(jobs)) if v is not None}
        with ThreadPoolExecutor(max_workers=6) as pool:
            trimmed = list(pool.map(lambda kv: tighten(jobs[keys.index(kv[0])][2], kv[1]), spoken.items()))
        spoken = dict(zip(spoken, trimmed))
        thinking = {}                     # (lang, shot) -> (second the question ends, second the answer starts)
        for key in [k for k in spoken if len(k) == 4 and k[3] == "q"]:
            lang, kind, idx, _ = key
            q, a = spoken.pop(key), spoken.pop((lang, kind, idx, "a"), None)
            if a is None:
                continue
            try:
                off = join_pause(jobs[keys.index(key)][2], jobs[keys.index((lang, kind, idx, "a"))][2], CHECK_PAUSE,
                                 os.path.join(job, f"{lang}_{kind}{idx}.mp3"))
            except RuntimeError:
                continue
            spoken[(lang, kind, idx)] = q + [(s + off, e + off, w) for s, e, w in a]
            thinking[(lang, idx)] = (q[-1][1] if q else 0.0, off)
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
                                                      FPS, LEAD),
                        "diagram": diagram.timed(s.get("diagram"), spoken.get(("en", "long", i), []), frames[i], FPS, LEAD),
                        **({"think": LEAD + round(thinking.get(("en", i), (frames[i] * 0.4 / FPS, 0))[0] * FPS),
                            "reveal": LEAD + round(thinking.get(("en", i), (0, frames[i] * 0.6 / FPS))[1] * FPS)}
                           if s["kind"] == "check" else {})}
                       for i, s in enumerate(scenes)]
        # every diagram is rendered, looked at, corrected and kept only if it is good
        self.polish_diagrams(scenes, long_scenes, spoken, theme, job)
        # the English captions are part of the picture: short lines, timed to the spoken words
        long_captions = []
        for i in range(n_long):
            for ca, cz, line in word_lines(spoken.get(("en", "long", i), []), 0, 42):
                long_captions.append({"from": starts[i] + LEAD + round(ca * FPS),
                                      "to": starts[i] + LEAD + round(cz * FPS), "text": line})
        props = os.path.join(job, "long.json")
        with open(props, "w", encoding="utf-8") as f:
            sub = subscribe_at(starts, [s["kind"] for s in scenes], total)
            json.dump({"scenes": long_scenes, "captions": long_captions, "channel": self.s.channel_name, "theme": theme,
                       "thumbText": plan["thumb_text"], "thumbHighlight": plan["thumb_highlight"],
                       "subscribe": {"at": sub, "name": self.s.channel_name} if sub is not None else None},
                      f, ensure_ascii=False)
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
        files["long_video_en.mp4"] = "video"
        thumb_props = props
        hero = hero_shot(long_scenes, starts)
        if hero is not None:              # a clean frame (no headline, captions or badge) of the best visual
            clean = os.path.join(job, "hero.json")
            with open(props, encoding="utf-8") as f:
                p = json.load(f)
            with open(clean, "w", encoding="utf-8") as f:
                json.dump({**p, "captions": [], "clean": True}, f, ensure_ascii=False)
            try:
                hero_png = os.path.join(VIDEO_APP, "public", "job", "hero.png")
                remotion(["still", "src/index.jsx", "Long", hero_png, f"--props={clean}", f"--frame={hero}",
                          f"--scale={LONG_SCALE}", "--image-format=png"], self.log)
                aspect = crop_to_content(hero_png, theme["bg"]) or 1.8
                thumb_props = os.path.join(job, "thumb.json")
                with open(thumb_props, "w", encoding="utf-8") as f:
                    json.dump({**p, "hero": "job/hero.png", "heroAspect": round(aspect, 3)}, f, ensure_ascii=False)
            except RuntimeError:
                pass
        remotion(["still", "src/index.jsx", "Thumb", os.path.join(out, "thumbnail.png"), f"--props={thumb_props}",
                  "--jpeg-quality=100"], self.log)
        files["thumbnail.png"] = "thumbnail"

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
                short_scenes.append({**{k: v for k, v in visual.items() if k != "diagram"}, "frames": fr[j]})
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

        # everything the last stage needs, so it can run here or on another machine after a farmed render
        shutil.copy(os.path.join(job, "long_en.mp3"), os.path.join(out, SOUNDTRACK))
        state = {"run_dir": os.path.abspath(run_dir), "files": files, "plan": plan, "texts": texts, "credits": credits,
                 "n_lines": n_long + n_short + sum(per_beat), "product": (meta.get("gumroad") or {}).get("url", ""),
                 "meta": meta, "sources": sources, "email": email, "total": total, "t0": t0, "lesson": lesson}
        with open(os.path.join(out, "finish.json"), "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
        parts = render_parts(total)
        if os.environ.get("RENDER_FARM") and len(parts) > 1:
            plan_file = {"total": total, "parts": [{"frames": f"{a}-{b}", "args": part_args(a, b, f"parts/part{k:02d}.mp4")}
                                                   for k, (a, b) in enumerate(parts)]}
            with open(os.path.join(job, "render_plan.json"), "w", encoding="utf-8") as f:
                json.dump(plan_file, f)
            self.log(f"[video] the long video ({total / FPS:.0f}s) renders on {len(parts)} machines in parallel; "
                     "the rest follows when they finish")
            return {}
        self.log(f"[video] rendering the long video ({total / FPS:.0f}s)")
        render("Long", props, os.path.join(out, SOUNDTRACK), os.path.join(out, "long_video_en.mp4"), self.log)
        return self.finish(out)

    def finish(self, out: str) -> Dict[str, str]:
        """The last stage: the long video joined from its parts (when several machines rendered it), the quality
        check, the posting guide and the delivery."""
        with open(os.path.join(out, "finish.json"), encoding="utf-8") as f:
            st = json.load(f)
        dest = os.path.join(out, "long_video_en.mp4")
        parts = sorted(glob.glob(os.path.join(out, "parts", "part*.mp4")))
        if not os.path.exists(dest) and parts:
            self.log(f"[video] joining the {len(parts)} rendered parts")
            join_parts(parts, os.path.join(out, SOUNDTRACK), dest)
        if not os.path.exists(dest):
            raise RuntimeError("the long video was not rendered")
        files, plan, texts = st["files"], st["plan"], st["texts"]
        self.log("[video] quality check (contact sheet + stillness)")
        try:
            verdict = review(self.s, dest, st["total"] / FPS, os.path.join(out, "contact_sheet.jpg"))
        except Exception as exc:          # the check must never cost the videos
            verdict = {}
            self.log(f"[video] quality check failed: {type(exc).__name__}: {str(exc)[:120]}")
        if os.path.exists(os.path.join(out, "contact_sheet.jpg")):
            files["contact_sheet.jpg"] = "review"
        self.log("[video] " + summary(verdict).replace("\n", "\n[video] "))
        with open(os.path.join(out, "posting_guide.txt"), "w", encoding="utf-8") as f:
            f.write(summary(verdict) + "\n\n" + posting_guide(plan, texts, st["n_lines"], st["credits"], st["product"],
                                                                st["meta"], st["sources"], st.get("lesson")))
        with open(os.path.join(out, "video_script.json"), "w", encoding="utf-8") as f:
            json.dump({"plan": plan, "texts": texts, "credits": st["credits"], "review": verdict}, f, indent=2,
                      ensure_ascii=False)
        for leftover in [SOUNDTRACK, "finish.json"]:
            if os.path.exists(os.path.join(out, leftover)):
                os.remove(os.path.join(out, leftover))
        shutil.rmtree(os.path.join(out, "parts"), ignore_errors=True)
        shutil.rmtree(os.path.join(VIDEO_APP, "public", "job"), ignore_errors=True)
        self.log(f"[video] done in {time.time() - st['t0']:.0f}s: {', '.join(files)}")
        self.deliver(st["run_dir"], out, files, plan, st["email"], verdict)
        return {name: os.path.join(out, name) for name in files}

    def design_json(self, prompt: str, **kw):
        """Diagrams need the strongest model: Gemini Flash first, then the usual providers."""
        reply = gemini_json(self.s, prompt, effort="medium", temperature=0.8, log=self.log)
        return reply if reply is not None else self.llm.complete_json(prompt, max_tokens=8000, temperature=0.8)

    def expand(self, plan: dict, words_needed: int) -> dict:
        """Lengthen a short script line by line (same shots, same meaning, more explanation). A line only changes
        if the new one is longer and not overlong; any failure keeps the script as it was."""
        rows = [sc for sc in plan.get("scenes") or [] if isinstance(sc, dict)]
        lines = [str(sc.get("narration", "")) for sc in rows]
        if not lines:
            return plan
        have = sum(len(t.split()) for t in lines)
        try:
            reply = self.llm.complete_json(EXPAND.format(total=words_needed, have=have, n=len(lines),
                                                         lines=json.dumps(lines, ensure_ascii=False)), max_tokens=8000)
        except LLMError:
            return plan
        new = reply.get("lines") if isinstance(reply, dict) else None
        if not isinstance(new, list) or len(new) != len(lines):
            return plan
        for k, (sc, line) in enumerate(zip(rows, new)):
            line = str(line or "").strip()
            if len(lines[k].split()) < len(line.split()) <= (28 if k == 0 else 60):
                sc["narration"] = line
        after = sum(len(str(sc.get("narration", "")).split()) for sc in rows)
        self.log(f"[video] narration lengthened from {have} to {after} words")
        return plan

    def draw_diagrams(self, scenes: List[dict], brief: dict, title: str) -> None:
        """A bespoke animated diagram for every shot that explains an idea (in news, the shots without a photo or
        a real graphic). Formulas inside are checked with KaTeX."""
        explain = brief["style"] in ("education", "concept", "story")
        idx = [i for i, s in enumerate(scenes) if i > 0 and s["kind"] in graphics.ELIGIBLE and not s.get("video")
               and (explain or not s.get("graphic") or s["graphic"]["type"] == "kinetic")]
        if not idx:
            return
        cap = DIAGRAM_MAX_LONG if brief["minutes"] >= LONG_MINUTES else DIAGRAM_MAX
        if len(idx) > cap:                # the shots the writer asked a picture for first, the rest spread over the video
            asked = [i for i in idx if scenes[i]["kind"] == "diagram"][:cap]
            rest = [i for i in idx if i not in asked]
            room = cap - len(asked)
            idx = sorted(asked + [rest[int(k * len(rest) / room)] for k in range(room)] if room > 0 else asked)
        made = diagram.design(self.design_json, scenes, idx, title, f"{brief['mood']} {brief['tone']}", _verified,
                              tex_complete, self.log)
        bad = typeset_errors([el["tex"] for s in scenes for el in (s.get("diagram") or {}).get("elements", [])
                              if el["type"] == "tex"])
        for s in scenes:
            if s.get("diagram") and bad:
                s["diagram"]["elements"] = [el for el in s["diagram"]["elements"] if el.get("tex") not in bad]
                if len(s["diagram"]["elements"]) < 3:
                    s.pop("diagram")
        self.log(f"[diagram] {made} diagram(s) designed for {len(idx)} idea shot(s)")

    def stills(self, shots: List[tuple], job: str) -> Dict[int, str]:
        """shots: (key, props, frame) -> {key: jpeg path}, all from one bundle and one browser."""
        jobs = [{"props": props, "frame": max(0, frame), "out": os.path.join(job, f"look_{key}.jpg"), "scale": 0.5}
                for key, props, frame in shots]
        path = os.path.join(job, "looks.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(jobs, f, ensure_ascii=False)
        node = shutil.which("node") or shutil.which("node.exe")
        try:
            r = subprocess.run([node, "stills.mjs", path], cwd=VIDEO_APP, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=1800)
            for line in (r.stdout or "").splitlines():
                if line.startswith("failed"):
                    self.log(f"[diagram] preview {line[:200]}")
            if r.returncode and not any(l.startswith(("ok", "failed")) for l in (r.stdout or "").splitlines()):
                self.log(f"[diagram] the preview renderer stopped: {(r.stderr or r.stdout or '')[-300:]}")
        except (OSError, subprocess.SubprocessError, TypeError) as exc:
            self.log(f"[diagram] could not render previews: {type(exc).__name__}")
        return {key: os.path.join(job, f"look_{key}.jpg") for key, _, _ in shots
                if os.path.exists(os.path.join(job, f"look_{key}.jpg"))}

    def polish_diagrams(self, scenes: List[dict], long_scenes: List[dict], spoken: dict, theme: dict, job: str,
                        rounds: int = 3) -> None:
        """Render each diagram's last frame, let the vision model judge it against its sentence and correct it
        (up to `rounds` times; a correction the checks reject goes back once with the reason), and keep the best
        version only if it scores 7 or more; otherwise the shot falls back to its library graphic or animated type."""
        idx = [i for i, s in enumerate(long_scenes) if s.get("diagram")]
        if not idx:
            return
        best: Dict[int, tuple] = {}
        settled, unrendered = set(), set()
        problems: Dict[int, str] = {}
        words = lambda i: spoken.get(("en", "long", i), [])            # noqa: E731
        for rnd in range(rounds + 1):
            todo = [i for i in idx if i not in settled]
            if not todo:
                break
            looks = self.stills([(i, {"scenes": [{k: v for k, v in long_scenes[i].items() if k != "chapter"}],
                                      "captions": [], "theme": theme}, long_scenes[i]["frames"] - 20) for i in todo], job)
            def review(i: int) -> None:       # one shot's critique and correction; shots run side by side
                if i not in looks:            # it did not draw: it could break the video's render too
                    unrendered.add(i)
                    settled.add(i)
                    return
                with open(looks[i], "rb") as f:
                    image = f.read()
                ask = diagram.refine_prompt(scenes[i], scenes[i]["diagram"], diagram.ICON_LIST)
                reply = gemini_json(self.s, ask, [image], effort="medium", temperature=0.5, log=self.log)
                try:
                    score = float(reply.get("score")) if isinstance(reply, dict) else None
                except (TypeError, ValueError):
                    score = None
                if score is None:             # no verdict: the version that passed the checks stands
                    settled.add(i)
                    return
                if score > best.get(i, (-1.0, None))[0]:
                    best[i] = (score, scenes[i]["diagram"])
                    problems[i] = str((reply or {}).get("problem") or "")[:110] if isinstance(reply, dict) else ""
                if not isinstance(reply, dict) or score >= 9 or rnd == rounds:
                    settled.add(i)
                    return
                why: List[str] = []
                d = diagram.check({"elements": reply.get("elements") or []}, scenes[i], _verified, tex_complete, why)
                if not d and reply.get("elements"):         # one more try, told exactly what the checks refused
                    again = gemini_json(self.s, ask + diagram.RETRY.format(why="; ".join(why[:4])), [image],
                                        effort="medium", temperature=0.4)
                    d = diagram.check({"elements": (again or {}).get("elements") or []} if isinstance(again, dict)
                                      else None, scenes[i], _verified, tex_complete)
                if d and not typeset_errors([el["tex"] for el in d["elements"] if el["type"] == "tex"]):
                    unrendered.discard(i)
                    scenes[i]["diagram"] = d
                    long_scenes[i]["diagram"] = diagram.timed(d, words(i), long_scenes[i]["frames"], FPS, LEAD)
                else:
                    settled.add(i)

            with ThreadPoolExecutor(max_workers=REVIEWERS) as pool:
                list(pool.map(review, todo))
        kept, unreviewed = [], []
        for i in idx:
            if i not in best and i not in unrendered and scenes[i].get("diagram"):
                unreviewed.append(str(i))     # no vision model answered: it passed every check, so it stays
                continue
            score, d = best.get(i, (0.0, None))
            if d is not None and score >= 7:
                scenes[i]["diagram"] = d
                long_scenes[i]["diagram"] = diagram.timed(d, words(i), long_scenes[i]["frames"], FPS, LEAD)
                kept.append(f"{i}:{score:g}")
                continue
            self.log(f"[diagram] shot {i} dropped " + ("(its preview did not render)" if i in unrendered
                                                        else f"at {score:g}/10: {problems.get(i) or 'weak'}"))
            scenes[i].pop("diagram", None)
            long_scenes[i]["diagram"] = None
            if not scenes[i].get("graphic") and not scenes[i].get("images") and not scenes[i].get("video"):
                scenes[i]["graphic"] = {"type": "kinetic", "nodes": []}
                long_scenes[i]["graphic"] = graphics.timed(scenes[i]["graphic"], scenes[i].get("headline", ""), words(i),
                                                           long_scenes[i]["frames"], FPS, LEAD)
        self.log(f"[diagram] kept {len(kept) + len(unreviewed)} of {len(idx)} after review (shot:score {' '.join(kept)})"
                 + (f"; kept unreviewed (no vision model answered): {' '.join(unreviewed)}" if unreviewed else ""))

    def art_direct(self, scenes: List[dict], only: Optional[set] = None) -> None:
        """Motion graphics for the shots without a strong picture; any failure leaves the templates in place.
        only: just these shots, each of which must get a graphic (the second pass for lessons)."""
        try:
            reply = self.llm.complete_json(graphics.prompt(scenes, only), max_tokens=4000, temperature=0.6)
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
                  meta: dict, sources: Optional[List[dict]] = None, lesson: Optional[dict] = None) -> str:
    credit_lines = "\n".join(f"- {c['subject']}: {c['author'] or 'see file page'}, {c['license']}, {c['file']}"
                             for c in credits) or "- none (no photos used)"
    report = f"Full report: {product}\n" if product else ""
    links = list(dict.fromkeys(s.get("url", "") for s in sources or [] if str(s.get("url", "")).startswith("http")))
    listed = "".join(f"- {u}\n" for u in links[:15]) + (f"- and {len(links) - 15} more\n" if len(links) > 15 else "")
    dubbed = [lang for lang in texts if lang != "en"]
    course = (f"COURSE: {lesson['course']} - lesson {lesson['number']} of {lesson['total']}"
              f"{' (module: ' + lesson['module'] + ')' if lesson.get('module') else ''}. Add it to the playlist "
              f"\"{lesson['course']}\" in this position.\n" if lesson else "")
    parts = [f"POSTING GUIDE - {plan['title']}\n", course, "Nothing was posted automatically. Review the videos first.\n",
             "LONG VIDEO (YouTube)",
             "1. YouTube Studio > Create > Upload videos > long_video_en.mp4. Use the English title and description "
             "below and thumbnail.png. English captions are already in the picture; subtitles_en.srt is optional (CC).",
             *(["2. After it is processed: Studio > Subtitles > Add language. For each language: "
                "Audio > Add > upload audio_track_<lang>.mp3; Subtitles > Upload file > subtitles_<lang>.srt; "
                "Title & description > add the translated text below.",
                "3. Viewers then hear the video in their own language from one video and one view count.\n"]
               if dubbed else [""]),
             "SHORTS: upload short_<lang>.mp4 as separate Shorts with that language's title.\n" if dubbed else
             "SHORT: upload short_en.mp4 as a YouTube Short with the title below.\n",
             "Music and sound effects are generated by the pipeline itself: no licence or credit needed.\n"
             "Credits below cover the photos and video clips (Wikimedia Commons, NASA, Pixabay).\n"]
    for lang, lines in texts.items():
        title, desc = lines[n_lines], lines[n_lines + 1]
        parts.append(f"===== {LANGS[lang].upper()} =====\nTitle: {title}\nDescription:\n{desc}\n\n{report}"
                     f"Sources: {meta.get('sources', '?')} sources, {meta.get('verified_facts', '?')} verified facts.\n"
                     f"{listed}"
                     f"Photo and footage credits (required by the licences):\n{credit_lines}\n")
    parts.append("Tags: " + ", ".join(plan["tags"]))
    return "\n".join(parts) + "\n"


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "finish":       # after a farmed render: python -m blogwriter.video finish <out>
        VideoMaker(Settings.from_env()).finish(sys.argv[2])
        sys.exit(0)
    if len(sys.argv) < 2:
        sys.exit("usage: python -m blogwriter.video output/<run folder> [--no-email] [--style=auto|news|story|education|concept]")
    VideoMaker(Settings.from_env()).make(sys.argv[1], email="--no-email" not in sys.argv,
                                         style=next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--style=")), ""))
