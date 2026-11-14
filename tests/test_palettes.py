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


def test_the_models_shortlist_decides_and_the_last_videos_are_not_repeated(monkeypatch):
    monkeypatch.delenv("FILM_LOOK", raising=False)
    asked = []

    def model(prompt, **kw):
        asked.append(prompt)
        return {"worlds": ["plum", "ocean", "nonsense", "neon"], "backdrops": ["circuit", "mesh", "bogus"]}
    worlds, backs = palettes.shortlist(model, "T", "education", "calm")
    assert worlds == ["plum", "ocean", "neon"] and backs == ["circuit", "mesh"] and "ember" in asked[0]
    assert palettes.shortlist(lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")), "T", "e", "") == ([], [])
    # a model that always names the same three still varies from title to title, and skips what was just used
    picks = [palettes.pick("x", f"title {k}", worlds)["world"] for k in range(120)]
    assert {"plum", "ocean", "neon"} <= set(picks)                       # its three are used, with two keyword matches
    assert sum(w in worlds for w in picks) >= 0.45 * len(picks)         # ...and are the most common picks
    for k in range(30):
        assert palettes.pick("x", f"title {k}", worlds, avoid=["plum"])["world"] != "plum"
        assert palettes.backdrops("x", f"t{k}", (), backs, ["circuit"]) != "circuit"
    assert palettes.pick("x", "t", ["plum"], avoid=["plum"])["world"] in palettes.WORLDS   # all used: still a world
    d = design.design(model, "A title", "education", "calm", lambda m: None, {"worlds": ["plum"], "backs": ["circuit"]})
    assert d["world"] != "plum" and d["back"] != "circuit"      # the recent ones are avoided


def test_the_history_remembers_the_last_videos_and_no_two_film_looks_run_together(monkeypatch):
    store = {}
    from blogwriter import storage
    monkeypatch.setattr(storage, "get_text", lambda s, key, **k: store.get(key, ""))
    monkeypatch.setattr(storage, "put_text", lambda s, key, text, mime="", **k: store.update({key: text}) or True)
    h = palettes.load_history(None)
    assert h == {"worlds": [], "backs": [], "looks": [], "captions": []}
    for k in range(12):
        palettes.save_history(None, h, {"world": f"w{k}", "back": f"b{k}"})
        h = palettes.load_history(None)
    assert h["worlds"] == [f"w{k}" for k in range(4, 12)] and h["backs"][-1] == "b11" and len(h["backs"]) == 5
    palettes.save_history(None, h, {"look": {"slug": "chalkboard"}})            # a film look has no world of the library
    h = palettes.load_history(None)
    assert h["looks"][-1] == "chalkboard" and h["worlds"][-1] == "w11"
    assert not design.film_look_wanted("any title", "", h["looks"][-1:])            # the next one is a design of its own
    assert any(design.film_look_wanted(f"t{k}", "", [""]) for k in range(40))       # and after that, films come back
    # the same style is not used twice in a few videos: the model's pick is refused, the design is its own
    monkeypatch.setenv("FILM_LOOK", "auto")
    pick = lambda *a, **k: {"look": "chalkboard", "accent": "pink", "why": "x"}
    assert "look" not in design.design(pick, "Topic", "education", "", lambda m: None, {"looks": ["chalkboard", "", ""]})
