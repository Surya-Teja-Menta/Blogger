"""How samey is a finished plan? A score per video, logged before the render, after the idea of OpenMontage's
"slideshow risk" check (a plan that is mostly animated type, or the same picture again and again, is an animated
slideshow). Viewers said the videos felt templated; this puts a number on it so a run that drifts that way is seen
in the log instead of guessed at. It changes nothing in the video."""
from collections import Counter
from typing import List

from . import vizlib

# a shot with these and no picture is only words on a background
BARE = ("photo", "hook")


def label(s: dict) -> str:
    """What a shot shows: its library technique, 'diagram', its motion graphic, or its own kind."""
    els = (s.get("diagram") or {}).get("elements") or []
    if els:
        return next((e["type"] for e in els if e["type"] in vizlib.TECH), "diagram")
    if s.get("graphic"):
        return s["graphic"]["type"]
    return s.get("kind", "?")


def words_only(s: dict) -> bool:
    """Animated type, or a picture shot with nothing in it."""
    if label(s) == "kinetic":
        return True
    return s.get("kind") in BARE and not (s.get("images") or s.get("video") or s.get("graphic") or s.get("diagram"))


def score(scenes: List[dict]) -> dict:
    """{"score": 0-100, "words_only": share, "run": the longest run of one picture, "top": (label, share),
    "distinct": how many different pictures, "techniques": how many library techniques}. The weights are a judgement,
    not a measurement: type-only shots cost most, then one picture repeating in a row, then one picture dominating."""
    if not scenes:
        return {"score": 100, "words_only": 0.0, "run": 0, "top": ("", 0.0), "distinct": 0, "techniques": 0, "shots": 0}
    labels = [label(s) for s in scenes]
    n = len(labels)
    typed = sum(1 for s in scenes if words_only(s)) / n
    run = best = 0
    for k, l in enumerate(labels):
        run = run + 1 if k and l == labels[k - 1] else 1
        best = max(best, run)
    top, top_n = Counter(labels).most_common(1)[0]
    distinct = len(set(labels))
    value = 100 - min(40, 80 * typed) - min(20, 8 * max(0, best - 2)) - min(20, 80 * max(0.0, top_n / n - 0.25)) \
        - min(20, 40 * max(0.0, 0.5 - distinct / n))
    return {"score": max(0, round(value)), "words_only": typed, "run": best, "top": (top, top_n / n),
            "distinct": distinct, "techniques": len({l for l in labels if l in vizlib.TECH}), "shots": len(labels)}


def report(scenes: List[dict]) -> str:
    """The log line."""
    r = score(scenes)
    warn = " <- samey: check the diagrams" if r["score"] < 60 else ""
    return (f"[variety] {r['score']}/100: {r['shots']} shots, {r['distinct']} different pictures ({r['techniques']} library "
            f"techniques), {round(100 * r['words_only'])}% type only, longest repeat {r['run']}, most used "
            f"{r['top'][0]} {round(100 * r['top'][1])}%{warn}")


# the pictures that run the real thing (video/src/viz/sim.jsx, physics, prob, quantum, chem, astro, mind, llmreal, blackbox)
LIVE = {"nntrain", "optimizers", "orbits", "engine4", "gears", "rigidbody", "blackbox", "montecarlo", "randomwalk", "markov", "bayes",
        "qubit", "qcircuit", "doubleslit", "molecule", "gaslaw", "equilibrium", "transit", "doppler", "binarycards", "illusion", "llmreal"}


def coverage(scenes: List[dict]) -> str:
    """The log line for what the video shows inside: how many shots got a live picture, and the headlines of the shots that are only
    words, so the next pictures to build are the ones the videos actually needed."""
    live = [label(s) for s in scenes if label(s) in LIVE]
    bare = [str(s.get("headline") or s.get("narration", ""))[:50] for s in scenes if words_only(s)]
    return (f"[pictures] {len(live)} of {len(scenes)} shots run the real thing ({', '.join(f'{k} x{n}' for k, n in Counter(live).most_common(6)) or 'none'})"
            + (f"; words only: {' | '.join(bare[:6])}" if bare else ""))
