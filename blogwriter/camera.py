"""The camera plan of a video: a cinematographer's choice of move for every shot (video/src/camera.jsx performs it).

Before, every shot got the same slow push with a small sway, so a ten-minute video had one camera move sixty times.
Now each shot has its own: a dolly-in (push) to open, a pull-out reveal where a new part begins, then trucks, pedestals,
arcs, a handheld drift, a rare dutch angle and a rack focus, never the same move as one of the last two shots. On a shot's
key moment (the piece the narrator names, a diagram's glow) a quick punch-in, the crash zoom an editor cuts on a beat.
Text-heavy shots (equations, graphs, diagrams, steps) get only the quiet moves, with no roll, so words stay crisp.

shot["cam"] = {"move", "dir", "amount", "fx", "fy", "punch" (frame or None), "dutch" (degrees)}; deterministic by title."""
import hashlib
from collections import Counter
from typing import Dict, List, Optional

# how often each move is chosen
MOVES: Dict[str, int] = {"push": 4, "pull": 2, "truck": 3, "pedestal": 2, "arc": 2, "drift": 2, "rack": 2}
CALM = ("push", "pull", "truck", "pedestal", "drift")          # no roll, no blur: for shots full of small text
CALM_KINDS = {"equation", "graph", "derive", "plot", "check", "steps", "diagram", "timeline", "list", "map", "compare",
              "bars", "line", "donut", "kpis"}
PUNCH_SHARE = 0.45          # the share of shots with a punch-in on their key moment


def _r(seed: str, i: int, tag: str) -> float:
    """A repeatable number in [0, 1) for this video, shot and purpose."""
    return int(hashlib.sha256(f"{seed}|{i}|{tag}".encode()).hexdigest()[:12], 16) / 16 ** 12


def key_frame(shot: dict) -> Optional[int]:
    """The frame (from the shot's start) of its key moment: a diagram's glow cue, else the middle appearance of its
    timed pieces; None when nothing is timed or the moment is too early or too late to punch on."""
    g = shot.get("graphic") or {}
    found = [p["at"] for p in ([g["center"]] if g.get("center") else []) + list(g.get("nodes") or []) if "at" in p]
    glows = [e["glow"]["at"] for e in (shot.get("diagram") or {}).get("elements", []) if e.get("glow") and "at" in e["glow"]]
    found += [e["at"] for e in (shot.get("diagram") or {}).get("elements", []) if e.get("at") is not None]
    pick = glows[0] if glows else (sorted(found)[len(found) // 2] if found else None)
    frames = shot.get("frames") or 0
    return pick if pick is not None and 24 <= pick <= frames - 24 else None


def plan(scenes: List[dict], seed: str) -> str:
    """Give every shot its camera move. Returns a one-line summary of the moves used."""
    last: List[str] = []
    dutch_left = max(1, len(scenes) // 25)
    used = Counter()
    for i, s in enumerate(scenes):
        calm = s.get("kind") in CALM_KINDS or bool(s.get("diagram"))
        if i == 0:
            move = "push"                                       # the opening dollies in
        elif s.get("chapter"):
            move = "pull"                                       # a new part opens with a reveal
        else:
            pool = {m: w for m, w in MOVES.items() if (m in CALM or not calm) and m not in last[-2:]} or {"drift": 1}
            roll = _r(seed, i, "move") * sum(pool.values())
            move = list(pool)[-1]
            for m, w in pool.items():
                roll -= w
                if roll < 0:
                    move = m
                    break
        dutch = 0.0
        if i and not calm and not s.get("chapter") and dutch_left and _r(seed, i, "dutch") < 0.08:
            move, dutch, dutch_left = "dutch", round(0.8 + 0.5 * _r(seed, i, "deg"), 2), dutch_left - 1
        punch = key_frame(s) if move not in ("rack", "dutch") and _r(seed, i, "punch") < PUNCH_SHARE else None
        s["cam"] = {"move": move, "dir": 1 if _r(seed, i, "dir") < 0.5 else -1, "amount": round(0.6 if calm else 0.9 + 0.4 * _r(seed, i, "amt"), 2),
                    "fx": round(0.38 + 0.24 * _r(seed, i, "fx"), 2), "fy": round(0.38 + 0.14 * _r(seed, i, "fy"), 2),
                    "punch": punch, "dutch": dutch}
        last.append(move)
        used[move] += 1
    return ", ".join(f"{n} {m}" for m, n in used.most_common())
