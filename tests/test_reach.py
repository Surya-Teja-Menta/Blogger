"""What gets a video found: a hook before the welcome, chapters in the description, three Shorts that all upload."""
import json

from blogwriter import email_page, plainwords, video, youtube


def _scenes(*titles):
    return [{"chapter": {"title": t}} if t else {} for t in titles]


def test_chapters_start_at_zero_and_follow_youtube_s_rules():
    fps = video.FPS
    scenes = _scenes("", "how it starts", "Too close", "The power stroke", "At the end")
    starts = [0, 65 * fps, 70 * fps, 130 * fps, 297 * fps]
    got = video.chapter_lines(scenes, starts, 300 * fps)
    assert got == ["0:00 Introduction", "1:05 How it starts", "2:10 The power stroke"]      # too close / too late left out
    assert video.chapter_lines(_scenes("", "Only one"), [0, 65 * fps], 300 * fps) == []     # fewer than three: none


def test_the_description_carries_the_chapters():
    plan = {"tags": [], "chapters": ["0:00 Introduction", "1:05 Intake", "2:10 Power"]}
    yt = video.youtube_text(plan, {"en": ["T", "What it covers."]}, 0, [], "", {})
    assert "What it covers.\n\n0:00 Introduction\n1:05 Intake\n2:10 Power" in yt["description"]
    assert "0:00" not in yt["short_description"]


def test_the_first_line_asks_for_a_hook_before_the_welcome():
    rule = video.opening_rule({"channel": "Adyora"}, "education", "Engines")
    assert rule.index("surprising") < rule.index("Welcome to Adyora")
    assert "FIRST one short surprising" in plainwords.INTRO
    assert plainwords.has_welcome(["Your car makes thousands of explosions. Welcome to Adyora. Today, engines."])


class _LLM:
    def __init__(self, reply):
        self.reply = reply

    def complete_json(self, *a, **k):
        return self.reply


def test_two_more_shorts_each_answer_a_question_and_bad_beats_are_dropped():
    maker = video.VideoMaker.__new__(video.VideoMaker)
    scenes = [{"kind": "hook", "narration": "a"}, {"kind": "diagram", "narration": "b"}]
    good = {"question": "Why does it spark?", "beats": [{"scene": 0, "narration": "Why?"}, {"scene": 1, "narration": "Heat."}]}
    maker.llm = _LLM({"shorts": [good, {"question": "Bad", "beats": [{"scene": 9, "narration": "x"}]}, "junk"]})
    got = maker.more_shorts(scenes, "")
    assert [m["title"] for m in got] == ["Why does it spark?"] and len(got[0]["beats"]) == 2
    maker.llm = _LLM("not a dict")
    assert maker.more_shorts(scenes, "") == []


def test_upload_short_sends_every_short_and_one_failure_spares_the_rest(monkeypatch, tmp_path):
    meta = {"title": "T", "short_title": "T #Shorts", "shorts": [
        {"file": "short_en_2.mp4", "title": "Q2 #Shorts", "description": "d2"},
        {"file": "short_en_3.mp4", "title": "Q3 #Shorts", "description": "d3"}]}
    (tmp_path / "youtube.json").write_text(json.dumps(meta), encoding="utf-8")
    for name in ("short_en.mp4", "short_en_2.mp4", "short_en_3.mp4"):
        (tmp_path / name).write_bytes(b"x")
    sent, times = [], []
    monkeypatch.setattr(youtube.time, "time", lambda: 0)

    def upload(token, path, info, short, privacy, log=print, publish_at=""):
        sent.append(info["short_title"])
        times.append(publish_at)
        if info["short_title"] == "Q2 #Shorts":
            raise RuntimeError("quota")
        return f"id{len(sent)}"

    from blogwriter import storage
    monkeypatch.setattr(storage, "get_text", lambda *a: "")
    monkeypatch.setattr(storage, "put_text", lambda *a: True)
    monkeypatch.setattr(storage, "remove", lambda *a: None)
    monkeypatch.setattr(youtube, "access_token", lambda: "tok")
    monkeypatch.setattr(youtube, "fetch", lambda run, names, dest, log=print: {n: str(tmp_path / n) for n in names if (tmp_path / n).exists()})
    monkeypatch.setattr(youtube, "upload_video", upload)
    monkeypatch.setattr(youtube, "privacy_of", lambda *a: "public")
    monkeypatch.setattr(youtube, "set_label", lambda *a, **k: "off")
    monkeypatch.setattr(youtube, "add_link_line", lambda *a, **k: "linked")
    monkeypatch.setattr(youtube, "link_pair", lambda *a, **k: [])
    monkeypatch.setattr(youtube, "add_thumbnail", lambda *a, **k: True)
    monkeypatch.setattr(youtube, "add_captions", lambda *a, **k: True)
    report = youtube.run("upload short 20261113_053132_Mean", log=lambda *_: None)
    assert sent == ["T #Shorts", "Q2 #Shorts", "Q3 #Shorts"]
    assert report.startswith("Uploaded") and "Short 2: not uploaded" in report and "Short 3: [Q3 #Shorts]" in report
    assert times == ["", "1970-01-01T03:00:00Z", "1970-01-01T06:00:00Z"]          # Shorts alone: at once, 3 h, 6 h
    times.clear()
    (tmp_path / "long_video_en.mp4").write_bytes(b"x")
    youtube.run("upload both 20261113_053132_Mean", log=lambda *_: None)
    assert times == ["", "1970-01-01T01:00:00Z", "1970-01-01T04:00:00Z", "1970-01-01T07:00:00Z"]      # video first
    status = youtube.video_body({"title": "T"}, False, "public", publish_at="1970-01-01T01:00:00Z")["status"]
    assert status["privacyStatus"] == "private" and status["publishAt"] == "1970-01-01T01:00:00Z"


def test_the_email_offers_all_the_shorts(monkeypatch):
    monkeypatch.delenv("UPLOAD_BUTTON_URL", raising=False)
    links = {n: f"https://r2/{n}" for n in ("long_video_en.mp4", "short_en.mp4", "short_en_2.mp4")}
    page, _ = email_page.build("T", links, None, "", [], "o/r", "20261113_053132_Mean", 4)
    assert "Upload Shorts" in page and "Short 2" in page


def test_the_monthly_report_covers_last_month_and_names_where_viewers_leave(monkeypatch):
    import datetime as dt

    from blogwriter import monthly
    assert monthly.month_of(today=dt.date(2026, 3, 1)) == (dt.date(2026, 2, 1), dt.date(2026, 2, 28))
    curve = [(k / 100, 1.0 if k < 50 else 0.4) for k in range(100)]
    assert "biggest fall after it is 60%" in monthly.leave_point(curve) and monthly.leave_point(curve[:5]) == ""

    def query(token, first, last, **extra):
        if extra.get("dimensions") == "elapsedVideoTimeRatio":
            return curve
        return [["v1", 120, 300, 150, 40.0, 2]] if extra.get("dimensions") else [[120, 300, 150, 40.0, 2]]
    monkeypatch.setattr(monthly, "query", query)
    monkeypatch.setattr(monthly, "titles", lambda token, ids: {"v1": "Engines"})
    text = monthly.build("tok", dt.date(2026, 2, 1), dt.date(2026, 2, 28))
    assert "Views: 120" in text and "2:30 (40%) | 2 | Engines" in text and "Engines: the first tenth" in text


def test_a_lesson_is_never_planned_shorter_than_eight_minutes():
    assert video.check_brief({"minutes": 4}, "concept")["minutes"] == 8
    assert video.check_brief({"minutes": 4}, "education")["minutes"] == 8
    assert video.check_brief({"minutes": 4}, "news")["minutes"] == 4


def test_the_starting_page_is_the_named_article_read_in_full(monkeypatch):
    from blogwriter import research
    lead = "Cache invalidation removes stale entries from a cache. " * 4
    monkeypatch.setattr(research, "wikipedia_leads", lambda q, n=3: [
        ("Cache invalidation", "https://en.wikipedia.org/wiki/Cache_invalidation", lead)])
    monkeypatch.setattr(research, "fetch_text", lambda u, n=6000: lead * 5)
    r = research.Researcher.__new__(research.Researcher)
    r.log = lambda m: None
    r.clean_topic = lambda t: {"subject": "Cache invalidation", "wikipedia": ["Cache invalidation"], "keywords": ["hot key"]}
    article, text = r.seed("cache invalidation")
    assert article.url.endswith("Cache_invalidation") and text == lead * 5 and "cache" in r.subject_words


def test_a_lesson_with_too_few_facts_stops_instead_of_making_a_thin_video(monkeypatch):
    import pytest

    from blogwriter import pipeline
    monkeypatch.delenv("MIN_FACTS", raising=False)
    p = pipeline.BlogPipeline.__new__(pipeline.BlogPipeline)
    p.writer = type("W", (), {})()
    p.s = type("S", (), {"study_notes": False})()
    p.log = lambda m: None
    p._run = lambda *a, **k: {"verified_facts": 5, "dir": "x"}
    with pytest.raises(pipeline.PipelineError, match="only 5 verified facts"):
        p.run("caching", source="topic", video=True, style="education")


def test_one_make_a_video_run_is_one_video_whatever_was_pasted():
    from blogwriter import videoqueue as q
    pasted = ("Statistics:  Covariance and correlation (Pearson, Spearman), Correlation vs causation, and Simpson's paradox\n"
              "[ ] 14. Correlation vs causation, and Simpson's paradox")
    assert q.one_topic(pasted) == ["Statistics: Covariance and correlation (Pearson, Spearman), Correlation vs causation, "
                                   "and Simpson's paradox"]
    assert q.one_topic("Linear regression; The Titanic") == ["Linear regression, The Titanic"]
    assert q.one_topic(" \n ") == []
    assert q.split_topics("- [x] 3. Mean\n4) Median") == ["Mean", "Median"]          # the queue still takes a list


def test_a_line_the_owner_s_voice_could_not_say_is_tried_again_then_the_video_stops(monkeypatch, tmp_path):
    import pytest

    from blogwriter import voicefarm
    from blogwriter.config import Settings
    monkeypatch.setattr(voicefarm, "available", lambda s: True)
    monkeypatch.setattr(voicefarm, "clone", lambda texts, s, job, log: [{"ok": False, "words": [], "out": ""}])
    monkeypatch.setenv("VOICE_PYTHON", __import__("sys").executable)
    asked = []
    monkeypatch.setattr(video, "clone_here", lambda py, jobs, which, s, job, log: asked.append(which) or {})
    monkeypatch.setattr(video, "speak_all", lambda jobs: pytest.fail("the standard voice must never speak"))
    with pytest.raises(video.VoiceError):
        video.speak_cloned([("one", "v", str(tmp_path / "1.mp3"))], Settings(), str(tmp_path), lambda m: None)
    assert asked == [[0]]                                       # spoken again with more takes before giving up


def test_make_a_video_runs_wait_in_line_and_are_made_one_after_another(monkeypatch, tmp_path):
    from blogwriter import videoqueue as q
    monkeypatch.setattr(q, "LINE", str(tmp_path / "now.jsonl"))
    monkeypatch.setattr(q, "DONE", str(tmp_path / "done.jsonl"))
    first = q.push("Covariance, Pearson and Spearman\n[ ] 14. Pearson and Spearman", "use formulas", style="education")
    second = q.push("Simpson's paradox", style="education")
    assert q.push("covariance, pearson and spearman") == first                 # the same topic is not added twice
    up = q.next_up()
    assert up["topic"] == "Covariance, Pearson and Spearman" and up["notes"] == "use formulas"
    out = tmp_path / "out.txt"
    assert q.main(["next", "--out", str(out)]) == 0
    assert "topic<<END_OF_VALUE\nCovariance, Pearson and Spearman\nEND_OF_VALUE" in out.read_text(encoding="utf-8")
    assert "publish<<END_OF_VALUE\nfalse\n" in out.read_text(encoding="utf-8")
    assert q.pop(first["id"], ok=False) == "failed; 1 waiting"                  # a failed video leaves the line too
    assert q.next_up()["id"] == second["id"]
    assert q.pop(second["id"], ok=True) == "made; 0 waiting" and q.next_up() == {}
    assert [d["status"] for d in q.read(q.DONE)] == ["failed", "made"]
