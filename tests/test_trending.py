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
