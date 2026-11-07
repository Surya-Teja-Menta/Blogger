"""Film looks for the videos, after the style guides of the Lemo-Opuscar library (MIT licence, LemoLab,
https://github.com/lemomo-ai/lemo-opuscar): each is a surface, a way of drawing lines, type, a colour logic and a
motion character, drawn by video/src/looks.jsx. A language model picks the look that suits each video's subject (or
none, and the video gets a design of its own); the colour logic of the look is kept, and only the accent the style
leaves free (the accent chalk, the signal colour, the phosphor, the ink set) is chosen for the subject.

Only looks the renderer can really draw are offered; the other styles of the library (3D, games, cartoons, East Asian
traditions...) wait until it can. Credit: "Film styles after Lemo-Opuscar by LemoLab (MIT)"."""
from typing import Callable, Dict, Optional

# palette keys: bg, panel, line, text, muted, accent, hot, cool, violet (see design.py)
LOOKS: Dict[str, dict] = {
    "chalkboard": {
        "cuts_native": ('wipe', 'slideBlur'), "moves": "write the claim people believe, then cross it out or stamp it MYTH and write the true one beside it; circle in the accent chalk the one part the lesson tracks; few words, big letters",
        "name": "Chalkboard", "uses": "lessons, myth-busting, a misconception set right, a worked problem",
        "line": "chalk writes itself on a deep green slate: white for every structure, one accent chalk for the one thing tracked",
        "surface": "slate", "stroke": "chalk", "overlay": "", "display": "Kalam", "body": "Kalam", "hand": "Kalam",
        "palette": {"bg": "#1f3a31", "panel": "#264438", "line": "#5c7b6f", "text": "#f3f1ea", "muted": "#c8cfc5",
                    "accent": "#f2a45a", "hot": "#f4dc78", "cool": "#a9d6e5", "violet": "#eab0cc"},
        "accents": {"orange chalk": "#f2a45a", "pink chalk": "#f48fb1", "green chalk": "#8fd3a0", "yellow chalk": "#f4dc78"},
        "enter": "write", "ease": "outSine", "cards": "outline", "cuts": ("fade", "split"), "handwrite": "readability"},
    "whiteboard": {
        "cuts_native": ('slideBlur', 'pushCut'), "moves": "a map of connected ideas drawn by hand: boxes, arrows and little icons joined across the board; circle and underline what matters",
        "name": "Whiteboard Explainer", "uses": "explainers, online courses, science, how something works",
        "line": "a glossy dry-erase board, marker lines with a hand's wobble, three marker colours with fixed meanings",
        "surface": "whiteboard", "stroke": "marker", "overlay": "", "display": "ArchitectsDaughter", "body": "Kalam",
        "hand": "ArchitectsDaughter",
        "palette": {"bg": "#f6f7f8", "panel": "#ffffff", "line": "#d7dbe0", "text": "#23262c", "muted": "#5d636d",
                    "accent": "#d9603b", "hot": "#2a5cb3", "cool": "#2f9e6b", "violet": "#8f5bd1"},
        "accents": {"orange marker": "#d9603b", "red marker": "#d63a3a", "green marker": "#2f9e6b", "purple marker": "#8f5bd1"},
        "enter": "write", "ease": "outSine", "cards": "outline", "cuts": ("fade", "diagonal"), "handwrite": "tech"},
    "blueprint": {
        "cuts_native": ('slideBlur', 'wipe'), "moves": "technical drawings: dimension lines with measured labels, an exploded view (pieces moving apart), callout arrows; one red stamp for the verdict",
        "name": "Blueprint", "uses": "engineering, machines, hardware, tech explainers, how a system is built",
        "line": "white technical line work on Prussian-blue cyanotype paper with a drafting grid; one red stamp for the verdict",
        "surface": "blueprint", "stroke": "technical", "overlay": "", "display": "ArchitectsDaughter", "body": "ArchitectsDaughter",
        "hand": "ArchitectsDaughter",
        "palette": {"bg": "#1b3d78", "panel": "#214785", "line": "#5e86c3", "text": "#e9f1fa", "muted": "#b7cbe6",
                    "accent": "#ffffff", "hot": "#ff6b6b", "cool": "#9cc8ff", "violet": "#ffe08a"},
        "accents": {"white": "#ffffff"},
        "enter": "write", "ease": "inOutSine", "cards": "outline", "cuts": ("fade", "split"), "handwrite": "tech"},
    "dataviz": {
        "cuts_native": ('slideBlur', 'wipe'), "moves": "the data drawn mark by mark (live samples, bars, curves) with a handwritten note pinned to the number that matters",
        "name": "Data Storytelling", "uses": "data journalism, reports, climate and science, statistics, numbers that tell a story",
        "line": "charts drawn mark by mark on cream paper by a red and blue pencil, with handwritten notes on the numbers",
        "surface": "paper", "stroke": "", "overlay": "", "display": "LibreBaskerville", "body": "IBMPlexSans", "hand": "Caveat",
        "palette": {"bg": "#f6f1e6", "panel": "#fbf8f1", "line": "#d8cfbd", "text": "#1d2430", "muted": "#5b6573",
                    "accent": "#c23b31", "hot": "#2a64b0", "cool": "#4f8f86", "violet": "#b07a2a"},
        "accents": {"red pencil": "#c23b31", "blue pencil": "#2a64b0"},
        "enter": "rise", "ease": "outQuart", "cards": "solid", "cuts": ("fade", "corner")},
    "dark-keynote": {
        "cuts_native": ('zoomBlur', 'slideBlur'), "moves": "one giant number on its own; interface-like cards that snap into a grid; light that reveals the protagonist",
        "name": "Dark Tech Keynote", "uses": "technology, AI, software, product and platform explainers",
        "line": "near-black stage, hairline grid, soft light, one luminous accent reserved for the protagonist",
        "surface": "keynote", "stroke": "", "overlay": "", "display": "Inter", "body": "Inter", "hand": "Inter",
        "palette": {"bg": "#0a0c11", "panel": "#12161e", "line": "#232a36", "text": "#f2f4f8", "muted": "#8b93a3",
                    "accent": "#5b8cff", "hot": "#ff4d5e", "cool": "#5ad1ff", "violet": "#b18cff"},
        "accents": {"electric blue": "#5b8cff", "violet": "#8f6bff", "mint": "#2fd3a0", "amber": "#ffb020"},
        "enter": "blur", "ease": "snap", "cards": "glass", "cuts": ("fade", "diagonal")},
    "newsreel": {
        "cuts_native": ('iris', 'wipe'), "moves": "place-and-date cards, a map with a moving arrow, a headline that spins in; everything in silver",
        "name": "1920s Newsreel", "uses": "history stories, eras, anniversaries, how something began",
        "line": "a monochrome silver newsreel: cream type on near-black, Art Deco titles, vignette and film grain",
        "surface": "film", "stroke": "", "overlay": "film", "mono": True, "display": "Limelight", "body": "Oswald",
        "hand": "Oswald",
        "palette": {"bg": "#121110", "panel": "#1d1b18", "line": "#4a463f", "text": "#f3eee4", "muted": "#d6cfc0",
                    "accent": "#efe7d6", "hot": "#bdb5a6", "cool": "#9c9588", "violet": "#7d776c"},
        "accents": {"silver": "#efe7d6"},
        "enter": "scale", "ease": "outCirc", "cards": "outline", "cuts": ("fade", "circle"), "upper": True},
    "risograph": {
        "cuts_native": ('pushCut', 'slideBlur'), "moves": "flat shapes in two or three overprinting inks, bold type, a few big simple pictures per idea",
        "name": "Risograph Print", "uses": "lifestyle, culture, creative and indie subjects, light-hearted explainers",
        "line": "two or three translucent spot inks overprinted on warm paper, halftone dots, plates that never quite line up",
        "surface": "paper", "stroke": "ink", "overlay": "halftone", "misregister": "accent", "display": "BricolageGrotesque",
        "body": "WorkSans", "hand": "Caveat",
        "palette": {"bg": "#f4eee2", "panel": "#faf6ee", "line": "#d9cfbf", "text": "#1d3a8a", "muted": "#4a5a8f",
                    "accent": "#ff48b0", "hot": "#ffb000", "cool": "#0078bf", "violet": "#00a95c"},
        "accents": {"fluorescent pink": "#ff48b0", "orange": "#ff6c2f", "teal": "#00a0a0"},
        "enter": "drop", "ease": "outBack", "cards": "solid", "cuts": ("split", "bars")},
    "halftone-dossier": {
        "cuts_native": ('pushCut', 'flip'), "moves": "a case file read exhibit by exhibit: labelled exhibits, a stamp slammed on the verdict, typewritten notes",
        "name": "Halftone Dossier", "uses": "investigations, case files, humour, surprising facts, myths and scams",
        "line": "a retro case file: cream archive paper, halftone dots in flat inks, heavy headlines with misregistered shadows",
        "surface": "paper", "stroke": "ink", "overlay": "halftone", "misregister": "cool", "display": "RobotoSlab",
        "body": "RobotoSlab", "hand": "SpecialElite",
        "palette": {"bg": "#f2e8d5", "panel": "#f8f1e3", "line": "#d6c7a8", "text": "#1f2a44", "muted": "#4b5670",
                    "accent": "#e0a526", "hot": "#d1495b", "cool": "#2a9d8f", "violet": "#7a5c99"},
        "accents": {"mustard": "#e0a526", "red stamp": "#d1495b"},
        "enter": "type", "ease": "outBack", "cards": "outline", "cuts": ("bars", "split")},
    "ascii-crt": {
        "cuts_native": ('wipe', 'sweep'), "moves": "typed lines and counters, boxes drawn like terminal windows, one soft second colour for the one thing that matters",
        "name": "ASCII / CRT Terminal", "uses": "programming, computers, hacking, the internet, developer topics",
        "line": "everything is a character on a monospace grid, lit by one phosphor on an old monochrome screen",
        "surface": "crt", "stroke": "", "overlay": "scanlines", "display": "VT323", "body": "VT323", "hand": "VT323",
        "palette": {"bg": "#040804", "panel": "#0a120a", "line": "#1b3a1b", "text": "#8dffa8", "muted": "#4fbf6c",
                    "accent": "#c8ffd6", "hot": "#ff9ec4", "cool": "#5fd77a", "violet": "#2e8c47"},
        "accents": {"green phosphor": "#c8ffd6"},
        "enter": "type", "ease": "snap", "cards": "outline", "cuts": ("fade", "bars"), "upper": True},
    "swiss-motion": {
        "cuts_native": ('slideBlur', 'wipe'), "moves": "a strict grid, huge numbers and short words flush left, one signal-coloured shape as the protagonist",
        "name": "Swiss Motion Graphics", "uses": "design, ideas and concepts, clean explainers of a single big idea",
        "line": "a modular grid, one typeface, ink and greys and ONE signal colour, movement as exact as a printing press",
        "surface": "paper", "stroke": "", "overlay": "", "display": "Archivo", "body": "Archivo", "hand": "Archivo",
        "palette": {"bg": "#eae9e5", "panel": "#ffffff", "line": "#c9c8c3", "text": "#111111", "muted": "#4d4d4d",
                    "accent": "#e30613", "hot": "#5c5c5c", "cool": "#8c8c8c", "violet": "#2e2e2e"},
        "accents": {"signal red": "#e30613", "signal orange": "#ff5a00", "ultramarine": "#1f3fff", "green": "#00954f"},
        "enter": "slide", "ease": "snap", "cards": "solid", "cuts": ("split", "corner")},
    "engraving": {
        "cuts_native": ('iris', 'wipe'), "moves": "a plate built up line by line: outline first, then hatching; labelled parts with leader lines; a magnified detail",
        "name": "Copperplate Engraving", "uses": "science explainers, natural history, anatomy, heritage, how a thing is made",
        "line": "an intaglio plate: ink line work and hatching on buff paper, roman capitals, a transparent wash on one part",
        "surface": "paper", "stroke": "ink", "overlay": "", "display": "CormorantGaramond", "body": "Lora",
        "hand": "CormorantGaramond",
        "palette": {"bg": "#efe4cc", "panel": "#f6eedc", "line": "#cdbf9f", "text": "#1c1712", "muted": "#5a4e40",
                    "accent": "#a8571c", "hot": "#5f7a8f", "cool": "#4f8a73", "violet": "#9b4a5a"},
        "accents": {"amber wash": "#a8571c", "madder rose": "#9b4a5a", "sea green": "#4f8a73"},
        "enter": "rise", "ease": "inOutSine", "cards": "outline", "cuts": ("fade", "circle"), "upper": True},
    "watercolor": {
        "cuts_native": ('iris', 'zoomBlur'), "moves": "soft painted shapes that bloom in, handwritten notes beside what is painted, colour that carries the meaning",
        "name": "Watercolor Brush", "uses": "nature, travel, biology, earth science, gentle science explainers",
        "line": "a hand-painted journal page: translucent brush colour on warm cotton paper, handwritten notes beside it",
        "surface": "watercolor", "stroke": "brush", "overlay": "", "display": "CormorantGaramond", "body": "Lora",
        "hand": "Caveat",
        "palette": {"bg": "#f7f1e3", "panel": "#fbf7ee", "line": "#dccfb6", "text": "#2b2420", "muted": "#6a5d52",
                    "accent": "#2f7fb0", "hot": "#c9733d", "cool": "#5f9c5f", "violet": "#b85c6e"},
        "accents": {"blue wash": "#2f7fb0", "rose": "#b85c6e", "ochre": "#c9733d", "leaf green": "#5f9c5f"},
        "enter": "blur", "ease": "inOutSine", "cards": "solid", "cuts": ("fade", "circle")},
}

PICK = """You are the art director of an explainer YouTube channel. Choose the film style for ONE video, the one that
suits its subject and its audience best. A film style is a whole visual world (surface, lines, type, colour), so pick
what makes THIS subject feel right; if none fits, answer "free" and the video gets a look designed for it alone.

Video: {title}
Video style: {style}
Mood: {mood}

Film styles (after the Lemo-Opuscar library):
{rows}

Reply with JSON: {{"look": "<style key or free>", "accent": "<one of that style's accent names>", "why": "one line"}}"""


def pick_prompt(title: str, style: str, mood: str) -> str:
    rows = "\n".join(f'- "{k}": {v["name"]}. Suits {v["uses"]}. {v["line"]}. Accents: {", ".join(v["accents"])}'
                     for k, v in LOOKS.items())
    return PICK.format(title=title, style=style, mood=mood or "-", rows=rows)


def choose(complete_json: Callable, title: str, style: str, mood: str,
           log: Callable[[str], None] = print) -> Optional[tuple]:
    """(look key, accent colour) the model chose for this video, or None for a look of its own."""
    try:
        raw = complete_json(pick_prompt(title, style, mood), max_tokens=400, temperature=0.7)
    except Exception as exc:                     # a look is a nice-to-have; a failed call keeps the free design
        log(f"[look] no choice from the model ({type(exc).__name__})")
        return None
    key = str((raw or {}).get("look") or "").strip().lower() if isinstance(raw, dict) else ""
    if key not in LOOKS:
        if key not in ("", "free"):
            log(f"[look] unknown style {key!r}: a look of its own")
        return None
    accents = LOOKS[key]["accents"]
    name = str(raw.get("accent") or "").strip().lower()
    accent = next((c for n, c in accents.items() if n.lower() == name), next(iter(accents.values())))
    log(f"[look] {LOOKS[key]['name']} ({name or 'default accent'}): {str(raw.get('why') or '')[:120]}")
    return key, accent


def theme_for(key: str, accent: str, finish: Callable, check_fx: Callable, seed: str) -> dict:
    """The video's theme for a film look: its palette (with the chosen accent), fonts, surface and motion."""
    L = LOOKS[key]
    pal = {**L["palette"], "accent": accent}
    light = L["surface"] not in ("slate", "blueprint", "keynote", "crt", "film")
    fx = check_fx({"layers": [{"shape": "dot", "count": 1, "opacity": 0.02}], "text": {"enter": L["enter"]},
                   "motion": {"ease": L["ease"], "bounce": 0.15, "frames": 18, "from": "first", "gap": 2},
                   "transitions": [{"shape": c, "angle": 0, "blur": 0, "scale": 0, "spin": 0} for c in L["cuts"]],
                   "camera": 0.5, "cards": {"radius": 10, "fill": L["cards"], "shadow": 0.4},
                   "texture": {"grain": 0, "vignette": 0.1}, "bigWord": False}, seed, light)
    theme = finish(pal, L["display"], L["body"], bool(L.get("upper")), "paper", ["wipe", "pushCut"], "steady",
                   f"look:{key}", "left", "rule", fx)
    theme["hand"] = L["hand"]
    # transitions native to the medium (a board pans, an eraser wipes, a newsreel irises) alternate with the look's
    # own shaped cuts
    shaped = list(theme.get("cuts") or [])
    theme["cuts"] = [c for k, n in enumerate(L["cuts_native"]) for c in (n, shaped[k % len(shaped)] if shaped else None)
                     if c is not None]
    theme["look"] = {"slug": key, "surface": L["surface"], "stroke": L["stroke"], "overlay": L["overlay"],
                     "misregister": L.get("misregister", ""), "mono": bool(L.get("mono")), "hand": L.get("handwrite", "")}
    return theme


def moves_text(theme: Optional[dict]) -> str:
    """What the diagram designer is told about the video's film look: its world and its native moves."""
    look = (theme or {}).get("look") or {}
    L = LOOKS.get(look.get("slug", ""))
    if not L:
        return ""
    return (f"This video is drawn as {L['name']}: {L['line']}. Speak its language: {L['moves']}. Somewhere at the "
            "video's peak, use the style's one native move that nothing else can do.")
