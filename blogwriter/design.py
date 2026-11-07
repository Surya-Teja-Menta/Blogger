"""A fresh look for every video. A language model designs it from the topic and the mood of the script: a colour
palette, a font pairing, a moving background, the transitions and the pace of motion. Nothing is a preset: the
model writes the colours itself, and if its design fails a check (unreadable contrast, unknown font) a new design
is generated from the title instead, so two videos never share a look. video/src/theme.js draws it."""
import colorsys
import hashlib
import random
import re
from typing import Callable, Dict, List, Optional

# font key (as imported in video/src/theme.js) -> (weights available, role)
FONTS: Dict[str, tuple] = {
    "Inter": ((400, 600, 800, 900), "both"), "BebasNeue": ((400,), "display"),
    "SpaceGrotesk": ((400, 500, 700), "both"), "Unbounded": ((400, 600, 800, 900), "display"),
    "PlayfairDisplay": ((400, 700, 900), "display"), "Manrope": ((400, 600, 800), "both"),
    "Oswald": ((400, 500, 700), "display"), "Sora": ((400, 600, 800), "both"),
    "DMSerifDisplay": ((400,), "display"), "Fraunces": ((400, 700, 900), "display"),
    "Archivo": ((400, 600, 800, 900), "both"), "Syne": ((400, 600, 800), "display"),
    "RobotoSlab": ((400, 700, 900), "display"), "Anton": ((400,), "display"),
    "Lora": ((400, 700), "body"), "IBMPlexSans": ((400, 600, 700), "body"),
    "Outfit": ((400, 600, 800, 900), "both"), "BricolageGrotesque": ((400, 600, 800), "both"),
    "InstrumentSerif": ((400,), "display"), "Lexend": ((400, 600, 800), "both"),
    "Poppins": ((400, 600, 800, 900), "both"), "Montserrat": ((400, 600, 800, 900), "both"),
    "LibreBaskerville": ((400, 700), "display"), "WorkSans": ((400, 600, 800), "both"),
    "Rubik": ((400, 600, 800, 900), "both"), "BarlowCondensed": ((400, 600, 800), "display"),
    "ArchivoBlack": ((400,), "display"), "AbrilFatface": ((400,), "display"),
    "Merriweather": ((400, 700, 900), "both"), "Nunito": ((400, 700, 900), "body"),
    "DMSans": ((400, 600, 800), "body"),
    # used only by the film looks (looks.py): handwriting, technical and period faces
    "Kalam": ((400, 700), "hand"), "ArchitectsDaughter": ((400,), "hand"), "Caveat": ((400, 700), "hand"),
    "PatrickHand": ((400,), "hand"), "SpecialElite": ((400,), "hand"), "IBMPlexMono": ((400, 600), "mono"),
    "ShareTechMono": ((400,), "mono"), "VT323": ((400,), "mono"), "CourierPrime": ((400, 700), "mono"),
    "CormorantGaramond": ((400, 600, 700), "look"), "Limelight": ((400,), "look"), "Bungee": ((400,), "look"),
}
OPEN_FONTS = [f for f, (_, role) in FONTS.items() if role in ("display", "both", "body")]   # what a free design picks
BACKGROUNDS = ("aurora", "orbs", "grid", "contour", "paper", "rays", "dots", "waves")
CUTS = ("zoomBlur", "slideBlur", "sweep", "pushCut", "iris", "clock", "flip", "wipe")
DARK_ONLY = ("grid", "orbs")      # backdrops drawn for dark backgrounds
PACES = {"calm": (0.6, 22, 3.5), "steady": (1.0, 16, 2.5), "brisk": (1.5, 12, 1.6)}   # speed, damping, stagger
COLOURS = ("bg", "panel", "line", "text", "muted", "accent", "hot", "cool", "violet")

PROMPT = """You are the art director of a premium YouTube channel. Design the complete look of ONE video from scratch,
so it feels made for this subject and unlike any other video. Think about what the subject feels like (a lesson on
statistics, a war story, a space mystery, a business deal) and design for that feeling.

Video: {title}
Style: {style}
Mood words: {mood}

Decide:
- "palette": 9 hex colours. "bg" background, "panel" cards (close to bg), "line" rules and grids, "text" body text
  (very high contrast with bg), "muted" secondary text, "accent" the one signature colour (strong contrast with
  bg), "hot", "cool", "violet": three more chart colours, distinct from each other and from accent.
  Dark or light backgrounds are both fine; choose what suits the subject.
- "display": the headline font, "body": the text font, from: {fonts}
- "upper": true to set headlines in capitals.
- "background": the moving backdrop, one of: {backs}
  (aurora: drifting colour fields; orbs: bold colour orbs; grid: retro perspective grid; contour: flowing map lines;
  paper: dotted paper with rings; rays: slowly turning light rays; dots: a drifting dot field; waves: layered waves)
- "cuts": 3 or 4 transitions between shots, from: {cuts}
- "pace": "calm", "steady" or "brisk" (how energetic the motion is).
- "title": "left" or "center" (where headlines sit); "kicker": "pill" (glass tag) or "rule" (accent line and
  spaced capitals) for the small label above each headline.
- "fx": the motion language, invented for THIS video (be inventive; it must not look like a stock template):
  "layers": 1 to 3 backdrop layers, each {{"shape": circle, ring, dot, square, line, plus, triangle or blob,
  "count": 1-80, "size": 0.004-0.7 (share of the screen), "speed": 0-3, "drift": up, down, left, right, orbit,
  float or pulse, "opacity": 0.02-0.5, "color": accent, hot, cool, violet or text, "blur": 0-60, "stroke": true/false}}
  (e.g. a starfield of tiny dots drifting up; a few huge blurred blobs; thin lines sliding right like data);
  "gradient": {{"x": 0-100, "y": 0-100, "color": ..., "strength": 0-0.4}} (a light source);
  "text": {{"enter": rise, blur, scale, slide, drop, mask, flip, spread or tilt}} (how words appear);
  "transitions": 2 to 4 of {{"shape": circle, diamond, split, bars, corner, diagonal or fade, "angle": -60 to 60,
  "blur": 0-30, "scale": 0-0.4, "spin": -20 to 20}};
  "motion": {{"ease": how every piece arrives, one of outExpo (fast then still), outQuart, outQuint, outCirc,
  outSine (soft), inOutSine (calm, documentary), inOutQuart, outBack (overshoots and settles), outElastic (springy
  wobble), spring (physical bounce) or snap (a crisp designer curve); "bounce": 0-1 (overshoot for outBack,
  outElastic and spring); "frames": 8-30 (how long an arrival takes at 30 fps); "from": first, last, center, edges or
  random (the order a group of dots, points or icons appears); "gap": 0.5-6 (frames between them)}};
  "camera": 0-2 (how much the camera drifts), "cards": {{"radius": 0-48, "fill": glass, solid or outline,
  "shadow": 0-1.5}}, "texture": {{"grain": 0-0.2, "vignette": 0-0.6}}, "bigWord": true/false (a giant outlined
  word drifting behind each shot).

Reply with JSON: {{"palette": {{"bg": "#...", ...}}, "display": "...", "body": "...", "upper": false,
"background": "...", "cuts": ["..."], "pace": "...", "title": "...", "kicker": "...", "fx": {{...}}}}"""


def _rgb(h: str) -> tuple:
    return tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))


def _hex(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02x}" for c in rgb)


def luminance(h: str) -> float:
    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


NEEDS = {"text": 7.0, "muted": 3.5, "accent": 3.0, "hot": 2.2, "cool": 2.2, "violet": 2.2}   # contrast with bg


def fit(colour: str, bg: str, need: float) -> str:
    """The colour with its hue and saturation kept, made lighter or darker (away from the background) until it
    has the contrast it needs."""
    h, l, s = colorsys.rgb_to_hls(*_rgb(colour))
    step = -0.02 if luminance(bg) > 0.4 else 0.02
    while contrast(colour, bg) < need and 0 < l < 1:
        l = min(1.0, max(0.0, l + step))
        colour = _hex(colorsys.hls_to_rgb(h, l, s))
    return colour


def _weight(font: str, want: int) -> int:
    return min(FONTS[font][0], key=lambda w: abs(w - want))


SHAPES = ("circle", "ring", "dot", "square", "line", "plus", "triangle", "blob")
DRIFTS = ("up", "down", "left", "right", "orbit", "float", "pulse")
FX_COLOURS = ("accent", "hot", "cool", "violet", "text")
ENTERS = ("rise", "blur", "scale", "slide", "drop", "mask", "flip", "spread", "tilt", "write")
CLIPS = ("circle", "diamond", "split", "bars", "corner", "diagonal", "fade")
# how pieces arrive (anime.js easing curves, drawn in video/src/motion.js) and in what order a group appears
EASES = ("outExpo", "outQuart", "outQuint", "outCirc", "outSine", "inOutSine", "inOutQuart", "outBack", "outElastic",
         "spring", "snap")
FROMS = ("first", "last", "center", "edges", "random")


def check_fx(raw, seed: str, light: bool = False) -> dict:
    """The motion language as the video can draw it: every number clamped to a safe range, every name checked;
    anything missing or wrong is drawn at random (seeded by the title), never taken from a preset."""
    rnd = random.Random(int(hashlib.sha256(("fx" + seed).encode()).hexdigest(), 16))
    raw = raw if isinstance(raw, dict) else {}

    def num(v, lo, hi, default):
        try:
            return round(min(hi, max(lo, float(v))), 3)
        except (TypeError, ValueError):
            return round(default, 3)

    def pick(v, options):
        return v if v in options else rnd.choice(options)

    layers = []
    for L in (raw.get("layers") or [])[:3]:
        if isinstance(L, dict):
            layers.append({"shape": pick(L.get("shape"), SHAPES), "count": int(num(L.get("count"), 1, 80, rnd.randint(4, 40))),
                           "size": num(L.get("size"), 0.004, 0.7, rnd.uniform(0.005, 0.3)),
                           "speed": num(L.get("speed"), 0, 3, rnd.uniform(0.2, 1.5)), "drift": pick(L.get("drift"), DRIFTS),
                           "opacity": num(L.get("opacity"), 0.02, 0.5, rnd.uniform(0.05, 0.3)),
                           "color": pick(L.get("color"), FX_COLOURS), "blur": num(L.get("blur"), 0, 60, 0),
                           "stroke": bool(L.get("stroke"))})
    while len(layers) < 1 + (rnd.random() < 0.6):          # at least one layer, often two
        big = rnd.random() < 0.35
        layers.append({"shape": "blob" if big else rnd.choice(SHAPES), "count": rnd.randint(2, 5) if big else rnd.randint(6, 60),
                       "size": rnd.uniform(0.25, 0.6) if big else rnd.uniform(0.004, 0.08), "speed": rnd.uniform(0.1, 1.6),
                       "drift": rnd.choice(DRIFTS), "opacity": rnd.uniform(0.08, 0.3) if big else rnd.uniform(0.06, 0.35),
                       "color": rnd.choice(FX_COLOURS[:4]), "blur": rnd.uniform(20, 50) if big else rnd.choice((0, 0, 2, 6)),
                       "stroke": rnd.random() < 0.4})
    g = raw.get("gradient") if isinstance(raw.get("gradient"), dict) else {}
    cuts = []
    for c in (raw.get("transitions") or [])[:4]:
        if isinstance(c, dict):
            cuts.append({"shape": pick(c.get("shape"), CLIPS), "angle": num(c.get("angle"), -60, 60, rnd.uniform(-40, 40)),
                         "blur": num(c.get("blur"), 0, 30, rnd.uniform(0, 16)), "scale": num(c.get("scale"), 0, 0.4, 0.1),
                         "spin": num(c.get("spin"), -20, 20, 0)})
    while len(cuts) < 2:
        cuts.append({"shape": rnd.choice(CLIPS), "angle": round(rnd.uniform(-45, 45), 1), "blur": round(rnd.uniform(0, 20), 1),
                     "scale": round(rnd.uniform(0, 0.3), 2), "spin": round(rnd.choice((0, 0, rnd.uniform(-12, 12))), 1)})
    text = raw.get("text") if isinstance(raw.get("text"), dict) else {}
    cards = raw.get("cards") if isinstance(raw.get("cards"), dict) else {}
    tex = raw.get("texture") if isinstance(raw.get("texture"), dict) else {}
    mo = raw.get("motion") if isinstance(raw.get("motion"), dict) else {}
    curve = pick(mo.get("ease"), EASES)
    springy = curve in ("outElastic", "spring")            # a wobble needs time to settle
    motion = {"ease": curve, "bounce": num(mo.get("bounce"), 0, 1, rnd.uniform(0.15, 0.7)),
              "frames": num(mo.get("frames"), 18 if springy else 8, 30, rnd.uniform(18 if springy else 10, 26)),
              "from": pick(mo.get("from"), FROMS), "gap": num(mo.get("gap"), 0.5, 6, rnd.uniform(0.8, 3.5))}
    return {"seed": seed[:24], "layers": layers, "motion": motion,
            "gradient": {"x": num(g.get("x"), 0, 100, rnd.uniform(10, 90)), "y": num(g.get("y"), 0, 100, rnd.uniform(0, 70)),
                         "color": pick(g.get("color"), FX_COLOURS[:4]), "strength": num(g.get("strength"), 0, 0.4, rnd.uniform(0.06, 0.25))},
            "text": {"enter": pick(text.get("enter"), ENTERS)}, "transitions": cuts,
            "camera": num(raw.get("camera"), 0, 2, rnd.uniform(0.3, 1.4)),
            "cards": {"radius": num(cards.get("radius"), 0, 48, rnd.uniform(4, 36)),
                      "fill": pick(cards.get("fill"), ("glass", "solid", "outline")),
                      "shadow": num(cards.get("shadow"), 0, 1.5, rnd.uniform(0.3, 1.2))},
            "texture": {"grain": num(tex.get("grain"), 0, 0.2, rnd.uniform(0, 0.12)),
                        "vignette": num(tex.get("vignette"), 0, 0.6, rnd.uniform(0, 0.45)) * (0.3 if light else 1)},
            "bigWord": bool(raw.get("bigWord")) if "bigWord" in raw else rnd.random() < 0.5}


def _finish(palette: dict, display: str, body: str, upper: bool, back: str, cuts: List[str], pace: str,
            source: str, title: str = "left", kicker: str = "pill", fx: Optional[dict] = None) -> dict:
    speed, damping, stagger = PACES[pace]
    fx = fx or check_fx(None, palette["bg"] + display, luminance(palette["bg"]) > 0.4)
    return {**palette, "fx": fx, "cuts": fx["transitions"], "named_cuts": cuts, "title": title if title in ("left", "center") else "left",
            "kicker": kicker if kicker in ("pill", "rule") else "pill", "light": luminance(palette["bg"]) > 0.4, "display": display, "body": body,
            "weight": _weight(display, 900), "upper": upper, "back": back, "pace": pace,
            "speed": speed, "damping": damping, "stagger": stagger, "source": source}


def check(raw) -> Optional[dict]:
    """The model's design as the video can draw it, or None if it is unreadable or uses unknown pieces."""
    if not isinstance(raw, dict) or not isinstance(raw.get("palette"), dict):
        return None
    pal = {k: str(raw["palette"].get(k, "")).strip().lower() for k in COLOURS}
    if not all(re.fullmatch(r"#[0-9a-f]{6}", v) for v in pal.values()):
        return None
    bg = pal["bg"]
    for key, need in NEEDS.items():          # a colour a little too faint keeps its hue and gets the contrast
        pal[key] = fit(pal[key], bg, need)
    if contrast(pal["text"], bg) < NEEDS["text"] or contrast(pal["panel"], bg) > 2.2:
        return None
    display, body = raw.get("display"), raw.get("body")
    if display not in OPEN_FONTS or body not in OPEN_FONTS or len(FONTS[body][0]) < 2:   # body needs regular and bold
        return None
    back = raw.get("background")
    cuts = [c for c in (raw.get("cuts") or []) if c in CUTS][:4]
    pace = raw.get("pace") if raw.get("pace") in PACES else "steady"
    if back not in BACKGROUNDS or len(cuts) < 2:
        return None
    if luminance(bg) > 0.4 and back in DARK_ONLY:     # a glowing grid or bold orbs wash a light design out
        back = "dots"
    return _finish(pal, display, body, bool(raw.get("upper")), back, cuts, pace, "designed",
                   raw.get("title"), raw.get("kicker"), check_fx(raw.get("fx"), pal["bg"] + display + pal["accent"], luminance(pal["bg"]) > 0.4))


def generate(seed: str) -> dict:
    """A new design from a seed (the title): colour harmony, fonts, backdrop and motion all drawn at random."""
    rnd = random.Random(int(hashlib.sha256(seed.encode()).hexdigest(), 16))
    light = rnd.random() < 0.35
    hue = rnd.random()
    harmony = rnd.choice(((0.5, 0.42, 0.58), (0.33, 0.66, 0.15), (0.08, 0.5, 0.92), (0.25, 0.5, 0.75)))

    def colour(h, s, l, need=0.0):
        """an HLS colour, moved away from the background until it has the contrast it needs"""
        c = _hex(colorsys.hls_to_rgb(h % 1, l, s))
        while need and contrast(c, bg) < need and 0.02 < l < 0.98:
            l += -0.03 if light else 0.03
            c = _hex(colorsys.hls_to_rgb(h % 1, l, s))
        return c

    bg = ""
    if light:
        bg = colour(hue, 0.25, 0.95)
        panel, line = colour(hue, 0.2, 0.99), colour(hue, 0.15, 0.82)
        text, muted = colour(hue, 0.3, 0.09, 7.5), colour(hue, 0.12, 0.36, 4)
        lit = 0.42
    else:
        bg = colour(hue, 0.45, 0.05)
        panel, line = colour(hue, 0.4, 0.1), colour(hue, 0.3, 0.2)
        text, muted = colour(hue, 0.25, 0.95, 7.5), colour(hue, 0.18, 0.66, 4)
        lit = 0.62
    acc = hue + harmony[0]
    pal = {"bg": bg, "panel": panel, "line": line, "text": text, "muted": muted,
           "accent": colour(acc, 0.9, lit, 3.2), "hot": colour(acc + harmony[1], 0.8, lit, 2.4),
           "cool": colour(acc + harmony[2], 0.75, lit, 2.4),
           "violet": colour(hue + 0.02, 0.7, lit + (0.08 if not light else -0.06), 2.4)}
    displays = [f for f, (_, role) in FONTS.items() if role in ("display", "both")]
    bodies = [f for f, (_, role) in FONTS.items() if role in ("body", "both")]
    display = rnd.choice(displays)
    upper = display in ("BebasNeue", "Anton", "Oswald", "BarlowCondensed") or rnd.random() < 0.3
    back = rnd.choice([b for b in BACKGROUNDS if light == (b == "paper") or b in ("dots", "waves", "rays")])
    return _finish(pal, display, rnd.choice([b for b in bodies if b != display]), upper, back,
                   rnd.sample(CUTS, 4), rnd.choice(list(PACES)), "generated",
                   rnd.choice(("left", "center")), rnd.choice(("pill", "rule")), check_fx(None, seed, light))


def prompt(title: str, style: str, mood: str) -> str:
    return PROMPT.format(title=title, style=style, mood=mood or "-", fonts=", ".join(OPEN_FONTS),
                         backs=", ".join(BACKGROUNDS), cuts=", ".join(CUTS))


def design(complete_json: Callable, title: str, style: str, mood: str, log: Callable[[str], None]) -> dict:
    """The video's look: a film style from the library when one suits the subject (looks.py), else a design of its
    own. FILM_LOOK=<key> or FILM_LOOK=free forces the choice."""
    import os
    from . import looks
    forced = os.environ.get("FILM_LOOK", "").strip().lower()
    picked = ((forced, next(iter(looks.LOOKS[forced]["accents"].values()))) if forced in looks.LOOKS else
              None if forced == "free" else looks.choose(complete_json, title, style, mood, log))
    if picked:
        d = looks.theme_for(picked[0], picked[1], _finish, check_fx, title)
        log(f"[design] film look {picked[0]}: {d['display']}/{d['body']}, surface {d['look']['surface']}, "
            f"lines {d['look']['stroke'] or 'clean'}, {'light' if d['light'] else 'dark'} {d['bg']} accent {d['accent']}")
        return d
    try:
        d = check(complete_json(prompt(title, style, mood), max_tokens=2000, temperature=1.0))
    except Exception as exc:            # a design is a nice-to-have; a failed call never stops the video
        log(f"[design] no design from the model ({type(exc).__name__})")
        d = None
    d = d or generate(title)
    fx = d["fx"]
    layers = ", ".join(f"{L['count']} {L['shape']}s {L['drift']}" for L in fx["layers"])
    log(f"[design] motion: {layers}; "
        f"words {fx['text']['enter']}; arrivals {fx['motion']['ease']} {fx['motion']['frames']:g}f from "
        f"{fx['motion']['from']}; cuts {'/'.join(c['shape'] for c in fx['transitions'])}; cards {fx['cards']['fill']}")
    log(f"[design] {d['source']}: {d['display']}/{d['body']}, {d['back']}, {d['pace']}, {d['title']}/{d['kicker']}, "
        f"{'light' if d['light'] else 'dark'} {d['bg']} accent {d['accent']}")
    return d
