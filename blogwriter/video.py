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
import secrets
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
from .footage import CLIP_SECONDS, encoders as footage_encoders, ffmpeg_exe, find_clip, gemini_json, photo_fits
from .llm import LLMClient, LLMError
from .mailer import send_email
from .pricing import label
from . import composer, design, diagram, email_page, graphics, layout, looks, mathexpr, palettes, sfx, vizlib, voicefarm
from .research import domain
from .storage import keep_latest_runs, link_for, put_text, upload_run
from .web import UA
from .writer import LANGS, strip_site_credits, strip_unsupported_numbers

VIDEO_APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "video")
VOICES = {"en": "en-US-BrianMultilingualNeural", "hi": "hi-IN-MadhurNeural", "te": "te-IN-MohanNeural",
          "kn": "kn-IN-GaganNeural", "ta": "ta-IN-ValluvarNeural"}
FPS = 30
TRANSITION = 15           # frames two scenes overlap; must equal TRANSITION in video/src/theme.js
LEAD = 6                  # frames after a shot starts before its narration begins
GAP = 15                  # frames (half a second) of stillness after the narration before the next shot's picture arrives
HOLD = 15                 # extra frames (half a second) held on the last shot of a part before the next part begins
PACE = 0.91               # narration speed (NARRATION_PACE, 0.8 to 1): 1.0 was a little too fast, 0.88 a little slow


def narration_pace() -> float:
    try:
        return max(0.8, min(1.0, float(os.environ.get("NARRATION_PACE") or PACE)))
    except ValueError:
        return PACE
MP3_BYTES_PER_SECOND = 6000   # edge-tts speaks 24 kHz, 48 kbit/s mono MP3
WAV_BYTES_PER_SECOND = 48000  # 24 kHz, 16 bit, mono
SHORT_MAX_SECONDS = 38     # a Short is a thirty second explanation of the whole thing
MAX_TEMPO = 1.3           # a dubbed track may be sped up this much (pitch kept) to fit the English picture
LONG_MINUTES = 6          # from this length a script is written part by part (one request comes back too short)
SHOTS_PER_REQUEST = 14    # the most shots one request is asked to write (asked for 70 at once, a model returns ~18)
MAX_SCENES = 110          # shots in one video
DIAGRAM_MAX = 18          # bespoke diagrams per video (each costs several vision-model calls) ...
DIAGRAM_MAX_LONG = 30     # ... and in a long video, where most shots are pictures of the idea
CHECK_PAUSE = 3.0         # seconds of silence in a "check" shot for the viewer to think before the answer
REVIEWERS = 4             # diagram critiques run side by side (each is a slow vision-model call)
KEEP_SCORE = 5            # a diagram scoring this (of 10) stays: a fair picture of the idea beats words alone
KEEP_VIDEOS = 4           # after every video, only this many newest video folders stay (the new one and the 3 before it); older ones are emptied (PDFs stay)
KINDS = ("hook", "photo", "stat", "compare", "bars", "line", "donut", "kpis", "timeline", "steps", "map", "list",
         "quote", "equation", "plot", "graph", "derive", "surface", "check", "diagram")
MATH_KINDS = ("equation", "plot", "graph", "derive", "surface")   # lesson shots drawn from maths, not facts or photos
PLOTS = ("scatter", "fit", "residuals", "squares", "descent")
# plus vizlib.PLOT_TYPES (15 more plot types) and vizlib.SHOT_KINDS (125 more shot kinds): a shot that picks one
# becomes a "diagram" shot that WANTS that technique, and the diagram designer fills it in (check_scene)
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
  "sound": "3 to 5 words for how the MUSIC under this video should feel, as a composer would say it (e.g. 'slow,
    glassy, quietly hopeful'; 'tense, low, creeping'; 'playful, bouncy, light'): chosen for this subject",
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

Verified facts (number, [the website it was found on: for you only, never said aloud], claim | supporting quote):
{facts}

THE PLAN FOR THIS VIDEO (follow it; it was made for this subject)
- Shape: {structure}
- Parts, in order: {acts}
- Opening: {opening_rule}
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
- HISTORY: viewers care what an idea does for them, not who found it in which year. Do not walk through
  scientists, dates and earlier versions. Give a discovery's importance in one line, in terms of what it lets us do
  ("this is why a small poll can speak for a whole country"), with at most one name and no list of years.
  Tell the history fully only when the subject itself is historical or the idea cannot be understood without it.
- CINEMA: only once the welcome, the definition and why it matters are done, move into a real-life moment of today; raise a question, hold it, then reveal; vary the
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
  line is"). Say what a formula MEANS, the way a teacher would, never symbol by symbol and never "open bracket":
  "Z counts how many standard errors the average sits from the true mean", not "Z equals open bracket X bar
  minus mu close bracket". Never use a technical word (affine, conditional mean, regressor) without saying what it means in the
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
- Spoken style: short sentences, plain words, contrast and stakes. Never say where a fact was found: a website,
  encyclopedia or online course is never named as the one who says something (no "Wikipedia says", no "according
  to GeeksforGeeks"); those are not scholars. State established facts plainly, in the narrator's own voice. Credit
  only a quote, an opinion or a disputed claim, and then to the person, scientist, book or organisation behind it;
  in news, the agency that reported an event may be named ("Reuters reports"). No predictions, opinions, advice or facts that are not listed. Write figures as they are said aloud
  ("115 billion dollars"); on-screen fields keep the short form ("$115B").
- "outro": 1 or 2 closing sentences in this video's own voice that {outro_ask}invite the viewer to subscribe to
  {channel} (say the channel's name). Not a slogan; make it fit the story.

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
{{"title": "YouTube title, max 70 characters, in two parts: the topic's key terms first, as a student would search for them, then a short catchy hook that makes a viewer curious (a question, a surprise, a stake), e.g. 'Mean, Median and Mode: Which Average Is Lying to You?', 'Statistics Explained: Why One Sample Can Fool You'; honest (the video delivers it), no ALL CAPS, no emoji, no fake shock",
  "thumb_text": "3 or 4 words for the thumbnail", "thumb_highlight": "1 word of thumb_text",
  "description": "2 or 3 plain sentences on what the video covers",
  "tags": ["8 to 12 search tags"],
  "scenes": [{{"kind": "...", "narration": "...", "headline": "...", "kicker": "...", "highlight": "...",
              "number": "", "label": "", "items": [], "events": [], "countries": [], "quote": "", "speaker": "",
              "subjects": [], "footage": "", "act": "", "facts": []}}],
  "outro": "...", "short": [{{"scene": scene index, "narration": "..."}}]}}

"short": 4 beats for a vertical Short of 30 seconds that explains the WHOLE story or defines the idea on its own
(not a few parts of it, not a trailer), reusing scenes' visuals by index. Beat 1 stops the scroll in at most 12
words; beat 2 says what it is; beat 3 the one thing that makes it work or matter; beat 4 the takeaway; about 65 words
in all."""

OUTRO = ("That's the short version. The full report has {facts} verified facts, and every source is linked. "
         "It's in the description. And if you want one story like this, researched properly, every day, subscribe "
         "to {channel}.")
OUTRO_SOURCES = ("Every one of the {facts} facts in this video was checked, and every source is linked in the "
                 "description. If you want more like this, explained properly, subscribe to {channel}.")
SHORT_OUTRO = "Full story, with every source, on {channel}."
# DESCRIPTION_REPORT off (the default): the description carries no links, so nothing may point there
OUTRO_PLAIN = "That's the idea, minus the headache. If it finally clicked, subscribe to {channel} for the next one."
SHORT_OUTRO_PLAIN = "The full lesson is on {channel}."
POINTS_DOWN = re.compile(r"\b(description|link(ed|s)?|below|report|sources?)\b", re.I)
# a long video is planned as an outline, then written part by part (placeholders are filled with fill())
OUTLINE = """

THIS IS A LONG VIDEO, so plan it before writing it: about [minutes] minutes, [words] spoken words, [shots] shots.
Break it into the parts of the plan, in order: ONE entry in "parts" for EACH part of the plan (never a single part
for the whole video), and each part into beats. One beat is one thing the viewer SEES and learns (it becomes one or
two shots), written as its shot kind and what it shows, e.g. "graph: the cost as w slides, its lowest point marked"
or "check: which way does w move if the slope is negative?". About [shots] beats in all.
Reply with JSON: {"title": "YouTube title, max 70 characters, in two parts: the topic's key terms first, as a student would search for them, then a short catchy hook that makes a viewer curious (a question, a surprise, a stake), e.g. 'Mean, Median and Mode: Which Average Is Lying to You?', 'Statistics Explained: Why One Sample Can Fool You'; honest (the video delivers it), no ALL CAPS, no emoji, no fake shock",
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
SHORT_PICK = """These are the shots of a video (index | kind | narration). Write a vertical Short of 30 seconds that
EXPLAINS THE WHOLE TOPIC on its own: a viewer who knows nothing must finish it understanding what the thing is and
why it works or matters. It is not a trailer and not a few parts of the video: it is the entire idea in miniature.
Use exactly 4 beats, each reusing the picture of the shot that shows it best:
1. a hook that stops the scroll, at most 12 words (a question or a surprising claim about the topic itself);
2. what it is: a plain definition in one sentence, at most 18 words;
3. the one thing that makes it work, or how it works, at most 22 words (the picture of the mechanism);
4. why it matters or what to remember, at most 14 words.
About 65 words in all, plain words, no names and no dates. Say only what the shots say.
[rows]
Reply with JSON: {"short": [{"scene": index, "narration": "..."}]}"""


def outline_parts(outline) -> List[dict]:
    """The parts of a long video's outline, read leniently: "parts", "acts" or "sections"; beats as a list, a string
    or objects."""
    raw = (outline.get("parts") or outline.get("acts") or outline.get("sections")) if isinstance(outline, dict) \
        else outline if isinstance(outline, list) else None
    parts = []
    for p in raw or []:
        if not isinstance(p, dict):
            continue
        beats = p.get("beats") or p.get("shots") or p.get("points") or p.get("scenes")
        if isinstance(beats, str):
            beats = re.split(r"\s*(?:[;|\n]|\s-\s)\s*", beats)
        if not isinstance(beats, list):
            continue
        beats = [str(b.get("beat") or b.get("text") or b.get("narration") or b.get("what") or "") if isinstance(b, dict)
                 else str(b) for b in beats]
        beats = [b.strip() for b in beats if b and b.strip()]
        if beats:
            parts.append({"title": str(p.get("title") or p.get("name") or ""), "beats": beats})
    return parts


def fill(template: str, **values) -> str:
    """str.format for prompts that also contain JSON braces: [name] placeholders."""
    for k, v in values.items():
        template = template.replace(f"[{k}]", str(v))
    return template
PUNCH = """You are the comedy writer of a science channel whose narrator is dry, deadpan and sarcastic: a teacher who has
heard every wrong answer and finds them all hilarious, warm underneath. These are the narration lines of one lesson,
one per shot, in order. Punch them up so the sarcasm is UNMISTAKABLE when a calm voice reads them aloud.
- About one line in three gets a real joke, written for THAT line: a deadpan aside, ironic understatement, mock
  praise, a jab at the obvious wrong intuition, at jargon or at the subject's scary reputation, an everyday
  absurdity, or a callback to the running example ({examples}). A joke that could sit in any other video is not good
  enough: no catchphrases, no stock lines, never the same joke twice.
  The standard, from a lesson on gravity (do not reuse it): "Drop a hammer and a feather on the Moon and they land
  together. Galileo predicted it four centuries ago. Physics teachers have not stopped bringing it up since."
- Timing: the punchline comes LAST, after a full stop or an ellipsis, and is short (under 12 words).
- The other lines may get a sharper, wittier wording, but stay calm; never two jokes in a row.
- Never mock the viewer, a real person or a group. A joke never replaces the explanation: every line still teaches
  exactly what it taught, in simple everyday words.
- Keep every number, name, symbol and technical term a line has; add no new numbers, names or facts. No line over
  55 words; the first line stays a hook of at most 28 words.
Lines (JSON): {lines}
Reply with JSON: {{"lines": [exactly {n} strings, in the same order]}}"""
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


def audio_seconds(path: str) -> float:
    """How long a narration clip is. Clips are 24 kHz mono WAV (lossless: a 48 kbit MP3 kept after the voice model
    had spoken was measured to leave an error as loud as the speech itself above 3 kHz, which is what hiss is made
    of); an MP3 left by the free voice service is measured by its bitrate."""
    if path.endswith(".wav"):
        try:
            import wave
            with wave.open(path, "rb") as w:
                return w.getnframes() / float(w.getframerate())
        except (wave.Error, EOFError, OSError):
            return os.path.getsize(path) / WAV_BYTES_PER_SECOND
    return os.path.getsize(path) / MP3_BYTES_PER_SECOND


mp3_seconds = audio_seconds           # the old name


async def _speak(text: str, voice: str, path: str, gate: asyncio.Semaphore) -> List[tuple]:
    """Write the narration to `path`; returns its words as (start s, end s, word), so captions and on-screen
    reveals can land on the exact spoken word."""
    import edge_tts
    async with gate:
        for attempt in range(5):           # the free voice service drops connections now and then
            try:
                sentences, audio = [], bytearray()
                stream = edge_tts.Communicate(text, voice, rate=f"{round((narration_pace() - 1) * 100):+d}%" if voice.startswith("en") else "+0%",
                                              boundary="WordBoundary").stream()
                async for chunk in stream:
                    if chunk["type"] == "audio":
                        audio += chunk["data"]
                    elif chunk["type"] == "WordBoundary":
                        start = chunk["offset"] / 1e7
                        sentences.append((start, start + chunk["duration"] / 1e7, chunk["text"]))
                if not audio:
                    raise RuntimeError("no audio returned")
                with open(path + ".src.mp3", "wb") as f:
                    f.write(audio)
                ffmpeg(["-i", path + ".src.mp3", "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", path])
                os.remove(path + ".src.mp3")
                return sentences or [(0.0, len(audio) / MP3_BYTES_PER_SECOND, text)]
            except Exception as exc:
                if attempt == 4:                # one unspeakable line must not sink the whole video
                    print(f"[video] no voice for {text[:60]!r}: {type(exc).__name__}")
                    return None
                await asyncio.sleep(5 * (attempt + 1))


VOICE_SAMPLE_KEY = "voices/narrator.m4a"     # the owner's recording, in the private storage bucket (never in git)
CLONE_TOOL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clone_voice.py")


def align_words(text: str, heard: List[list]) -> List[tuple]:
    """The script's own words, timed by when they were heard (speech recognition can mishear a number or a name;
    the captions keep the exact wording): matched words take their heard times, the rest are spread between."""
    import difflib
    script = text.split()
    if not script or not heard:
        return []
    norm = lambda w: re.sub(r"[^a-z0-9]", "", str(w).lower())          # noqa: E731
    times: List[Optional[tuple]] = [None] * len(script)
    sm = difflib.SequenceMatcher(None, [norm(w) for w in script], [norm(h[2]) for h in heard], autojunk=False)
    for blk in sm.get_matching_blocks():
        for j in range(blk.size):
            times[blk.a + j] = (float(heard[blk.b + j][0]), float(heard[blk.b + j][1]))
    k = 0
    while k < len(script):                # a run of unmatched words shares the time between its neighbours
        if times[k] is not None:
            k += 1
            continue
        end = k
        while end < len(script) and times[end] is None:
            end += 1
        a = times[k - 1][1] if k else float(heard[0][0])
        b = times[end][0] if end < len(script) else float(heard[-1][1])
        step = max(0.0, b - a) / (end - k)
        for j in range(k, end):
            times[j] = (a + step * (j - k), a + step * (j - k + 1))
        k = end
    return [(s, e, w) for (s, e), w in zip(times, script)]


def voice_sample(settings: Settings, job: str, log: Callable[[str], None]) -> Optional[str]:
    """The owner's recording from the private bucket, as 24 kHz mono WAV for the cloning model; None if absent."""
    if not settings.storage_configured:
        return None
    key = os.environ.get("VOICE_SAMPLE_KEY") or VOICE_SAMPLE_KEY
    raw, ref = os.path.join(job, "narrator_sample" + os.path.splitext(key)[1]), os.path.join(job, "narrator_ref.wav")
    try:
        from .storage import _client
        _client(settings).download_file(settings.s3_bucket, key, raw)
        ffmpeg(["-i", raw, "-ac", "1", "-ar", "24000", "-af", "loudnorm=I=-18:TP=-2", ref])
        return ref
    except Exception as exc:                     # no sample, no access: the usual voice speaks
        log(f"[voice] no voice sample at {key} ({type(exc).__name__}): using the standard voice")
        return None
    finally:
        if os.path.exists(raw):
            os.remove(raw)                       # the recording is not kept in the job folder (or its artifacts)


def clone_with_budget(python: str, spec: str, ref: str, texts: List[str], log: Callable[[str], None]) -> bool:
    """Run the cloning tool, watching its progress: once a few lines are done, the time for the whole narration is
    projected from them, and if it would exceed CLONE_BUDGET_MINUTES (default 150) the tool is stopped, so the
    whole video speaks in the standard voice instead (never half one voice and half another). Returns True when
    stopped that way. The measured speed is logged either way."""
    budget = float(os.environ.get("CLONE_BUDGET_MINUTES") or 150) * 60
    total = sum(len(t) for t in texts) or 1
    t0, ready, aborted = time.time(), None, False
    try:
        proc = subprocess.Popen([python, CLONE_TOOL, spec, ref], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace")
    except OSError as exc:
        log(f"[voice] the cloning tool could not run: {type(exc).__name__}")
        return True
    tail: List[str] = []
    for line in proc.stdout:
        tail = (tail + [line.rstrip()])[-6:]
        if line.startswith("[clone] models ready"):
            ready = time.time()
            log(f"[voice] cloning models ready in {ready - t0:.0f}s")
        m = re.match(r"\[clone\] (\d+)/(\d+)", line)
        if m and ready:
            k = int(m.group(1))
            done = sum(len(t) for t in texts[:k]) or 1
            projected = (time.time() - ready) / done * total
            if k >= min(4, len(texts)) and projected > budget:
                log(f"[voice] cloning would take about {projected / 60:.0f} min for {len(texts)} lines (budget "
                    f"{budget / 60:.0f}): the standard voice speaks this video")
                proc.kill()
                aborted = True
                break
    try:
        proc.wait(timeout=60)
    except subprocess.SubprocessError:
        proc.kill()
    if proc.returncode and not aborted:
        log(f"[voice] the cloning tool stopped: {' | '.join(tail)[-400:]}")
    return aborted


def clone_here(python: str, jobs: List[tuple], which: List[int], settings: Settings, job: str,
               log: Callable[[str], None]) -> Optional[Dict[int, dict]]:
    """The lines `which` cloned on this machine (within the time budget). {line: result}; None when the sample is
    missing or the budget stopped it."""
    ref = voice_sample(settings, job, log)
    if not ref:
        return None
    spec = os.path.join(job, "clone_jobs.json")
    try:
        with open(spec, "w", encoding="utf-8") as f:
            json.dump([{"text": jobs[k][0], "out": jobs[k][2][:-4] + ".clone.wav"} for k in which], f, ensure_ascii=False)
        if clone_with_budget(python, spec, ref, [jobs[k][0] for k in which], log):
            return None
        with open(spec, encoding="utf-8") as f:
            return dict(zip(which, json.load(f)))
    except (OSError, ValueError):
        return {}
    finally:
        os.remove(ref)


class Cloned(list):
    """The word timings of a line spoken in the cloned voice: already cut at the line's real edges and verified."""


def slow_down(src: str, dest: str, pace: float) -> None:
    """The line at `pace` of its speed, pitch kept, as lossless 24 kHz mono WAV. Rubber Band (a phase-vocoder stretcher
    made for speech and music) when this ffmpeg has it, else the plainer atempo filter."""
    if abs(pace - 1.0) < 0.005:
        ffmpeg(["-i", src, "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", dest])
        return
    for flt in (f"rubberband=tempo={pace:.4f}:pitch=1.0", f"atempo={pace:.4f}"):
        try:
            ffmpeg(["-i", src, "-ac", "1", "-ar", "24000", "-af", flt, "-c:a", "pcm_s16le", dest])
            return
        except RuntimeError:
            continue
    raise RuntimeError("the pace could not be set")


def speak_cloned(jobs: List[tuple], settings: Settings, job: str, log: Callable[[str], None]) -> List[Optional[list]]:
    """jobs: (text, voice, path). Every line in the owner's cloned voice when NARRATOR_VOICE=clone (the default): on
    the voice farm's parallel machines (voicefarm.py) when that is available, else, or for any chunk the farm did
    not deliver, on this machine (VOICE_PYTHON, within the time budget). A line that fails, or everything when
    cloning cannot be done, is spoken by the standard voice. Returns each line's word timings, like speak_all."""
    results: List[Optional[list]] = [None] * len(jobs)
    python = os.environ.get("VOICE_PYTHON", "")
    if os.environ.get("NARRATOR_VOICE", "clone").strip().lower() == "clone" and jobs:
        t0 = time.time()
        items: Dict[int, dict] = {}
        farmed = voicefarm.clone([t for t, _, _ in jobs], settings, job, log) if voicefarm.available(settings) else None
        if farmed:
            items = {k: it for k, it in enumerate(farmed) if not it.get("missing")}
        left = [k for k in range(len(jobs)) if k not in items]
        if left:
            if not python or not os.path.exists(python):
                log("[voice] the cloning environment is not installed (VOICE_PYTHON): using the standard voice")
            else:
                made = clone_here(python, jobs, left, settings, job, log)
                if made is None:
                    items = {}                       # never half one voice and half another: the standard voice speaks all
                else:
                    items.update(made)
        from . import voicecheck as vc

        def hissy(it) -> bool:
            return float((it.get("checks") or {}).get("hiss", -99.0)) > vc.HISS_MAX

        def rank(it) -> tuple:
            """Lower is better: a hissy take is worse than any clean one (hiss is heard by every viewer, above all
            in a quiz where the music stops), then fewer unsure words, then less hiss."""
            c = it.get("checks") or {}
            return (hissy(it), c.get("bad", 99), float(c.get("hiss", -99.0)))

        weak = [k for k, it in items.items() if it.get("ok") and ((it.get("checks") or {}).get("bad", 0) > 0 or hissy(it))]
        if weak and python and os.path.exists(python):
            # a line whose words the checks could not get right, or that came out hissy, in the usual number of takes:
            # spoken again here, with far more takes, and kept only if it is better (the time does not matter, a
            # missing word or a hiss does)
            log(f"[voice] {len(weak)} line(s) still have words the checks could not get right or hiss "
                f"({sum(hissy(items[k]) for k in weak)} hissy): spoken again with more takes")
            before = os.environ.get("CLONE_TAKES")
            os.environ["CLONE_TAKES"] = "16"
            try:
                again = clone_here(python, jobs, weak, settings, job, log) or {}
            finally:
                if before is None:
                    os.environ.pop("CLONE_TAKES", None)
                else:
                    os.environ["CLONE_TAKES"] = before
            for k, it in again.items():
                if it.get("ok") and rank(it) < rank(items[k]):
                    items[k] = it
            still = sorted(k for k in weak if hissy(items[k]))
            if still:
                log(f"[voice] lines {still} are still hissy after 16 more takes; "
                    "they will be cleaned before mixing")
        checked = [it.get("checks") or {} for it in items.values() if it.get("checks")]
        if checked:
            left = sorted(k for k, it in items.items() if (it.get("checks") or {}).get("bad", 0) > 0)
            log(f"[voice] checked {sum(c.get('takes', 0) for c in checked)} takes for {len(checked)} lines: "
                f"{sum(c.get('mended', 0) for c in checked)} holes or noises mended, "
                f"{sum(c.get('split', 0) for c in checked)} sentences spoken in two halves; "
                + (f"words still unsure in lines {left}" if left else "every line says its script"))
        for k, item in sorted(items.items()):
            text, _, path = jobs[k]
            if not item.get("ok") or not os.path.exists(item.get("out", "")):
                continue
            try:                 # the pipeline's own audio format (24 kHz mono WAV, lossless), at the chosen pace
                pace = narration_pace()
                slow_down(item["out"], path, pace)
                heard = [[a / pace, b / pace, w] for a, b, w in item["words"]]
                aligned = align_words(text, heard)
                results[k] = Cloned(aligned) if aligned else None
            except RuntimeError:
                pass
            finally:
                os.remove(item["out"])
        if items:
            cloned = sum(r is not None for r in results)
            spoken_s = sum(r[-1][1] for r in results if r)
            took = time.time() - t0
            log(f"[voice] {cloned} of {len(jobs)} lines spoken in the owner's voice ({took:.0f}s; "
                f"{spoken_s / max(1.0, took):.2f}x real time)")
    missing = [k for k, r in enumerate(results) if r is None]
    if missing:
        for k, words in zip(missing, speak_all([jobs[k] for k in missing])):
            results[k] = words
    return results


def speak_all(jobs: List[tuple]) -> List[List[tuple]]:
    """jobs: (text, voice, path). Spoken a few at a time, so the free voice service is not hammered."""
    async def run():
        gate = asyncio.Semaphore(3)
        return await asyncio.gather(*(_speak(t, v, p, gate) for t, v, p in jobs))
    return asyncio.run(run())


def tighten(path: str, words: List[tuple]) -> List[tuple]:
    """Cut the voice service's silence before the first word and after the last, so shots follow each other at
    the pace of speech; returns the word timings moved to match. Re-encoded at the service's own bitrate, so
    audio_seconds still holds. A cloned line is already cut at its real edges and verified (clone_voice.py): left alone."""
    if not words or isinstance(words, Cloned):
        return words
    a = max(0.0, words[0][0] - 0.04)
    b = words[-1][1] + 0.30           # a word's tail runs on past the time the recogniser gives it (the cloned voice's
                                      # sentences are already cut where their speech ends, see clone_voice.speech_end)
    tmp = path + ".tmp.wav"
    try:
        ffmpeg(["-ss", f"{a:.3f}", "-i", path, "-t", f"{b - a:.3f}", "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", tmp])
        os.replace(tmp, path)
    except RuntimeError:
        return words
    return [(s - a, e - a, w) for s, e, w in words]


QUIZ_STOP = {"the", "and", "its", "are", "was", "for", "with", "that", "this", "than", "not", "will", "you", "your",
             "one", "all", "has", "have", "into", "from", "gets", "get"}


def answer_moment(words: List[tuple], start: float, scene: dict) -> float:
    """When the right option of a check is actually said: the first word from `start` on that belongs to the right
    option's text (so the answer lights up on the voice, not before it); else `start`, where the answer begins."""
    opts, k = scene.get("options") or [], scene.get("answer")
    if not isinstance(k, int) or not 0 <= k < len(opts):
        return start
    want = {w for w in re.findall(r"[a-z0-9]+", str(opts[k]).lower()) if len(w) > 2 and w not in QUIZ_STOP}
    for s, _, w in words:
        if s >= start - 0.05 and re.sub(r"[^a-z0-9]", "", w.lower()) in want:
            return s
    return start


def check_cues(line: str, words: List[tuple], scene: dict, frames: int) -> dict:
    """think / reveal frames of a check spoken in one clip (the Short): the question ends at the line's last "?",
    the answer shows when the right option is said."""
    ask = line.rfind("?") + 1
    n_q = len(line[:ask].split()) if ask else 0
    if not words or not 0 < n_q < len(words):
        return {"think": round(frames * 0.4), "reveal": round(frames * 0.6)}
    return {"think": LEAD + round(words[n_q - 1][1] * FPS),
            "reveal": LEAD + round(answer_moment(words, words[n_q][0], scene) * FPS)}


def join_pause(first: str, second: str, pause: float, dest: str) -> float:
    """first, then `pause` seconds of silence, then second, as one clip at the voice's own format (so
    mp3_seconds holds); returns the second the second part starts."""
    mono = "aresample=24000,aformat=channel_layouts=mono"
    ffmpeg(["-i", first, "-f", "lavfi", "-t", f"{pause:.2f}", "-i", "anullsrc=r=24000:cl=mono", "-i", second,
            "-filter_complex", f"[0:a]{mono}[a];[2:a]{mono}[c];[a][1:a][c]concat=n=3:v=0:a=1[out]", "-map", "[out]",
            "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", dest])
    return audio_seconds(first) + pause


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
    # a caption stays up a little past its last word: the recogniser's word ends come early, and the last words of a
    # shot were seen to vanish while they were still being said
    return [(offset + l[0][0], offset + l[-1][1] + min(0.22, (lines[k + 1][0][0] - l[-1][1]) if k + 1 < len(lines) else 0.22),
             " ".join(x[2] for x in l)) for k, l in enumerate(lines)]


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
    """A full ffmpeg (the system's with SVT-AV1, else the imageio-ffmpeg wheel's): the one Remotion ships lacks the
    audio filters and modern encoders used here."""
    r = subprocess.run([ffmpeg_exe(), "-hide_banner", "-y", "-v", "error", *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {r.stderr[-600:]}")


# The delivered video's codec. The owner watched the AV1 10-bit 4K files stall (picture and sound stopping and
# starting): most laptops, TVs and browsers cannot decode AV1 in hardware, and in software 4K 10-bit runs at half
# speed. So the default is H.264 High 4:2:0 8-bit, which every device since about 2012 plays from hardware, with a key
# frame every second, a capped bit rate (a player's buffer never starves on a spike) and the index first (starts
# at once). VIDEO_CODEC=av1|hevc forces a smaller file when the playback device is known to cope.
CODECS = {
    "h264": ("libx264", ["-crf", "20", "-pix_fmt", "yuv420p", "-profile:v", "high", "-level:v", "5.1", "-g", "30",
                         "-keyint_min", "30", "-bf", "2", "-maxrate", "30M", "-bufsize", "60M"]),
    "hevc": ("libx265", ["-crf", "20", "-pix_fmt", "yuv420p10le", "-tag:v", "hvc1", "-g", "30",
                         "-x265-params", "log-level=error"]),
    "av1": ("libsvtav1", ["-crf", "28", "-pix_fmt", "yuv420p10le", "-g", "300", "-svtav1-params", "tune=0"]),
}


def final_codec() -> str:
    """H.264 (plays everywhere), or the codec VIDEO_CODEC asks for when this ffmpeg can encode it."""
    have = footage_encoders(ffmpeg_exe())
    wanted = os.environ.get("VIDEO_CODEC", "").strip().lower()
    order = ([wanted] if wanted in CODECS else []) + ["h264", "hevc", "av1"]
    return next((c for c in order if CODECS[c][0] in have), "h264")


def final_encode(video: str, soundtrack: str, dest: str, pixels: int, log: Callable[[str], None] = print,
                 concat: bool = False) -> str:
    """Encode the delivered video once, with its soundtrack. `video` is a rendered H.264 file (or, with concat, a list
    of parts for ffmpeg's concat demuxer). If the encode fails, the rendered pictures are kept as they are (never a
    lost video). The result is then checked the way a player meets it (playback_check). Returns the codec used."""
    codec = final_codec()
    encoder, args = CODECS[codec]
    speed = {"av1": ("6", "8", "10"), "hevc": ("medium", "fast", "faster"),
             "h264": ("medium", "fast", "veryfast")}.get(codec)
    if speed:                            # bigger frames, faster preset: a long 4K or 8K encode still fits its job
        args = args + ["-preset", speed[0] if pixels <= 2560 * 1440 else speed[1] if pixels <= 3840 * 2160 else speed[2]]
    source = ["-f", "concat", "-safe", "0", "-i", video] if concat else ["-i", video]
    tail = ["-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest",
            "-movflags", "+faststart", dest]
    try:
        ffmpeg([*source, "-i", soundtrack, "-c:v", encoder, *args, *tail], timeout=4 * 3600)
    except (RuntimeError, subprocess.SubprocessError) as exc:
        log(f"[video] {codec.upper()} encode failed ({str(exc)[:160]}); keeping the rendered H.264")
        ffmpeg([*source, "-i", soundtrack, "-c:v", "copy", *tail], timeout=3600)
        codec = "h264"
    log(f"[video] {os.path.basename(dest)}: {codec.upper()}, {os.path.getsize(dest) / 1e6:.0f} MB")
    try:
        log("[video] playback check: " + playback_check(dest)["summary"])
    except Exception as exc:             # a check must never cost a video
        log(f"[video] playback check failed: {type(exc).__name__}: {str(exc)[:120]}")
    return codec


def playback_check(path: str) -> dict:
    """The file as a player meets it: codec and pixel format, every frame and audio packet one step after the other
    (a missing or doubled timestamp is a stall), the picture and the sound ending together, and how fast this machine
    decodes it (below 1.3x real time a player without hardware decoding would stutter). Returns the numbers, the
    problems found ("problems": []) and a one-line "summary"."""
    exe = ffmpeg_exe()
    info = subprocess.run([exe, "-hide_banner", "-i", path], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=120).stderr
    one = lambda pattern: (re.search(pattern, info) or [None, "?"])[1]                  # noqa: E731
    codec, pix, size = one(r"Video: (\w+)"), one(r"Video:.*?(yuv\w+)"), one(r"Video:.*?, (\d{3,5}x\d{3,5})")
    problems: List[str] = []
    ends, irregular, frames = {}, {}, {}
    for kind, tb in (("v", 15360), ("a", 48000)):
        out = subprocess.run([exe, "-v", "error", "-i", path, "-map", f"0:{kind}:0", "-c", "copy", "-f", "framecrc", "-"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900).stdout
        rows = [ln.split(",") for ln in out.splitlines() if re.match(r"^\d", ln)]
        pts, dur = [int(r[1]) for r in rows], [int(r[3]) for r in rows]
        irregular[kind] = sum(1 for i in range(len(pts) - 1) if pts[i + 1] - pts[i] != dur[i])
        frames[kind] = len(rows)
        ends[kind] = (pts[-1] + dur[-1]) / tb if rows else 0.0
    if codec != "h264" and os.environ.get("VIDEO_CODEC", "").strip().lower() not in ("av1", "hevc"):
        problems.append(f"codec {codec} is not H.264")
    if pix != "yuv420p" and codec == "h264":
        problems.append(f"pixel format {pix}")
    if irregular["v"] > 2 or irregular["a"] > 2:
        problems.append(f"irregular timestamps (picture {irregular['v']}, sound {irregular['a']})")
    if abs(ends["v"] - ends["a"]) > 0.25:
        problems.append(f"picture ends at {ends['v']:.2f} s but sound at {ends['a']:.2f} s")
    speed = 0.0
    try:
        mid = max(0.0, min(ends["v"], ends["a"]) / 2 - 10)
        err = subprocess.run([exe, "-hide_banner", "-ss", f"{mid:.1f}", "-t", "20", "-i", path, "-an", "-f", "null", "-"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900).stderr
        m = re.findall(r"speed=\s*([\d.]+)x", err)
        speed = float(m[-1]) if m else 0.0
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    if 0 < speed < 1.3 and codec == "h264":
        problems.append(f"decodes at only {speed:.1f}x real time here")
    summary = (f"{codec} {pix} {size}, {frames['v']} frames and {frames['a']} audio packets in regular steps "
               f"({irregular['v']}+{irregular['a']} irregular), picture {ends['v']:.2f} s / sound {ends['a']:.2f} s, "
               f"decodes at {speed:.1f}x real time" + (f"; PROBLEMS: {'; '.join(problems)}" if problems else "; fine"))
    return {"codec": codec, "pix_fmt": pix, "size": size, "frames": frames, "irregular": irregular, "ends": ends,
            "decode_speed": speed, "problems": problems, "summary": summary}


def timeline(seconds: List[float], kinds: List[str], holds: Optional[List[int]] = None) -> tuple:
    """Scene lengths in frames and the frame each scene starts at. Scenes overlap by TRANSITION frames, so
    each one lasts its narration plus the lead-in, a breath and the overlap; a silent chapter card gets 2.5 s."""
    frames = [max(75 if k == "chapter" else 60, math.ceil(s * FPS) + LEAD + GAP + TRANSITION) + (holds[i] if holds else 0)
              for i, (s, k) in enumerate(zip(seconds, kinds))]
    starts = [sum(frames[:i]) - i * TRANSITION for i in range(len(frames))]
    return frames, starts, sum(frames) - TRANSITION * (len(frames) - 1)


# the gentlest noise reduction that works, tried in this order (ffmpeg filters): measured on a hissy take from a real
# video (-27.6 dB against about -43 for a clean line): the first two bring it to -35 and -44; the last is a strong one.
# Every step also cuts the top of the band: the leftover the owner still heard in a quiz sat above what hiss_ratio
# measures (10-12 kHz of the 24 kHz voice, mirrored to 12-16 kHz in the 48 kHz mix, 25 dB over a clean line's)
HISS_LADDER = ["afftdn=nr=12:nf=-45,lowpass=f=10500", "afftdn=nr=20:nf=-40:tn=1,lowpass=f=10000",
               "afftdn=nr=20:nf=-40:tn=1,lowpass=f=9000", "afftdn=nr=30:nf=-35:tn=1,lowpass=f=8500"]


def repair_hiss(clips: List[str], log: Callable[[str], None], strict=()) -> List[str]:
    """Narration lines that are hissy get cleaned before mixing: each line's high-frequency noise is measured
    (voicecheck.hiss_ratio); above HISS_MAX the gentlest filter of HISS_LADDER that brings it under HISS_FIX_TO is
    applied to a copy (the original stays). A line already clean, silent, or too short is left alone, and a repair
    that does not help is not used. `strict`: the indices of quiz lines, which play with the music stopped: they are
    cleaned from HISS_STRICT_MAX down to HISS_STRICT_TO, a clean line's level. Never raises: a line that cannot be
    measured is used as it is."""
    import numpy as np
    from . import voicecheck as vc
    out = []
    for k, clip in enumerate(clips):
        try:
            sr, x = sound._read_mono(clip)
            if len(x) < 0.8 * sr or float(np.percentile(vc.frames_db(x, sr), 90)) < -45:
                out.append(clip)
                continue
            before = vc.hiss_ratio(x, sr)
            quiz = k in strict
            limit, target = (vc.HISS_STRICT_MAX, vc.HISS_STRICT_TO) if quiz else (vc.HISS_MAX, vc.HISS_FIX_TO)
            if before <= limit:
                out.append(clip)
                continue
            best, best_db, best_filter = clip, before, ""
            for flt in HISS_LADDER:
                fixed = clip + ".clean.wav"
                ffmpeg(["-i", clip, "-af", flt, "-ac", "1", "-c:a", "pcm_s16le", fixed])
                _, y = sound._read_mono(fixed)
                after = vc.hiss_ratio(y, sr)
                if after < best_db - 3:
                    best, best_db, best_filter = fixed, after, flt
                    if after <= target:
                        break
            if best != clip:
                kept = clip + ".denoised.wav"
                os.replace(best, kept)
                best = kept
            log(f"[audio] {'quiz ' if quiz else ''}line {k + 1} was hissy ({before:.1f} dB, a clean line is about -43): "
                + (f"cleaned to {best_db:.1f} dB with {best_filter}" if best != clip else "no filter helped; left as it was"))
            out.append(best)
        except Exception as exc:
            log(f"[audio] line {k + 1}: hiss check failed ({type(exc).__name__}: {str(exc)[:80]})")
            out.append(clip)
        finally:
            if os.path.exists(clip + ".clean.wav"):
                os.remove(clip + ".clean.wav")
    return out


def music_gain_for(clips: List[str], voice_at: List[float], tempos: Optional[List[float]], inputs: List[str],
                   pre: str, log: Callable[[str], None], seconds: float, rounds: int = 3) -> float:
    """The factor to put on the music bed so that, in the pauses, it sits at least sound.PAUSE_FLOOR_DB under the
    narration. Measured on the real thing: the narration and the bed are mixed on their own (no effects), their
    levels compared where the lines pause, and the bed lowered by exactly the shortfall; then measured again, so a
    loud composition, a quiet voice or a changed setting can never leave the music louder than the voice allows."""
    spans = [(t, t + audio_seconds(c) / (tempos[k] if tempos and tempos[k] > 1.005 else 1.0))
             for k, (c, t) in enumerate(zip(clips, voice_at))]
    gain, v_wav, b_wav = 1.0, pre + ".voice.wav", pre + ".bed.wav"
    try:
        for attempt in range(rounds):
            graph, _ = sound.mix_filter(voice_at, [], [], tempos, final=False, music_gain=gain, stems=True)
            ffmpeg([*inputs, "-filter_complex", graph, "-t", f"{seconds:.3f}", "-map", "[outv]", "-ac", "2", v_wav,
                    "-map", "[outb]", "-ac", "2", b_wav])
            got = sound.pause_margin(v_wav, b_wav, spans)
            if got is None:
                return gain
            speech, pause, n = got
            margin = speech - pause
            log(f"[audio] music in {n} pauses is {margin:.1f} dB under the narration (want {sound.PAUSE_FLOOR_DB:.0f}+), "
                f"music gain {gain:.2f}")
            if margin >= sound.PAUSE_FLOOR_DB or sound.bed_level() <= 0:
                return gain
            gain *= 10 ** (-(sound.PAUSE_FLOOR_DB - margin + 0.5) / 20)
        return gain
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:      # never cost a video: the plain mix goes on
        log(f"[audio] music level check failed ({type(exc).__name__}: {str(exc)[:100]}); using the standard level")
        return min(gain, 1.0)
    finally:
        for f in (v_wav, b_wav):
            if os.path.exists(f):
                os.remove(f)


def master(clips: List[str], starts: List[int], kinds: List[str], total: int, assets: dict, dest: str,
           log: Callable[[str], None], tempos: Optional[List[float]] = None, sfx_cues: Optional[dict] = None,
           root_hz: float = 65.0) -> None:
    """The finished soundtrack of one language: narration (cleaned up), music ducked under it, a whoosh on
    every transition and a hit under every figure, mastered to YouTube loudness. The music's level is measured in the
    pauses and lowered until it is well under the voice (music_gain_for)."""
    clips = repair_hiss(clips, log, strict={k for k, kind in enumerate(kinds) if kind == "check"})
    voice_at = [(st + LEAD) / FPS for st in starts]
    whoosh_at = [st / FPS - 0.25 for st in starts[1:]]
    hit_at = [(st + 14) / FPS for st, k in zip(starts, kinds) if k in CHART_KINDS]
    inputs = sum((["-i", c] for c in clips), []) + ["-i", assets["music"], "-i", assets["whoosh"], "-i", assets["hit"]]
    pre = dest + ".pre.wav"
    gain = music_gain_for(clips, voice_at, tempos, inputs, pre, log, total / FPS)
    sfx_wav = ""
    if sfx_cues and sound.sfx_level() > 0:           # a soft sound under every picture that appears (sfx.py)
        sfx_wav = dest + ".sfx.wav"
        n = sfx.render(sfx_wav, total / FPS, sfx_cues, root_hz)
        inputs += ["-i", sfx_wav]
        hit_at = hit_at + sfx_cues["hits"]
        log(f"[audio] {n} pop/tick sounds and {len(sfx_cues['hits'])} thump(s) under the pictures")
    graph, _ = sound.mix_filter(voice_at, whoosh_at, hit_at, tempos, final=False, music_gain=gain, sfx_track=bool(sfx_wav))
    ffmpeg([*inputs, "-filter_complex", graph, "-map", "[out]", "-t", f"{total / FPS:.3f}", "-ac", "2", pre])
    if sfx_wav:
        os.remove(sfx_wav)
    try:        # two passes: measure the mix, then set it to -14 LUFS by one fixed gain (no pumping between sentences)
        r = subprocess.run([ffmpeg_exe(), "-hide_banner", "-nostats", "-i", pre, "-af",
                            "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        loud = sound.two_pass_filter(r.stderr)
    except (OSError, subprocess.SubprocessError):
        loud = sound.two_pass_filter("")
    ffmpeg(["-i", pre, "-af", loud, "-ar", "48000", "-ac", "2", "-b:a", "192k", dest])
    os.remove(pre)


# The long video's resolution: its 1920x1080 layout is rendered at a higher device scale, so text, formulas and thin
# lines are drawn sharp at that size (vector, not upscaled). 2K (2560x1440) by default, the owner's choice: sharper
# than 1080p on YouTube, at about half the size and render time of 4K. Set the repository variable VIDEO_RESOLUTION
# to 4k or 8k for more. A render machine's share shrinks with the pixel count, so each part takes about as long.
RESOLUTIONS = {"1440": 1440, "1440p": 1440, "2160": 2160, "4k": 2160, "2160p": 2160, "4320": 4320, "8k": 4320, "4320p": 4320}
RESOLUTION = RESOLUTIONS.get(os.environ.get("VIDEO_RESOLUTION", "1440").strip().lower(), 1440)
LONG_SCALE = repr(RESOLUTION / 1080)


# the rendered parts are an intermediate (the delivered file is encoded once more, see final_encode): near-lossless
QUALITY = ["--muted", "--crf=12", "--x264-preset=fast", "--image-format=png"]   # lossless frames: crisp coloured text
# one render machine's share of a long video: 90 s of video at 1440p, 40 s at 4K, 10 s at 8K (~30-40 min each)
CHUNK_FRAMES = max(300, min(2700, round(2700 * (1440 / RESOLUTION) ** 2 / 100) * 100))
SOUNDTRACK = "soundtrack_en.mp3"


def render(composition: str, props: str, soundtrack: str, dest: str, log: Callable[[str], None]) -> None:
    """Render the pictures silently, then put the soundtrack on: rendering with audio attached is three to
    four times slower in Remotion. Quality over speed: full-quality frames, low CRF, slow preset."""
    silent = dest + ".silent.mp4"
    scale = [f"--scale={LONG_SCALE}"] if composition == "Long" else []
    remotion(["render", "src/index.jsx", composition, silent, f"--props={props}", *QUALITY, *scale], log,
             timeout=5 * 3600)
    pixels = (RESOLUTION * 16 // 9) * RESOLUTION if composition == "Long" else 1080 * 1920
    final_encode(silent, soundtrack, dest, pixels, log)
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


def join_parts(parts: List[str], soundtrack: str, dest: str, log: Callable[[str], None] = print) -> None:
    """The long video from its separately rendered parts (same encoder settings, each starting on a key frame, so
    they join seamlessly), encoded once with the most efficient codec available, with the soundtrack laid on."""
    listing = dest + ".parts.txt"
    with open(listing, "w", encoding="utf-8") as f:
        f.write("".join(f"file '{os.path.abspath(p)}'\n" for p in parts))
    final_encode(listing, soundtrack, dest, (RESOLUTION * 16 // 9) * RESOLUTION, log, concat=True)
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


TITLE_SMALL = {"a", "an", "and", "or", "vs", "of", "the", "in", "on", "to", "for", "with", "at", "by", "from", "as"}
TITLE_FILLER = TITLE_SMALL | {"what", "is", "are", "how", "why", "when", "does", "do", "its", "it", "explained",
                              "introduction", "intro", "basics", "guide", "lesson"}
# fake shock is not a hook: "you won't believe", "SHOCKING", "!!", emoji, a shouted word (acronyms up to 5 letters pass)
TITLE_BAIT = re.compile(r"won'?t believe|\bshock|!!|[\U0001F300-\U0001FAFF☀-➿]|\b[A-Z]{6,}\b")


def _title_words(text: str) -> set:
    return {w.rstrip("s") for w in re.findall(r"[a-z0-9][a-z0-9'\-]*", text.lower()) if w not in TITLE_FILLER and len(w) > 1}


def title_case(text: str) -> str:
    """'what statistics is: descriptive vs inferential' -> 'What Statistics Is: Descriptive vs Inferential'. Words
    that already carry capitals or a hyphenated letter ('ANOVA', 'p-value', 't-test') are left as written."""
    words = text.strip().split()
    out = []
    for i, w in enumerate(words):
        bare = w.strip(":,;?()\"'")
        lower = bare.lower() in TITLE_SMALL and i and not words[i - 1].endswith(":")
        if bare.isalpha() and bare.islower() and not lower:
            w = w.replace(bare, bare[0].upper() + bare[1:], 1)
        out.append(w)
    return " ".join(out)


def topic_title(candidate: str, topic: str) -> str:
    """A lesson's YouTube title: the topic's key terms (found in search) plus a catchy hook (clicked in the feed),
    the owner's wish. The model's title is kept when it carries most of the topic's key words and no fake shock. A
    hook that forgot the topic gets the topic in front of it ("Mean, Median and Mode: Which Average Lies?") when that
    fits; otherwise the topic itself, in title case."""
    candidate = " ".join(str(candidate or "").split())[:100]
    need = _title_words(topic)
    has = _title_words(candidate)
    clean = candidate and not TITLE_BAIT.search(candidate)
    if clean and need and len(need & has) >= 0.75 * len(need):
        return candidate
    # a course line ("System Design: caching strategies, cache-aside, write-through...") is a syllabus entry, too long
    # for a title to carry 3/4 of: the subject in full and one of the detail's own words is enough
    # (a subject is a name like "System Design", not a phrase like "What statistics is")
    subject, _, detail = topic.partition(":")
    subj = _title_words(subject)
    if clean and detail and len(subj) == len(subject.split()) and subj <= has and (_title_words(detail) - subj) & has:
        return candidate
    plain = title_case(" ".join(topic.split()))
    hook = candidate.split(":", 1)[-1].strip() if clean else ""
    if hook and len(plain) + 2 + len(hook) <= 90:
        return f"{plain}: {hook}"
    return plain[:100]


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
    want = sc.get("kind") if sc.get("kind") in vizlib.SHOT_KINDS else (
        sc.get("plot") if sc.get("kind") == "plot" and sc.get("plot") in vizlib.PLOT_TYPES else "")
    if want:          # a library technique: a diagram shot that must be built around it
        sc = {**sc, "kind": "diagram",
              "picture": f'a "{want}" part ({vizlib.TECH[want]["use"][:70]}): {words(sc.get("picture"), 28)}'}
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
        out["picture"] = words(sc.get("picture"), 48)
        if want:
            out["want"] = want
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


WORDS_IN_TEX = re.compile(r"(?<![\\A-Za-z{])([A-Za-z]{3,}(?:[ ]+[A-Za-z]+)+)(?![A-Za-z}])")


def words_tex(tex: str) -> str:
    r"""Plain words inside a formula keep their spaces: "Normal density" becomes \text{Normal density} (in maths mode
    KaTeX drops the spaces and italicises them: "Normaldensity"). Symbols and commands are left alone."""
    if not tex or "\\text" in tex:
        return tex
    return WORDS_IN_TEX.sub(lambda m: f"\\text{{{m.group(1)}}}", tex)


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


LEVEL_RULES = {
    "basic": "\n- AUDIENCE: complete beginners. Everyday words only, no proofs, history in one line at most. Leave out "
             "advanced generalisations, technical conditions and the names of later theorems unless the idea cannot "
             "be understood without them: depth comes from pictures and examples, not jargon.",
    "intermediate": "\n- AUDIENCE: viewers who know the basics. Name the key conditions and at most one generalisation "
                    "that matters; proofs only as intuition.",
    "advanced": "\n- AUDIENCE: viewers who want the full picture: the conditions, the generalisations and a sketch of "
                "why it is true are all welcome.",
}


WELCOME = ("""The video does NOT start straight at the point, and it does NOT start with a story or a joke. It welcomes the
  viewer, says plainly what the topic is and why it matters, and only THEN moves into a real-life moment. Its first four
  shots (about 90 to 120 words in all, each shot at most 35, calm and warm, a touch of dry humour allowed):
  1. welcome the viewer to {channel} in one short, friendly line and name the topic ("Welcome to {channel}. Today,
     {topic}.");
  2. WHAT IT IS: define the topic literally, in one or two simple sentences ("{topic} is ..."), helped by a small
     everyday comparison, with a picture of the idea. This shot is a real definition, never a quip about the topic;
  3. WHY IT MATTERS: its importance in plain words: what it lets us do, what goes wrong without it, and where it quietly
     works in the viewer's world today (their phone, their feed, the shops, the hospital, the news). No history;
  4. THE ROAD: one sentence on where we are going (first this, then that).
  In an outline the first part is "Welcome" with exactly these four beats. Shots 2 to 4 are pictures of the idea (a
  diagram, the steps), not a talking head or a repeated title.
  Only after shot 4 does the first real part begin, and it opens inside a real situation from today's world that the
  viewer is living right now, told in the present tense ("you are in the queue, your phone is at 14 percent ..."),
  and the video then keeps narrating that live situation while it teaches.""")


def opening_rule(brief: dict, style: str, title: str) -> str:
    """How the video opens: a lesson or a concept video welcomes the viewer, names the topic, defines it and says where
    it is going before it begins (the owner: it must not start straight at the point); other styles open cold."""
    if style in ("education", "concept"):
        return WELCOME.format(channel=brief.get("channel") or "the channel", topic=title)
    return f"{brief['opening']} At most 28 words. No greeting, no \"in this video\"."


def quizzes_on() -> bool:
    """Quiz shots in a lesson. OFF by default since 2026-11-13: the owner heard hiss at the quizzes three times (the
    music stops there, so any noise in the voice is heard) and asked to remove them. QUIZZES=on (a repository
    variable) brings them back."""
    return os.environ.get("QUIZZES", "off").strip().lower() in ("on", "1", "yes", "true")


REAL_WORLD = r"""
- REAL-WORLD DEPTH: anchor every main idea in at least one REAL, NAMED case from the facts: a company, product
  or system that uses it and how it does (how a named service splits its data, how a named model was
  trained), a documented outage or failure and what it taught, or a well-known study and its finding. The
  deep-dive parts carry two or more such cases each; an everyday analogy is still welcome first. Use only what
  the facts support: never invent a company, a number, a date or an incident.
- REFERENCES: when an idea comes from a paper, a book or a named team, say so in one short line ("this is the
  idea behind Amazon's Dynamo paper"), once or twice per video; a "paper" shot can show the paper itself.
  Credit people, papers, books and organisations, never websites."""


def technique_text(title: str, facts: str = "") -> str:
    """The animated techniques this video may use as shot kinds and plot types. The menu is ranked by what the video
    is about (its title AND its research facts) across the whole library, whatever field a technique belongs to;
    and any technique of the library may be named, the menu only describes the likeliest ones."""
    shots = vizlib.match(f"{title} {facts}", 26, pool=vizlib.SHOT_KINDS, title=title, seed=title)
    plots = vizlib.match(f"{title} {facts}", 8, pool=vizlib.PLOT_TYPES, title=title, seed=title)
    others = [n for n in vizlib.SHOT_KINDS if n not in shots]
    lines = "\n".join(f'  - "{n}": {vizlib.TECH[n]["use"]}' for n in shots)
    plot_lines = "\n".join(f'  - "{n}": {vizlib.TECH[n]["use"]}' for n in plots)
    return ("\n- TECHNIQUE SHOTS: besides the kinds listed, a shot's \"kind\" may be one of these animated "
            "techniques, picked for this video. Use at least 5 different ones, each at most once, wherever "
            "one SHOWS the mechanism better than a plain diagram; give \"picture\": what it shows for THIS "
            "sentence, naming the real things (max 35 words). The diagram designer fills in its data."
            "\n" + lines +
            "\n- More \"plot\" types (give \"plot\": the type and \"picture\": what it shows):\n" + plot_lines
            + "\n  Any other technique of the library may be a shot kind the same way when it fits a sentence better: " + ", ".join(others)
            + "\n  Other plot types: " + ", ".join(n for n in vizlib.PLOT_TYPES if n not in plots))


def shape_prompt(brief: dict, style: str, title: str, facts: str, lesson: Optional[dict] = None) -> tuple:
    """The writer's brief: the style's voice plus the plan made for this subject (braces escaped for the
    script prompt), and the number of shots that fits the planned length."""
    acts = "; ".join(f"{a['title']} ({a['job']})" for a in brief["acts"])
    minutes = brief["minutes"]
    text = SHAPE.format(persona=STYLES[style], minutes=f"{minutes:g}", title=title, facts=facts, acts=acts,
                        narrator=brief["narrator"], device=brief["device"],
                        structure=brief["structure"], opening_rule=opening_rule(brief, style, title),
                        ending=brief["ending"], tone=brief["tone"])
    if brief.get("maths"):
        text += MATHS_RULES
    if style == "education":
        text += TEACHING + VOICE.replace("[examples]", brief.get("examples") or "everyday situations the viewer knows")
        if not quizzes_on():
            text += '\n- NO QUIZ in this video: no "check" shots at all; skip step (7) and go on to the recap.'
    if style in ("education", "concept"):
        text += LEVEL_RULES.get(brief.get("level") or "intermediate", "")
    if style in ("education", "concept", "story"):          # whatever style "auto" lands on for a subject
        text += REAL_WORLD + technique_text(title, facts)
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
            "tone": s("tone", "clear, curious, warm"), "mood": s("mood", ""), "sound": s("sound", ""),
            "minutes": minutes,
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
        if style in ("education", "concept"):
            rule += ("; this is a lesson, so do not plan a part around the history of the idea (who discovered what, "
                     "and when) unless the subject itself is historical: viewers want the idea and why it matters")
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
        outline, parts = {}, []
        for attempt in range(2):          # an outline in an unexpected shape is read leniently, then asked for again
            try:
                outline = self.llm.complete_json(
                    rules + fill(OUTLINE, minutes=f"{brief['minutes']:g}", words=words_needed, shots=n_shots) +
                    ("\n\nYour last reply had no usable \"parts\" list with \"beats\": reply in exactly that format."
                     if attempt else ""), max_tokens=6000, temperature=0.6)
            except LLMError as exc:
                self.log(f"[video] no outline ({str(exc)[:80]})")
                continue
            parts = outline_parts(outline)
            if parts:
                break
            self.log("[video] the outline came back without parts" + ("; asking once more" if not attempt else ""))
        if not parts:                     # never one request for a long video: write it part by part from the plan
            self.log("[video] writing part by part from the plan's acts")
            parts = [{"title": a["title"], "beats": [a.get("job") or a["title"]]} for a in brief["acts"]]
        outline = outline if isinstance(outline, dict) else {}
        total = sum(len(p["beats"]) for p in parts)
        listing = "\n".join(f"{k + 1}. {p.get('title', '')}: " + " | ".join(str(b) for b in p["beats"])
                             for k, p in enumerate(parts))
        if total < n_shots * 0.75:
            self.log(f"[video] the outline has {total} beats for about {n_shots} shots: each part is written longer")
        scenes = []
        words_of = lambda shots: sum(len(str(s.get("narration", "")).split()) for s in shots)      # noqa: E731
        # each request writes at most SHOTS_PER_REQUEST shots (a model asked for 70 at once returns ~18): a part whose
        # share of the planned length is bigger is written in pieces, each continuing where the last one ended
        jobs = []
        for k, part in enumerate(parts):
            beats = [str(b) for b in part["beats"]][:16]
            name = " ".join(str(part.get("title") or f"Part {k + 1}").split()[:4])
            share_shots = max(len(beats), round(n_shots * len(beats) / total))
            share_words = round(words_needed * len(beats) / total)
            m = max(1, math.ceil(share_shots / SHOTS_PER_REQUEST))
            for r in range(m):
                a, b = r * len(beats) // m, max((r + 1) * len(beats) // m, r * len(beats) // m + 1)
                jobs.append((k, name, beats[a:b], round(share_shots / m), round(share_words / m), r, m))
        for k, name, beats, lo, target, r, m in jobs:
            piece = (f" (piece {r + 1} of {m} of this part: continue exactly where the last piece ended, never repeat "
                     "it, and go deeper into the same beats with new pictures and examples)") if m > 1 else ""
            first = ('Its first shot is the opening (see "Opening") and has "act": "".' if k == 0 and r == 0 else
                     f'Its first shot has "act": "{name}"; every other shot has "act": "".' if r == 0 else
                     'Every shot has "act": "".')
            ask = rules + fill(ACT, outline=listing, k=k + 1, n=len(parts), title=name + piece,
                               beats="\n".join(f"- {b}" for b in beats), lo=lo, hi=lo + max(3, lo // 3),
                               words=target, first=first,
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
            for sc in got:
                sc["act"] = ""
            if got and k and r == 0:
                got[0]["act"] = name
            scenes += got
            self.log(f"[video] part {k + 1}/{len(parts)} \"{name}\"" + (f" piece {r + 1}/{m}" if m > 1 else "") +
                     f": {len(got)} shots, {words_of(got)} words")
        if len(scenes) < 5:
            self.log(f"[video] the parts gave only {len(scenes)} shots: writing in one go instead")
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
        return beats[:4]

    def script(self, title: str, facts: List[dict], sources: List[dict], style: str = "news",
               brief: Optional[dict] = None, report: bool = False, lesson: Optional[dict] = None) -> dict:
        """report: a full report is for sale and linked; otherwise the outro points to the sources only.
        lesson: this video's place in a course (its goal, what it covers, what came before and after)."""
        linked = self.s.description_report      # off: the description has no links, so nothing points there
        report = report and linked
        lines = []
        for i, f in enumerate(facts, 1):
            src = sources[int(f["source"]) - 1] if str(f.get("source", "")).isdigit() else {}
            lines.append(f"{i}. [{domain(src.get('url', ''))}] {f['claim']} | \"{f.get('quote', '')[:240]}\"")
        brief = brief or check_brief({}, style)
        shape, shots = shape_prompt(brief, brief["style"], title, "\n".join(lines), lesson)
        prompt = SCRIPT_PROMPT.replace("{shape}", shape).replace("{shots}", shots).replace(
            "{outro_ask}", ("say the full report, with every source, is linked in the description, and " if report
                            else "say every source is linked in the description, and ") if linked
            else "do not mention the description, links, sources or a report; ").replace(
            "{channel}", self.s.channel_name)
        prompt = prompt.replace("{{", "{").replace("}}", "}")
        words_needed = round(brief["minutes"] * 160 * narration_pace())   # ~170 words a minute at full speed; pauses take the rest
        plan = None
        if brief["minutes"] >= LONG_MINUTES:
            plan = self.long_plan(prompt.split("\nReturn JSON:")[0], brief, words_needed)
        written_long = plan is not None
        plan = plan or self.llm.complete_json(prompt, max_tokens=12000)
        kicker = KICKERS[int(hashlib.md5(title.encode()).hexdigest(), 16) % len(KICKERS)]
        allowed = " ".join(f"{f['claim']} {f.get('quote', '')}" for f in facts)
        quotes = " ".join(_norm(f.get("quote", "")) for f in facts)
        countries = country_names()
        # websites are where facts were found, not who says them; in a lesson that includes this run's own sources
        # (news may still name the agency that reported an event)
        site_urls = [s.get("url", "") for s in sources] if style == "education" else []

        def uncredit(text: str) -> str:
            clean = strip_site_credits(text, site_urls)
            if clean != text:
                self.log(f"[video] website credit taken out: \"{text[:90]}\" -> \"{clean[:90]}\"")
            return clean

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
        if style == "education":                            # the lesson voice: sarcasm a viewer actually hears
            plan = self.punch_up(plan, brief)
        scenes, act, acts = [], "", 0
        for sc in plan.get("scenes", [])[:MAX_SCENES]:
            if not isinstance(sc, dict):
                continue
            if sc.get("kind") == "chapter":        # an old-style title shot becomes the next shot's act sting
                act = str(sc.get("headline") or "")
                continue
            act = str(sc.get("act") or "").strip() or act
            scene = check_scene(sc, allowed, quotes, countries)
            if scene["kind"] == "check" and not quizzes_on():
                self.log("[video] quiz shot left out (QUIZZES=off)")
                continue
            # a fact's number must be in the research; a worked example's numbers must be on screen in the shot
            narration = uncredit(strip_persona(strip_unsupported_numbers(speakable(str(sc.get("narration", "")).strip()),
                                                                         f"{allowed} {maths_shown(scene)}")))
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
        for sc in scenes:             # plain words in a formula keep their spaces
            for p in sc.get("parts", []) + sc.get("steps", []) + (sc.get("graph") or {}).get("curves", []) + \
                    ([sc["surface"]] if sc.get("surface") else []):
                if p.get("tex"):
                    p["tex"] = words_tex(p["tex"])
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
        pointless = (not report and "report" in outro.lower()) or (not linked and POINTS_DOWN.search(outro))
        if not 8 <= len(outro.split()) <= 60 or pointless:
            outro = (OUTRO if report else OUTRO_SOURCES if linked else OUTRO_PLAIN).format(
                facts=len(facts), channel=self.s.channel_name)
        scenes.append({"kind": "outro", "narration": outro,
                       "kicker": ("Full report below" if report else "Sources below") if linked else "Subscribe",
                       "card": ("Documentary report" if report else "Checked facts") if linked else self.s.channel_name,
                       "channel": self.s.channel_name,
                       "headline": str(plan.get("thumb_text") or title)[:40],
                       "highlight": ("report" if report else "sources") if linked else "subscribe",
                       "label": f"{len(facts)} verified facts · {len(sources)} sources", "number": "", "items": [],
                       "events": [], "countries": [], "quote": "", "speaker": "", "source": "", "subjects": []})
        if plan.get("short") is None:      # a long video's Short is picked from its finished shots
            plan["short"] = self.pick_short(scenes[:-1], allowed)
        short = []
        for item in plan.get("short", [])[:4]:
            idx = item.get("scene")
            text = uncredit(strip_unsupported_numbers(str(item.get("narration", "")).strip(), allowed))
            if isinstance(idx, int) and 0 <= idx < len(scenes) - 1 and text:
                short.append({"scene": idx, "narration": text})
        short = short or [{"scene": 0, "narration": scenes[0]["narration"]}]
        short.append({"scene": len(scenes) - 1,
                      "narration": (SHORT_OUTRO if linked else SHORT_OUTRO_PLAIN).format(channel=self.s.channel_name)})
        video_title = str(plan.get("title", title))[:100]
        if style == "education":
            chosen = topic_title(video_title, title)
            if chosen != video_title:
                self.log(f"[video] title \"{video_title}\" is not the topic; using \"{chosen}\"")
            video_title = chosen
        return {"title": video_title, "thumb_text": str(plan.get("thumb_text", ""))[:40],
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
        brief["level"] = meta.get("level") or "intermediate"         # who the lesson is for (the run's --level)
        brief["channel"] = self.s.channel_name                       # named once, in the welcome
        plan = self.script(title, facts, sources, brief["style"], brief,
                           report=bool((meta.get("gumroad") or {}).get("url")), lesson=lesson)
        scenes, beats = plan["scenes"], plan["short"]
        recent = palettes.load_history(self.s)           # what the last videos used: no two in a row look alike
        theme = design.design(self.llm.complete_json, plan["title"], brief["style"],
                              f"{brief['mood']} {brief['tone']}", self.log, recent)
        palettes.save_history(self.s, recent, theme)
        self.log(f"[video] {len(scenes)} scenes ({', '.join(s['kind'] for s in scenes)}), Short of {len(beats)} beats")
        self.art_direct(scenes)
        bare = {i for i, s in enumerate(scenes) if s["kind"] in graphics.ELIGIBLE and not s.get("graphic")
                and not s.get("video") and i > 0}
        if brief["style"] in ("education", "concept") and bare:
            self.art_direct(scenes, only=bare)      # in a lesson every idea gets a picture, not just its words
        brief["look"] = looks.moves_text(theme)       # the film look's own language, for the diagram designer
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
                path = os.path.join(job, f"{lang}_{kind}{idx}.wav")
                # the quiz question is the LAST "?" (a rhetorical question before it must not start the answer early)
                ask = line.rfind("?") + 1 if kind == "long" and scenes[idx]["kind"] == "check" else 0
                if 0 < ask < len(line.rstrip()):   # a check: question and answer spoken apart, a pause between
                    jobs += [(line[:ask].strip(), VOICES[lang], path[:-4] + "_q.wav"),
                             (line[ask:].strip(), VOICES[lang], path[:-4] + "_a.wav")]
                    keys += [(lang, kind, idx, "q"), (lang, kind, idx, "a")]
                    continue
                jobs.append((line, VOICES[lang], path))
                keys.append((lang, kind, idx))
        spoken = {k: v for k, v in zip(keys, speak_cloned(jobs, self.s, job, self.log)) if v is not None}
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
                                 os.path.join(job, f"{lang}_{kind}{idx}.wav"))
            except RuntimeError:
                continue
            answer = [(s + off, e + off, w) for s, e, w in a]
            spoken[(lang, kind, idx)] = q + answer
            # the question ends, the pause runs, and the answer lights up when the right option is said
            thinking[(lang, idx)] = (q[-1][1] if q else 0.0, answer_moment(answer, off, scenes[idx]))
        self.log(f"[video] {len(jobs)} narration clips spoken in {', '.join(texts)}")

        def clip(lang, kind, idx):
            path = os.path.join(job, f"{lang}_{kind}{idx}.wav")
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
        # the music is composed for this video alone: its mood words and a seed of its own (the same topic made
        # twice still sounds different), the key and mode, tempo, instrument and the arrangement all follow from them
        music_seed = f"{title}|{time.time_ns()}"
        music_mood = f"{brief.get('sound', '')} {brief.get('sound', '')} {brief['mood']} {brief['tone']} {title}"
        root_hz = composer.hz(composer.feel(music_mood, music_seed)["root"] - 24)      # the video's low key note
        sound.hit(assets["hit"], root_hz)

        # long video: the pictures follow the English narration. A dubbed line that runs longer is sped up (at
        # most MAX_TEMPO, pitch kept), and only what still does not fit lengthens the shot, so the English video
        # has no silent waits and every language still fits the pictures
        kinds = [s["kind"] for s in scenes]
        secs = {(l, i): audio_seconds(clip(l, "long", i)) for l in texts for i in range(n_long) if clip(l, "long", i)}
        longest = []
        for i in range(n_long):
            en = secs.get(("en", i), 0.0)
            dub = max((v for (l, k), v in secs.items() if k == i and l != "en"), default=0.0)
            longest.append(max(en, dub / MAX_TEMPO) if en else dub)
        tempo = {key: max(1.0, v / longest[key[1]]) if longest[key[1]] else 1.0 for key, v in secs.items()}
        holds = [HOLD if i + 1 < n_long and scenes[i + 1].get("chapter") else 0 for i in range(n_long)]   # a beat before a new part
        frames, starts, total = timeline(longest, kinds, holds)
        score = sound.music(total / FPS + 1, assets["music"], seed=music_seed, mood=music_mood,
                            sections=[(st / FPS, (st + fr) / FPS, k) for st, fr, k in zip(starts, frames, kinds)])
        self.log(f"[video] music composed for this video: {score}")
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
        # every shot is measured as drawn, captions included: nothing may run into anything else
        self.audit_layout(scenes, long_scenes, spoken, theme, job, long_captions, starts)
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
                   self.log, [tempo.get((lang, i), 1.0) for i in range(n_long)],
                   sfx.cues(long_scenes, starts, FPS), root_hz)
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
            secs = lambda bs: sum(audio_seconds(clip(lang, "short", b)) + 0.4 for b in bs if clip(lang, "short", b))
            while secs(order) > SHORT_MAX_SECONDS and len(order) > 2:
                order.pop(-2)               # drop the weakest middle beat, keep the hook and the ending
            order = [b for b in order if clip(lang, "short", b)]
            seconds = [audio_seconds(clip(lang, "short", b)) for b in order]
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
                if visual["kind"] == "check":     # the Short's own voice decides when its answer shows
                    short_scenes[-1].update(check_cues(texts[lang][n_long + b], words, visual, fr[j]))
                for ca, cz, line in word_lines(words, 0, 30):
                    captions.append({"from": st[j] + LEAD + round(ca * FPS), "to": st[j] + LEAD + round(cz * FPS),
                                     "text": line})
            self.audit_short(short_scenes, captions, st, [spoken[(lang, "short", b)] for b in order], theme, job, lang)
            path = os.path.join(job, f"short_{lang}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"scenes": short_scenes, "captions": captions, "channel": self.s.channel_name, "theme": theme},
                          f, ensure_ascii=False)
            track = os.path.join(job, f"short_{lang}.mp3")
            short_music = os.path.join(job, f"short_music_{lang}.wav")
            sound.music(tot / FPS + 1, short_music, seed=music_seed, mood=music_mood,
                        sections=[(a / FPS, (a + f) / FPS, k) for a, f, k in zip(st, fr, sk)])
            master([clip(lang, "short", b) for b in order], st, sk, tot, {**assets, "music": short_music}, track, self.log,
                   sfx_cues=sfx.cues(short_scenes, st, FPS), root_hz=root_hz)
            self.log(f"[video] rendering the {LANGS[lang]} Short ({tot / FPS:.0f}s)")
            render("Short", path, track, os.path.join(out, f"short_{lang}.mp4"), self.log)
            files[f"short_{lang}.mp4"] = "short"

        # everything the last stage needs, so it can run here or on another machine after a farmed render
        shutil.copy(os.path.join(job, "long_en.mp3"), os.path.join(out, SOUNDTRACK))
        state = {"run_dir": os.path.abspath(run_dir), "files": files, "plan": plan, "texts": texts, "credits": credits,
                 "n_lines": n_long + n_short + sum(per_beat), "product": (meta.get("gumroad") or {}).get("url", ""),
                 "meta": {k: v for k, v in meta.items() if k != "stored"},      # no signed links in a public artifact
                 "notes_key": notes_key(run_dir, meta), "sources": sources, "email": email, "total": total, "t0": t0, "lesson": lesson}
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
            join_parts(parts, os.path.join(out, SOUNDTRACK), dest, self.log)
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
                                                                st["meta"], st["sources"], st.get("lesson"),
                                                                linked=self.s.description_report))
        # exactly what the email shows and the upload button sends to YouTube (stored with the videos, no secrets)
        yt = youtube_text(plan, texts, st["n_lines"], st["credits"], st["product"], st["meta"], st["sources"],
                          linked=self.s.description_report)
        yt.update(category="27", lesson=st.get("lesson") or {})        # 27 = Education
        with open(os.path.join(out, "youtube.json"), "w", encoding="utf-8") as f:
            json.dump(yt, f, ensure_ascii=False, indent=1)
        files["youtube.json"] = "youtube"
        with open(os.path.join(out, "video_script.json"), "w", encoding="utf-8") as f:
            json.dump({"plan": plan, "texts": texts, "credits": st["credits"], "review": verdict}, f, indent=2,
                      ensure_ascii=False)
        for leftover in [SOUNDTRACK, "finish.json"]:
            if os.path.exists(os.path.join(out, leftover)):
                os.remove(os.path.join(out, leftover))
        shutil.rmtree(os.path.join(out, "parts"), ignore_errors=True)
        shutil.rmtree(os.path.join(VIDEO_APP, "public", "job"), ignore_errors=True)
        self.log(f"[video] done in {time.time() - st['t0']:.0f}s: {', '.join(files)}")
        self.deliver(st["run_dir"], out, files, plan, st["email"], verdict, st["meta"], st.get("notes_key", ""))
        return {name: os.path.join(out, name) for name in files}

    def design_json(self, prompt: str, **kw):
        """Diagrams need the strongest model: Gemini Flash first, then the usual providers."""
        reply = gemini_json(self.s, prompt, effort="medium", temperature=0.8, log=self.log)
        return reply if reply is not None else self.llm.complete_json(prompt, max_tokens=8000, temperature=0.8)

    def punch_up(self, plan: dict, brief: dict) -> dict:
        """A comedy writer's pass over a lesson: about one line in three gets a deadpan, sarcastic joke with the
        punchline last, so a calm voice still lands it. A line keeps its meaning, terms and numbers: a rewrite that
        adds, drops or changes a number, or runs too long, is ignored and the line stays as it was."""
        rows = [sc for sc in plan.get("scenes") or [] if isinstance(sc, dict)]
        lines = [str(sc.get("narration", "")) for sc in rows]
        if len(lines) < 3:
            return plan
        out, changed, used = [], 0, set()
        for start in range(0, len(lines), 40):          # in batches, so each reply stays well inside the limits
            batch = lines[start:start + 40]
            try:                                         # comedy needs the strongest writer available
                reply = self.design_json(PUNCH.format(examples=brief.get("examples") or "-", n=len(batch),
                                                      lines=json.dumps(batch, ensure_ascii=False)))
            except LLMError:
                out += batch
                continue
            new = reply.get("lines") if isinstance(reply, dict) else None
            if not isinstance(new, list) or len(new) != len(batch):
                out += batch
                continue
            for k, (old, line) in enumerate(zip(batch, new)):
                line = " ".join(str(line or "").split())
                same_numbers = sorted(re.findall(r"\d[\d,.]*", line)) == sorted(re.findall(r"\d[\d,.]*", old))
                limit = 28 if start + k == 0 else 60
                # the joke a line gained (its last sentence): the same joke twice in one video is a catchphrase
                tail = re.sub(r"[^a-z ]", "", re.split(r"(?<=[.!?…])\s+", line)[-1].lower()).strip()
                repeat = tail in used and tail not in re.sub(r"[^a-z ]", "", old.lower())
                if line and line != old and same_numbers and len(line.split()) <= limit and not repeat:
                    used.add(tail)
                    out.append(line)
                    changed += 1
                else:
                    out.append(old)
        for sc, line in zip(rows, out):
            sc["narration"] = line
        self.log(f"[video] comedy pass: {changed} of {len(lines)} lines punched up")
        return plan

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
                              tex_complete, self.log, brief.get("look", ""))
        bad = typeset_errors([el["tex"] for s in scenes for el in (s.get("diagram") or {}).get("elements", [])
                              if el["type"] == "tex"])
        for s in scenes:
            if s.get("diagram") and bad:
                s["diagram"]["elements"] = [el for el in s["diagram"]["elements"] if el.get("tex") not in bad]
                if not diagram.enough(s["diagram"]["elements"]):
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
                        rounds: int = 2) -> None:
        """Render three moments of each diagram (a third in, two thirds in, the end), let the vision model judge it
        against its sentence and correct it
        (up to `rounds` times; a correction the checks reject goes back once with the reason), and keep the best
        version only if it scores 7 or more; otherwise the shot falls back to its library graphic or animated type."""
        idx = [i for i, s in enumerate(long_scenes) if s.get("diagram")]
        if not idx:
            return
        best: Dict[int, tuple] = {}
        settled, unrendered = set(), set()
        fresh: Dict[int, dict] = {}
        problems: Dict[int, str] = {}
        words = lambda i: spoken.get(("en", "long", i), [])            # noqa: E731
        for rnd in range(rounds + 1):
            todo = [i for i in idx if i not in settled]
            if not todo:
                break
            shots = []
            for i in todo:                    # three moments of the shot, so the reviewer can see what moves
                props = {"scenes": [{k: v for k, v in long_scenes[i].items() if k != "chapter"}], "captions": [],
                         "theme": theme}
                n = long_scenes[i]["frames"]
                shots += [(f"{i}a", props, round(n * 0.35)), (f"{i}b", props, round(n * 0.65)), (i, props, n - 20)]
            looks = self.stills(shots, job)
            def review(i: int) -> None:       # one shot's critique and correction; shots run side by side
                if i not in looks:            # it did not draw: it could break the video's render too
                    unrendered.add(i)
                    settled.add(i)
                    return
                images = []
                for key in (f"{i}a", f"{i}b", i):
                    if key in looks:
                        with open(looks[key], "rb") as f:
                            images.append(f.read())
                ask = diagram.refine_prompt(scenes[i], scenes[i]["diagram"], diagram.ICON_LIST)
                reply = gemini_json(self.s, ask, images, effort="medium", temperature=0.5, log=self.log)
                try:
                    score = float(reply.get("score")) if isinstance(reply, dict) else None
                except (TypeError, ValueError):
                    score = None
                if score is None:             # no verdict: the version that passed the checks stands
                    settled.add(i)
                    return
                fresh.pop(i, None)            # this version has its verdict
                if score > best.get(i, (-1.0, None))[0]:
                    best[i] = (score, scenes[i]["diagram"])
                    problems[i] = str((reply or {}).get("problem") or "")[:110] if isinstance(reply, dict) else ""
                if not isinstance(reply, dict) or score >= 9 or rnd == rounds:
                    settled.add(i)
                    return
                why: List[str] = []
                d = diagram.check({"elements": reply.get("elements") or []}, scenes[i], _verified, tex_complete, why)
                if not d and reply.get("elements"):         # one more try, told exactly what the checks refused
                    again = gemini_json(self.s, ask + diagram.RETRY.format(why="; ".join(why[:4])), images,
                                        effort="medium", temperature=0.4, log=self.log)
                    d = diagram.check({"elements": (again or {}).get("elements") or []} if isinstance(again, dict)
                                      else None, scenes[i], _verified, tex_complete)
                if d and not typeset_errors([el["tex"] for el in d["elements"] if el["type"] == "tex"]):
                    unrendered.discard(i)
                    fresh[i] = d                  # a correction made from the critique, awaiting its own verdict
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
            if i in fresh and i not in unrendered and score >= KEEP_SCORE - 1:
                d, score = fresh[i], max(score, KEEP_SCORE)      # its correction, made from the critique, stands
                problems[i] = "corrected, not re-checked"
            if d is not None and score >= KEEP_SCORE:
                scenes[i]["diagram"] = d
                long_scenes[i]["diagram"] = diagram.timed(d, words(i), long_scenes[i]["frames"], FPS, LEAD)
                kept.append(f"{i}:{score:g}" + ("*" if problems.get(i) == "corrected, not re-checked" else ""))
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

    def audit_layout(self, scenes: List[dict], long_scenes: List[dict], spoken: dict, theme: dict, job: str,
                     captions: Optional[List[dict]] = None, starts: Optional[List[int]] = None, rounds: int = 4) -> None:
        """Draw every shot of the long video, with the captions that run over it, and measure the page itself."""
        words = lambda i: spoken.get(("en", "long", i), [])            # noqa: E731
        targets = [{"name": f"shot {i}", "view": ls, "scene": scenes[i], "frames": ls["frames"],
                    "captions": layout.shot_captions(captions, starts[i], ls["frames"]) if captions and starts else [],
                    "retime": lambda g, i=i, ls=ls: graphics.timed(g, scenes[i].get("headline", ""), words(i),
                                                                    ls["frames"], FPS, LEAD)}
                   for i, ls in enumerate(long_scenes)]
        self.audit_shots(targets, "Long", theme, job, "", rounds)

    def audit_short(self, short_scenes: List[dict], captions: List[dict], starts: List[int], spoken: List[list],
                    theme: dict, job: str, lang: str = "en", rounds: int = 4) -> None:
        """The same audit for a vertical Short (its own pictures, its own captions): short_scenes are repaired in place."""
        targets = [{"name": f"Short beat {j}", "view": v, "scene": v, "frames": v["frames"],
                    "captions": layout.shot_captions(captions, starts[j], v["frames"]),
                    "retime": lambda g, v=v, w=spoken[j]: graphics.timed(g, v.get("headline", ""), w, v["frames"], FPS, LEAD)}
                   for j, v in enumerate(short_scenes)]
        self.audit_shots(targets, "Short", theme, job, f"_short_{lang}", rounds)

    def audit_shots(self, targets: List[dict], composition: str, theme: dict, job: str, tag: str, rounds: int) -> None:
        """Every target (a shot: name, view that is drawn, scene that holds the source, frames, captions, retime) is drawn
        at several moments; where two texts, two boxes or a label and a box edge run into each other, it gets the
        mildest repair that can clear it (a shorter headline, then plain animated type for its picture, then no
        headline) and is measured again, up to `rounds` times. A shot that is still not clean after that is logged by
        name; the audit never stops the video."""
        todo = list(range(len(targets)))
        first = True
        for rnd in range(rounds + 1):
            shots = []
            for i in todo:
                t = targets[i]
                one = {"scenes": [{k: v for k, v in t["view"].items() if k != "chapter"}], "captions": t["captions"],
                       "theme": theme}
                shots += [(i, one, f) for f in layout.moments(t["frames"])]
            found = layout.audit(VIDEO_APP, shots, job, self.log, composition=composition, tag=tag)
            if found is None:
                if first:
                    self.log(f"[layout] no {composition} audit this time; the shots stay as designed")
                return
            bad = sorted(i for i, f in found.items() if f)
            if first:
                self.log(f"[layout] {composition}: {len(bad)} of {len(todo)} shots have pieces running into each other")
                first = False
            if not bad:
                return
            if rnd == rounds:
                for i in bad:
                    self.log(f"[layout] {composition} {targets[i]['name']} ({targets[i]['view'].get('kind')}) still has: "
                             + "; ".join(layout.describe(f) for f in found[i][:3]))
                return
            for i in bad:
                t = targets[i]
                did = layout.repair(t["scene"], t["view"], rnd, t["retime"], found[i])
                self.log(f"[layout] {composition} {t['name']}: {layout.describe(found[i][0])} -> {did or 'nothing left to simplify'}")
            todo = bad

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
                verdict: Optional[dict] = None, meta: Optional[dict] = None, notes_at: str = "") -> None:
        """Store the videos, then empty every video folder but the KEEP_VIDEOS newest (this one included), and email the
        links plus the small files. Never posts."""
        names = list(files) + ["posting_guide.txt"]
        links = upload_run(self.s, out, names, self.log,
                           prefix=f"videos/{os.path.basename(os.path.normpath(run_dir))}")
        if links.get("long_video_en.mp4"):      # only once this video is safely stored: never leave fewer than before
            try:
                keep_latest_runs(self.s, keep=KEEP_VIDEOS, log=self.log)
            except Exception as exc:            # the clean-up must never cost a video
                self.log(f"[storage] clean-up skipped: {type(exc).__name__}: {str(exc)[:120]}")
        if not email:
            return
        # the Upload buttons' key: random per video, kept only in the private bucket and in this email (never in
        # the run folder, which may become a public artifact). The button relay checks it before starting the job.
        upload_key = ""
        if links.get("long_video_en.mp4") and email_page.button_base():
            key = secrets.token_urlsafe(24)
            if put_text(self.s, f"videos/{os.path.basename(os.path.normpath(run_dir))}/upload_key.txt", key):
                upload_key = key
            else:
                self.log("[mail] the upload key could not be stored: the email gets the GitHub-page buttons")
        pdf_url = link_for(self.s, notes_at)      # the study notes in Cloudflare storage; made here, never in the artifact
        shown = {**links, **({"study_notes.pdf": pdf_url} if pdf_url else {})}
        yt = None
        try:
            with open(os.path.join(out, "youtube.json"), encoding="utf-8") as f:
                yt = json.load(f)
        except (OSError, ValueError):
            pass
        notes = [line.strip() for line in notes_section(meta or {}).strip().splitlines()[1:] if line.strip()]
        page, body = email_page.build(plan["title"], shown, yt, summary(verdict or {}), notes,
                                      email_page.repository(), os.path.basename(os.path.normpath(run_dir)),
                                      KEEP_VIDEOS, upload_key)
        small = [os.path.join(out, n) for n in names if n.endswith((".txt", ".srt", ".png", ".jpg"))]
        pdf = fetch_notes(self.s, notes_at, os.path.join(out, "study_notes.pdf"), self.log)
        if pdf:
            small.append(pdf)
        send_email(self.s, f"[Video] {plan['title'][:120]}", body, small, self.log, html=page)


SR_SILENCE = sound.SR // 2
NOTES_MAX_MB = 20            # an email's attachments must stay under the mail server's limit


def notes_key(run_dir: str, meta: dict) -> str:
    """Where the study-notes PDF was stored (its object-storage key), so the last stage can attach it without the
    PDF (which may be for sale) travelling in a public artifact."""
    if not (meta.get("stored") or {}).get("documentary_report.pdf"):
        return ""
    return f"reports/{os.path.basename(os.path.normpath(run_dir))}/documentary_report.pdf"


def fetch_notes(settings, key: str, dest: str, log) -> str:
    """The study-notes PDF downloaded from storage to `dest` ('' when there is none or it is too big to email)."""
    if not key or not settings.storage_configured:
        return ""
    try:
        from .storage import _client
        _client(settings).download_file(settings.s3_bucket, key, dest)
        mb = os.path.getsize(dest) / 1e6
        if mb > NOTES_MAX_MB:
            os.remove(dest)
            log(f"[notes] the PDF is {mb:.0f} MB, too big to attach")
            return ""
        log(f"[notes] study notes attached ({mb:.1f} MB)")
        return dest
    except Exception as exc:
        log(f"[notes] could not attach the PDF: {type(exc).__name__}: {str(exc)[:120]}")
        return ""


def notes_section(meta: dict, pdf_url: str = "") -> str:
    """The email's account of the study notes: what is in them, what they cost and why, where they are sold."""
    if not meta.get("report_words"):
        return ""
    g = meta.get("gumroad") or {}
    size = f"{meta['pdf_pages']} pages, " if meta.get("pdf_pages") else ""
    chapters = meta.get("chapters") or []
    lines = ["", "STUDY NOTES (PDF, attached as study_notes.pdf)",
             f"  {meta.get('title', meta.get('topic', ''))}",
             f"  {size}{meta['report_words']:,} words, {len(chapters)} chapters, "
             f"{meta.get('verified_facts', '?')} verified facts from {meta.get('sources', '?')} sources",
             f"  Written for: {meta.get('level', 'intermediate')} level, {meta.get('niche', 'general')} reader"]
    if pdf_url:
        lines.append(f"  PDF download (Cloudflare{', link works 7 days' if 'X-Amz-Signature' in pdf_url else ''}): {pdf_url}")
    if g.get("url"):
        lines += [f"  PRICE: {label(g.get('price', 0), g.get('currency', 'inr'))}  ({meta.get('price_reason', 'see above')})",
                  f"  Gumroad: {g['url']}  "
                  f"({'LIVE: anyone can buy or get it now' if g.get('published') else 'DRAFT: not on sale until you publish it'})"]
    if chapters:
        lines.append("  Chapters: " + "; ".join(f"{i}. {c}" for i, c in enumerate(chapters, 1)))
    return "\n".join(lines) + "\n"


def youtube_block(guide_path: str) -> str:
    """The English title, description, study-notes link and sources from the posting guide (for the email)."""
    try:
        with open(guide_path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return ""
    m = re.search(r"===== ENGLISH =====\n(.*?)(?=Photo and footage credits|\n===== |\Z)", text, re.S)
    return m.group(1).strip() if m else ""


def hashtags(tags: List[str], n: int = 3) -> List[str]:
    """The first few tags as hashtags ("standard deviation" -> "#StandardDeviation"), short ones only."""
    out = []
    for tag in tags:
        h = "#" + "".join(w[:1].upper() + w[1:] for w in re.findall(r"[A-Za-z0-9]+", str(tag)))
        if 2 < len(h) <= 26 and h.lower() not in {x.lower() for x in out}:
            out.append(h)
        if len(out) == n:
            break
    return out


def youtube_text(plan: dict, texts: Dict[str, List[str]], n_lines: int, credits: List[dict], product: str,
                 meta: dict, sources: Optional[List[dict]] = None, lang: str = "en", linked: bool = False) -> dict:
    """What goes into YouTube for one language: the title, the description and the tags of the long video and of its
    Short. linked (DESCRIPTION_REPORT): the description also links the study notes and the sources; off (the
    default): no links at all, the owner's wish. Photo credits the licences require are named (without links)."""
    lines = texts[lang]
    title, desc = lines[n_lines], lines[n_lines + 1]
    tags = [str(t) for t in plan.get("tags", [])][:12]
    tagline = " ".join(hashtags(tags))
    extra = ""
    if linked:
        g = meta.get("gumroad") or {}
        if product:
            extra += f"Full study notes (PDF, {label(g.get('price', 0), g.get('currency', 'inr'))}): {product}\n"
        urls = list(dict.fromkeys(x.get("url", "") for x in sources or [] if str(x.get("url", "")).startswith("http")))
        if urls:
            extra += (f"Sources ({len(urls)}):\n" + "".join(f"- {u}\n" for u in urls[:15])
                      + (f"- and {len(urls) - 15} more\n" if len(urls) > 15 else ""))
    photos = "; ".join(f"{c['subject']}: {c['author'] or 'Wikimedia Commons'}, {c['license']}" for c in credits)
    description = "\n\n".join(x for x in (desc.strip(), extra.strip(), f"Photos: {photos}" if photos else "",
                                          tagline) if x)
    short_title = (title if len(title) <= 90 else title[:89].rsplit(" ", 1)[0]) + " #Shorts"
    short_description = "\n\n".join(x for x in (desc.strip(), (tagline + " #Shorts").strip()) if x)
    return {"title": title[:100], "description": description[:4900], "tags": tags,
            "short_title": short_title, "short_description": short_description[:4900]}


def posting_guide(plan: dict, texts: Dict[str, List[str]], n_lines: int, credits: List[dict], product: str,
                  meta: dict, sources: Optional[List[dict]] = None, lesson: Optional[dict] = None,
                  linked: bool = False) -> str:
    credit_lines = "\n".join(f"- {c['subject']}: {c['author'] or 'see file page'}, {c['license']}, {c['file']}"
                             for c in credits) or "- none (no photos used)"
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
             "Music and sound effects are generated by the pipeline itself: no licence or credit needed.\n"]
    for lang in texts:
        yt = youtube_text(plan, texts, n_lines, credits, product, meta, sources, lang, linked)
        parts.append(f"===== {LANGS[lang].upper()} =====\nTitle: {yt['title']}\nDescription:\n{yt['description']}\n\n"
                     f"Short title: {yt['short_title']}\n"
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
