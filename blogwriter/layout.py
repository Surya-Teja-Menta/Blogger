"""A layout audit for the finished shots: every shot is drawn at several moments by the preview renderer, which measures,
in the page itself, every visible piece of text and every visible box (video/src/audit.jsx). Two texts on top of each
other, two boxes sharing a corner, a label across a box's edge: each is reported, and the shot is repaired with the
mildest change that clears it (a shorter headline, then a simpler picture, then no headline) and measured again.
A viewer therefore never meets a collision that the layout code did not foresee, whatever topic or visual made it.

The audit never blocks a video: if the renderer is missing or prints nothing, the shots stay as they were."""
import json
import os
import shutil
import subprocess
from typing import Callable, Dict, List, Optional

HEADLINE_WORDS = 3          # what a headline is cut to when a long one is what collides
MOMENTS = (0.2, 0.35, 0.5, 0.65, 0.8)   # fractions of a shot's length that are drawn, plus its last moments (a camera
                                          # that moves between the pieces shows them in different company)
SCALE = 0.1                 # the picture is not used, only the measurement, so it is drawn small


def moments(frames: int) -> List[int]:
    """The frames of a shot that are measured: spread through it and (nearly) the last, where every piece has landed."""
    return sorted({max(0, round(frames * m)) for m in MOMENTS} | {max(0, frames - 25)})


def shorter(headline: str, highlight: str = "", words: int = HEADLINE_WORDS) -> tuple:
    """The headline cut to `words` words around its highlighted word -> (headline, highlight kept)."""
    parts = str(headline or "").split()
    if len(parts) <= words:
        return " ".join(parts), highlight
    marks = {w.lower() for w in str(highlight or "").split()}
    hit = next((k for k, w in enumerate(parts) if w.lower().strip(".,!?;:") in marks), 0)
    start = min(max(0, hit - words + 1), len(parts) - words)
    cut = parts[start:start + words]
    kept = " ".join(w for w in str(highlight or "").split() if w.lower() in " ".join(cut).lower())
    return " ".join(cut), kept


def describe(found: dict) -> str:
    return f"{found.get('kind', '?')}: \"{found.get('a', '')}\" / \"{found.get('b', '')}\""


def parse(stdout: str) -> Dict[str, List[dict]]:
    """The renderer's `audit <picture> {json}` lines -> {picture path: [findings]} (a frame that printed nothing is
    simply absent)."""
    out: Dict[str, List[dict]] = {}
    for line in (stdout or "").splitlines():
        if not line.startswith("audit "):
            continue
        path, _, body = line[6:].partition(" {")
        try:
            data = json.loads("{" + body) if body else {}
        except ValueError:
            continue
        if "found" in data:
            out[path] = data["found"]
    return out


def shot_captions(captions: List[dict], start: int, frames: int) -> List[dict]:
    """The captions that are on screen during one shot, moved so the shot's own first frame is 0 (a shot is drawn on
    its own, but a viewer sees the captions over it, so they are part of what is measured)."""
    return [{**c, "from": c["from"] - start, "to": c["to"] - start} for c in captions or []
            if start <= c.get("from", -1) < start + frames]


def audit(app_dir: str, shots: List[tuple], job: str, log: Callable[[str], None], timeout: int = 2400,
          composition: str = "Long", tag: str = "") -> Optional[Dict[int, List[dict]]]:
    """shots: (shot index, props, frame). composition: the picture they are drawn in ("Long" or the vertical "Short").
    -> {shot index: findings over all its frames}, or None when the preview renderer could not run (then nothing is
    changed)."""
    node = shutil.which("node") or shutil.which("node.exe")
    if not node or not shots:
        return None
    jobs, owner = [], {}
    for i, props, frame in shots:
        out = os.path.join(job, f"audit{tag}_{i}_{frame}.jpg")
        jobs.append({"props": props, "frame": max(0, frame), "out": out, "scale": SCALE, "audit": True,
                     "composition": composition})
        owner[out] = i
    path = os.path.join(job, f"audit{tag}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False)
    try:
        r = subprocess.run([node, "stills.mjs", path], cwd=app_dir, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        log(f"[layout] the audit could not run: {type(exc).__name__}")
        return None
    heard = parse(r.stdout)
    if not heard:
        log(f"[layout] the audit printed nothing: {(r.stderr or r.stdout or '')[-200:].strip()}")
        return None
    result: Dict[int, List[dict]] = {i: [] for i in set(owner.values())}
    for out, found in heard.items():
        mine = result.setdefault(owner.get(out, -1), [])
        for item in found:
            if not any(item["kind"] == m["kind"] and item["a"] == m["a"] and item["b"] == m["b"] for m in mine):
                mine.append(item)
    result.pop(-1, None)
    return result


def _words_of(el: dict) -> str:
    return " ".join(str(el.get("text") or el.get("tex") or "").lower().split())


def drop_collider(scene: dict, long_scene: dict, found: List[dict]) -> str:
    """In a drawn diagram, remove the one piece that collides (a stamp first, else the one that arrives last), so
    the rest of the picture stays. -> what was removed ('' when no piece matches or too few would be left)."""
    els = (scene.get("diagram") or {}).get("elements") or []
    if len(els) <= 3 or not found:
        return ""
    named = {w for f in found for w in (f.get("a", ""), f.get("b", "")) if w}
    hit = [k for k, e in enumerate(els) if _words_of(e) and any(_words_of(e).startswith(n.lower()[:20]) or
                                                               n.lower().startswith(_words_of(e)[:20]) for n in named)]
    if not hit:
        return ""
    k = next((k for k in hit if els[k]["type"] == "stamp"), max(hit, key=lambda k: els[k].get("at") or 0))
    gone = els[k]
    for d in (scene.get("diagram"), long_scene.get("diagram")):
        if d and d.get("elements"):
            d["elements"] = [e for e in d["elements"] if not (e.get("type") == gone["type"] and _words_of(e) == _words_of(gone))]
    return f"{gone['type']} \"{_words_of(gone)}\" removed from the diagram"


def repair(scene: dict, long_scene: dict, step: int, retime: Callable[[dict], Optional[dict]],
           found: Optional[List[dict]] = None) -> str:
    """One notch milder on a shot that collides. Steps 0 and 1: the colliding piece of a diagram is removed, else the
    headline is cut shorter. Step 2: the shot's diagram or motion graphic becomes
    the plain animated type. Step 3: no headline. -> what was done ('' when nothing could change)."""
    if step <= 1 and scene.get("diagram"):
        did = drop_collider(scene, long_scene, found or [])
        if did:
            return did
    if step <= 1:
        head, mark = shorter(scene.get("headline", ""), scene.get("highlight", ""))
        if head == scene.get("headline", ""):
            return repair(scene, long_scene, 2, retime)
        for s in (scene, long_scene):
            s["headline"], s["highlight"] = head, mark
        long_scene["hcue"] = None if not mark else long_scene.get("hcue")
        return "headline cut to " + str(HEADLINE_WORDS) + " words"
    if step == 2:
        kinetic = (long_scene.get("graphic") or {}).get("type") == "kinetic" and not long_scene.get("diagram")
        if kinetic and not long_scene.get("diagram"):
            return repair(scene, long_scene, 3, retime)
        scene.pop("diagram", None)
        long_scene["diagram"] = None
        scene["graphic"] = {"type": "kinetic", "nodes": []}
        long_scene["graphic"] = retime(scene["graphic"])
        return "picture replaced by animated type"
    if step >= 3 and (scene.get("headline") or long_scene.get("headline")):
        for s in (scene, long_scene):
            s["headline"], s["highlight"] = "", ""
        long_scene["hcue"] = None
        return "headline removed"
    return ""
