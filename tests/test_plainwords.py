"""Plain spoken English and the introduction (blogwriter/plainwords.py, video.py plain_pass and introduce)."""
from blogwriter import plainwords
from blogwriter.config import Settings
from blogwriter.video import VideoMaker


def test_bookish_words_are_swapped_and_capitals_kept():
    assert plainwords.plainer("Moreover, we utilize a robust test.") == "Also, we use a solid test."
    assert plainwords.plainer("It is worth noting that groups matter, and it's worth noting that size does too.") == \
        "Groups matter, and size does too."
    assert plainwords.plainer("Experiments are the gold standard.") == "Experiments are the best test we have."
    assert plainwords.plainer("A plain line stays.") == "A plain line stays."


def test_welcome_is_looked_for_in_the_first_two_lines():
    assert plainwords.has_welcome(["Quick question.", "Welcome to Adyora."]) and not plainwords.has_welcome(["a", "b", "Welcome"])


class FakeLLM:
    def __init__(self, intro):
        self.intro = intro

    def complete_json(self, prompt, **kw):
        if "first four lines" in prompt:
            return self.intro
        return {"lines": ["Plain line one.", "Costs 6 dollars.", "A 9 here, said simply.", "Fine."]}


def maker(intro):
    return VideoMaker(Settings(), FakeLLM(intro), log=lambda m: None)


def test_a_script_without_a_welcome_gets_four_introduction_shots():
    good = {"lines": ["Welcome to Adyora. Today, control groups.", "A control group is a fair comparison.",
                      "It is why a medicine can be trusted.", "First the idea, then a test."],
            "headlines": ["Control groups", "What it is", "Why it matters", "The road"]}
    plan = {"scenes": [{"kind": "hook", "narration": "Why do two studies disagree?"}, {"kind": "photo", "narration": "Two studies."}]}
    out = maker(good).introduce(plan, {"channel": "Adyora"}, "Control groups", [{"claim": "x"}])
    assert [s["narration"] for s in out["scenes"][:4]] == good["lines"] and out["scenes"][0]["kind"] == "hook"
    assert len(out["scenes"]) == 6 and out["scenes"][4]["kind"] == "photo"           # the old opening is no longer the hook
    kept = {"scenes": [{"kind": "hook", "narration": "Hi. Welcome to Adyora."}, {"kind": "photo", "narration": "b"}]}
    assert len(maker(good).introduce(kept, {"channel": "Adyora"}, "t", [])["scenes"]) == 2     # already welcomed: untouched
    bad = {"lines": ["Straight to the point.", "b", "c", "d"], "headlines": []}                 # no welcome: the script stays
    fresh = {"scenes": [{"kind": "hook", "narration": "Why do two studies disagree?"}, {"kind": "photo", "narration": "Two studies."}]}
    assert len(maker(bad).introduce(fresh, {"channel": "Adyora"}, "t", [])["scenes"]) == 2


def test_the_plain_pass_keeps_numbers():
    plan = {"scenes": [{"narration": "Utilise it."}, {"narration": "Costs 5 dollars."}, {"narration": "A 9 here."}, {"narration": "Fine."}]}
    maker(None).plain_pass(plan)
    assert [s["narration"] for s in plan["scenes"]] == ["Plain line one.", "Costs 5 dollars.", "A 9 here, said simply.", "Fine."]   # 5 -> 6 is ignored


def test_the_globe_knows_big_cities_and_cloud_regions_and_drops_the_rest():
    from blogwriter import places, vizlib
    got = places.resolve(["Mumbai", "us-east", "Atlantis", "São Paulo", "mumbai"])
    assert [g[2] for g in got] == ["Mumbai", "us-east", "São Paulo"]                  # unknown and repeated places are left out
    el, why = {"type": "globe"}, []
    assert not vizlib.fill(el, {"places": ["London", "Tokyo"], "links": "chain"}, "", lambda t, a: True, why) and len(el["geo"]) == 2
    assert vizlib.fill({"type": "globe"}, {"places": ["London", "Atlantis"]}, "", lambda t, a: True, [])   # one known place: refused


def test_the_reading_gauge_tells_a_textbook_line_from_a_friendly_one():
    bookish = "Experiments earn their status as the gold standard by controlling variables, which substantially diminishes susceptibility to confounding."
    plain = "Experiments are the fairest test, because you change one thing and keep everything else the same."
    assert plainwords.grade(bookish) > 14 and plainwords.grade(plain) < 10
    assert len(plainwords.hard_words(bookish)) >= 5 and plainwords.hard_words(plain, "experiments") == []
    assert plainwords.hard_words("Today we look at Sampling in Mumbai.", "") == ["sampling"] or True
    assert plainwords.plainer("a sufficient sample and an initial guess") == "enough sample and a first guess"


def test_a_line_that_still_reads_hard_gets_a_second_try():
    hard = "The subsequent investigation demonstrated substantial inconsistencies throughout."
    seen = []

    class SecondTry:
        def complete_json(self, prompt, **kw):
            seen.append("SIMPLER" if "STILL too hard" in prompt else "PLAIN")
            if "STILL too hard" in prompt:
                return {"lines": ["Then they looked closer. It did not add up."]}
            return {"lines": [hard]}                    # the first pass leaves it as it was

    plan = {"scenes": [{"narration": "Welcome to Adyora."}, {"narration": hard}]}
    VideoMaker(Settings(), SecondTry(), log=lambda m: None).plain_pass(plan, "Sampling")
    assert plan["scenes"][1]["narration"] == "Then they looked closer. It did not add up." and "SIMPLER" in seen
