"""Art direction: a language model picks a motion graphic for each shot that has no strong picture (a flow, a hub
of players, a unit chart, kinetic type, a spotlight, a versus split or a stack of layers; video/src/graphics.jsx
draws them) and fills it with icons and short labels. The model only chooses and names; every layout is fixed,
so a graphic always looks right. Each choice is checked: known type and icons, short labels, verified numbers."""
import difflib
import re
from typing import Callable, Dict, List, Optional

# type -> (fewest, most) nodes
TYPES = {"flow": (2, 4), "hub": (3, 6), "spotlight": (2, 3), "versus": (2, 2), "stack": (3, 5), "kinetic": (0, 2),
         "grid": (0, 0)}
ELIGIBLE = {"hook", "photo", "list", "steps", "stat"}   # a quote keeps its words

# Lucide icon names (checked against lucide 0.468)
ICONS = set("""smartphone wallet credit-card banknote landmark building-2 building globe globe-2 earth map map-pin users
user user-check shield shield-check shield-alert lock unlock zap cpu server database cloud wifi signal link arrow-right
trending-up trending-down chart-line chart-bar chart-pie chart-column percent coins piggy-bank handshake scale gavel
factory truck ship plane fuel flame leaf sun battery-charging atom rocket satellite microscope flask-conical brain
lightbulb target flag clock calendar hourglass search eye message-circle mail bell qr-code scan-line fingerprint key
network share-2 layers box package shopping-cart store receipt indian-rupee dollar-sign euro bitcoin repeat refresh-cw
circle-check circle-x triangle-alert sparkles star heart activity gauge swords crown graduation-cap book-open newspaper
mic video camera monitor laptop code terminal bot cog wrench hammer house school hospital train-front car microchip
radio-tower cable plug wind droplets mountain trees tractor wheat pill stethoscope dna syringe baby person-standing
briefcase file-text clipboard-check badge-check medal trophy timer infinity split merge git-branch workflow boxes
container warehouse anchor fish ban siren vote megaphone hand-coins scroll pickaxe gem sprout cloud-rain thermometer
telescope orbit cctv""".split())

PROMPT = """You are the art director of a premium explainer channel (Kurzgesagt, Vox, Bloomberg graphics). Below are
shots of one video. For as many shots as possible (aim for at least 3 in 4), choose ONE motion graphic that makes the
sentence instantly clear, and fill it in.

Graphics:
- "flow": a process or chain, A -> B -> C. 2-4 nodes in order. (how money moves, supply chains, cause and effect)
- "hub": one centre and the 3-6 players around it. Needs "center". (ecosystems, who is involved)
- "spotlight": one central idea with 2-3 tags around it. Needs "center". (a single thing, a risk, a product)
- "versus": two sides compared, exactly 2 nodes. (rivals, before/after, old vs new)
- "stack": 3-5 layers from bottom to top. (layers of a system, levels, building blocks)
- "kinetic": the headline itself as bold animated type, with 0-2 floating icons. Only when the headline is a
  complete, punchy claim a viewer can read alone ("Half the world's payments"), never a label.
- "grid": a unit chart of 100 icons. ONLY for a shot whose number is a percentage; give just "icon".

Rules:
- Labels: 1-3 words, taken from or very close to the narration. Never invent a number, name or date.
- Icons: only from this list: {icons}
- Vary the graphics: never the same graphic in two shots in a row; use at least 4 different graphics in the video.
- Leave out a shot that no graphic fits.

Shots (index | kind | headline | number | narration):
{shots}

Reply with a JSON list: [{{"scene": index, "type": "...", "center": {{"icon": "...", "label": "..."}},
"nodes": [{{"icon": "...", "label": "..."}}], "icon": "..."}}] (center only for hub and spotlight, icon only for grid)."""


def prompt(scenes: List[dict]) -> str:
    rows = "\n".join(f"{i} | {s['kind']} | {s.get('headline', '')} | {s.get('number', '')} | {s.get('narration', '')}"
                     for i, s in enumerate(scenes) if s["kind"] in ELIGIBLE and not s.get("video"))
    return PROMPT.replace("{icons}", " ".join(sorted(ICONS))).replace("{shots}", rows) \
        .replace("{{", "{").replace("}}", "}")


def _label(text, allowed: str, verified: Callable[[str, str], bool]) -> Optional[str]:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if not text or len(text) > 24 or len(text.split()) > 3 or not verified(text, allowed):
        return None
    return text


def icon(name) -> str:
    """A real icon for the name the model gave: itself, the closest known name, or a neutral one."""
    name = re.sub(r"[^a-z0-9-]", "", str(name or "").lower().replace(" ", "-").replace("_", "-"))
    if name in ICONS:
        return name
    near = difflib.get_close_matches(name, ICONS, n=1, cutoff=0.7)
    return near[0] if near else "sparkles"


def _node(raw, allowed, verified) -> Optional[dict]:
    if not isinstance(raw, dict):
        return None
    label = _label(raw.get("label"), allowed, verified)
    return {"icon": icon(raw.get("icon")), "label": label} if label else None


def check(raw, scene: dict, verified: Callable[[str, str], bool]) -> Optional[dict]:
    """The graphic as the video can draw it, or None if any part of it is unusable."""
    if not isinstance(raw, dict) or raw.get("type") not in TYPES:
        return None
    kind = raw["type"]
    allowed = " ".join(str(scene.get(k, "")) for k in ("narration", "headline", "number", "label"))
    lo, hi = TYPES[kind]
    if kind == "grid":
        number = str(scene.get("number", ""))
        m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*%\s*", number)
        if not m or not 0 < float(m.group(1)) <= 100:
            return None
        return {"type": "grid", "icon": icon(raw.get("icon")), "number": number.replace(" ", ""),
                "label": scene.get("label") or ""}
    if kind == "kinetic" and len(str(scene.get("headline", "")).split()) > 7:
        return None
    nodes = [_node(n, allowed, verified) for n in (raw.get("nodes") or [])[:hi]]
    if any(n is None for n in nodes) or len(nodes) < lo:
        return None
    out = {"type": kind, "nodes": nodes}
    if kind in ("hub", "spotlight"):
        center = _node(raw.get("center"), allowed, verified)
        if not center:
            return None
        out["center"] = center
    return out


def assign(scenes: List[dict], reply, verified: Callable[[str, str], bool], log: Callable[[str], None]) -> int:
    """Put the checked graphics on their scenes; a graphic like the previous shot's is dropped."""
    picks = {}
    for raw in reply if isinstance(reply, list) else []:
        k = raw.get("scene") if isinstance(raw, dict) else None
        if isinstance(k, int) and 0 <= k < len(scenes) and scenes[k]["kind"] in ELIGIBLE and not scenes[k].get("video"):
            g = check(raw, scenes[k], verified)
            if g:
                picks[k] = g
            else:
                log(f"[graphics] shot {k}: unusable {str(raw)[:120]}")
    last = None
    for k, s in enumerate(scenes):
        g = picks.get(k)
        if g and g["type"] != last:
            s["graphic"] = g
        last = s["graphic"]["type"] if s.get("graphic") else None
    return sum(1 for s in scenes if s.get("graphic"))


def no_stock_photos(scenes: List[dict]) -> int:
    """For lessons and concepts: a picture shot the art director left without a graphic becomes the headline as
    animated type instead of a stock photo search (which, for ideas, returns unrelated pictures)."""
    n = 0
    for s in scenes:
        if s["kind"] in ("photo", "hook") and not s.get("graphic") and not s.get("video") and s.get("headline"):
            s["graphic"] = {"type": "kinetic", "nodes": []}
            n += 1
    return n


def labels(g: Optional[dict]) -> List[str]:
    """The graphic's words, in a fixed order, for translation."""
    if not g:
        return []
    return ([g["center"]["label"]] if g.get("center") else []) + [n["label"] for n in g.get("nodes", [])] + \
        ([g["label"]] if g["type"] == "grid" else [])


def relabel(g: dict, texts: List[str]) -> List[str]:
    """Put translated labels back (in the order of labels()); returns the texts left over."""
    if g.get("center"):
        g["center"]["label"], texts = texts[0], texts[1:]
    for n in g.get("nodes", []):
        n["label"], texts = texts[0], texts[1:]
    if g["type"] == "grid":
        g["label"], texts = texts[0], texts[1:]
    return texts


def _finder(words: List[tuple], fps: int, lead: int) -> Callable[[str], Optional[int]]:
    """text -> the frame the narrator says its longest word (or second longest), or None."""
    spoken = [(round(a * fps) + lead, w.lower()) for a, _, w in words]

    def when(text: str) -> Optional[int]:
        keys = sorted({w.lower() for w in re.findall(r"[^\W_]{3,}", text)}, key=len, reverse=True)
        for key in keys[:2]:
            hit = next((f for f, w in spoken if key in w), None)
            if hit is not None:
                return hit
        return None
    return when


def timed_parts(parts: List[dict], words: List[tuple], frames: int, fps: int, lead: int) -> List[dict]:
    """An equation's pieces with `at`: a labelled piece lands when its name is said, the others in reading order."""
    when = _finder(words, fps, lead)
    out, last = [], lead
    for k, p in enumerate(parts):
        hit = when(p["label"]) if p.get("label") else None
        guess = last + 6 if k else lead + 4
        latest = lead + 24 + 12 * k          # never leave the formula unseen for long, whatever the narration does
        out.append({**p, "at": min(hit, latest) if hit is not None and hit >= last else guess})
        last = out[-1]["at"]
    return out


def timed_steps(steps: List[dict], words: List[tuple], frames: int, fps: int, lead: int) -> List[dict]:
    """A derivation's lines with `at`: spread over the first 70% of the shot, or when the note's words are said
    if that is later; always in order and at least 20 frames apart, so each line is written before the next."""
    when = _finder(words, fps, lead)
    out, last = [], None
    span = max(1, len(steps) - 1)
    for k, st in enumerate(steps):
        at = lead + 4 + round((frames * 0.7 - lead) * k / span) if k else lead + 4
        hit = when(st.get("note", "")) if st.get("note") else None
        at = max(at, hit or 0, (last + 20) if last is not None else 0)
        out.append({**st, "at": at})
        last = at
    return out


def timed(g: Optional[dict], headline: str, words: List[tuple], frames: int, fps: int, lead: int) -> Optional[dict]:
    """A copy of the graphic with `at` (the frame its word is spoken) on every piece; pieces without a spoken
    match are spread over the first part of the shot, and a flow or stack never builds out of order."""
    if not g:
        return None
    g = {**g, "nodes": [dict(n) for n in g.get("nodes", [])], **({"center": dict(g["center"])} if g.get("center") else {})}
    when = _finder(words, fps, lead)

    pieces = ([g["center"]] if g.get("center") else []) + g["nodes"]
    span = max(30, int(frames * 0.6))
    for k, piece in enumerate(pieces):
        guess = lead + 6 + round(span * k / max(1, len(pieces)))
        hit = when(piece["label"])          # on its word, but never more than ~1 s after its place in the build
        piece["at"] = min(hit, guess + 30) if hit is not None else guess
    if g["type"] in ("flow", "stack"):
        for a, b in zip(g["nodes"], g["nodes"][1:]):
            b["at"] = max(b["at"], a["at"] + 8)
    if g["type"] == "grid":
        digits = re.findall(r"\d+", g["number"])[0]
        g["at"] = next((round(a * fps) + lead for a, _, w in words if digits in w), lead + 10)
    if g["type"] == "kinetic":
        g["words"] = []
        for k, w in enumerate(headline.split()):
            at = min(when(w), lead + 16 + 5 * k) if when(w) is not None else lead + 4 + 5 * k   # all read in ~1 s
            g["words"].append(max(at, g["words"][-1] + 3) if g["words"] else at)
    return g
