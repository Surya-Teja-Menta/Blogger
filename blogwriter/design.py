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
}
BACKGROUNDS = ("aurora", "orbs", "grid", "contour", "paper", "rays", "dots", "waves")
CUTS = ("zoomBlur", "slideBlur", "sweep", "pushCut", "iris", "clock", "flip", "wipe")
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

Reply with JSON: {{"palette": {{"bg": "#...", ...}}, "display": "...", "body": "...", "upper": false,
"background": "...", "cuts": ["..."], "pace": "..."}}"""


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


def _finish(palette: dict, display: str, body: str, upper: bool, back: str, cuts: List[str], pace: str,
            source: str) -> dict:
    speed, damping, stagger = PACES[pace]
    return {**palette, "light": luminance(palette["bg"]) > 0.4, "display": display, "body": body,
            "weight": _weight(display, 900), "upper": upper, "back": back, "cuts": cuts, "pace": pace,
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
    if display not in FONTS or body not in FONTS or len(FONTS[body][0]) < 2:    # body text needs regular and bold
        return None
    back = raw.get("background")
    cuts = [c for c in (raw.get("cuts") or []) if c in CUTS][:4]
    pace = raw.get("pace") if raw.get("pace") in PACES else "steady"
    if back not in BACKGROUNDS or len(cuts) < 2:
        return None
    return _finish(pal, display, body, bool(raw.get("upper")), back, cuts, pace, "designed")


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
                   rnd.sample(CUTS, 4), rnd.choice(list(PACES)), "generated")


def prompt(title: str, style: str, mood: str) -> str:
    return PROMPT.format(title=title, style=style, mood=mood or "-", fonts=", ".join(FONTS),
                         backs=", ".join(BACKGROUNDS), cuts=", ".join(CUTS))


def design(complete_json: Callable, title: str, style: str, mood: str, log: Callable[[str], None]) -> dict:
    try:
        d = check(complete_json(prompt(title, style, mood), max_tokens=900, temperature=1.0))
    except Exception as exc:            # a design is a nice-to-have; a failed call never stops the video
        log(f"[design] no design from the model ({type(exc).__name__})")
        d = None
    d = d or generate(title)
    log(f"[design] {d['source']}: {d['display']}/{d['body']}, {d['back']}, {d['pace']}, "
        f"{'light' if d['light'] else 'dark'} {d['bg']} accent {d['accent']}")
    return d
