"""The visual-technique library (blogwriter/vizlib.py, video/src/viz/): every technique declared, checked and drawn,
offered to the script writer, the art director and the diagram designer, and never repeated within a video."""
import os
import re

from blogwriter import diagram, graphics, research, video, vizlib

ROOT = os.path.join(os.path.dirname(__file__), "..")
ok = lambda text, allowed: True          # noqa: E731


def drawn_names() -> set:
    names = set()
    for f in os.listdir(os.path.join(ROOT, "video", "src", "viz")):
        if f.endswith(".jsx") and f not in ("kit.jsx", "graphic.jsx"):
            src = open(os.path.join(ROOT, "video", "src", "viz", f), encoding="utf-8").read()
            for block in re.findall(r"export const [A-Z0-9]+ = \{([^}]*)\}", src):
                names |= set(re.findall(r"(\w+):\s*\w+", block))
    return names


def test_every_technique_is_declared_drawn_and_its_example_passes_its_checks():
    assert len(vizlib.TECH) == 168
    assert drawn_names() == set(vizlib.TECH)              # no technique without a component, no stray component
    for name, t in vizlib.TECH.items():
        el, why = {"type": name}, []
        assert not vizlib.fill(el, dict(t["sample"]), "", ok, why), (name, why)
        assert t["use"] and t["fields"] and not set(t["fields"]) & vizlib.RESERVED
    assert not set(vizlib.TECH) & set(diagram.TYPES[:len(diagram.TYPES) - len(vizlib.TECH)])


def test_the_library_gives_100_plus_shot_kinds_20_plot_types_and_35_motion_graphics():
    assert len(video.KINDS) + len(vizlib.SHOT_KINDS) == 145
    assert len(video.PLOTS) + len(vizlib.PLOT_TYPES) == 20
    assert len(graphics.TYPES) + len(vizlib.GRAPHIC_TYPES) == 35
    roles = set(vizlib.SHOT_KINDS) | set(vizlib.PLOT_TYPES) | set(vizlib.GRAPHIC_TYPES)
    assert roles == set(vizlib.TECH) and len(vizlib.SHOT_KINDS + vizlib.PLOT_TYPES + vizlib.GRAPHIC_TYPES) == 168
    fams = {t["fam"] for t in vizlib.TECH.values()}
    assert {"system", "chart", "ml", "dl", "llm", "genai", "k8s", "ops", "pattern", "paper", "data", "explain"} <= fams


def test_numbers_are_printed_only_when_the_narration_says_them():
    from blogwriter.video import _verified
    el = {"type": "waffle"}
    assert not vizlib.fill(el, {"items": [{"text": "mobile", "value": 62}, {"text": "desktop", "value": 38}]},
                           "most traffic is mobile", _verified, [])
    assert el["show"] is False                              # the shares only shape the picture
    el = {"type": "waffle"}
    vizlib.fill(el, {"items": [{"text": "mobile", "value": 62}, {"text": "desktop", "value": 38}]},
                "62 percent mobile and 38 desktop", _verified, [])
    assert el["show"] is True
    # a label with an unspoken number is dropped; too few left refuses the technique, with the reason
    why = []
    assert vizlib.fill({"type": "staircase"}, {"steps": ["v1", "v2 in 2019", "v3"]}, "three versions", _verified, why)
    assert any("staircase needs at least 3" in w for w in why)


def test_references_resolve_by_index_or_by_text():
    el = {"type": "sequence"}
    assert not vizlib.fill(el, {"actors": ["client", "server"], "messages": [
        {"from": "client", "to": "server", "text": "GET"}, {"from": 1, "to": 0, "text": "200"}, {"from": "x", "to": 0}]},
        "", ok, [])
    assert [(m["from"], m["to"]) for m in el["messages"]] == [(0, 1), (1, 0)]       # the unknown "x" is dropped


def test_each_video_gets_its_own_topic_first_selection():
    sd = vizlib.pick("System Design: consistent hashing and sharding", 20, pool=vizlib.SHOT_KINDS)
    ml = vizlib.pick("LLM: how RLHF aligns a language model", 20, pool=vizlib.SHOT_KINDS)
    k8 = vizlib.pick("Kubernetes: rolling updates and autoscaling", 10)
    assert "hashring" in sd[:8] and "shards" in sd[:8]
    assert "rlhf" in ml[:6] and set(sd) != set(ml)
    assert {"rollout", "hpa"} <= set(k8[:6])
    assert vizlib.pick("x", 28, used={"architecture"}).count("architecture") == 0
    assert vizlib.pick("Same title", 10) == vizlib.pick("Same title", 10)        # repeatable for one video


def test_pictures_follow_the_context_across_the_whole_library_not_the_subject_family():
    from collections import Counter
    facts = ("The Transformer replaces recurrence with self-attention; ablations removed attention heads; dropout; "
             "beam search decoding; training loss fell over steps")
    picked = vizlib.match(facts, 24, title="Research paper: Attention Is All You Need")
    fams = Counter(vizlib.TECH[n]["fam"] for n in picked)
    assert {"attention", "transformer", "ablation", "beam"} <= set(picked)
    assert len(fams) >= 4 and fams["paper"] <= 2              # a paper video is not limited to the 2 paper parts
    # one shot's words decide its candidates, whatever the video's title
    assert {"shards", "hashring"} <= set(vizlib.match("Netflix splits users across shards with consistent hashing", 6,
                                                      title="Statistics: types of data"))
    scenes = [{"headline": "Hot keys", "narration": "consistent hashing spreads keys over a ring of servers"},
              {"headline": "The long tail", "narration": "most requests are fast but the p99 latency tail is slow"}]
    p = diagram.prompt(scenes, [0, 1], "Statistics: averages", "calm")
    assert '"hashring"' in p and '"latency"' in p
    menu = video.technique_text("Research paper: Attention Is All You Need", facts)
    assert all(f"{n}" in menu for n in vizlib.SHOT_KINDS) and "Any other technique" in menu


def test_a_technique_kind_from_the_script_becomes_a_diagram_that_wants_it():
    sc = video.check_scene({"kind": "raft", "headline": "A leader falls", "narration": "The leader fails and a vote",
                            "picture": "five servers elect a new leader"}, "", "", {})
    assert sc["kind"] == "diagram" and sc["want"] == "raft" and '"raft" part' in sc["picture"]
    sc = video.check_scene({"kind": "plot", "plot": "ridgeline", "headline": "Shifts", "narration": "n"}, "", "", {})
    assert sc["kind"] == "diagram" and sc["want"] == "ridgeline"
    sc = video.check_scene({"kind": "plot", "plot": "fit", "headline": "Fit", "narration": "n"}, "", "", {})
    assert sc["kind"] == "plot" and "want" not in sc
    text = video.technique_text("System Design: replication")
    assert "TECHNIQUE SHOTS" in text and '"replication"' in text and "More \"plot\" types" in text


def test_the_designer_is_held_to_the_wanted_part_and_never_repeats_one():
    scenes = [{"headline": "Keys on a ring", "narration": "consistent hashing puts every key on a ring",
               "picture": 'a "hashring" part', "want": "hashring"},
              {"headline": "Again", "narration": "keys move when a node joins", "picture": ""}]
    ring = {"type": "hashring", "x": 5, "y": 5, "w": 90, "h": 88, "nodes": ["A", "B", "C"], "keys": 8}
    other = {"type": "waffle", "x": 5, "y": 5, "w": 90, "h": 88,
             "items": [{"text": "a", "value": 1}, {"text": "b", "value": 2}]}
    replies = [[{"scene": 0, "elements": [other]}, {"scene": 1, "elements": [dict(ring)]}],
               [{"scene": 0, "elements": [dict(ring)]}]]
    asked = []

    def fake(prompt, **kw):
        asked.append(prompt)
        return replies[len(asked) - 1]
    made = diagram.design(fake, scenes, [0, 1], "System Design", "calm", ok, lambda t: True, lambda *a: None)
    assert scenes[0]["diagram"]["elements"][0]["type"] == "hashring"        # retried: the writer asked for it
    assert scenes[1]["diagram"]["elements"][0]["type"] == "hashring" and made == 2
    assert 'asked for a "hashring" part' in asked[1]
    assert "MORE MOVING PARTS" in asked[0] and '"hashring"' in asked[0]


def test_library_motion_graphics_are_checked_timed_and_used_once():
    sc = {"kind": "photo", "headline": "Speed or safety", "narration": "speed against safety"}
    g = graphics.check({"type": "tug", "left": "speed", "right": "safety"}, sc, ok)
    assert g["type"] == "tug" and graphics.timed(g, "h", [], 120, 30, 8)["at"] == 14 and graphics.labels(g) == []
    assert graphics.check({"type": "tug"}, sc, ok) is None                   # its required sides are missing
    scenes = [dict(sc) for _ in range(3)]
    reply = [{"scene": k, "type": "tug", "left": "a", "right": "b"} for k in range(3)]
    reply[1] = {"scene": 1, "type": "flow", "nodes": [{"icon": "server", "label": "a"}, {"icon": "database", "label": "b"}]}
    graphics.assign(scenes, reply, ok, lambda *a: None)
    assert [s.get("graphic", {}).get("type") for s in scenes] == ["tug", "flow", None]
    assert "More graphics" in graphics.prompt(scenes)


def test_lessons_research_real_cases_and_references_early():
    names = [n for n, _ in research.STUDY_PERSPECTIVES]
    assert names.index("Case studies") < 4 and "References" in names          # even the fast mode asks for cases
    assert "REAL-WORLD DEPTH" in video.REAL_WORLD and "never websites" in video.REAL_WORLD
