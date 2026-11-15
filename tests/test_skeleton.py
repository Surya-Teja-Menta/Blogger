"""The layout plan (blogwriter/skeleton.py, video/src/skeleton.jsx): every option is drawn, consecutive videos differ in
every choice, and the label above a headline shows only where a part begins when the plan says so."""
import json
import os
from collections import Counter

from blogwriter import design, palettes, skeleton

SRC = os.path.join(os.path.dirname(__file__), "..", "video", "src")
read = lambda f: open(os.path.join(SRC, f), encoding="utf-8").read()      # noqa: E731


def test_every_layout_option_is_drawn():
    sk, scenes, graphics, video = read("skeleton.jsx"), read("scenes.jsx"), read("graphics.jsx"), read("Video.jsx")
    for mode in skeleton.OPTIONS["decor"]:
        assert mode == "shapes" or f'"{mode}"' in sk, mode                    # shapes is the fall-through branch
    for mode in skeleton.OPTIONS["outro"]:
        assert mode == "side" or f'"{mode}"' in scenes, mode
    for run in skeleton.OPTIONS["flow"]:
        assert run == "line" or f"{run}:" in graphics, run
    assert 'capAlign === "left"' in video and 'logo === "tr"' in video and 'progress === "bottom"' in video
    for mode in skeleton.OPTIONS["hub"]:
        assert mode == "ring" or f'"{mode}"' in graphics, mode
    assert 'spot === "right"' in graphics and 'versus === "straight"' in graphics
    for place in skeleton.OPTIONS["stack"]:
        assert place == "center" or f'"{place}"' in graphics, place
    for mode in skeleton.OPTIONS["quote"]:
        assert mode == "left" or f'"{mode}"' in scenes, mode
    for mode in skeleton.OPTIONS["list"]:
        assert mode == "stack" or f'"{mode}"' in scenes, mode
    assert 'title === "right"' in read("fx.jsx")
    for mode in skeleton.OPTIONS["hook"]:
        assert mode == "center" or f'"{mode}"' in graphics, mode
    assert "kickerPolicy(s0)" in video and "<Decor " in graphics


def test_consecutive_videos_differ_in_every_choice_and_the_label_on_every_shot_is_rare():
    last = None
    seen = {field: Counter() for field in skeleton.OPTIONS}
    for k in range(120):
        plan = skeleton.choose(f"title {k}", last)
        assert set(plan) == set(skeleton.OPTIONS)
        if last:
            assert all(plan[f] != last[f] for f in plan), (plan, last)          # no field repeats from one video to the next
        for f, v in plan.items():
            seen[f][v] += 1
        last = plan
    assert all(set(seen[f]) == set(skeleton.OPTIONS[f]) for f in seen)           # every option gets used
    assert seen["kicker"]["all"] < seen["kicker"]["parts"] and seen["kicker"]["all"] < seen["kicker"]["none"]
    assert skeleton.choose("same", None) == skeleton.choose("same", None)         # one video, one plan


def test_the_history_carries_the_last_plan_and_a_design_never_repeats_it(monkeypatch):
    store = {}
    from blogwriter import storage
    monkeypatch.setattr(storage, "get_text", lambda s, key, **k: store.get(key, ""))
    monkeypatch.setattr(storage, "put_text", lambda s, key, text, mime="", **k: store.update({key: text}) or True)
    history = palettes.load_history(None)
    assert skeleton.last_plan(history) == {}
    previous = None
    for k in range(8):
        d = design.design(lambda *a, **kw: {}, f"Topic {k}", "education", "calm", lambda m: None, history)
        assert set(d["layout"]) == set(skeleton.OPTIONS)
        if previous:
            assert all(d["layout"][f] != previous[f] for f in previous)
        palettes.save_history(None, history, d)
        history = palettes.load_history(None)
        previous = d["layout"]
        assert json.loads(history["layouts"][-1]) == previous and len(history["layouts"]) == 1


def test_a_shot_opens_a_part_at_the_start_at_an_act_and_when_the_label_changes():
    scenes = [{"kicker": "Intro"}, {"kicker": "Intro"}, {"kicker": "Risk"}, {"kicker": "Risk"},
              {"kicker": "Risk", "chapter": {"title": "Part two"}}, {"kicker": ""}, {"kicker": ""}]
    assert skeleton.mark_parts(scenes) == 4
    assert [s["partStart"] for s in scenes] == [True, False, True, False, True, True, False]
