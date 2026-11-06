"""Bespoke animated diagrams: for each shot a language model draws what the sentence explains, from a small
drawing vocabulary (points, point clouds, lines, arrows, curves, boxes, bars, labels, icons, formulas), and says on
which spoken word each piece appears, moves, glows or leaves. video/src/diagram.jsx draws it. Nothing here is a
layout template: the model composes every picture for its sentence. The guard rails are in the checking: known
pieces only, everything on the canvas, short labels taken from the narration, numbers only if they are spoken,
formulas KaTeX can typeset, labels that do not collide; and after rendering a vision model scores each diagram
and a weak one is dropped (the shot falls back to its library graphic)."""
import re
from typing import Callable, Dict, List, Optional

from . import graphics

TYPES = ("dot", "dots", "circle", "box", "label", "arrow", "line", "curve", "bar", "icon", "tex")
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
MOTION (optional on any element, each with its own "on" word, which must come after the element's own "on" word):
- "move": {{"on": word, then the new x, y (or x1, y1, x2, y2 for a line or arrow; h for a bar; r for a circle)}}
- "glow": {{"on": word}} (it pulses to draw the eye)      - "hide": {{"on": word}} (it fades away)

RULES: labels use words from the narration, placed right next to what they name; never write a number that is not
in the narration; text never overlaps other text or shapes; one idea per diagram; the eye follows the sentence."""

PROMPT = """You are the visual explainer of a channel like 3Blue1Brown, Kurzgesagt and StatQuest. For each shot
below, design ONE animated diagram that SHOWS what the narration says: the mechanism, the relationship, the change.
Not decoration, not a list of words. Ask: what would a brilliant teacher draw on the board while saying this exact
sentence, and what would MOVE while it is said? Every diagram is drawn fresh for its sentence; make each one look
different from the others.

Video: {title}  |  Mood: {mood}

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

Shots (index | headline | narration):
{shots}

Reply with a JSON list: [{{"scene": index, "elements": [...]}}]"""

REFINE = """You designed this animated diagram for one shot of an educational YouTube video.
Narration: "{narration}"
Headline (drawn above the canvas): "{headline}"
The image is the shot's last frame as rendered. Its JSON:
{diagram}

""" + SPEC + """

Judge the image like the art director of 3Blue1Brown, strictly: does it SHOW the idea of the sentence (not merely
name it)? Is it clean: nothing overlapping or cut off, labels readable and right next to what they name, the canvas
used well (not sparse, not crammed into one area), one clear focal point, and something that changes while the
sentence is said? Score 9-10 only for a picture a top channel would publish; any overlap or a cramped or sparse
layout is at most 6; a picture that only names the idea instead of showing it is at most 5. Then give an improved
version that fixes every problem you saw.
Reply: {{"score": 1-10 for the image as it is, "problem": "the main problem in one line, or empty",
"elements": [the complete improved element list in the same format, or [] if it is already excellent]}}"""

RETRY = """

Your improved version could not be drawn: {why}.
Send the complete improved element list again, fixing that as well. Same reply format."""


def refine_prompt(scene: dict, d: dict, icons: str) -> str:
    import json as _json
    plain = [{k: v for k, v in el.items() if k not in ("at",)} for el in d["elements"]]
    for el in plain:
        for m in ("move", "glow", "hide"):
            if isinstance(el.get(m), dict):
                el[m] = {k: v for k, v in el[m].items() if k != "at"}
    return REFINE.format(narration=scene.get("narration", ""), headline=scene.get("headline", ""),
                         diagram=_json.dumps(plain), icons=icons)


def prompt(scenes: List[dict], idx: List[int], title: str, mood: str) -> str:
    rows = "\n".join(f"{i} | {scenes[i].get('headline', '')} | {scenes[i].get('narration', '')}" for i in idx)
    return PROMPT.format(title=title, mood=mood or "-", icons=" ".join(sorted(graphics.ICONS)), shots=rows)


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
    for key in ("text",):
        t = el.get(key)
        if not t:
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
    for n, (k1, a, kind1) in enumerate(pieces):
        for k2, b, kind2 in pieces[n + 1:]:
            if k1 == k2:
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
    for e in raw["elements"][:MAX_ELEMENTS]:
        if not isinstance(e, dict) or e.get("type") not in TYPES:
            continue
        t = e["type"]
        el = {"type": t, "color": e.get("color") if e.get("color") in COLOURS else ("accent" if t != "label" else "text"),
              "on": _on(e.get("on"), narration), "anim": e.get("anim") if e.get("anim") in ANIMS else ""}
        xy = lambda k, d=50: _num(e.get(k), 3, 97, d)          # noqa: E731
        if t in ("dot", "circle", "label", "icon", "tex"):
            el.update(x=xy("x"), y=xy("y"))
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
        for motion in ("move", "glow", "hide"):
            m = e.get(motion)
            if isinstance(m, dict) and _on(m.get("on"), narration):
                mv = {"on": _on(m.get("on"), narration)}
                if motion == "move":
                    for k in ("x", "y", "x1", "y1", "x2", "y2"):
                        if k in m:
                            mv[k] = _num(m[k], 3, 97, 50)
                    if "h" in m:
                        mv["h"] = _num(m["h"], 1, 85, 30)
                    if "r" in m:
                        mv["r"] = _num(m["r"], 0.8, 40, 5)
                    if len(mv) == 1:
                        continue
                el[motion] = mv
        out.append(el)
    if len(out) < 3:
        why.append(f"only {len(out)} usable element(s); a diagram needs at least 3")
        return None
    hit = collision(out)
    if hit:                               # pieces on top of each other read badly; the shot keeps its other picture
        why.append(f"{describe(out[hit[0]])} and {describe(out[hit[1]])} overlap; move them apart")
        return None
    return {"elements": out}


def design(complete_json: Callable, scenes: List[dict], idx: List[int], title: str, mood: str,
           verified: Callable[[str, str], bool], tex_ok: Callable[[str], bool], log: Callable[[str], None]) -> int:
    """Design diagrams for the shots in idx (a few per request); a design the checks refuse is asked for once more,
    with the reason. Returns how many were usable."""
    made = 0
    failed: Dict[int, List[str]] = {}
    batches = [(idx[start:start + BATCH], "") for start in range(0, len(idx), BATCH)]
    for attempt in range(2):
        for part, note in batches:
            try:
                reply = complete_json(prompt(scenes, part, title, mood) + note, max_tokens=8000, temperature=0.8)
            except Exception as exc:          # diagrams are an upgrade; a failed request leaves the shots as they are
                log(f"[diagram] no designs for shots {part}: {str(exc)[:100]}")
                continue
            for item in reply if isinstance(reply, list) else []:
                k = item.get("scene") if isinstance(item, dict) else None
                if k in part and not scenes[k].get("diagram"):
                    why: List[str] = []
                    d = check(item, scenes[k], verified, tex_ok, why)
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
        for motion in ("move", "glow", "hide"):
            if el.get(motion):
                m = dict(el[motion])
                f = frame_of(m["on"])
                m["at"] = max(el["at"] + 10, f if f is not None else el["at"] + 30)
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
