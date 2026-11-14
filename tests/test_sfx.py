"""The little sounds under the pictures (blogwriter/sfx.py, sound.mix_filter) and the caption styles
(video/src/captions.jsx, palettes.caption): timed from each picture's own frame, soft, hiss-free, one style per video."""
import os
import re
import wave

import numpy as np

from blogwriter import design, palettes, sfx, sound

SRC = os.path.join(os.path.dirname(__file__), "..", "video", "src")


def scenes():
    return [{"graphic": {"center": {"at": 12}, "nodes": [{"at": 30}, {"at": 60}, {"at": 90}]}},
            {"diagram": {"elements": [{"type": "box", "at": 20}, {"type": "arrow", "at": 40}, {"type": "stamp", "at": 70},
                                      {"type": "label", "at": 75}, {"type": "icon", "at": 110}]}}]


def test_every_picture_that_lands_gets_a_sound_on_its_own_frame_and_a_shot_stays_calm():
    got = sfx.cues(scenes(), [0, 200], 30)
    assert [round(t, 2) for t in got["pops"][0]] == [0.4, 7.33]          # the first pop of each shot is the root note
    assert [len(p) for p in got["pops"]] == [2, 2, 1, 1, 0]               # a build climbs the pentatonic scale
    assert got["ticks"] == [8.0] and got["hits"] == [9.0]                 # a drawn line ticks, a stamp thumps
    # the label 0.17 s after the stamp is too close to it: a sound at most every 0.3 s
    many = [{"diagram": {"elements": [{"type": "box", "at": 12 + 12 * k} for k in range(30)]}}]
    c = sfx.cues(many, [0], 30)
    assert sum(len(p) for p in c["pops"]) <= sfx.MAX_PER_SHOT
    assert sfx.cues([{"graphic": {"at": 14}}], [60], 30)["pops"][0] == [(60 + 14) / 30]     # a library graphic: one pop


def test_the_sound_track_is_soft_pure_tones_with_nothing_up_where_hiss_lives(tmp_path):
    path = str(tmp_path / "sfx.wav")
    n = sfx.render(path, 12, sfx.cues(scenes(), [0, 200], 30), 65.0)
    assert n == 7
    with wave.open(path) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype("float32").reshape(-1, 2).mean(1) / 32768
    assert 0.2 < np.abs(x).max() < 0.9
    spec = np.abs(np.fft.rfft(x)) ** 2
    f = np.fft.rfftfreq(len(x), 1 / sound.SR)
    assert 10 * np.log10(spec[f > 4000].sum() / spec.sum()) < -45        # the whoosh was cut at 1.5 kHz for the same reason
    # the pops are tuned to the video's own key, one pentatonic note each
    top = []
    for r in sfx.SCALE:
        tone = sfx.pop(65.0 * 4 * r)
        top.append(np.fft.rfftfreq(len(tone), 1 / sound.SR)[np.argmax(np.abs(np.fft.rfft(tone)))])
    assert all(abs(t / (260 * r) - 1) < 0.2 for t, r in zip(top, sfx.SCALE))      # (the quick chirp starts a little high)


def test_the_mix_takes_the_track_as_one_input_after_the_hit_sound(monkeypatch):
    plain, _ = sound.mix_filter([0.0, 2.0], [1.0], [1.5], None, final=False)
    withs, _ = sound.mix_filter([0.0, 2.0], [1.0], [1.5], None, final=False, sfx_track=True)
    assert "[5:a]" in withs and "[sfxt]" in withs and "sfxt" not in plain       # 2 voices, music 2, whoosh 3, hit 4, sfx 5
    last = lambda g: int(re.findall(r"amix=inputs=(\d+):normalize=0", g)[-1])      # noqa: E731  (the final mix)
    assert last(withs) == last(plain) + 1
    monkeypatch.setenv("SFX_LEVEL", "0")
    assert sound.sfx_level() == 0
    monkeypatch.setenv("SFX_LEVEL", "0.25")
    assert sound.sfx_level() == 0.25


def test_every_caption_style_is_drawn_chosen_for_the_subject_and_not_repeated():
    jsx = open(os.path.join(SRC, "captions.jsx"), encoding="utf-8").read()
    drawn = set(re.findall(r"^  (\w+): \(", jsx, re.M))
    assert drawn == set(palettes.CAPTIONS) and 'data-caption="1"' in open(os.path.join(SRC, "Video.jsx"), encoding="utf-8").read()
    assert "glow" not in {palettes.caption("tech ai future", f"t{k}", True) for k in range(60)}      # neon needs a dark design
    assert len({palettes.caption("a story", f"t{k}", False) for k in range(60)}) >= 5
    for k in range(40):
        assert palettes.caption("x", f"t{k}", False, avoid=["pill", "paper"]) not in ("pill", "paper")
    d = design.design(lambda *a, **kw: {}, "Some title", "education", "calm", lambda m: None, {"captions": ["clean", "pill"]})
    assert d["caption"] in palettes.CAPTIONS and d["caption"] not in ("clean", "pill")
