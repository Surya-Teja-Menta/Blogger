"""Fixing one thing in a finished video (blogwriter/patch.py)."""
import pytest

from blogwriter import patch


def test_an_edit_finds_its_shot_by_number_or_by_time():
    starts, frames = [0, 100, 200, 300], [115, 115, 115, 100]
    assert patch.locate(starts, frames, {"shot": 3}) == 2
    assert patch.locate(starts, frames, {"at": "0:07"}) == 2            # 210 frames: inside shot 3
    assert patch.locate(starts, frames, {"at": "10"}) == 3
    with pytest.raises(ValueError):
        patch.locate(starts, frames, {"shot": 9})
    with pytest.raises(ValueError):
        patch.locate(starts, frames, {})


def test_text_edits_change_the_screen_words_and_never_the_narration():
    scene = {"kind": "diagram", "headline": "Colour map", "narration": "The colour is red.", "kicker": "A",
             "diagram": {"elements": [{"type": "text", "text": "colour"}, {"type": "box", "label": "no colour here"}]}}
    assert patch.apply_text_edit(scene, {"replace": {"colour": "color"}, "label": "New"})
    assert scene["headline"] == "Color map" and scene["narration"] == "The colour is red." and scene["label"] == "New"
    assert scene["diagram"]["elements"][0]["text"] == "color" and scene["diagram"]["elements"][0]["type"] == "text"
    assert not patch.apply_text_edit(scene, {"replace": {"zzz": "y"}})


def test_only_the_changed_shots_are_drawn_again_and_neighbours_merge():
    starts, frames = [0, 100, 200, 300, 400], [115] * 5
    assert patch.ranges([1], starts, frames) == [(100, 214)]
    assert patch.ranges([3, 1], starts, frames) == [(100, 214), (300, 414)]
    assert patch.ranges([1, 2], starts, frames) == [(100, 314)]          # shots 2 and 3 overlap: one range
    g = patch.splice_filter([(100, 214), (300, 414)], 515)
    assert "trim=start_frame=0:end_frame=100" in g and "[1:v]" in g and "[2:v]" in g and "concat=n=5" in g
    assert "trim=start_frame=415" in g
    assert "concat=n=1" in patch.splice_filter([(0, 514)], 515)          # the whole video drawn again


def test_new_captions_and_subtitles_replace_only_their_shot():
    words = [(0.0, 0.4, "Fixed"), (0.5, 0.9, "line")]
    caps = [{"from": 10, "to": 40, "text": "before"}, {"from": 110, "to": 140, "text": "old"}, {"from": 210, "to": 240, "text": "after"}]
    new = patch.recaption(caps, 100, 100, words)
    assert [c["text"] for c in new] == ["before", "Fixed line", "after"] and new[1]["from"] == 106
    srt = "1\n00:00:00,300 --> 00:00:01,300\nbefore\n\n2\n00:00:03,700 --> 00:00:04,500\nold\n\n3\n00:00:07,000 --> 00:00:08,000\nafter\n"
    out = patch.patch_srt(srt, 100, 100, words)
    assert "old" not in out and "before" in out and "after" in out and "Fixed line" in out
