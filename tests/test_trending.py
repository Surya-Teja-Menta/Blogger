"""Hashtag research (blogwriter/trending.py) and how its result reaches the video's and the Short's text."""
from blogwriter import trending, video


def test_the_topic_is_cut_from_a_title_and_made_a_hashtag():
    assert trending.core("System Design: Consistent Hashing, Rings and Keys: How Data Finds Its Server") == "Consistent Hashing"
    assert trending.core("Mean, Median and Mode: Which Average Lies?") == "Mean Median and Mode"
    assert trending.core("") == ""
    assert trending.hashtag("standard deviation") == "#StandardDeviation"
    assert trending.hashtag("a b") == "" and trending.hashtag("x" * 40) == ""


def test_only_descriptive_suggestions_become_hashtags_and_a_trending_one_ranks_higher():
    found = {"consistent hashing": ["consistent hashing", "consistent hashing explained", "consistent hashing bytebytego",
                                    "how consistent hashing works", "consistent hashing algorithm"],
             "consistent hashing explained": ["consistent hashing explained", "consistent hashing interview"]}
    tags = trending.rank("Consistent Hashing", found, [], "System Design")
    assert tags[:2] == ["#ConsistentHashing", "#SystemDesign"]
    assert "#ConsistentHashingExplained" in tags and "#ConsistentHashingAlgorithm" in tags
    assert not any("Bytebytego" in t or t.startswith("#How") for t in tags)          # no names, no questions
    boosted = trending.rank("Consistent Hashing", found, ["consistent hashing algorithm tutorial"], "")
    assert boosted.index("#ConsistentHashingAlgorithm") < boosted.index("#ConsistentHashingExplained")


def test_research_never_raises_and_keeps_going_offline(monkeypatch):
    def down(*a, **k):
        raise OSError("offline")
    monkeypatch.setattr(trending, "get", down)
    logs = []
    out = trending.research("System Design: Consistent Hashing, Rings: x", ["consistent hashing"], logs.append)
    assert out["hashtags"][0] == "#ConsistentHashing" and out["phrases"] == [] and logs      # still the topic's own tag


def test_the_researched_tags_come_first_under_the_video_and_the_short():
    plan = {"tags": ["consistent hashing", "sharding", "load balancing", "distributed systems"],
            "trend": {"hashtags": ["#ConsistentHashing", "#SystemDesign", "#ConsistentHashingExplained", "#Explained"],
                      "phrases": ["consistent hashing explained", "consistent hashing algorithm"]}}
    assert video.pick_hashtags(plan)[:3] == ["#ConsistentHashing", "#SystemDesign", "#ConsistentHashingExplained"]
    assert len(video.pick_hashtags(plan)) == 5 and len(video.pick_hashtags(plan, 4)) == 4
    texts = {"en": ["Line"] * 3 + ["Consistent Hashing: how data finds its server", "It covers the ring."]}
    yt = video.youtube_text(plan, texts, 3, [], "", {}, [])
    assert "#ConsistentHashing #SystemDesign" in yt["description"] and "consistent hashing explained" in yt["tags"]
    assert yt["short_description"].endswith("#Shorts") and "#ConsistentHashing" in yt["short_description"]
    assert len(yt["tags"]) <= 15


def test_a_sentence_with_a_typo_becomes_a_subject_before_the_encyclopedia_is_asked(monkeypatch):
    from blogwriter import research
    asked = []

    class Model:
        def complete_json(self, prompt, **kw):
            assert "Auto mobile" in prompt
            return {"subject": "Internal combustion engine", "wikipedia": ["Internal combustion engine"], "keywords": ["combustion", "exhaust"]}

    lead = "An internal combustion engine is a heat engine in which the combustion of a fuel occurs with an oxidizer. " * 6
    monkeypatch.setattr(research, "wikipedia_leads", lambda q, n: asked.append(q) or [("Internal combustion engine", "https://en.wikipedia.org/wiki/X", lead)])
    r = research.Researcher(Model(), lambda m: None)
    article, text = r.seed("How the Auto mobile Engine works, end to end process explanation")
    assert article.title == "Internal combustion engine" and text and asked[0] == "Internal combustion engine"

    class Down:
        def complete_json(self, prompt, **kw):
            raise TypeError("no model")
    assert research.Researcher(Down(), lambda m: None).clean_topic("Gears, a long request about what to cover")["subject"] == "Gears"
