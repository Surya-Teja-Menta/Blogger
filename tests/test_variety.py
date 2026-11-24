"""blogwriter/variety.py: a plan that is mostly type, or one picture again and again, scores low; a varied one high."""
from blogwriter import variety


def shot(kind="diagram", **kw):
    return {"kind": kind, **kw}


def test_a_varied_plan_scores_high_and_a_samey_one_low():
    varied = [shot(diagram={"elements": [{"type": t}]}) for t in ("raft", "hashring", "shards", "waffle", "sequence", "box")]
    varied += [shot("photo", graphic={"type": g}) for g in ("flow", "hub", "versus", "stack")]
    good = variety.score(varied)
    assert good["score"] >= 90 and good["techniques"] == 5 and good["run"] == 1
    samey = [shot("photo", graphic={"type": "kinetic"}) for _ in range(6)] + [shot("photo", graphic={"type": "flow"})] * 4
    bad = variety.score(samey)
    assert bad["score"] < 40 and bad["words_only"] == 0.6 and bad["run"] == 6
    assert "samey" in variety.report(samey) and "samey" not in variety.report(varied)


def test_a_picture_shot_with_nothing_in_it_counts_as_words_only():
    assert variety.words_only(shot("photo")) and variety.words_only(shot("hook"))
    assert not variety.words_only(shot("photo", images=["a.jpg"])) and not variety.words_only(shot("stat"))
    assert variety.label(shot(diagram={"elements": [{"type": "box"}, {"type": "ridgeline"}]})) == "ridgeline"
    assert variety.score([])["score"] == 100                                    # no shots, nothing to judge


def test_a_plan_that_is_mostly_type_asks_the_art_director_again_with_type_ruled_out():
    from blogwriter import graphics
    from blogwriter.config import Settings
    from blogwriter.video import VARY_ABOVE, VideoMaker

    class Director:              
        def __init__(self):
            self.prompts = []

        def complete_json(self, prompt, **kw):
            self.prompts.append(prompt)
            return [{"scene": k, "type": "flow" if k % 2 else "versus",             # alternating: no two alike in a row
                     "nodes": [{"icon": "server", "label": "a"}, {"icon": "database", "label": "b"}]} for k in range(6)]

    def plan(n_typed):
        scenes = [{"kind": "hook", "headline": "Open", "narration": "a b c"}]
        scenes += [{"kind": "photo", "headline": f"Idea {k}", "narration": "a and b", "graphic": {"type": "kinetic", "nodes": []}}
                   for k in range(n_typed)]
        scenes += [{"kind": "photo", "headline": f"Fine {k}", "narration": "a and b",
                    "graphic": {"type": "hub" if k % 2 else "stack", "nodes": []}} for k in range(5)]
        return scenes, [{**s, "frames": 150} for s in scenes]
    d = Director()
    maker = VideoMaker(Settings(), d, log=lambda m: None)
    scenes, long_scenes = plan(4)                                   # 4 of 10 shots are type only: 40% > the limit
    assert VARY_ABOVE < 0.4
    assert maker.vary(scenes, long_scenes, {}) == 4
    assert "NEVER kinetic" in d.prompts[0] and variety.score(long_scenes)["words_only"] == 0.1      # only the opening hook is left
    assert [s["graphic"]["type"] for s in scenes[1:5]] == ["flow", "versus", "flow", "versus"]
    # a plan with few type-only shots is left alone, and a director that fails leaves the shots as they were
    scenes, long_scenes = plan(1)
    assert maker.vary(scenes, long_scenes, {}) == 0 and len(d.prompts) == 1
    scenes, long_scenes = plan(4)
    broken = VideoMaker(Settings(), type("Down", (), {"complete_json": lambda self, *a, **k: (_ for _ in ()).throw(
        __import__("blogwriter.llm", fromlist=["LLMError"]).LLMError("down"))})(), log=lambda m: None)
    assert broken.vary(scenes, long_scenes, {}) == 0 and scenes[1]["graphic"]["type"] == "kinetic"
    # the pass refuses animated type and knows which library graphics are already used
    only = {"scene": 0, "type": "kinetic", "nodes": []}
    kin = [{"kind": "photo", "headline": "Short head", "narration": "x"}]
    assert graphics.assign(kin, [only], lambda *a: True, lambda m: None, no_kinetic=True) == 0
    assert graphics.assign(kin, [only], lambda *a: True, lambda m: None) == 1


def test_the_coverage_line_counts_live_pictures_and_lists_the_shots_that_are_only_words():
    from blogwriter import variety
    scenes = [{"kind": "diagram", "headline": "Engine", "diagram": {"elements": [{"type": "engine4"}]}},
              {"kind": "diagram", "diagram": {"elements": [{"type": "engine4"}]}}, {"kind": "diagram", "diagram": {"elements": [{"type": "hashring"}]}},
              {"kind": "photo", "headline": "Why it matters", "graphic": {"type": "kinetic"}}]
    line = variety.coverage(scenes)
    assert "2 of 4 shots run the real thing (engine4 x2)" in line and "Why it matters" in line
