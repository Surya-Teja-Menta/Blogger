"""Bespoke animated diagrams: for each shot a language model draws what the sentence explains, from a drawing
vocabulary (points, point clouds, lines, arrows, curves, boxes, bars, labels, icons, formulas, morphing shapes, crowds
of icons, counters, live random samples and real physics), and says on which spoken word each piece appears, moves,
glows, is marked by a hand-drawn pen, or leaves. video/src/diagram.jsx draws it. Nothing here is a
layout template: the model composes every picture for its sentence. The guard rails are in the checking: known
pieces only, everything on the canvas, short labels taken from the narration, numbers only if they are spoken,
formulas KaTeX can typeset, labels that do not collide; and after rendering a vision model scores each diagram
and a weak one is dropped (the shot falls back to its library graphic)."""
import re
from typing import Callable, Dict, List, Optional

from . import graphics, vizlib
from .mathexpr import compile_expr, finite_share

TYPES = ("dot", "dots", "circle", "box", "label", "arrow", "line", "curve", "bar", "icon", "tex",
         "samples", "physics", "counter", "shape", "crowd", "stamp",
         "plot", "network", "tree", "grid", "venn", "cycle", "code", "wave", "surface", "bars", "flow")
RICH = ("plot", "network", "tree", "grid", "venn", "cycle", "code", "wave", "surface", "bars", "flow")     # moving pictures of how a thing works (rich.jsx)
TYPES = TYPES + tuple(vizlib.TECH)        # the visual-technique library (vizlib.py, video/src/viz/)
RICH = RICH + tuple(vizlib.TECH)
REGIONS = ("samples", "physics", "crowd") + RICH   # parts that fill a box of the canvas
SOURCES = ("uniform", "skewed", "exponential", "bimodal", "normal", "dice", "coin")
SHAPES = ("circle", "square", "triangle", "diamond", "hexagon", "star", "heart")
MARKS = ("circle", "underline", "box", "cross")
MOTIONS = ("move", "glow", "hide", "mark", "fit", "click")
COLOURS = ("accent", "hot", "cool", "violet", "text", "muted")
ANIMS = ("pop", "draw", "fade", "grow")
SIZES = ("s", "m", "l")
MAX_ELEMENTS = 14
BATCH = 5

SPEC = """CANVAS: x from 0 (left) to 100 (right), y from 0 (top) to 100 (bottom); the headline sits above it and the
captions below it. The canvas is 2.5 times wider than tall, so lay ideas out left to right, and remember that a
square h units tall is h / 2.5 units wide. Keep everything between 6 and 94, spread over the whole canvas (never
crammed into one corner, never tiny), with clear space between elements and one obvious focal point.
"r" and "size" are in units of 1% of the canvas HEIGHT (r 2 = a data point, r 15 = a big circle; icon size 10-20).

ELEMENTS (each has "type"; optional "id", "color": accent, hot, cool, violet, text or muted; "on": the word of the
narration at which it appears, copied exactly from the narration, or "" for the start; "anim": pop, draw, fade or grow):
- "dot": x, y, r                      - "dots": "points": [[x, y], ...] up to 40 (made-up illustrative data is fine), r
- "circle": x, y, r, "fill": true/false, optional "text" inside (max 3 words)
- "box": x, y (top-left), w, h, optional "text" inside (max 4 words)
- "label": x, y, "text" (max 5 words), "size": s, m or l, "align": left, center or right
- "arrow": x1, y1, x2, y2, optional "bend" (-0.5 to 0.5), optional "text" (max 3 words, shown at its middle)
- "line": x1, y1, x2, y2, optional "dashed": true
- "curve": "points": [[x, y], ...] (3 to 30, drawn as a smooth path)
- "bar": x (left), y (baseline, bottom), w, h (height upwards), optional "text" under it (max 3 words)
- "icon": x, y, "name" (one of: {icons}), size
- "tex": x, y, "tex" (KaTeX, short), "size": s, m or l
- "shape": x, y, size, "shape": circle, square, triangle, diamond, hexagon, star or heart, "fill": true/false
- "stamp": x, y, "text": a verdict of 1 or 2 words (MYTH, BUSTED, TRUE, PROVEN, WRONG, NOT QUITE, CONFIRMED...),
  "size": s, m or l: a rubber stamp that SLAMS onto the picture on its word, red ink, tilted. It sits on EMPTY canvas
  next to the claim it judges (above, beside or under it), NEVER over a word, a box or any other piece: a stamp on top
  of text makes both unreadable. Use it for a verdict: a myth busted, a guess proven, a claim checked. At most one
  per diagram.
- "counter": x, y, "from", "to" (numbers the narration says), optional "text" after the number (max 3 words), "size":
  the number counts from "from" to "to" when it appears (a total climbing, a price falling)
- "crowd": x, y (top-left), w, h, "name" (an icon from the list, e.g. user), "count": 4 to 100 icons in a grid,
  "highlight": how many of them light up (on the crowd's "glow" word): shares, odds, "1 in 10", a sample of people
- "samples": x, y (top-left), w, h (a big region: w at least 40, h at least 50): random values falling one by one
  into a histogram that builds while the narration runs (the first few slowly, then a time-lapse; a counter shows
  how many). "source": where one value comes from: uniform, skewed, exponential, bimodal, normal, dice or coin;
  "n": how many values each dot averages (1 = single values, 30 = every dot is the average of 30); "count": dots
  (30 to 600); "lo", "hi": the axis range in the example's own units (e.g. 10 and 70); "unit": the axis unit (max 2
  words, e.g. "minutes"); "text": what one dot is (max 5 words); "mean": true marks the average. Use it whenever the
  sentence is about chance, averages, spread, sampling, noise, risk or a distribution: the viewer SEES it happen.
- "physics": x, y (top-left), w, h (a tall region: h at least 60): balls dropped into a real physics simulation.
  "balls": 20 to 160; "pegs": rows of pegs they bounce through (0 to 12; 10 makes a Galton board); "bins": bins at
  the bottom (0 = none; with pegs there is one bin per landing spot); "drop": "center" (one stream) or "spread"
  (rain over the width); "text": what is counted (max 4 words). Use it for many small random pushes adding up,
  things piling up, filling, overflowing or sorting by chance.
- "plot": x, y, w, h (a big region: w at least 40, h at least 45): a function drawn live on axes. "expr": the curve in
  x, e.g. "x^2", "sin(x)", "1/(1+exp(-x))", "exp(-x^2/2)", "a*x^2" (numbers, x, one parameter a, + - * / ^, brackets,
  sin cos tan exp log sqrt abs, pi, e; nothing else); "lo", "hi": the x range; optional "expr2": a second curve to
  compare; optional "sweep": {{"from": number, "to": number}}: the parameter a slides from one value to the other
  with a slider on screen while the curve bends (what a knob DOES: slope, rate, width, strength); optional
  "trace": true: a point travels along the curve with its tangent line and its distances to the axes (slope,
  rate of change, a derivative); optional "shade": [x0, x1]: the area under the curve there fills in on the
  element's "glow" word (an integral, a probability, a total); "xlabel", "ylabel": axis names (max 3 words each).
- "network": region (w at least 40, h at least 45): connected things. "nodes": [{{"id": "a", "text": "name" (max 2
  words)}}, ...] 3 to 12; "edges": [["a", "b"], ...] up to 24; "layout": "force" (default, finds its own shape) or
  "layers" (give each node "layer": 0, 1, 2 ...: a neural net, a pipeline); optional "start": the node a wave
  starts from. On the element's "glow" word a WAVE spreads from the start through the connections with pulses
  riding the lines and each node lighting in turn (news spreading, a disease, a signal, influence, a forward pass).
- "tree": region (w at least 40, h at least 40): a hierarchy that grows level by level. "nodes": [{{"id": "r",
  "parent": "" (the root; exactly one), "text": max 2 words}}, ...] up to 15, each parent given before its
  children; optional "path": a node id: on the element's "glow" word the route from the root to it lights up
  (a decision path, a chain of choices, a branch of probability, recursion, categories inside categories).
- "grid": region (w at least 30, h at least 35): a board of cells. "rows", "cols" (2 to 10); optional "values": a
  list of rows*cols numbers (0 to 9 reads best; else made up); "show": numbers, heat or both; optional "scan": 2 or
  3: on the element's "glow" word a window of that size slides over the board and the result of each position (op:
  sum, max or mean) fills an output grid beside it (a convolution, pooling, a moving average, a sliding window,
  pixels of an image); optional "cells": [[row, col], ...] lit on the "glow" word (a pattern, a winner, an error).
- "venn": region (w at least 35, h at least 45): "sets": 2 or 3 of {{"text": max 2 words}}; the circles start apart
  and drift together on the element's "glow" word; "overlap": 0.15 to 0.7 (how much they end up overlapping);
  optional "both": what the overlap is (max 3 words). For what is shared, what is common, and, or, intersection.
- "cycle": region (w at least 40, h at least 50): a loop of 3 to 7 stages, "nodes": ["plan", "build", ...] (each max
  2 words, in order), with a comet circling the loop and lighting each stage in turn; optional "text": the loop's
  name in the middle (max 2 words). For repeating processes, feedback, orbits, routines, life cycles.
- "code": region (w at least 35, h at least 40): a program typed out, then run line by line. "lines": up to 10 lines of
  code (each up to 44 characters, indentation kept; any language); "lang": its name (one word); "steps": up to 8 of
  {{"line": 1-based line number, "note": max 4 words, e.g. "i is 0"}}: on the element's "glow" word a marker steps
  through them with the note beside each; "output": up to 3 lines the program prints at the end.
- "wave": region (w at least 40, h at least 40): waves that add up. "waves": up to 5 of {{"freq": 0.5 to 12, "amp":
  0.05 to 1}} or "preset": "square" (odd harmonics building a square wave), "saw" or "beats" (two close notes);
  "mode": "sum" (the parts and their sum) or "fourier" (turning circles whose tip draws the wave). The parts join
  one by one on the element's "glow" word. For sound, signals, vibration, interference, Fourier, seasons, cycles.
- "surface": region (w at least 40, h at least 50): a lit 3D landscape z = f(x, y) that rises and slowly turns.
  "expr": in x and y, e.g. "x^2+y^2" (a bowl), "x^2-y^2" (a saddle), "sin(x)*cos(y)" (hills), "exp(-(x^2+y^2))" (a
  peak); "lo", "hi": the range of x and y; "descent": true: on the element's "glow" word a ball rolls down it
  in gradient-descent steps, leaving its trail (optimisation, loss, minimum, saddle, energy, terrain).
- "bars": region (w at least 35, h at least 35): bars that grow and swap places as numbers change. "items": [{{"text":
  name (max 3 words), "value": number}}, ...] 2 to 8; "to": the new values (same count) the bars move to on the
  element's "glow" word; "sort": true: the bars re-rank as they move (a race, a before and after, who overtakes
  whom); "show": true prints the numbers (only numbers the narration says); "unit": max 2 words.
- "flow": region (w at least 45, h at least 40): streams of particles through a pipeline. "stages": 2 to 5 of {{"text":
  max 2 words, "share": 0 to 1 (the first is 1; how much is left at that stage)}}: the pipe narrows with each share
  and the lost particles fall away. For funnels, conversion, supply chains, energy, money, water, losses, filters.
These moving parts fill the picture: use at most ONE per shot, with a few labels, arrows or a stamp around it.
Choose one whenever the sentence is about a function or how a knob changes it (plot), connections or spreading
(network), choices or hierarchy (tree), a board, image or sliding window (grid), what two things share (venn),
something that repeats (cycle), a program (code), signals or vibration (wave), an optimisation landscape or terrain
(surface), things changing rank or size (bars), or what is lost at each step (flow): the viewer SEES how it works,
which a static drawing cannot show.
MOTION (optional on any element, each with its own "on" word, which must come after the element's own "on" word):
- "move": {{"on": word, then the new x, y (or x1, y1, x2, y2 for a line or arrow; h for a bar; r for a circle)}}
  A "curve" or "dots" can RESHAPE: give the new "points" (same count) and the shape morphs into them (a straight
  line bending into a wiggly overfit curve, scattered points collapsing onto a line, a wide bell narrowing).
  A "dot" can TRAVEL along a curve: give "along": the curve's "id" (give that curve an "id"), plus the x, y it
  stops at; it rides the curve exactly (a ball rolling down a cost curve, a point sliding along a path).
- "glow": {{"on": word}} (it pulses to draw the eye)      - "hide": {{"on": word}} (it fades away)
- "mark": {{"on": word, "style": circle, underline, box or cross}}: a hand-drawn pen mark on it, like a teacher on a
  board (cross = this is wrong)
- "fit": {{"on": word}} (samples and physics only): the pile melts into the smooth bell curve that fits it
- "click": {{"on": word}}: a mouse pointer glides to the piece and clicks it, a ripple spreads (an interface, a
  button, choosing something, "tap here"; makes the picture feel operated)
- A "shape" can MORPH: "move" with a new "shape" (and size) turns it into that shape (an idea becoming another).
CAMERA: the camera pushes in on each piece as its word is spoken and pulls back to the whole picture at the end, so
give each new idea its own piece and its own word; samples and physics run for the rest of the shot, so they start
on an early word.

RULES: labels use words from the narration, placed right next to what they name; never write a number that is not
in the narration; text never overlaps other text or shapes; one idea per diagram; the eye follows the sentence;
the subject is big (at least a third of the canvas height), never a tiny drawing in a corner; never a colour drawn on
the same colour (muted on muted, a label inside a box of its own colour)."""

PROMPT = """You are the visual explainer of a channel like 3Blue1Brown, Kurzgesagt and StatQuest. For each shot
below, design ONE animated diagram that SHOWS what the narration says: the mechanism, the relationship, the change.
Not decoration, not a list of words. Ask: what would a brilliant teacher draw on the board while saying this exact
sentence, and what would MOVE while it is said? Every diagram is drawn fresh for its sentence; make each one look
different from the others.

Video: {title}  |  Mood: {mood}
{style}
""" + SPEC + """

Two examples of the standard expected (do not copy them; draw what YOUR sentence needs):
"A single outlier drags the whole line toward it" ->
[{{"type": "dots", "color": "cool", "r": 2.4, "points": [[12,78],[20,70],[27,73],[34,63],[42,61],[50,53],[57,56],[64,47],[72,45]]}},
 {{"type": "line", "color": "accent", "x1": 8, "y1": 80, "x2": 80, "y2": 40, "anim": "draw", "move": {{"on": "drags", "y2": 26}}}},
 {{"type": "dot", "color": "hot", "x": 88, "y": 12, "r": 3.6, "on": "outlier", "anim": "pop", "glow": {{"on": "drags"}}}},
 {{"type": "arrow", "color": "hot", "x1": 80, "y1": 40, "x2": 84, "y2": 18, "bend": 0.15, "on": "drags", "text": "pulled"}},
 {{"type": "label", "color": "muted", "x": 40, "y": 92, "text": "the rest of the data", "size": "s"}}]
"Squaring makes a point twice as far away count four times as much" ->
[{{"type": "line", "color": "muted", "x1": 8, "y1": 76, "x2": 92, "y2": 76}},
 {{"type": "dot", "color": "cool", "x": 25, "y": 64, "r": 2.6}}, {{"type": "line", "color": "hot", "x1": 25, "y1": 64, "x2": 25, "y2": 76, "dashed": true}},
 {{"type": "box", "color": "hot", "x": 25, "y": 64, "w": 4.8, "h": 12, "on": "squaring", "anim": "grow"}},
 {{"type": "dot", "color": "cool", "x": 62, "y": 52, "r": 2.6, "on": "twice"}}, {{"type": "line", "color": "hot", "x1": 62, "y1": 52, "x2": 62, "y2": 76, "dashed": true, "on": "twice"}},
 {{"type": "label", "color": "cool", "x": 62, "y": 44, "text": "twice as far", "size": "m", "on": "twice"}},
 {{"type": "box", "color": "hot", "x": 62, "y": 52, "w": 9.6, "h": 24, "on": "four", "anim": "grow", "glow": {{"on": "much"}}}},
 {{"type": "label", "color": "hot", "x": 67, "y": 88, "text": "four times as much", "size": "m", "on": "four"}}]

"Gradient descent rolls downhill, step by step, until the slope is flat" ->
[{{"type": "curve", "id": "bowl", "color": "muted", "anim": "draw", "points": [[8,14],[20,46],[32,68],[44,80],[50,82],[56,80],[68,68],[80,46],[92,14]]}},
 {{"type": "dot", "color": "hot", "x": 14, "y": 31, "r": 3.4, "on": "rolls", "move": {{"on": "step", "along": "bowl", "x": 50, "y": 82}}}},
 {{"type": "arrow", "color": "accent", "x1": 20, "y1": 20, "x2": 32, "y2": 50, "bend": -0.2, "on": "downhill", "text": "downhill"}},
 {{"type": "line", "color": "accent", "x1": 38, "y1": 82, "x2": 62, "y2": 82, "on": "flat", "glow": {{"on": "flat"}}}},
 {{"type": "label", "color": "hot", "x": 50, "y": 93, "text": "the slope is flat", "size": "m", "on": "flat"}}]

"A bigger knob makes the curve steeper, so the output reacts faster" ->
[{{"type": "plot", "color": "accent", "x": 8, "y": 8, "w": 84, "h": 76, "expr": "1/(1+exp(-a*x))", "lo": -6, "hi": 6,
  "sweep": {{"from": 0.5, "to": 4}}, "trace": true, "xlabel": "input", "ylabel": "output", "on": "knob"}},
 {{"type": "label", "color": "hot", "x": 50, "y": 94, "text": "steeper", "size": "m", "on": "steeper"}}]

The moving parts (plot, network, tree, grid, venn, cycle, code, wave, surface, bars, flow, samples, physics, crowd,
counter) are what make the video
worth watching: use one wherever the sentence fits one, and "click", "mark" and "glow" to point at what matters. A
shot with only labels and arrows is the last resort.

MORE MOVING PARTS: the technique library, a selection for this video. Each fills a region like the parts above
(give x, y, w, h and the fields named), at most one per shot. A technique already used in another shot of this
video is not used again. When a shot's WANTED names a part ("a "hashring" part ..."), build that shot around
exactly that part, filled with this sentence's own things.
{library}

Shots (index | headline | narration | WANTED: the picture the writer asked for, when given; build that):
{shots}

Reply with a JSON list: [{{"scene": index, "elements": [...]}}]"""

REFINE = """You designed this animated diagram for one shot of an educational YouTube video.
Narration: "{narration}"
Headline (drawn above the canvas): "{headline}"
The picture the writer asked for: "{picture}"
The images are three moments of the shot as rendered, in order: a third of the way in, two thirds in, and its
last frame, so you can see what appears, moves, fills or morphs while the sentence is said. Its JSON:
{diagram}

""" + SPEC + """

Judge the shot like the art director of 3Blue1Brown, strictly (across all three moments): does it SHOW the idea of the sentence (not merely
name it)? Is it clean: nothing overlapping or cut off, labels readable and right next to what they name, the canvas
used well (not sparse, not crammed into one area), one clear focal point, and something that changes while the
sentence is said? Score 9-10 only for a picture a top channel would publish; any overlap or a cramped or sparse
layout is at most 6; a picture that only names the idea instead of showing it is at most 5. Then give an improved
version that fixes every problem you saw.
Reply: {{"score": 1-10 for the shot as it is, "problem": "the main problem in one line, or empty",
"elements": [the complete improved element list in the same format, or [] if it is already excellent]}}"""

RETRY = """

Your improved version could not be drawn: {why}.
Send the complete improved element list again, fixing that as well. Same reply format."""


def refine_prompt(scene: dict, d: dict, icons: str) -> str:
    import json as _json
    plain = [{k: v for k, v in el.items() if k not in ("at",)} for el in d["elements"]]
    for el in plain:
        for m in MOTIONS:
            if isinstance(el.get(m), dict):
                el[m] = {k: v for k, v in el[m].items() if k != "at"}
    return REFINE.format(narration=scene.get("narration", ""), headline=scene.get("headline", ""),
                         picture=scene.get("picture") or "(none: show what the narration says)",
                         diagram=_json.dumps(plain), icons=icons)


def used_parts(scenes: List[dict]) -> set:
    """The library techniques the video's diagrams already use."""
    return {el["type"] for s in scenes for el in (s.get("diagram") or {}).get("elements", []) if el["type"] in vizlib.TECH}


def prompt(scenes: List[dict], idx: List[int], title: str, mood: str, style: str = "") -> str:
    used = used_parts(scenes)
    wanted = [scenes[i]["want"] for i in idx if scenes[i].get("want") in vizlib.TECH]
    names = list(dict.fromkeys(wanted + vizlib.pick(title, 22, used)))
    rows = "\n".join(f"{i} | {scenes[i].get('headline', '')} | {scenes[i].get('narration', '')}"
                     + (f" | WANTED: {scenes[i]['picture']}" if scenes[i].get("picture") else "") for i in idx)
    return PROMPT.format(title=title, mood=mood or "-", icons=" ".join(sorted(graphics.ICONS)), shots=rows,
                         style=style + "\n" if style else "", library=vizlib.catalogue(names))


ICON_LIST = " ".join(sorted(graphics.ICONS))


def _num(v, lo: float, hi: float, default: float) -> float:
    try:
        return round(min(hi, max(lo, float(v))), 2)
    except (TypeError, ValueError):
        return default


def _words(v, n: int) -> str:
    return " ".join(str(v or "").split()[:n])


def _on(v, narration: str) -> str:
    """The cue word, if it really is in the narration (else the element simply appears in order)."""
    w = re.sub(r"[^\w'-]", "", str(v or "")).lower()
    return w if w and w in narration.lower() else ""


def _text_ok(text: str, allowed: str, verified: Callable[[str, str], bool]) -> bool:
    return not text or verified(text, allowed)


def _boxes(el: dict) -> List[tuple]:
    """Rough text extents (x0, y0, x1, y1 in canvas units; x is 2.5x wider) for collision checks."""
    out = []
    size = {"s": 4.5, "m": 6.5, "l": 9}.get(el.get("size", "m"), 6.5)
    if el["type"] == "counter":
        size = {"s": 4.5, "m": 6.5, "l": 9}.get(el.get("size", "l"), 9) * 1.6
        t = f'{el["to"]} {el.get("text", "")}'.strip()
        w = len(t) * size * 0.55 / 2.5
        return [(el["x"] - w / 2, el["y"] - size / 2, el["x"] + w / 2, el["y"] + size / 2)]
    for key in ("text",):
        t = el.get(key)
        if not t or el["type"] in REGIONS:          # a region's caption is drawn inside its own box
            continue
        w = len(t) * size * 0.55 / 2.5          # characters to x-units on a 2.5:1 canvas
        if el["type"] == "label":
            x = el["x"] - (w / 2 if el.get("align", "center") == "center" else w if el.get("align") == "right" else 0)
            out.append((x, el["y"] - size / 2, x + w, el["y"] + size / 2))
        elif el["type"] == "arrow":
            mx, my = (el["x1"] + el["x2"]) / 2, (el["y1"] + el["y2"]) / 2
            out.append((mx - w / 2, my - size, mx + w / 2, my))
    return out


def _solids(el: dict) -> List[tuple]:
    """Extents of the solid pieces (boxes, circles, icons, formulas) in canvas units, for collision checks."""
    t = el["type"]
    if t == "box":
        return [(el["x"], el["y"], el["x"] + el["w"], el["y"] + el["h"])]
    if t == "circle":
        return [(el["x"] - el["r"] / 2.5, el["y"] - el["r"], el["x"] + el["r"] / 2.5, el["y"] + el["r"])]
    if t == "icon":
        h = el["size"] / 2
        return [(el["x"] - h / 2.5, el["y"] - h, el["x"] + h / 2.5, el["y"] + h)]
    if t in REGIONS:
        return [(el["x"], el["y"], el["x"] + el["w"], el["y"] + el["h"])]
    if t == "shape":
        return [(el["x"] - el["size"] / 2.5, el["y"] - el["size"], el["x"] + el["size"] / 2.5, el["y"] + el["size"])]
    if t == "stamp":                      # a tilted rubber stamp: its words in big capitals, a border and a little slack
        size = {"s": 4.5, "m": 6.5, "l": 9}.get(el.get("size", "l"), 9) * 1.5
        w = len(el.get("text", "")) * size * 0.72 / 2.5 + 6
        return [(el["x"] - w / 2, el["y"] - size * 1.1, el["x"] + w / 2, el["y"] + size * 1.1)]
    if t == "tex":
        h = {"s": 5, "m": 7, "l": 10}[el["size"]]
        w = len(re.sub(r"\\[a-zA-Z]+|[{}_^ ]", "", el["tex"])) * h * 0.6 / 2.5 + 2
        return [(el["x"] - w / 2, el["y"] - h, el["x"] + w / 2, el["y"] + h)]
    return []


def collision(els: List[dict]) -> Optional[tuple]:
    """The first two elements (indexes) where two labels, or a label and a solid piece, or two solid pieces sit on
    top of each other (a box's own text, inside it, is fine); None when nothing collides."""
    pieces = [(k, b, "text") for k, el in enumerate(els) for b in _boxes(el)] + \
             [(k, b, "solid") for k, el in enumerate(els) for b in _solids(el)]
    def inside(small: tuple, big: tuple) -> bool:          # small sits (nearly) wholly within big
        w = min(small[2], big[2]) - max(small[0], big[0])
        h = min(small[3], big[3]) - max(small[1], big[1])
        area = (small[2] - small[0]) * (small[3] - small[1])
        return w > 0 and h > 0 and area > 0 and w * h / area >= 0.9 and area < (big[2] - big[0]) * (big[3] - big[1])

    for n, (k1, a, kind1) in enumerate(pieces):
        for k2, b, kind2 in pieces[n + 1:]:
            if k1 == k2:
                continue
            # a box is a container: a formula, icon or label placed wholly inside it is its content, not a clash
            if (els[k1]["type"] == "box" and kind1 == "solid" and els[k2]["type"] != "stamp" and inside(b, a)) or \
                    (els[k2]["type"] == "box" and kind2 == "solid" and els[k1]["type"] != "stamp" and inside(a, b)):
                continue
            limit = 0.35 if kind1 == kind2 == "text" else 0.15
            if _overlap(a, b) > limit:
                return k1, k2
    return None


def crowded(els: List[dict]) -> bool:
    return collision(els) is not None


def describe(el: dict) -> str:
    """An element as a reviewer would name it: its type and its words, icon or formula."""
    what = el.get("text") or el.get("name") or el.get("tex") or ""
    if what:
        return f'{el.get("type", "?")} "{what}"'
    return f'{el.get("type", "?")} at ({el.get("x", el.get("x1"))}, {el.get("y", el.get("y1"))})'


def _overlap(a: tuple, b: tuple) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    small = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1])) or 1
    return w * h / small


def _ident(v, n: int = 12) -> str:
    return re.sub(r"[^\w-]", "", str(v if v is not None else ""))[:n]


def _rich(el: dict, e: dict, allowed: str, verified: Callable[[str, str], bool], why: List[str]) -> bool:
    """Fill the rich part's own fields into el; True when it cannot be drawn (and say why)."""
    t = el["type"]
    if t in vizlib.TECH:
        return vizlib.fill(el, e, allowed, verified, why)
    if t == "plot":
        expr = str(e.get("expr") or "").strip()[:60]
        lo, hi = _num(e.get("lo"), -1e4, 1e4, -5), _num(e.get("hi"), -1e4, 1e4, 5)
        if hi <= lo:
            lo, hi = -5, 5
        sweep = None
        sw = e.get("sweep")
        if isinstance(sw, dict):
            try:
                sweep = {"from": float(sw["from"]), "to": float(sw["to"]), "name": "a"}
            except (KeyError, TypeError, ValueError):
                sweep = None
        a = _num(e.get("a"), -1e3, 1e3, 1.0)
        params = [sweep["from"], sweep["to"]] if sweep else [a]
        try:
            f = compile_expr(expr)
        except ValueError:
            why.append(f'plot "expr" {expr[:40]!r} is not a curve in x (use numbers, x, a, + - * / ^, sin cos tan exp log sqrt abs, pi, e)')
            return True
        if finite_share(f, lo, hi, params) < 0.8:
            why.append(f'plot "{expr[:40]}" is not a real number across {lo} to {hi}; pick another range or curve')
            return True
        el.update(expr=expr, lo=lo, hi=hi, a=a, trace=bool(e.get("trace")), xlabel=_words(e.get("xlabel"), 3),
                  ylabel=_words(e.get("ylabel"), 3))
        if sweep and re.search(r"(?<![a-z])a(?![a-z])", expr.lower()):
            el["sweep"] = sweep
        expr2 = str(e.get("expr2") or "").strip()[:60]
        if expr2:
            try:
                if finite_share(compile_expr(expr2), lo, hi, params) >= 0.8:
                    el["expr2"] = expr2
            except ValueError:
                pass
        shade = e.get("shade")
        if isinstance(shade, (list, tuple)) and len(shade) == 2:
            try:
                s0, s1 = sorted(float(v) for v in shade)
                if hi >= s0 and lo <= s1 and s1 > s0:
                    el["shade"] = [max(lo, s0), min(hi, s1)]
            except (TypeError, ValueError):
                pass
        return False
    if t in ("network", "tree"):
        nodes, seen = [], set()
        for n in (e.get("nodes") or [])[:15 if t == "tree" else 12]:
            if not isinstance(n, dict):
                continue
            nid = _ident(n.get("id"))
            if not nid or nid in seen:
                continue
            seen.add(nid)
            text = _words(n.get("text"), 2)
            if text and not verified(text, allowed):
                why.append(f'{t} node "{text}" uses a number the narration never says; its label is left out')
                text = ""
            item = {"id": nid, "text": text}
            if t == "network" and isinstance(n.get("layer"), (int, float)):
                item["layer"] = int(_num(n.get("layer"), 0, 6, 0))
            if t == "tree":
                item["parent"] = _ident(n.get("parent"))
            nodes.append(item)
        ids = {n["id"] for n in nodes}
        if t == "network":
            edges, have = [], set()
            for pair in (e.get("edges") or [])[:24]:
                if isinstance(pair, (list, tuple)) and len(pair) == 2:
                    a, b = _ident(pair[0]), _ident(pair[1])
                    if a in ids and b in ids and a != b and (a, b) not in have and (b, a) not in have:
                        have.add((a, b))
                        edges.append([a, b])
            if len(nodes) < 3 or not edges:
                why.append("a network needs at least 3 nodes and some edges between their ids")
                return True
            layered = e.get("layout") == "layers" and all("layer" in n for n in nodes)
            start = _ident(e.get("start"))
            el.update(nodes=nodes, edges=edges, layout="layers" if layered else "force", start=start if start in ids else "")
            return False
        roots = [n for n in nodes if not n["parent"]]
        by = {n["id"]: n for n in nodes}

        def reaches_root(n: dict) -> bool:
            seen_ids = set()
            while n["parent"]:
                if n["id"] in seen_ids or n["parent"] not in by:
                    return False
                seen_ids.add(n["id"])
                n = by[n["parent"]]
            return True
        if len(nodes) < 3 or len(roots) != 1 or not all(reaches_root(n) for n in nodes):
            why.append('a tree needs 3 or more nodes with exactly one root (parent "") and every parent an existing id')
            return True
        path = _ident(e.get("path"))
        el.update(nodes=nodes, path=path if path in ids else "")
        return False
    if t == "grid":
        rows, cols = int(_num(e.get("rows"), 2, 10, 5)), int(_num(e.get("cols"), 2, 10, 5))
        scan = int(_num(e.get("scan"), 0, 3, 0))
        scan = scan if scan in (2, 3) and rows > scan and cols > scan else 0
        vals = e.get("values")
        if isinstance(vals, list) and len(vals) == rows * cols:
            try:
                vals = [round(float(v), 1) for v in vals]
            except (TypeError, ValueError):
                vals = None
        else:
            vals = None
        if vals is None:                     # illustrative numbers, fixed by the board's size
            vals = [(r * 5 + c * 3 + (r * c) % 4) % 10 for r in range(rows) for c in range(cols)]
        cells = []
        for rc in (e.get("cells") or [])[:6]:
            if isinstance(rc, (list, tuple)) and len(rc) == 2:
                cells.append([int(_num(rc[0], 0, rows - 1, 0)), int(_num(rc[1], 0, cols - 1, 0))])
        show = e.get("show") if e.get("show") in ("numbers", "heat", "both") else "both"
        el.update(rows=rows, cols=cols, values=[int(v) if v == int(v) else v for v in vals], scan=scan, show=show,
                  op=e.get("op") if e.get("op") in ("sum", "max", "mean") else "sum", cells=cells)
        return False
    if t == "venn":
        sets = []
        for s in (e.get("sets") or [])[:3]:
            text = _words(s.get("text") if isinstance(s, dict) else s, 2)
            if not text:
                continue
            if not verified(text, allowed):
                why.append(f'venn set "{text}" uses a number the narration never says')
                return True
            sets.append({"text": text})
        if len(sets) < 2:
            why.append("a venn needs 2 or 3 sets with a short text each")
            return True
        el.update(sets=sets, overlap=_num(e.get("overlap"), 0.15, 0.7, 0.35), both=_words(e.get("both"), 3))
        return False
    if t == "code":
        lines = [str(x).rstrip()[:44] for x in (e.get("lines") or [])[:10] if str(x).strip()]
        if len(lines) < 2:
            why.append("code needs 2 or more lines in \"lines\"")
            return True
        steps = []
        for st in (e.get("steps") or [])[:8]:
            if isinstance(st, dict) and isinstance(st.get("line"), (int, float)) and 1 <= int(st["line"]) <= len(lines):
                steps.append({"line": int(st["line"]), "note": _words(st.get("note"), 4)[:22]})
        out = [str(x)[:40] for x in (e.get("output") or [])[:3] if str(x).strip()]
        el.update(lines=lines, steps=steps, output=out, lang=_words(e.get("lang"), 1)[:12])
        return False
    if t == "wave":
        preset = e.get("preset")
        if preset == "square":
            ws = [{"freq": n, "amp": round(1 / n, 3)} for n in (1, 3, 5, 7, 9)]
        elif preset == "saw":
            ws = [{"freq": n, "amp": round(1 / n, 3)} for n in (1, 2, 3, 4, 5)]
        elif preset == "beats":
            ws = [{"freq": 5, "amp": 0.5}, {"freq": 5.6, "amp": 0.5}]
        else:
            ws = []
            for w in (e.get("waves") or [])[:5]:
                if isinstance(w, dict):
                    ws.append({"freq": _num(w.get("freq"), 0.5, 12, 1), "amp": _num(w.get("amp"), 0.05, 1, 0.5)})
        if len(ws) < 2:
            why.append('a wave needs 2 or more "waves" (or a "preset")')
            return True
        el.update(waves=ws, mode="fourier" if e.get("mode") == "fourier" else "sum", text=_words(e.get("text"), 5))
        return False
    if t == "surface":
        expr = str(e.get("expr") or "").strip()[:60]
        lo, hi = _num(e.get("lo"), -1e3, 1e3, -3), _num(e.get("hi"), -1e3, 1e3, 3)
        if hi <= lo:
            lo, hi = -3, 3
        try:
            f = compile_expr(expr, "y")
        except ValueError:
            why.append(f'surface "expr" {expr[:40]!r} is not a surface in x and y (numbers, x, y, + - * / ^, sin cos tan exp log sqrt abs, pi, e)')
            return True
        if finite_share(f, lo, hi, [lo, (lo + hi) / 2, hi]) < 0.8:
            why.append(f'surface "{expr[:40]}" is not a real number across {lo} to {hi}')
            return True
        start = e.get("start")
        try:
            sx, sy = (float(start[0]), float(start[1]))
            start = [min(hi, max(lo, sx)), min(hi, max(lo, sy))]
        except (TypeError, ValueError, IndexError, KeyError):
            start = [round(0.8 * hi, 2), round(-0.7 * hi, 2)]
        el.update(expr=expr, lo=lo, hi=hi, descent=bool(e.get("descent")), start=start, text=_words(e.get("text"), 5))
        return False
    if t == "bars":
        items = []
        for it in (e.get("items") or [])[:8]:
            if isinstance(it, dict) and _words(it.get("text"), 3):
                items.append({"text": _words(it.get("text"), 3), "value": _num(it.get("value"), 0, 1e9, 0)})
        if len(items) < 2 or max(i["value"] for i in items) <= 0:
            why.append('bars need 2 or more "items" with a text and a positive value')
            return True
        to = e.get("to")
        to = [_num(v, 0, 1e9, items[k]["value"]) for k, v in enumerate(to)] if isinstance(to, list) and len(to) == len(items) else None
        shown = bool(e.get("show")) and all(verified(str(int(v) if v == int(v) else v), allowed)
                                            for v in [i["value"] for i in items] + (to or []))
        el.update(items=items, show=shown, sort=bool(e.get("sort")), unit=_words(e.get("unit"), 2), text=_words(e.get("text"), 5))
        if to:
            el["to"] = to
        return False
    if t == "flow":
        stages = []
        for sg in (e.get("stages") or [])[:5]:
            if isinstance(sg, dict) and _words(sg.get("text"), 2):
                stages.append({"text": _words(sg.get("text"), 2), "share": _num(sg.get("share"), 0, 1, 1)})
        if len(stages) < 2:
            why.append('a flow needs 2 to 5 "stages" with a text and a share')
            return True
        top = stages[0]["share"] or 1
        prev = 1.0
        for sg in stages:
            sg["share"] = round(max(0.05, min(prev, sg["share"] / top)), 3)
            prev = sg["share"]
        el.update(stages=stages, text=_words(e.get("text"), 5))
        return False
    if t == "cycle":
        nodes = [_words(n, 2) for n in (e.get("nodes") or [])[:7] if _words(n, 2)]
        if len(nodes) < 3:
            why.append("a cycle needs 3 to 7 stages (short texts)")
            return True
        bad = [n for n in nodes if not verified(n, allowed)]
        if bad:
            why.append(f'cycle stage "{bad[0]}" uses a number the narration never says')
            return True
        el.update(nodes=nodes, text=_words(e.get("text"), 2))
        return False
    return False


def check(raw, scene: dict, verified: Callable[[str, str], bool], tex_ok: Callable[[str], bool],
          why: Optional[List[str]] = None) -> Optional[dict]:
    """The diagram as the video can draw it, or None if it is too thin, too crowded or untrue. why, if given,
    collects what was dropped or wrong, in words the designer can act on."""
    why = why if why is not None else []
    if not isinstance(raw, dict) or not isinstance(raw.get("elements"), list):
        why.append("the reply had no element list")
        return None
    narration = str(scene.get("narration", ""))
    allowed = f"{narration} {scene.get('headline', '')}"
    out = []
    raw_at: Dict[int, int] = {}            # the model's element positions -> ours (some are dropped)
    ids: Dict[str, int] = {}
    for k_raw, e in enumerate(raw["elements"][:MAX_ELEMENTS]):
        if not isinstance(e, dict) or e.get("type") not in TYPES:
            continue
        t = e["type"]
        raw_at[k_raw] = len(out)
        if str(e.get("id") or "").strip():
            ids[str(e["id"]).strip()[:24]] = len(out)
        el = {"type": t, "color": e.get("color") if e.get("color") in COLOURS else ("accent" if t != "label" else "text"),
              "on": _on(e.get("on"), narration), "anim": e.get("anim") if e.get("anim") in ANIMS else ""}
        xy = lambda k, d=50: _num(e.get(k), 3, 97, d)          # noqa: E731
        if t in ("dot", "circle", "label", "icon", "tex", "shape", "counter", "stamp"):
            el.update(x=xy("x"), y=xy("y"))
        if t == "stamp":
            el.update(text=_words(e.get("text"), 2).upper()[:16], size=e.get("size") if e.get("size") in SIZES else "l")
            if not el["text"] or any(o["type"] == "stamp" for o in out):
                continue
        if t in REGIONS:
            lo_w, lo_h = {"samples": (40, 50), "physics": (20, 60), "crowd": (10, 10), "plot": (40, 45),
                          "network": (40, 45), "tree": (40, 40), "grid": (30, 35), "venn": (35, 45),
                          "cycle": (40, 50), "code": (35, 40), "wave": (40, 40), "surface": (40, 50),
                          "bars": (35, 35), "flow": (45, 40)}.get(t) or vizlib.TECH[t]["size"]
            el.update(x=_num(e.get("x"), 3, 97 - lo_w, 10), y=_num(e.get("y"), 3, 97 - lo_h, 10))
            el.update(w=_num(e.get("w"), lo_w, 97 - el["x"], max(lo_w, 60)), h=_num(e.get("h"), lo_h, 97 - el["y"], max(lo_h, 70)))
        if t == "samples":
            src = str(e.get("source") or "").lower()
            el.update(source=src if src in SOURCES else "skewed", n=int(_num(e.get("n"), 1, 100, 1)),
                      count=int(_num(e.get("count"), 30, 600, 300)), unit=_words(e.get("unit"), 2),
                      text=_words(e.get("text"), 5), mean=bool(e.get("mean")))
            lo, hi = _num(e.get("lo"), -1e6, 1e6, 0), _num(e.get("hi"), -1e6, 1e6, 100)
            if hi <= lo:
                lo, hi = 0, 100
            if el["source"] == "coin" and "lo" not in e and "hi" not in e:
                lo, hi = 0, 1
            el.update(lo=lo, hi=hi)
        if t == "physics":
            bins = e.get("bins")
            el.update(balls=int(_num(e.get("balls"), 20, 160, 110)), pegs=int(_num(e.get("pegs"), 0, 12, 10)),
                      bins=0 if bins in (0, False, "0") else int(_num(bins, 3, 15, 9)),
                      drop="spread" if e.get("drop") == "spread" else "center", text=_words(e.get("text"), 4))
        if t in RICH and _rich(el, e, allowed, verified, why):
            continue
        if t == "counter":
            try:
                el.update(to=float(e.get("to")), **{"from": float(e.get("from") or 0)})
            except (TypeError, ValueError):
                why.append("a counter needs numbers in \"from\" and \"to\"")
                continue
            el["to"] = int(el["to"]) if el["to"] == int(el["to"]) else el["to"]
            el["from"] = int(el["from"]) if el["from"] == int(el["from"]) else el["from"]
            if not verified(str(el["to"]), allowed):
                why.append(f'counter "{el["to"]}" is a number the narration never says')
                continue
            el.update(text=_words(e.get("text"), 3), size=e.get("size") if e.get("size") in SIZES else "l")
        if t == "shape":
            sh = str(e.get("shape") or "").lower()
            el.update(shape=sh if sh in SHAPES else "circle", size=_num(e.get("size"), 3, 40, 10), fill=bool(e.get("fill")))
        if t == "crowd":
            n = int(_num(e.get("count"), 4, 100, 20))
            el.update(name=graphics.icon(e.get("name") or "user", e.get("text") or ""), count=n,
                      highlight=int(_num(e.get("highlight"), 0, n, 0)))
        if t in ("dot", "dots"):
            el["r"] = _num(e.get("r"), 0.8, 6, 2.2)
        if t == "dots" or t == "curve":
            pts = [[_num(p[0], 3, 97, 50), _num(p[1], 3, 97, 50)]
                   for p in (e.get("points") or []) if isinstance(p, (list, tuple)) and len(p) == 2][:40]
            if len(pts) < (3 if t == "curve" else 2):
                continue
            el["points"] = pts
        if t == "circle":
            el.update(r=_num(e.get("r"), 2, 40, 10), fill=bool(e.get("fill")), text=_words(e.get("text"), 3))
        if t == "box":
            el.update(x=_num(e.get("x"), 3, 90, 40), y=_num(e.get("y"), 3, 90, 40),
                      w=_num(e.get("w"), 6, 90, 20), h=_num(e.get("h"), 6, 90, 20), text=_words(e.get("text"), 4))
            need = len(el["text"]) * 1.45 + 4 if el["text"] else 0       # a box always holds its own words
            if el["w"] < need:
                el["w"] = round(min(need, 90), 2)
                el["x"] = round(min(el["x"], 97 - el["w"]), 2)
        if t == "label":
            el.update(text=_words(e.get("text"), 5), size=e.get("size") if e.get("size") in SIZES else "m",
                      align=e.get("align") if e.get("align") in ("left", "center", "right") else "center")
            if not el["text"]:
                continue
        if t in ("arrow", "line"):
            el.update(x1=xy("x1", 20), y1=xy("y1", 50), x2=xy("x2", 80), y2=xy("y2", 50))
            if abs(el["x1"] - el["x2"]) + abs(el["y1"] - el["y2"]) < 4:
                continue
            if t == "arrow":
                el.update(bend=_num(e.get("bend"), -0.5, 0.5, 0), text=_words(e.get("text"), 3))
            else:
                el["dashed"] = bool(e.get("dashed"))
        if t == "bar":
            el.update(x=_num(e.get("x"), 3, 92, 40), y=_num(e.get("y"), 10, 97, 90), w=_num(e.get("w"), 2, 30, 8),
                      h=_num(e.get("h"), 1, 85, 30), text=_words(e.get("text"), 3))
        if t == "icon":
            el.update(name=graphics.icon(e.get("name"), e.get("text") or ""), size=_num(e.get("size"), 4, 30, 12))
        if t == "tex":
            tex = str(e.get("tex", "")).strip()
            if not tex or len(tex) > 80 or not tex_ok(tex):
                why.append(f'formula "{tex[:40]}" is not complete LaTeX that typesets')
                continue
            el.update(tex=tex, size=e.get("size") if e.get("size") in SIZES else "m")
        if not _text_ok(el.get("text", ""), allowed, verified):
            why.append(f'{t} "{el["text"]}" uses words or numbers the narration never says')
            continue
        if any(not _text_ok(el.get(k, ""), allowed, verified) for k in ("xlabel", "ylabel", "both")):
            why.append(f"{t}: an axis name or overlap name uses a number the narration never says")
            continue
        for motion in MOTIONS:
            m = e.get(motion)
            if motion == "fit" and t not in ("samples", "physics"):
                continue
            if isinstance(m, dict) and _on(m.get("on"), narration):
                mv = {"on": _on(m.get("on"), narration)}
                if motion == "mark":
                    mv["style"] = m.get("style") if m.get("style") in MARKS else "circle"
                if motion == "move":
                    for k in ("x", "y", "x1", "y1", "x2", "y2"):
                        if k in m:
                            mv[k] = _num(m[k], 3, 97, 50)
                    if "h" in m:
                        mv["h"] = _num(m["h"], 1, 85, 30)
                    if "r" in m:
                        mv["r"] = _num(m["r"], 0.8, 40, 5)
                    if t == "shape" and str(m.get("shape") or "").lower() in SHAPES:
                        mv["shape"] = str(m["shape"]).lower()
                    if t == "shape" and "size" in m:
                        mv["size"] = _num(m["size"], 3, 40, 10)
                    if t in ("curve", "dots") and isinstance(m.get("points"), list):
                        pts = [[_num(p[0], 3, 97, 50), _num(p[1], 3, 97, 50)] for p in m["points"]
                               if isinstance(p, (list, tuple)) and len(p) == 2][:40]
                        if len(pts) >= (3 if t == "curve" else 2):
                            mv["points"] = pts
                    if t == "dot" and m.get("along") not in (None, ""):
                        mv["along"] = m["along"]          # a curve's id or position; resolved below
                    if len(mv) == 1:
                        continue
                el[motion] = mv
        out.append(el)
    for el in out:                        # a dot travels along a curve that is really there
        mv = el.get("move")
        if mv and "along" in mv:
            ref = mv.pop("along")
            k = ids.get(str(ref).strip()) if not isinstance(ref, int) else raw_at.get(ref)
            if k is not None and out[k]["type"] == "curve":
                mv["along"] = k
            elif len(mv) == 1:
                el.pop("move")
    # a box with no words and nothing placed inside it is an empty placeholder on screen: it is left out
    def anchor(el: dict) -> tuple:
        if "points" in el:
            return (sum(p[0] for p in el["points"]) / len(el["points"]), sum(p[1] for p in el["points"]) / len(el["points"]))
        if "x1" in el:
            return ((el["x1"] + el["x2"]) / 2, (el["y1"] + el["y2"]) / 2)
        if el["type"] in REGIONS:
            return (el["x"] + el["w"] / 2, el["y"] + el["h"] / 2)
        return (el.get("x", -1), el.get("y", -1))
    empty = {k for k, el in enumerate(out) if el["type"] == "box" and not el.get("text") and not any(
        j != k and el["x"] <= anchor(o)[0] <= el["x"] + el["w"] and el["y"] <= anchor(o)[1] <= el["y"] + el["h"]
        for j, o in enumerate(out))}
    if empty:
        why.append(f"{len(empty)} empty box(es) with no text and nothing inside were left out")
        new_at = {k: n for n, k in enumerate(k for k in range(len(out)) if k not in empty)}
        out = [el for k, el in enumerate(out) if k not in empty]
        for el in out:
            if el.get("move") and "along" in el["move"]:
                el["move"]["along"] = new_at[el["move"]["along"]]
    if len(out) < 3 and not any(el["type"] in vizlib.TECH for el in out):     # a library technique is a whole picture
        why.append(f"only {len(out)} usable element(s); a diagram needs at least 3")
        return None
    hit = collision(out)
    if hit:                               # pieces on top of each other read badly; the shot keeps its other picture
        why.append(f"{describe(out[hit[0]])} and {describe(out[hit[1]])} overlap; move them apart")
        return None
    return {"elements": out}


def design(complete_json: Callable, scenes: List[dict], idx: List[int], title: str, mood: str,
           verified: Callable[[str, str], bool], tex_ok: Callable[[str], bool], log: Callable[[str], None],
           style: str = "") -> int:
    """Design diagrams for the shots in idx (a few per request); a design the checks refuse is asked for once more,
    with the reason. Returns how many were usable."""
    made = 0
    failed: Dict[int, List[str]] = {}
    batches = [(idx[start:start + BATCH], "") for start in range(0, len(idx), BATCH)]
    for attempt in range(2):
        for part, note in batches:
            try:
                reply = complete_json(prompt(scenes, part, title, mood, style) + note, max_tokens=8000, temperature=0.8)
            except Exception as exc:          # diagrams are an upgrade; a failed request leaves the shots as they are
                log(f"[diagram] no designs for shots {part}: {str(exc)[:100]}")
                continue
            for item in reply if isinstance(reply, list) else []:
                k = item.get("scene") if isinstance(item, dict) else None
                if k in part and not scenes[k].get("diagram"):
                    why: List[str] = []
                    d = check(item, scenes[k], verified, tex_ok, why)
                    parts = {el["type"] for el in d["elements"] if el["type"] in vizlib.TECH} if d else set()
                    want = scenes[k].get("want")
                    if d and not attempt and want and want not in parts:
                        why.append(f'the writer asked for a "{want}" part: build this shot around it')
                        d = None
                    elif d and not attempt and parts & used_parts([s for j, s in enumerate(scenes) if j != k]):
                        why.append(f'{", ".join(sorted(parts))} is already used in another shot: pick another part')
                        d = None
                    if d:
                        scenes[k]["diagram"] = d
                        failed.pop(k, None)
                        made += 1
                    else:
                        failed[k] = why
                        log(f"[diagram] shot {k}: unusable design ({'; '.join(why[:2])[:160]})")
        if not failed or attempt:
            break
        reasons = "\n".join(f"shot {k}: {'; '.join(w[:3]) or 'no usable elements'}" for k, w in failed.items())
        batches = [(sorted(failed), f"\n\nYour earlier designs for these shots could not be drawn:\n{reasons}\n"
                                    "Design them again, avoiding those problems.")]
    return made


def texts(d: Optional[dict]) -> List[str]:
    """The diagram's words, in a fixed order, for translation."""
    return [el["text"] for el in (d or {}).get("elements", []) if el.get("text")]


def retext(d: dict, new: List[str]) -> List[str]:
    for el in d.get("elements", []):
        if el.get("text"):
            el["text"], new = new[0], new[1:]
    return new


def timed(d: Optional[dict], words: List[tuple], frames: int, fps: int, lead: int) -> Optional[dict]:
    """A copy with frames: each element appears on its word (never later than ~0.7 s after its turn in a build
    spread over the first half of the shot) and moves, glows or hides on its own word."""
    if not d:
        return None
    spoken = [(round(a * fps) + lead, re.sub(r"[^\w'-]", "", w).lower()) for a, _, w in words]

    def frame_of(word: str) -> Optional[int]:
        return next((f for f, w in spoken if w == word), None) if word else None

    els = [dict(el) for el in d["elements"]]
    span = max(30, int(frames * 0.5))
    for k, el in enumerate(els):
        turn = lead + 4 + round(span * k / max(1, len(els)))
        hit = frame_of(el["on"])
        el["at"] = min(hit, turn + (20 if k else 0)) if hit is not None else turn      # the first lands at once
        for motion in MOTIONS:
            if el.get(motion):
                m = dict(el[motion])
                f = frame_of(m["on"])
                m["at"] = max(el["at"] + 10, f if f is not None else el["at"] + 30)
                if motion == "fit":              # the bell comes once the pile is (nearly) complete
                    m["at"] = max(m["at"], el["at"] + int(0.75 * (frames - el["at"])))
                if m["at"] > frames - 12:
                    m["at"] = max(el["at"] + 6, frames - 30)
                el[motion] = m
    return {"elements": els}


VISION = """Each image is the finished frame of one shot from an educational YouTube video, drawn as an animated
diagram. For image N the narration was:
{lines}
Judge each like a demanding editor of a top explainer channel: does the drawing clearly SHOW what the narration
says, and is it clean (nothing overlapping, cut off, crowded, tiny or confusing)? Reply with JSON:
{{"shots": [{{"n": 1, "score": 1-10, "problem": "one line, or empty"}}]}}"""


def vision_prompt(narrations: List[str]) -> str:
    return VISION.format(lines="\n".join(f"{n + 1}. {t}" for n, t in enumerate(narrations)))


def verdicts(reply, count: int) -> Dict[int, tuple]:
    """image number (0-based) -> (score, problem)"""
    out = {}
    for s in (reply or {}).get("shots", []) if isinstance(reply, dict) else []:
        try:
            n = int(s.get("n")) - 1
            if 0 <= n < count:
                out[n] = (float(s.get("score", 0)), str(s.get("problem") or "")[:120])
        except (TypeError, ValueError):
            continue
    return out
