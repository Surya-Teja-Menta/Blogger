"""The skeleton of a video: its layout plan. Viewers saw different colours on the same layout: the same decoration in the
same corners of the big-type shots, the same end card, the same label above every headline. Now every video draws a
layout plan (video/src/skeleton.jsx draws it), and every choice differs from the previous video's, so consecutive
videos differ in their skeleton as well as their skin.

  decor    what decorates the big-type shots
  kicker   the small label above a headline: on every shot, only where a new part begins, or never
  outro    the end card
  flow     how a chain of steps runs
  capAlign where a wide video's captions sit
  logo     the top corner of the channel badge
  progress the thin progress line, at the top or the bottom
  hub, spot, versus, stack, quote, list: how those shots are arranged (ring or fan, centre at the left or right, a
           diagonal or straight split, stacked cards, the quote's layout, the list's columns)
  title    the headline at the left, the centre or the right"""
import hashlib
import json
import random
from typing import Dict, List, Optional

# every option is drawn by video/src/skeleton.jsx, scenes.jsx, graphics.jsx or Video.jsx (tests/test_skeleton.py checks)
OPTIONS: Dict[str, List[str]] = {
    "decor": ["shapes", "rules", "brackets", "dots", "band", "frame", "none"],
    "kicker": ["all", "parts", "none"],
    "outro": ["side", "flip", "center", "ribbon"],
    "flow": ["line", "stair", "zigzag", "rise"],
    "capAlign": ["center", "left"],
    "logo": ["tl", "tr"],
    "progress": ["top", "bottom"],
    "hub": ["ring", "fan", "fanr"],
    "spot": ["left", "right"],
    "versus": ["diag", "straight"],
    "stack": ["center", "left", "right"],
    "quote": ["left", "center", "split"],
    "list": ["stack", "stagger", "cols"],
    "title": ["left", "center", "right"],
    "hook": ["center", "left", "stacked"],
}
# how often each kicker choice is drawn: a label on every shot is the template tell, so it is the rarest
WEIGHTS = {"kicker": {"all": 1, "parts": 3, "none": 2}}


def choose(seed: str, last: Optional[dict] = None) -> dict:
    """The layout plan for a video: every field drawn by the title, and never the value the last video had (when there
    is another to choose)."""
    last = last or {}
    plan = {}
    for field, options in OPTIONS.items():
        pool = [o for o in options if o != last.get(field)] or options
        weights = [WEIGHTS.get(field, {}).get(o, 1) for o in pool]
        rnd = random.Random(int(hashlib.sha256((field + seed).encode()).hexdigest(), 16))
        plan[field] = rnd.choices(pool, weights)[0]
    return plan


def last_plan(history: Optional[dict]) -> dict:
    """The previous video's plan from the design history ({} if none)."""
    try:
        return json.loads((history or {}).get("layouts", [""])[-1] or "{}")
    except (ValueError, IndexError, TypeError):
        return {}


def mark_parts(scenes: List[dict]) -> int:
    """Flag the shots that open a part (the first shot, an act title, a new label): the label above a headline may be
    shown only there. Returns how many shots open a part."""
    last = None
    n = 0
    for k, s in enumerate(scenes):
        opens = k == 0 or bool(s.get("chapter")) or (s.get("kicker") or "") != last
        s["partStart"] = opens
        last = s.get("kicker") or ""
        n += opens
    return n
