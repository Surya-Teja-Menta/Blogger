"""The camera plan (blogwriter/camera.py, video/src/camera.jsx) and the instrument layer (skeleton.jsx Hud)."""
import os
from collections import Counter

from blogwriter import camera, skeleton

SRC = os.path.join(os.path.dirname(__file__), "..", "video", "src")


def shots(n=60):
    out = [{"kind": "hook", "frames": 150}]
    for k in range(1, n):
        s = {"kind": "photo" if k % 3 else "diagram", "frames": 200, "graphic": {"nodes": [{"at": 40}, {"at": 90}, {"at": 130}]}}
        if k % 10 == 0:
            s["chapter"] = {"title": "Part"}
        out.append(s)
    return out


def test_every_shot_gets_a_move_and_no_move_repeats_back_to_back():
    scenes = shots()
    summary = camera.plan(scenes, "A title")
    moves = [s["cam"]["move"] for s in scenes]
    assert moves[0] == "push" and all(s["cam"]["move"] == "pull" for s in scenes if s.get("chapter"))
    assert all(moves[k] != moves[k - 1] or moves[k] in ("push", "pull") for k in range(2, len(moves)))     # no repeat except the fixed openers
    assert len(set(moves)) >= 5 and "push" in summary


def test_text_heavy_shots_never_roll_or_blur_and_a_dutch_angle_is_rare():
    scenes = shots(120)
    camera.plan(scenes, "Another title")
    for s in scenes:
        if s["kind"] == "diagram":
            assert s["cam"]["move"] in camera.CALM and s["cam"]["move"] != "dutch"
    assert Counter(s["cam"]["move"] for s in scenes)["dutch"] <= max(1, 120 // 25)
    assert all(s["cam"]["punch"] is None or 24 <= s["cam"]["punch"] <= s["frames"] - 24 for s in scenes)
    assert any(s["cam"]["punch"] is not None for s in scenes)                                       # some shots punch in on a beat


def test_the_plan_is_the_same_for_the_same_title_and_differs_between_titles():
    a, b, c = shots(), shots(), shots()
    camera.plan(a, "Same"); camera.plan(b, "Same"); camera.plan(c, "Other")
    assert [s["cam"] for s in a] == [s["cam"] for s in b] and [s["cam"] for s in a] != [s["cam"] for s in c]


def test_every_move_and_every_hud_is_performed():
    cam, sk = open(os.path.join(SRC, "camera.jsx"), encoding="utf-8").read(), open(os.path.join(SRC, "skeleton.jsx"), encoding="utf-8").read()
    for move in list(camera.MOVES) + ["dutch"]:
        assert move == "push" or f'"{move}"' in cam, move                    # push is the default branch
    for mode in skeleton.OPTIONS["hud"]:
        assert mode == "none" or f'"{mode}"' in sk, mode
    assert "CamContext.Provider" in open(os.path.join(SRC, "Video.jsx"), encoding="utf-8").read()
