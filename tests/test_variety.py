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
