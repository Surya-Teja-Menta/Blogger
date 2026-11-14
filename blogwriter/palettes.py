"""Colour worlds and backdrops for the videos, chosen by what a video is about.

Why this exists: the art director (a language model) designed every palette itself, and it kept answering with the
same orange-red accent (#ff5342) on a near-white page; and the backdrop it chose was never drawn at all. Viewers
noticed ("all your videos look the same"). Now the code draws the colours from a library of colour worlds, ranked by
the video's subject and mood, picked among the best few by the title (so same-subject videos still differ), and
slightly shifted in hue per video, so no two videos share a palette."""
import colorsys
import hashlib
import random
from typing import Dict, List, Sequence

# name: (background, accent, hot, cool, violet, words it suits). The last three colours are the other chart colours.
WORLDS: Dict[str, tuple] = {
    # dark
    "ocean": ("#06141f", "#2ee6d6", "#ffb454", "#4aa3ff", "#9b8cff", "science water sea data research calm learning"),
    "forest": ("#08150f", "#8be28b", "#f2c14e", "#4fd1c5", "#c792ea", "nature health climate biology growth calm"),
    "ember": ("#140b08", "#ff7a2f", "#ffd166", "#5ec8d8", "#c77dff", "history war energy power fire industry"),
    "plum": ("#120a1c", "#e879f9", "#ffb86b", "#5eead4", "#a78bfa", "creative ai art design culture imagination"),
    "midnight-gold": ("#0a0f1f", "#f5c542", "#ff6b81", "#5aa9ff", "#b39ddb", "finance money market economy business formal"),
    "graphite-lime": ("#101214", "#b6f23a", "#ff5c8a", "#38bdf8", "#a78bfa", "code software developer tech system engineering"),
    "wine": ("#1a0a10", "#ff6b8b", "#ffc857", "#6ee7b7", "#c4b5fd", "society people human story relationship emotion"),
    "petrol": ("#07191c", "#5eead4", "#fbbf24", "#60a5fa", "#f0abfc", "network cloud infrastructure data pipeline"),
    "indigo-night": ("#0b0b2a", "#7c8cff", "#ff7eb6", "#3ee0ff", "#c4a1ff", "space math physics universe theory abstract"),
    "copper": ("#17110d", "#e0a15f", "#e5675a", "#7cc4b8", "#b8a1e3", "craft history culture heritage geography trade"),
    "emerald": ("#05140e", "#34e89e", "#f7d046", "#3fb9ff", "#d6a3ff", "statistics probability analysis measure sample"),
    "slate-rose": ("#12151c", "#ff8fab", "#ffd27d", "#7dd3fc", "#c3b1ff", "design product user interface brand"),
    "arctic": ("#08121a", "#8ee3ff", "#ffcf70", "#7aa2ff", "#c9a7ff", "security privacy reliability calm precision"),
    "olive": ("#11140a", "#c8e65a", "#ff9f5a", "#6dd5c3", "#d0a2f7", "agriculture food earth survival resource"),
    "noir": ("#130708", "#ff3b5c", "#ffb02e", "#4cc9f0", "#b388ff", "crime conflict risk failure attack danger breach"),
    "neon": ("#080818", "#00f5d4", "#ff3cac", "#4361ee", "#b517ff", "cyber future ai model neural machine learning"),
    "dusk": ("#1a0f2e", "#ff9e64", "#ff5d8f", "#4cc9f0", "#b794f6", "evening story narrative film media music"),
    "deep-teal": ("#031a1a", "#3dd9b8", "#ff8a65", "#5aa0ff", "#c39bff", "ocean medicine biology cell protein"),
    # light
    "paper-cobalt": ("#f6f4ee", "#2748d8", "#e5484d", "#0e9f8e", "#7b4fd0", "education learning lesson basics introduction guide"),
    "cream-forest": ("#f4f1e6", "#1f7a4d", "#d9822b", "#2b7fb8", "#8b5fbf", "nature health sustainability farm garden"),
    "mint-ink": ("#eefaf5", "#0f8a73", "#e4572e", "#2f6fdd", "#8a4fff", "health biology wellness data science"),
    "lilac": ("#f5f0ff", "#6d3fe0", "#e0457b", "#1e90c9", "#b15cd6", "creative ai art model language generative"),
    "sand-teal": ("#f7f1e8", "#0b7a86", "#d65a31", "#3b6fb6", "#8e5ea2", "history culture geography trade travel"),
    "sky": ("#eef6ff", "#1a62d6", "#ef5b5b", "#00a3a3", "#6b4ed8", "tech cloud software system network calm"),
    "blush": ("#fff1f2", "#c2255c", "#d9480f", "#1c7ed6", "#7048e8", "people human society relationship story"),
    "lemon": ("#fffbe6", "#a16207", "#dc2626", "#0369a1", "#7e22ce", "playful fun game puzzle quiz mystery curious"),
    "fog": ("#f1f3f5", "#0d9488", "#e11d48", "#2563eb", "#7c3aed", "data statistics analysis report metrics neutral"),
    "peach-navy": ("#fff4ea", "#1e3a8a", "#ea580c", "#0f766e", "#9333ea", "business finance market formal strategy"),
    "sage": ("#eef3ea", "#3f7d3a", "#c2410c", "#1d4ed8", "#86198f", "environment earth food growth farming"),
    "ice": ("#eaf4f8", "#0284c7", "#db2777", "#059669", "#6d28d9", "science physics energy water research"),
    "linen-red": ("#f8f4ef", "#b42318", "#b54708", "#175cd3", "#6941c6", "news politics law policy debate geopolitics"),
}

# the animated backdrops (video/src/fx.jsx and backdrops.jsx) and what each suits
BACKDROPS: Dict[str, str] = {
    "aurora": "calm creative ai space science soft",
    "orbs": "playful creative brand bold",
    "grid": "tech retro code data computing network future",
    "contour": "geography map terrain climate geopolitics nature earth",
    "paper": "education history notes lesson light",
    "rays": "energy hope sun power intro launch",
    "dots": "data statistics analysis pixels measure sample",
    "waves": "sea signal finance flow audio calm market",
    "stars": "space night universe physics mystery cosmos",
    "circuit": "electronics hardware chip computing network system infrastructure",
    "hexgrid": "chemistry molecule network blockchain cell material security",
    "bokeh": "city night human life story culture society",
    "ripples": "physics wave sound water impact spread event news cause",
    "stripes": "sports speed energy bold news motion race",
    "flow": "wind fluid streaming traffic weather learning flow",
    "mesh": "abstract modern brand design product startup interface",
}


def rank(options: Dict[str, str], context: str, seed: str, top: int) -> List[str]:
    """The `top` options that best fit the context (how many of their words it contains, whole words and stems),
    ties and the rest broken by the seed, so the same title always gets the same list."""
    rnd = random.Random(int(hashlib.sha256(seed.encode()).hexdigest(), 16))
    words = {w.rstrip("s") for w in context.lower().replace("-", " ").split() if len(w) > 2}
    scored = [(-sum(1 for w in text.split() if w.rstrip("s") in words), rnd.random(), name) for name, text in options.items()]
    return [name for _, _, name in sorted(scored)[:top]]


def choose(options: Dict[str, str], context: str, seed: str, top: int = 6) -> str:
    """One option: among the best-fitting few, the one the seed lands on (so a subject has several looks)."""
    best = rank(options, context, seed, top)
    return best[int(hashlib.sha256(("pick" + seed).encode()).hexdigest(), 16) % len(best)]


def _rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _hex(rgb) -> str:
    return "#" + "".join(f"{round(min(1, max(0, c)) * 255):02x}" for c in rgb)


def _turn(colour: str, by: float) -> str:
    """The colour with its hue turned a little (by is a share of the colour wheel), lightness and saturation kept."""
    h, l, s = colorsys.rgb_to_hls(*_rgb(colour))
    return _hex(colorsys.hls_to_rgb((h + by) % 1, l, s))


def world(name: str, seed: str) -> dict:
    """The nine colours of a world (design.COLOURS), its hue turned a few degrees by the seed so no two videos match.
    Cards, rules and text are derived from the background; the caller still runs design.fit for contrast."""
    bg, accent, hot, cool, violet, _ = WORLDS[name]
    rnd = random.Random(int(hashlib.sha256(("hue" + seed).encode()).hexdigest(), 16))
    by = rnd.uniform(-0.03, 0.03)
    bg, accent, hot, cool, violet = (_turn(c, by) for c in (bg, accent, hot, cool, violet))
    h, l, s = colorsys.rgb_to_hls(*_rgb(bg))
    light = l > 0.5

    def tone(lightness: float, sat: float) -> str:
        return _hex(colorsys.hls_to_rgb(h, lightness, sat))
    if light:
        panel, line, text, muted = tone(0.99, s), tone(l - 0.1, s * 0.8), tone(0.09, 0.3), tone(0.36, 0.12)
    else:
        panel, line, text, muted = tone(l + 0.05, s), tone(l + 0.13, s * 0.8), tone(0.95, 0.25), tone(0.66, 0.18)
    return {"bg": bg, "panel": panel, "line": line, "text": text, "muted": muted,
            "accent": accent, "hot": hot, "cool": cool, "violet": violet}


def pick(context: str, seed: str) -> dict:
    """The colour world for a video: ranked by its subject and mood words, chosen by the title among the best eight."""
    name = choose({k: v[5] for k, v in WORLDS.items()}, context, seed, 8)
    return {**world(name, seed), "world": name}


def backdrops(context: str, seed: str, skip: Sequence[str]) -> str:
    """The animated backdrop: the best-fitting few for the subject (leaving out those drawn for the other
    lightness), the title picks one."""
    return choose({k: v for k, v in BACKDROPS.items() if k not in skip}, context, seed, 5)
