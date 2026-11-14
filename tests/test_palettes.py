"""Colour worlds, backdrops and shapes (blogwriter/palettes.py, video/src/backdrops.jsx, gen.jsx): every one is
readable, every one is drawn, and videos do not all land on the same look."""
import colorsys
import os
import re

from blogwriter import design, palettes

SRC = os.path.join(os.path.dirname(__file__), "..", "video", "src")
read = lambda f: open(os.path.join(SRC, f), encoding="utf-8").read()      # noqa: E731


def test_every_colour_world_is_readable_and_the_accents_spread_over_the_wheel():
    hues = set()
    for name in palettes.WORLDS:
        pal = palettes.world(name, "t")
        for key, need in design.NEEDS.items():
            assert design.contrast(design.fit(pal[key], pal["bg"], need), pal["bg"]) >= need - 0.05, (name, key)
        assert design.contrast(pal["panel"], pal["bg"]) <= 2.2, name
        h = colorsys.rgb_to_hls(*palettes._rgb(pal["accent"]))[0]
        hues.add(int(h * 12))
    assert len(hues) >= 9          # the orange-red every video used to have is one of twelve slices of the wheel


def test_a_video_gets_colours_and_a_backdrop_that_suit_its_subject_but_not_always_the_same_ones():
    stats = {design.design(lambda *a, **k: {}, f"Statistics {k}: the average", "education", "calm", lambda m: None)["world"]
             for k in range(40)}
    assert len(stats) >= 5                                  # the daily Statistics videos do not share a palette
    same = [design.design(lambda *a, **k: {}, "Same title", "education", "calm", lambda m: None) for _ in range(2)]
    assert same[0]["bg"] == same[1]["bg"] and same[0]["back"] == same[1]["back"]      # one video, one look
    for k in range(60):
        d = design.design(lambda *a, **k: {}, f"Space {k}: stars and night sky", "education", "", lambda m: None)
        assert d["back"] in design.BACKGROUNDS
        assert not (d["light"] and d["back"] in design.DARK_ONLY) and not (not d["light"] and d["back"] == "paper")
    # the subject ranks the choices: space videos are offered the starfield, circuits for hardware
    assert "stars" in palettes.rank(palettes.BACKDROPS, "the universe and night sky", "x", 3)
    assert "circuit" in palettes.rank(palettes.BACKDROPS, "chip hardware electronics", "x", 3)


def test_every_backdrop_and_every_shape_is_drawn():
    fx, gen, back = read("fx.jsx"), read("gen.jsx"), read("backdrops.jsx")
    new = set(re.findall(r"(\w+): \w+(?:,|\})", back.split("export const BACKS = {")[1]))
    old = set(re.findall(r'C\.back === "(\w+)"', fx))
    assert (new | old | {"aurora"}) >= set(palettes.BACKDROPS)         # aurora is the plain branch
    assert not set(design.BACKGROUNDS) - (new | old | {"aurora"})
    for shape in design.SHAPES:
        assert f'"{shape}"' in gen or f"{shape}:" in gen or shape in ("circle", "dot"), shape
    assert "{layer" in fx                                   # the chosen backdrop is on screen, not just computed
