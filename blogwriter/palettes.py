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

# name: (background, accent, hot, cool, violet, words it suits). The accent is a metal (gold, champagne, copper, platinum,
# rose gold); the other three chart colours are muted jewels (ruby, sapphire, amethyst, emerald, topaz). No neon, no
# cyan on black: the channel is a luxury brand, and every video keeps that feel while its colours still differ.
WORLDS: Dict[str, tuple] = {
    # dark
    "obsidian-gold": ("#0c0b0a", "#d4af6a", "#c4545c", "#5e8fc9", "#a086c8", "finance money market economy business formal strategy law premium"),
    "midnight-champagne": ("#0a1020", "#e3c88f", "#d9776b", "#6aa5d6", "#a99bd6", "tech software system design architecture cloud network infrastructure data engineering"),
    "emerald-brass": ("#07140f", "#c9a24f", "#cf6b5f", "#4fa88a", "#9d86c2", "statistics probability analysis measure sample nature health growth biology"),
    "claret-cream": ("#16090c", "#ecd9b5", "#d4786c", "#6c9ad0", "#b08fc9", "history war conflict story society politics culture drama retro vintage"),
    "espresso-copper": ("#130d09", "#d09a62", "#c9605a", "#6fa9a0", "#a98bc4", "craft heritage trade geography food culture economy retro vintage nostalgic"),
    "ink-platinum": ("#0d1117", "#d3dae6", "#d98a6a", "#6fa0d8", "#a592d6", "security privacy reliability science research precision math physics"),
    "aubergine-rose": ("#150c1b", "#e3a995", "#d4647a", "#7fa6d8", "#b69ae0", "creative ai art design brand imagination language model"),
    "sapphire-gold": ("#07122a", "#e0b95a", "#d9685c", "#67a3dc", "#9f8bd0", "space universe theory abstract learning education lesson"),
    "forest-gold": ("#0a130d", "#cfae6e", "#c9655a", "#5aa7a0", "#a58cc8", "climate environment earth agriculture energy resource"),
    "charcoal-bronze": ("#141414", "#c58f4e", "#cf6a5a", "#5c9ac6", "#a68ac4", "engineering industry power machine hardware code developer"),
    "onyx-rosegold": ("#0e0b0c", "#e2a98f", "#c9566a", "#6b97c9", "#a88bc9", "beauty fashion lifestyle psychology mind behaviour perception"),
    "navy-silver": ("#0a1322", "#c9d2de", "#d07a68", "#5f9ad6", "#9e8ed2", "aviation transport logistics shipping operations queue scheduling"),
    "teal-brass": ("#06181a", "#cfa55a", "#cf6f61", "#5fae9c", "#a08cc6", "ocean water medicine chemistry lab molecule reaction"),
    "plum-gold": ("#1a0d1f", "#d9b35e", "#d46a76", "#7aa1d6", "#b593dd", "music art literature poetry philosophy mentalism illusion"),
    "graphite-amber": ("#121314", "#d8a24a", "#c95f55", "#6898c4", "#a48bc6", "manufacturing engine mechanics automotive physics motion force"),
    "oxblood-gold": ("#1a0a0b", "#d6b36a", "#e08a74", "#6f98c8", "#ad90c8", "crime justice mystery detective paradox causation bias"),
    "slate-copper": ("#11161b", "#d08a5c", "#c75f63", "#5e9bc7", "#9f8cc9", "database storage server backend distributed cache consistency"),
    "pine-champagne": ("#0b1612", "#e6cf9c", "#cf7266", "#64a88e", "#a593c9", "probability randomness games chance sports odds"),
    "indigo-pearl": ("#0f0f24", "#e6e1d6", "#d77c86", "#7c9de0", "#b39be3", "quantum neural network deep learning research transformer llm"),
    "cocoa-gold": ("#170f0b", "#d9b067", "#c86a58", "#6aa3a6", "#a58ac2", "economics trade agriculture coffee markets supply demand"),
    # light
    "ivory-gold": ("#f7f2e8", "#9a7420", "#b23a48", "#2b5f8f", "#6b4a99", "education learning lesson basics introduction guide"),
    "parchment-green": ("#f3eddc", "#1f5c46", "#a8452f", "#2a5f8a", "#6e4b8e", "nature health sustainability farm garden environment biology"),
    "alabaster-navy": ("#f6f5f1", "#1b2f55", "#a8873a", "#8a3b45", "#5d4a8a", "business finance market formal strategy law policy"),
    "stone-bordeaux": ("#f1ede6", "#7a1f33", "#a07a2a", "#2d5a82", "#5f4a86", "news politics history culture debate society story"),
    "linen-ink": ("#f5f3ee", "#26324a", "#b0842f", "#9a3b3b", "#4f6b5a", "data statistics analysis report metrics neutral science"),
    "champagne-espresso": ("#f6ede0", "#5a3a24", "#b3862e", "#2f5d7c", "#774a87", "craft food culture travel geography heritage trade"),
    "pearl-sapphire": ("#f5f6f8", "#1f3b70", "#b0863a", "#9a3e4c", "#5b4b8f", "technology software engineering algorithms code api"),
    "cream-emerald": ("#f6f1e4", "#1e5a43", "#b07a2c", "#9c3f3a", "#5a4d8c", "biology health medicine nature growth ecology"),
    "porcelain-plum": ("#f5f1f3", "#5b2a55", "#a8862f", "#2d5d86", "#7a3a46", "psychology mind philosophy art literature language"),
    "sand-terracotta": ("#f4ece0", "#8a3d24", "#3d6a5a", "#2e5a7f", "#6a4b86", "geography travel culture archaeology history civilisation"),
    "mist-graphite": ("#f2f3f2", "#2b2f36", "#b07d2b", "#8c3a3a", "#3f6b6a", "math logic proof theory statistics minimal regression"),
    "vellum-burgundy": ("#f4efe6", "#6c1e2e", "#2f5a7d", "#9a7a2c", "#4e5f3e", "law justice policy debate ethics causation correlation"),
}

# the animated backdrops (video/src/fx.jsx and backdrops.jsx) and what each suits: only the soft, slow ones (the neon grid,
# the circuit, hex cells, stripes, bold orbs, dot fields and ripples read as a tech template, not as a brand)
BACKDROPS: Dict[str, str] = {
    "aurora": "calm creative ai space science soft",
    "paper": "education history notes lesson light",
    "rays": "energy hope sun power intro launch",
    "contour": "geography map terrain climate geopolitics nature earth",
    "waves": "sea signal finance flow audio calm market",
    "stars": "space night universe physics mystery cosmos",
    "bokeh": "city night human life story culture society",
    "flow": "wind fluid streaming traffic weather learning flow",
    "mesh": "abstract modern brand design product startup interface data statistics system",
    # drawn by a shader (video/src/silk.jsx): the richest ones, the brand's signature
    "silk": "luxury premium elegant brand rich calm story education lesson learning explained statistics system finance business culture",
    "marble": "luxury premium elegant brand formal law finance history power strategy politics economy classic",
    "dunes": "desert geography travel time patience history landscape calm",
    "smoke": "chemistry fire combustion engine mystery heat energy reaction",
    "constellation": "network graph connections distributed system social ai neural data",
    "orbits": "astronomy physics planets cycles probability gravity system",
    "glass": "modern product interface software design cloud api premium",
    "lattice": "architecture structure engineering database math geometry crystal",
    "sheen": "luxury premium brand finance gold metal elegant formal",
    "beam": "reveal spotlight story drama surprise paradox insight",
    "drift": "gentle calm basics introduction lesson nature seasons",
    "ink": "art writing literature psychology creative mind philosophy",
    "threads": "flow streaming connection language time series signal elegant",
}


# the caption styles (video/src/captions.jsx): the glass pill only; the owner liked it and disliked the others
CAPTIONS: Dict[str, str] = {
    "pill": "general neutral simple everything",
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


SHORTLIST = """You are the art director of a luxury-brand explainer channel (deep, rich, restrained: metals and jewel tones,
never neon). Choose the colours and the moving backdrop of ONE video so they suit its subject and feeling. Videos on one subject must not all look alike, so name your three best
colour worlds and three best backdrops, best first.

Video: {title}
Style: {style}
Mood: {mood}

Colour worlds (name, lightness, what it suits):
{worlds}

Backdrops (name: what it suits):
{backs}

Reply with JSON: {{"worlds": ["", "", ""], "backdrops": ["", "", ""]}}"""


def shortlist(complete_json, title: str, style: str, mood: str, log=print) -> tuple:
    """(worlds, backdrops) the model finds best for this video, only names that exist; ([], []) if it cannot say, and
    the keyword ranking below decides alone."""
    nl = chr(10)
    worlds = nl.join(f"- {k} ({'light' if colorsys.rgb_to_hls(*_rgb(v[0]))[1] > 0.5 else 'dark'}): {v[5]}"
                     for k, v in WORLDS.items())
    backs = nl.join(f"- {k}: {v}" for k, v in BACKDROPS.items())
    try:
        raw = complete_json(SHORTLIST.format(title=title, style=style, mood=mood or "-", worlds=worlds, backs=backs),
                            max_tokens=300, temperature=0.8)
    except Exception as exc:                        # colours are a nice-to-have; a failed call never stops the video
        log(f"[design] no colour shortlist from the model ({type(exc).__name__})")
        return [], []
    raw = raw if isinstance(raw, dict) else {}
    names = lambda key, known: [n for n in dict.fromkeys(str(x).strip().lower() for x in (raw.get(key) or [])[:8])
                                if n in known][:3]  # noqa: E731
    return names("worlds", WORLDS), names("backdrops", BACKDROPS)


def _pool(options: Dict[str, str], context: str, seed: str, liked: Sequence[str], avoid: Sequence[str], top: int) -> str:
    """The model's shortlist plus the two best keyword matches (so a model that always names the same three still
    varies), without what the last videos used (unless that leaves nothing); the title picks one."""
    pool = [n for n in dict.fromkeys(list(liked) + rank(options, context, seed, 2 if liked else top)) if n in options]
    pool = [n for n in pool if n not in avoid] or pool
    return pool[int(hashlib.sha256(("pick" + seed).encode()).hexdigest(), 16) % len(pool)]


def pick(context: str, seed: str, liked: Sequence[str] = (), avoid: Sequence[str] = ()) -> dict:
    """The colour world for a video: the model's shortlist (or, without one, the eight best keyword matches), not one
    of the last videos' worlds, and the title decides among the rest."""
    name = _pool({k: v[5] for k, v in WORLDS.items()}, context, seed, liked, avoid, 8)
    return {**world(name, seed), "world": name}


def backdrops(context: str, seed: str, skip: Sequence[str], liked: Sequence[str] = (), avoid: Sequence[str] = ()) -> str:
    """The animated backdrop, chosen the same way (leaving out those drawn for the other lightness)."""
    return _pool({k: v for k, v in BACKDROPS.items() if k not in skip}, context, seed,
                 [n for n in liked if n not in skip], avoid, 5)


def caption(context: str, seed: str, light: bool, avoid: Sequence[str] = ()) -> str:
    """The caption style for a video: ranked by its subject, not one of the last two videos' styles; the neon glow only
    on a dark design."""
    return _pool({k: v for k, v in CAPTIONS.items() if not (light and k == "glow")}, context, "cap" + seed, (), avoid, 4)


def photo_grade(seed: str) -> str:
    """How a video's photos and footage are graded into one look (after the cinematic skill's prep_assets, which
    grades every image into one palette): "duotone" (shadows and lights in the design's colours), "tint" (the duotone
    over the photo, so colours show through) or "natural" (as shot). Chosen by the title."""
    n = int(hashlib.sha256(("grade" + seed).encode()).hexdigest(), 16) % 10
    return "duotone" if n < 3 else "tint" if n < 7 else "natural"


# ---- memory: what the last videos used, so two in a row never share a look --------------------------------------
HISTORY_KEY = "design_history.json"
KEEP = {"worlds": 8, "backs": 5, "looks": 3, "captions": 2, "layouts": 1, "fonts": 6}


def load_history(settings) -> dict:
    """The recent worlds, backdrops and film looks ({} lists when storage is off or empty)."""
    import json
    from . import storage
    try:
        data = json.loads(storage.get_text(settings, HISTORY_KEY) or "{}")
    except ValueError:
        data = {}
    return {k: [str(x) for x in (data.get(k) or [])][-n:] for k, n in KEEP.items()}


def save_history(settings, history: dict, theme: dict) -> None:
    """Add this video's world, backdrop and film look (if any) and keep the last few."""
    import json
    from . import storage
    # a video in a film look has no world or backdrop of the libraries; every video adds to "looks" ("" = none), so
    # the last entries say whether the last videos had one
    new = {"worlds": theme.get("world"), "backs": theme.get("back"), "looks": (theme.get("look") or {}).get("slug", ""),
           "captions": theme.get("caption"),
           "layouts": json.dumps(theme["layout"], sort_keys=True) if theme.get("layout") else None}
    out = {k: ([*history.get(k, []), new[k]] if (new[k] or k == "looks") else history.get(k, []))[-n:] for k, n in KEEP.items()
           if k != "fonts"}
    out["fonts"] = [*history.get("fonts", []), *[f for f in (theme.get("display"), theme.get("body")) if f]][-KEEP["fonts"]:]
    storage.put_text(settings, HISTORY_KEY, json.dumps(out), "application/json")
