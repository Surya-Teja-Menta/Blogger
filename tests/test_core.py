import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from blogwriter.history import History
from blogwriter.llm import extract_json, strip_think
from blogwriter.news import Article, deduplicate, parse_date, relevant, score
from blogwriter.web import normalize_url
from blogwriter.writer import clean_output, trim_to_words, validate, words

NOW = datetime.now(timezone.utc)


def art(title, url="http://x.com/a", src="BBC", age_h=2, desc="d" * 150):
    return Article(title, desc, url, NOW - timedelta(hours=age_h), src, "rss")


def test_clean_removes_chatter_from_real_failed_output():
    raw = ("Okay, let's do this. I'm launching into Chapter 1.\n\n---\n\nReal opening paragraph about Iran oil.\n\n"
           "Second paragraph with facts [2] (Word count: 812).\n\nThird paragraph.\n\n"
           "**Next Steps:**\n\nI will refine this draft.\n\n**Do you have any feedback?**")
    out = clean_output(raw)
    assert out.startswith("Real opening")
    assert "Next Steps" not in out and "feedback" not in out and "[2]" not in out and "Word count" not in out
    assert "Third paragraph." in out


def test_clean_keeps_short_text_intact():
    assert clean_output("Only one paragraph.") == "Only one paragraph."


def test_validate_flags_offtopic_and_length():
    issues = validate("Haifa drone algorithms " * 50, 100, 400, "Six Stocks That Could Soar")
    assert any("subject" in i for i in issues)
    assert any("short" in i for i in validate("stocks soar", 100, 400, "Stocks soar"))


def test_trim_to_words_paragraph_boundary():
    text = "one two three.\n\nfour five six.\n\nseven eight nine."
    assert trim_to_words(text, 7) == "one two three.\n\nfour five six."
    assert words(trim_to_words("a b c d e f g h", 3)) <= 3


def test_extract_json_handles_fences_think_and_chatter():
    assert extract_json('<think>hmm {x}</think>Sure!\n```json\n{"a": [1, 2]}\n```\nDone') == {"a": [1, 2]}
    assert extract_json("Here: [ {\"t\": 1} ] ok") == [{"t": 1}]


def test_strip_think():
    assert strip_think("<think>x</think>answer") == "answer"


def test_parse_date_variants_are_utc_aware():
    assert parse_date("2026-03-12T09:00:00Z").hour == 9
    d = parse_date("Thu, 12 Mar 2026 09:00:00 +0530")
    assert d.hour == 3 and d.minute == 30 and d.tzinfo is not None   # converted, not just stripped
    assert parse_date("garbage") is None and parse_date("") is None


def test_dedupe_counts_coverage():
    a = [art("Iran strikes oil facility in Gulf", "http://a.com/1"),
         art("Iran strikes oil facility in the Gulf", "http://b.com/2", src="Reuters"),
         art("Completely different story", "http://c.com/3")]
    out = deduplicate(a)
    assert len(out) == 2 and out[0].coverage == 2


def test_fluff_headline_ranked_lower():
    good = art("Strait of Hormuz closed after attack")
    fluff = art("Six Stocks That Could Soar in an Era of Instability")
    assert score(good, "geopolitics", 24, NOW) > score(fluff, "geopolitics", 24, NOW)


def test_relevance():
    assert relevant("indian politics", "Indian parliament passes bill on politics")
    assert not relevant("indian politics", "Football transfer news")


def test_history_blocks_duplicates_and_survives_corruption(tmp_path):
    p = tmp_path / "h.jsonl"
    p.write_text('{"url": "https://www.Site.com/a/?utm=1", "title": "Big Story Here"}\nNOT JSON\n', encoding="utf-8")
    h = History(str(p))
    assert h.is_processed("http://site.com/a", "x")                  # same URL, different decoration
    assert h.is_processed("http://other.com/z", "Big story here")    # same headline, different URL
    assert not h.is_processed("http://other.com/y", "Unrelated")
    h.add("t", "http://n.com/1", "New")
    assert History(str(p)).is_processed("http://n.com/1")


def test_normalize_url():
    assert normalize_url("https://www.A.com/x/?q=1#f") == normalize_url("http://a.com/x")


def test_relevance_filter_drops_unrelated_sources():
    from blogwriter.research import is_relevant_hit, story_vocab
    from blogwriter.web import Source
    a = art("Gustavo de Arístegui: Geopolitical analysis of 27 October")
    v = story_vocab(a)
    assert is_relevant_hit(Source("Gustavo de Aristegui - Wikipedia", "http://x", "Spanish diplomat"), v)
    assert not is_relevant_hit(Source("On this Day: October 27 in Financial Markets", "http://y", "1997 mini crash"), v)
    assert not is_relevant_hit(Source("Claudia Sheinbaum", "http://z", "President of Mexico"), v)


def test_relevance_uses_article_text_for_short_headlines():
    from blogwriter.research import is_relevant_hit, story_vocab
    from blogwriter.web import Source
    a = art("UAE Stocks Rose As Earnings Outshone Geopolitics")
    v = story_vocab(a, "Abu Dhabi and Dubai indexes climbed as banks reported stronger quarterly profits.")
    assert is_relevant_hit(Source("Dubai index gains as banks post profits", "http://x", "Abu Dhabi bourse"), v)
    assert not is_relevant_hit(Source("Claudia Sheinbaum", "http://z", "President of Mexico"), v)


def test_market_wraps_ranked_below_hard_news():
    hard = art("Saudi, Turkish and Pakistani chiefs hold talks in Tehran")
    for t in ("UAE Stocks Rose As Earnings Outshone Geopolitics", "WTI Crude Holds Below $100 as Geopolitics Limit Losses",
              "EUR/USD in the Red: Fed Rate, IPO and Geopolitics Support US Dollar"):
        assert score(hard, "geopolitics", 24, NOW) > score(art(t), "geopolitics", 24, NOW)


def test_on_topic_beats_off_topic():
    on = art("Gustavo de Arístegui: Geopolitical analysis of 27 October")
    off = art("The One Health Framework: A New Era for Mainstream Capital")
    assert score(on, "geopolitics", 24, NOW) > score(off, "geopolitics", 24, NOW) + 0.15


def test_entertainment_reviews_ranked_below_news():
    news = art("Iran and US resume nuclear talks in Oman")
    review = art("The Fix movie review: Liam Neeson, Zachary Levi's geopolitical thriller loses the plot")
    assert score(news, "geopolitics", 24, NOW) > score(review, "geopolitics", 24, NOW)


# ---- evidence ledger ------------------------------------------------------
PAGE = ("The IEA said on 11 March that member countries agreed to the largest-ever release of emergency oil "
        "stocks. About 20% of the world's LNG supply passes through the Strait of Hormuz, the agency noted.")


def test_quote_must_appear_in_source():
    from blogwriter.research import quote_supported
    assert quote_supported("agreed to the largest-ever release of emergency oil stocks", PAGE)
    assert quote_supported("Agreed to the LARGEST-EVER release of emergency oil stocks.", PAGE)   # case/punctuation
    assert not quote_supported("Saudi Arabia secretly funded the rebels through Tehran banks", PAGE)
    assert not quote_supported("too short", PAGE)


def test_fact_rejected_when_numbers_not_in_quote():
    from blogwriter.research import verify_fact
    quote = "About 20% of the world's LNG supply passes through the Strait of Hormuz"
    assert verify_fact({"claim": "About 20% of LNG passes through Hormuz.", "quote": quote}, PAGE) is None
    assert "numbers" in verify_fact({"claim": "About 30% of LNG passes through Hormuz.", "quote": quote}, PAGE)
    assert "not found" in verify_fact({"claim": "x", "quote": "A quote that the page never contained at all"}, PAGE)


def test_unverified_figures_are_stripped():
    from blogwriter.writer import strip_unsupported_numbers
    allowed = "release of emergency oil stocks on 11 March; 20% of LNG"
    text = ("## 2024 Heading kept\n\nOn 11 March the stocks were released. The conflict began on 28 February 2024. "
            "About 20% of LNG is affected.")
    out = strip_unsupported_numbers(text, allowed)
    assert "28 February" not in out and "2024 Heading" in out
    assert "11 March" in out and "20%" in out


def _dossier():
    from blogwriter.research import Dossier
    d = Dossier(article={"title": "T", "published": "2026-10-30T00:00:00+00:00", "source": "BBC", "description": ""},
                article_text="")
    d.sources = [{"id": 1, "title": "a", "url": "http://bbc.com/a", "text": "x"},
                 {"id": 2, "title": "b", "url": "http://iea.org/b", "text": "y"}]
    d.facts = [{"claim": "Fact one.", "quote": "q" * 30, "source": 2, "angle": "Timeline", "corroboration": 2},
               {"claim": "Fact two.", "quote": "q" * 30, "source": 1, "angle": "Timeline", "corroboration": 0},
               {"claim": "Fact three.", "quote": "q" * 30, "source": 1, "angle": "Timeline", "corroboration": 1},
               {"claim": "Fact four.", "quote": "q" * 30, "source": 1, "angle": "Economic", "corroboration": 0}]
    d.angles = {"Timeline": {"facts": 3}, "Economic": {"facts": 1}, "Political": {"facts": 0}}
    return d


def test_dossier_views_prefer_corroborated_facts_and_cap_per_angle():
    d = _dossier()
    text = d.facts_text("Timeline")
    assert text.index("Fact one") < text.index("Fact three") < text.index("Fact two")
    assert "iea.org" in text and "corroborated by 2" in text
    assert [f["claim"] for f in d.key_facts(3)] == ["Fact one.", "Fact three.", "Fact four."]   # max 2 per angle
    assert d.usable_angles() == ["Timeline", "Economic"]
    assert "Fact four" in d.notes_for("Political")        # empty angle falls back to all verified facts


def test_corroboration_counts_only_other_domains():
    from blogwriter.research import Researcher
    r = Researcher(llm=None, log=lambda m: None)
    r.dossier = _dossier()
    fact = {"claim": "IEA members released emergency oil stocks in March", "source": 1}
    texts = {1: "IEA members released emergency oil stocks in March",
             2: "The IEA reported its members released emergency oil stocks in March this year",
             3: "Football results"}
    r.dossier.sources.append({"id": 3, "title": "c", "url": "http://sport.com/c", "text": ""})
    assert r._corroboration(fact, texts) == 1


def test_abbreviations_do_not_split_sentences():
    from blogwriter.writer import strip_unsupported_numbers, SENTENCE_END
    s = "It hit Clinton, Franklin, St. Lawrence and Essex. U.S. Customs said 15,000 trucks cross."
    assert len(SENTENCE_END.split(s)) == 2
    out = strip_unsupported_numbers(s, "15,000 trucks")
    assert out == s                                  # nothing orphaned or lost
    out2 = strip_unsupported_numbers(s, "no numbers here")
    assert out2 == "It hit Clinton, Franklin, St. Lawrence and Essex."


def test_rich_vocab_demands_more_overlap():
    from blogwriter.research import is_relevant_hit, story_entities, story_vocab
    from blogwriter.web import Source
    text = ("Nepal and India border crossings closed after landslides blocked roads near Birgunj and Raxaul, "
            "officials in Kathmandu said, as customs traders warned of shortages across the Terai region.")
    v = story_vocab(art("Border Crossings Remain Closed Due to Natural Obstacles"), text)
    ents = frozenset(story_entities(text))
    assert {"india", "birgunj", "kathmandu"} <= ents
    # the real failure: a US-Canada page matched on generic words (border, crossings, roads)
    us = Source("List of Canada-United States border crossings", "http://x", "barricaded roads")
    assert is_relevant_hit(us, v)                      # generic words alone would let it through...
    assert not is_relevant_hit(us, v, ents)            # ...but it names none of the story's places
    assert is_relevant_hit(Source("Nepal India border crossings closed by landslides", "http://y", "Birgunj"), v, ents)


def test_output_sizes_follow_the_evidence():
    from blogwriter.config import MODES
    from blogwriter.pipeline import scaled_mode
    d = _dossier()                                    # 4 facts, no article text
    m = scaled_mode(MODES["standard"], d)
    assert m.article_words < MODES["standard"].article_words and m.blog_words < MODES["standard"].blog_words
    d.facts = d.facts * 20                            # 80 facts: plenty of evidence, mode targets win
    big = scaled_mode(MODES["standard"], d)
    assert big.article_words == MODES["standard"].article_words


def _writer():
    from blogwriter.llm import LLMError
    from blogwriter.writer import Writer

    class NoLLM:                                      # forces the deterministic fallbacks
        def complete_json(self, *a, **k):
            raise LLMError("offline")
    return Writer(NoLLM(), log=lambda m: None)


def test_documentary_follows_the_story_arc_and_skips_unsupported_sections():
    from blogwriter.config import MODES
    d = _dossier()
    d.facts = [{"claim": f"Fact {i}.", "quote": "q" * 30, "source": 1, "angle": a, "corroboration": 0}
               for i, a in enumerate(["Story"] * 5 + ["Timeline"] * 3 + ["Economic"] * 2 + ["Political"] * 1)]
    plan = _writer().plan_documentary(d, MODES["standard"])
    titles = [c["title"] for c in plan]
    # Economic (2) and Political (1) are each below the 3-fact minimum, but their 3 facts are pooled, not lost
    assert titles == ["The Story", "How It Unfolded", "Other Developments and Perspectives"]
    assert plan[0]["facts"] == 5 and plan[0]["angles"] == ["Story"]
    assert plan[-1]["facts"] == 3 and set(plan[-1]["angles"]) == {"Economic", "Political"}


def test_documentary_is_capped_by_mode_and_never_empty():
    from blogwriter.config import MODES
    d = _dossier()
    d.facts = []
    plan = _writer().plan_documentary(d, MODES["fast"])
    assert len(plan) == 1                              # falls back to a single chapter on whatever is verified
    d.facts = [{"claim": "x.", "quote": "q" * 30, "source": 1, "angle": a, "corroboration": 0}
               for a in ["Story", "Timeline", "Stakeholders", "Political", "Economic", "Historical"] for _ in range(3)]
    assert len(_writer().plan_documentary(d, MODES["fast"])) == MODES["fast"].chapters


def test_chapter_notes_list_every_fact_of_its_angles():
    d = _dossier()
    notes = d.notes_for(["Timeline", "Economic"])
    for claim in ("Fact one.", "Fact two.", "Fact three.", "Fact four."):
        assert claim in notes
    assert d.count(["Timeline", "Economic"]) == 4 and d.count("Timeline") == 3


def test_real_market_blurb_headline_is_penalized():
    news = art("Iran and US resume nuclear talks in Oman")
    blurb = art("Silver/AUD (XAGAUD) Moved Sharply on Oct 30: Inventories, the Dollar, or Geopolitics?")
    assert score(news, "geopolitics", 24, NOW) > score(blurb, "geopolitics", 24, NOW) + 0.2


def test_dossier_views_work_before_corroboration_is_scored():
    """Regression: the gap round builds a brief mid-research, before corroboration exists on the facts."""
    d = _dossier()
    for f in d.facts:
        del f["corroboration"]
    assert "Fact one" in d.brief() and "Fact two" in d.facts_text("Timeline")
    assert len(d.key_facts(3)) == 3 and "Fact four" in d.notes_for("Economic")


def test_thin_sections_below_pool_minimum_are_dropped():
    from blogwriter.config import MODES
    d = _dossier()
    d.facts = [{"claim": f"F{i}.", "quote": "q" * 30, "source": 1, "angle": a, "corroboration": 0}
               for i, a in enumerate(["Story"] * 4 + ["Economic"] * 2)]       # 2 thin facts < 3: no pooled chapter
    assert [c["title"] for c in _writer().plan_documentary(d, MODES["standard"])] == ["The Story"]


def test_strict_grounding_drops_a_chapter_the_factcheck_emptied():
    from blogwriter.writer import Writer

    class Emptying:
        def complete(self, *a, **k):
            return "No."                                  # fact-check deleted everything
    w = Writer(Emptying(), log=lambda m: None)
    draft = "An unsupported claim about secret funding. " * 20
    assert w.ground(draft, "notes", "Title", "notes", strict=True) == ""
    # the article and blog (non-strict) fall back to the draft rather than vanishing
    assert w.ground(draft, "notes", "Title", "notes", strict=False).startswith("An unsupported claim")


def test_restated_facts_are_recognised_as_duplicates():
    from blogwriter.research import same_fact
    assert same_fact("BP's underlying replacement cost profit quadrupled to $8.46bn from $2.2bn a year ago.",
                     "BP reported underlying replacement cost profit of $8.46bn, almost quadrupling from $2.2bn a year ago.")
    assert same_fact("BP described the quarter as a banner quarter for refining.",
                     "BP described the quarter as a 'banner quarter' for the refining business.")
    assert not same_fact("BP's profit rose to $8.46bn.", "BP's refining margin rose to $46.7 per barrel.")
    assert not same_fact("Qatari mediators returned to Tehran.", "Vance sent a letter to Rezaei.")


def test_source_files_contain_no_stray_control_characters():
    """Regression: an escape-sequence slip once put backspace characters inside a regex."""
    import glob
    for path in glob.glob(os.path.join(os.path.dirname(os.path.dirname(__file__)), "blogwriter", "*.py")):
        text = open(path, encoding="utf-8").read()
        bad = [c for c in text if ord(c) < 32 and c not in "\n\r\t"]
        assert not bad, f"{os.path.basename(path)} contains control characters {bad!r}"


# ---- step 2: audience ranking ----------------------------------------------
class FakeLLM:
    def __init__(self, reply=None, error=None):
        self.reply, self.error = reply, error

    def complete_json(self, *a, **k):
        if self.error:
            from blogwriter.llm import LLMError
            raise LLMError(self.error)
        return self.reply


def test_audience_rank_promotes_the_story_that_will_provoke_reaction():
    from blogwriter.rank import audience_rank
    dull = art("Committee publishes annual procurement guidelines")
    dull.score = 0.9                                  # objectively "fresh" and well covered...
    hot = art("Leaked memo shows ministers lied about war casualties")
    hot.score = 0.5
    out = audience_rank(FakeLLM([{"id": 1, "score": 2, "why": "routine"}, {"id": 2, "score": 9, "why": "scandal"}]),
                        [dull, hot], "politics", log=lambda m: None)
    assert out[0] is hot and out[0].audience == 9 and out[0].why == "scandal"


def test_audience_rank_falls_back_to_objective_order_when_llm_fails():
    from blogwriter.rank import audience_rank
    a, b = art("A"), art("B")
    a.score, b.score = 0.7, 0.4
    assert audience_rank(FakeLLM(error="down"), [a, b], "x", log=lambda m: None) == [a, b]


def test_audience_rank_tolerates_missing_and_garbage_ratings():
    from blogwriter.rank import audience_rank
    a, b = art("A"), art("B")
    a.score = b.score = 0.5
    out = audience_rank(FakeLLM([{"id": 1, "score": "high"}, {"id": 99, "score": 9}, "junk"]), [a, b], "x",
                        log=lambda m: None)
    assert len(out) == 2 and all(5.0 == x.audience for x in out)       # unrated items get a neutral 5


# ---- step 1: top 20 incl. a few research papers ------------------------------------
def test_pick_returns_top_20_with_papers_capped():
    from blogwriter.news import NewsCollector
    from blogwriter.config import Settings

    class NoHistory:
        def is_processed(self, *a):
            return False
    c = NewsCollector(Settings(), log=lambda m: None)
    items = [art(f"Paper number {i} on quantum error correction") for i in range(8)]
    for it in items:
        it.api = "arxiv"
    news = [art(f"Distinct news headline number {i} about elections") for i in range(25)]
    c.collect = lambda topic, window: items + news
    top = c.pick("x", NoHistory(), days=1)
    assert len(top) == 20 and sum(1 for a in top if a.api == "arxiv") == 4
    assert len(c.pool) == 33                           # the whole fresh pool is kept for the research step


# ---- step 5: email -----------------------------------------------------------------
def _mail_settings(**kw):
    from blogwriter.config import Settings
    base = dict(smtp_host="smtp.example.com", smtp_port=587, smtp_user="me@example.com", smtp_password="pw",
                mail_from="me@example.com", mail_to=["you@example.com"])
    base.update(kw)
    return Settings(**base)


def test_message_has_all_attachments_and_headers(tmp_path):
    from blogwriter.mailer import build_message
    files = []
    for name in ("documentary_report.html", "article.md", "blog.md"):
        p = tmp_path / name
        p.write_text("content of " + name, encoding="utf-8")
        files.append(str(p))
    msg = build_message(_mail_settings(mail_to=["a@x.com", "b@x.com"]), "Subject here", "Body here",
                        files + [str(tmp_path / "missing.pdf")])
    assert msg["To"] == "a@x.com, b@x.com" and msg["From"] == "me@example.com" and msg["Subject"] == "Subject here"
    assert sorted(p.get_filename() for p in msg.iter_attachments()) == ["article.md", "blog.md", "documentary_report.html"]


def test_email_is_skipped_when_smtp_is_not_configured():
    from blogwriter.config import Settings
    from blogwriter.mailer import send_email
    logs = []
    assert send_email(Settings(), "s", "b", [], logs.append) is False
    assert "not configured" in logs[0]


def test_email_failure_never_raises(monkeypatch):
    import smtplib
    from blogwriter.mailer import send_email

    def boom(*a, **k):
        raise smtplib.SMTPAuthenticationError(535, b"bad credentials")
    monkeypatch.setattr(smtplib, "SMTP", boom)
    logs = []
    assert send_email(_mail_settings(), "s", "b", [], logs.append) is False
    assert "FAILED" in logs[0] and "SMTPAuthenticationError" in logs[0]


def test_email_really_travels_over_smtp(tmp_path):
    """End to end over a real socket: a local SMTP sink receives the message with its attachments."""
    pytest = __import__("pytest")
    controller_mod = pytest.importorskip("aiosmtpd.controller")
    from blogwriter.mailer import send_email

    received = []

    class Sink:
        async def handle_DATA(self, server, session, envelope):
            received.append(envelope)
            return "250 OK"
    import socket
    with socket.socket() as probe:                    # ask the OS for a free port, then hand it to the sink
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    controller = controller_mod.Controller(Sink(), hostname="127.0.0.1", port=port)
    controller.start()
    try:
        attach = tmp_path / "blog.md"
        attach.write_text("# hello blog", encoding="utf-8")
        ok = send_email(_mail_settings(smtp_host="127.0.0.1", smtp_port=port,
                                       smtp_user="", smtp_password=""),
                        "Wire test", "Hello body", [str(attach)], lambda m: None)
    finally:
        controller.stop()
    assert ok is True and len(received) == 1
    raw = received[0].content.decode("utf-8", "replace")
    assert received[0].rcpt_tos == ["you@example.com"] and "Subject: Wire test" in raw and "blog.md" in raw


def test_unverified_pull_quote_is_dropped_and_verified_one_kept():
    from blogwriter.writer import strip_unverified_quotes
    allowed = "The minister said the agreement is a turning point for the whole Arctic region."
    text = ("Intro.\n\n> \"the agreement is a turning point for the whole Arctic region\" - Minister\n\n"
            "> \"we will never accept any foreign base on our island soil\" - Someone\n\nEnd.")
    out = strip_unverified_quotes(text, allowed)
    assert "turning point" in out and "foreign base" not in out and out.startswith("Intro.")


def test_documentary_html_has_cover_chapters_and_endmatter():
    from blogwriter.render import to_html
    md = ("# Big Story\n\n*A documentary report* · **Research date:** today\n\n## Key findings\n\n1. A fact\n\n"
          "## Contents\n\n1. One\n2. Two\n\n---\n\n## One\n\nFirst para.\n\n## Two\n\nSecond.\n\n---\n\n"
          "## How this report was researched\n\n- method\n\n## Sources\n\n1. [x](http://x)\n")
    html = to_html(md, "Big Story", {"Sources": 1})
    assert html.count("class='chapter'") == 2 and "Chapter Two" in html
    assert "class='cover'" in html and "class='findings'" in html and "class='endmatter'" in html
    assert "A documentary report</em>" not in html and "<h1>Big Story</h1>" in html


def test_upload_run_to_s3_returns_links_and_never_raises(tmp_path):
    import boto3
    from moto import mock_aws
    from blogwriter.config import Settings
    from blogwriter.storage import upload_run
    (tmp_path / "documentary_report.pdf").write_bytes(b"%PDF-1.4 test")
    (tmp_path / "blog.md").write_text("# hi", encoding="utf-8")
    s = Settings(s3_endpoint="https://s3.us-east-1.amazonaws.com", s3_bucket="reports-bkt", s3_access_key="x",
                 s3_secret_key="y", s3_region="us-east-1")
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="reports-bkt")
        links = upload_run(s, str(tmp_path), ["documentary_report.pdf", "blog.md", "missing.md"], log=lambda m: None)
        assert set(links) == {"documentary_report.pdf", "blog.md"} and "X-Amz-Signature" in links["blog.md"]
        obj = boto3.client("s3", region_name="us-east-1").get_object(
            Bucket="reports-bkt", Key=f"reports/{tmp_path.name}/documentary_report.pdf")
        assert obj["ContentType"] == "application/pdf"
        from dataclasses import replace
        pub = replace(s, s3_public_url="https://pub.example.dev")
        assert upload_run(pub, str(tmp_path), ["blog.md"], log=lambda m: None)["blog.md"] == \
            f"https://pub.example.dev/reports/{tmp_path.name}/blog.md"
        bad = replace(s, s3_bucket="no-such-bucket")        # failure is logged, not raised
        assert upload_run(bad, str(tmp_path), ["blog.md"], log=lambda m: None) == {}
    assert upload_run(Settings(), str(tmp_path), ["blog.md"], log=lambda m: None) == {}   # not configured


class _Resp:
    def __init__(self, payload, status=200, headers=None):
        self._p, self.status_code, self.headers, self.text = payload, status, headers or {}, str(payload)

    def json(self):
        return self._p

    def raise_for_status(self):
        assert self.status_code < 400


def _fake_gumroad(monkeypatch, calls, fail_attach=False):
    import requests

    def post(url, **kw):
        calls.append(("POST", url))
        if url.endswith("/files/presign"):
            return _Resp({"success": True, "upload_id": "u", "key": "k", "file_url": "https://s3/f.pdf",
                          "parts": [{"part_number": 1, "presigned_url": "https://s3/part1"}]})
        if url.endswith("/files/complete"):
            return _Resp({"success": True, "file_url": "https://s3/done.pdf"})
        return _Resp({"success": True, "product": {"id": "ab=", "short_url": "https://x.gumroad.com/l/ab"}})

    def put(url, **kw):
        calls.append(("PUT", url))
        if url == "https://s3/part1":
            return _Resp({}, headers={"ETag": '"e1"'})
        if fail_attach and url.endswith("/products/ab%3D"):
            return _Resp({"success": False, "message": "bad file"}, 422)
        return _Resp({"success": True})

    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(requests, "put", put)
    monkeypatch.setattr(requests, "delete", lambda url, **kw: calls.append(("DELETE", url)) or _Resp({"success": True}))


def test_gumroad_creates_draft_attaches_file_and_publishes_only_when_asked(tmp_path, monkeypatch):
    from dataclasses import replace
    from blogwriter.config import Settings
    from blogwriter.gumroad import list_product
    f = tmp_path / "r.pdf"
    f.write_bytes(b"%PDF-1.4 test")
    s = Settings(gumroad_token="tok")
    calls = []
    _fake_gumroad(monkeypatch, calls)
    out = list_product(s, "Title", "**hi**", str(f), log=lambda m: None)
    assert out == {"url": "https://x.gumroad.com/l/ab", "id": "ab=", "published": False}
    assert [m for m, u in calls if u.endswith("/disable")] and not [u for m, u in calls if u.endswith("/enable")]
    calls.clear()
    out = list_product(replace(s, gumroad_publish=True), "Title", "x", str(f), log=lambda m: None)
    assert out["published"] and calls[-1][1].endswith("/products/ab%3D/enable")
    assert list_product(Settings(), "T", "x", str(f), log=lambda m: None) == {}      # no token: skipped


def test_gumroad_failure_is_logged_and_the_half_made_product_deleted(tmp_path, monkeypatch):
    from blogwriter.config import Settings
    from blogwriter.gumroad import list_product
    f = tmp_path / "r.pdf"
    f.write_bytes(b"%PDF-1.4 test")
    calls, logs = [], []
    _fake_gumroad(monkeypatch, calls, fail_attach=True)
    assert list_product(Settings(gumroad_token="tok"), "T", "x", str(f), log=logs.append) == {}
    assert ("DELETE", "https://api.gumroad.com/v2/products/ab%3D") in calls and "FAILED" in logs[-1]


def test_five_w_one_h_chapter_is_built_from_labelled_groups_and_needs_three_answers():
    d = _dossier()
    d.facts = [{"claim": f"{a} fact {i}.", "quote": "q" * 30, "source": 1, "angle": a, "corroboration": 0}
               for a in ["Story", "Timeline", "Causes", "Mechanism"] for i in range(2)]
    ch = _writer().at_a_glance(d)
    assert ch["title"].startswith("The Story at a Glance")
    assert set(ch["angles"]) == {"Story", "Timeline", "Causes", "Mechanism"} and ch["facts"] == 8
    for label in ("WHAT HAPPENED:", "WHEN IT HAPPENED:", "WHY IT HAPPENED:", "HOW IT HAPPENED:"):
        assert label in ch["notes"]
    assert "WHO IS INVOLVED" not in ch["notes"] and "### Who is involved" not in ch["structure"]
    d.facts = d.facts[:4]                              # only Story + Timeline answered: not enough for the chapter
    assert _writer().at_a_glance(d) is None


def test_blog_source_gives_every_chapter_a_share_so_the_ending_is_not_cut():
    from blogwriter.writer import Writer
    d = _dossier()
    report = "\n\n".join(f"## Chapter {i}\n\n" + ("word " * 600) + f"END{i}" for i in range(10))
    src = Writer._source(d, report, max_chars=6000)
    assert len(src) < 7000 and all(f"Chapter {i}" in src for i in range(10))     # none of them dropped


def test_index_lists_recurring_names_with_chapter_numbers():
    from blogwriter.pipeline import index_md
    chapters = ["## One\n\nTalks held in Oman, said Foreign Minister Abbas Araghchi. Officials in Tehran agreed.",
                "## Two\n\nThe Strait of Hormuz stayed open, while Tehran waited. Mentioned by Abbas Araghchi again.",
                "## Three\n\nA one-off name like Zanzibar appears once, but the Strait of Hormuz returns."]
    idx = index_md(chapters)
    assert "**Tehran** — chapters 1, 2" in idx
    assert "**Abbas Araghchi** — chapters 1, 2" in idx
    assert "**Strait of Hormuz** — chapters 2, 3" in idx
    assert "Zanzibar" not in idx and "**The" not in idx


def test_evidence_register_and_acknowledgements_are_built_from_verified_facts():
    from blogwriter.pipeline import acknowledgements_md, evidence_md
    from blogwriter.news import Article
    d = _dossier()
    ev = evidence_md(d)
    assert ev.count("\n") == 3 and "bbc.com" in ev and "http://iea.org/b" in ev and "“" in ev
    ack = acknowledgements_md(Article("T", "d", "http://x", NOW, "Reuters", "rss"), d)
    assert "Reuters" in ack and "bbc.com" in ack and "iea.org" in ack and "no original reporting" in ack.lower()


def test_report_html_has_acknowledgements_summary_index_and_evidence_pages():
    from blogwriter.render import to_html
    md = ("# Big\n\n*A documentary report* · x\n\n## Acknowledgements\n\nThanks.\n\n## Executive Summary\n\nSum.\n\n"
          "## Key findings\n\n1. F\n\n## Contents\n\n1. One\n\n---\n\n## One\n\nBody.\n\n---\n\n"
          "## Index\n\n- **Iran** — chapter 1\n\n## Evidence register\n\n1. e\n\n## Sources\n\n1. s\n")
    html = to_html(md, "Big")
    assert "class='ack'" in html and "class='summary'" in html
    assert html.count("class='chapter'") == 1                      # front and end matter are not chapters
    assert "id='index'" in html and "id='evidence-register'" in html and html.count("class='newpage'") == 2


def test_pdf_page_counter(tmp_path):
    from blogwriter.render import pdf_pages
    p = tmp_path / "x.pdf"
    p.write_bytes(b"%PDF-1.4\n1 0 obj<</Type /Pages /Kids [2 0 R]>>\n2 0 obj<</Type /Page /Parent 1 0 R>>\n"
                  b"3 0 obj<</Type/Page/Parent 1 0 R>>")
    assert pdf_pages(str(p)) == 2 and pdf_pages(str(tmp_path / "missing.pdf")) == 0


def test_retry_after_reads_the_providers_own_wait():
    import pytest
    from blogwriter.llm import retry_after
    assert retry_after("Rate limit reached. Please try again in 7.8s.") == pytest.approx(8.8)
    assert retry_after("try again in 1m3.2s") == pytest.approx(64.2)
    assert retry_after("try again in 250ms") == pytest.approx(1.25)
    assert retry_after("try again in 2h4m0s") == 3600                    # capped; a daily quota is not waited out
    assert retry_after("no hint in this message") == 60


def _clocked_llm(monkeypatch, endpoints):
    import blogwriter.llm as L
    from blogwriter.config import Settings
    clock, slept = [1000.0], []
    monkeypatch.setattr(L.time, "time", lambda: clock[0])
    monkeypatch.setattr(L.time, "sleep", lambda s: (slept.append(s), clock.__setitem__(0, clock[0] + s)))
    c = L.LLMClient(Settings(), log=lambda m: None)
    monkeypatch.setattr(c, "_endpoints", lambda: endpoints)
    return c, slept


def test_llm_waits_out_a_short_rate_limit_instead_of_losing_the_run(monkeypatch):
    import blogwriter.llm as L
    calls = []

    def limited_once(system, prompt, max_tokens, temperature):
        calls.append(1)
        if len(calls) == 1:
            raise L._Hard("HTTP 429 rate limited", cooldown=20)
        return "the answer"
    c, slept = _clocked_llm(monkeypatch, [("groq#1", limited_once)])
    assert c.complete("hi") == "the answer" and len(calls) == 2
    assert len(slept) == 1 and 20 <= slept[0] <= 22


def test_llm_does_not_wait_for_a_long_outage(monkeypatch):
    import blogwriter.llm as L
    from blogwriter.llm import LLMError

    def daily_quota(system, prompt, max_tokens, temperature):
        raise L._Hard("HTTP 429 daily quota", cooldown=3600)
    c, slept = _clocked_llm(monkeypatch, [("groq#1", daily_quota)])
    try:
        c.complete("hi")
        assert False, "should have failed"
    except LLMError:
        pass
    assert slept == []


def _publish_settings(**kw):
    from blogwriter.config import Settings
    base = dict(devto_api_key="dk", hashnode_token="ht", hashnode_publication_id="pub1",
                wordpress_url="https://wp.example", wordpress_user="u", wordpress_app_password="p w",
                ghost_url="https://ghost.example", ghost_admin_key="abc123:" + "ab" * 16,
                telegram_bot_token="tg", telegram_chat_id="@chan")
    base.update(kw)
    return Settings(**base)


def _fake_posting(monkeypatch, sent, fail=()):
    import requests

    def post(url, **kw):
        sent.append((url, kw))
        for bad in fail:
            if bad in url:
                return _Resp({"message": "boom"}, 500)
        if "dev.to" in url:
            return _Resp({"url": "https://dev.to/me/post", "id": 1})
        if "hashnode" in url:
            node = "publishPost" if "publishPost" in kw["json"]["query"] else "createDraft"
            return _Resp({"data": {node: {"post": {"url": "https://me.hashnode.dev/p"}, "draft": {"id": "d"}}}})
        if "wp-json" in url:
            return _Resp({"link": "https://wp.example/p"})
        if "ghost" in url:
            return _Resp({"posts": [{"url": "https://ghost.example/p"}]})
        return _Resp({"ok": True})                                   # telegram
    monkeypatch.setattr(requests, "post", post)


BLOG = "# Blog headline\n\nBody of the blog."
ARTICLE = "# Article headline\n\n*Standfirst.*\n\n## Section\n\nText."
META = {"title": "Blog headline", "description": "A short description.", "tags": ["Iran War", "oil", "G20", "x y", "five", "six"]}


def test_posts_blog_to_devto_and_hashnode_article_to_wordpress_and_ghost_then_announces(monkeypatch):
    import json as _json
    from blogwriter.publish import post_all
    sent, logs = [], []
    _fake_posting(monkeypatch, sent)
    done = post_all(_publish_settings(), BLOG, ARTICLE, META, log=logs.append)
    assert done == {"Dev.to": "https://dev.to/me/post", "Hashnode": "https://me.hashnode.dev/p",
                    "WordPress": "https://wp.example/p", "Ghost": "https://ghost.example/p"}
    by = {u.split("/")[2]: kw for u, kw in sent}
    dev = by["dev.to"]["json"]["article"]
    assert dev["title"] == "Blog headline" and dev["body_markdown"] == "Body of the blog." and dev["published"] is True
    assert dev["tags"] == ["iranwar", "oil", "g20", "xy"] and by["dev.to"]["headers"]["api-key"] == "dk"
    assert by["gql.hashnode.com"]["json"]["variables"]["i"]["publicationId"] == "pub1"
    assert by["gql.hashnode.com"]["json"]["variables"]["i"]["tags"][0] == {"slug": "iran-war", "name": "iran-war"}
    wp = by["wp.example"]["json"]
    assert wp["title"] == "Article headline" and wp["status"] == "publish" and "<h2>Section</h2>" in wp["content"]
    assert by["wp.example"]["headers"]["Authorization"].startswith("Basic ")
    assert by["ghost.example"]["json"]["posts"][0]["status"] == "published"
    tg = by["api.telegram.org"]["json"]
    assert tg["chat_id"] == "@chan" and "Blog headline" in tg["text"] and "https://dev.to/me/post" in tg["text"]


def test_drafts_when_not_live_and_telegram_stays_silent(monkeypatch):
    from blogwriter.publish import post_all
    sent = []
    _fake_posting(monkeypatch, sent)
    done = post_all(_publish_settings(publish_live=False), BLOG, ARTICLE, META, log=lambda m: None)
    assert len(done) == 4 and not [u for u, _ in sent if "telegram" in u]
    by = {u.split("/")[2]: kw for u, kw in sent}
    assert by["dev.to"]["json"]["article"]["published"] is False
    assert "createDraft" in by["gql.hashnode.com"]["json"]["query"]
    assert by["wp.example"]["json"]["status"] == "draft" and by["ghost.example"]["json"]["posts"][0]["status"] == "draft"


def test_one_platform_failing_does_not_stop_the_others_and_unconfigured_ones_are_skipped(monkeypatch):
    from blogwriter.config import Settings
    from blogwriter.publish import post_all
    sent, logs = [], []
    _fake_posting(monkeypatch, sent, fail=("dev.to",))
    done = post_all(_publish_settings(), BLOG, ARTICLE, META, log=logs.append)
    assert "Dev.to" not in done and {"Hashnode", "WordPress", "Ghost"} <= set(done)
    assert any("Dev.to FAILED" in m for m in logs)
    sent.clear()
    assert post_all(Settings(), BLOG, ARTICLE, META, log=logs.append) == {} and sent == []


def test_ghost_admin_token_is_a_valid_hs256_jwt():
    import base64, hashlib, hmac, json as _json
    from blogwriter.publish import _ghost_token
    secret = "ab" * 16
    head, payload, sig = _ghost_token(f"kid1:{secret}").split(".")
    pad = lambda s: s + "=" * (-len(s) % 4)
    assert _json.loads(base64.urlsafe_b64decode(pad(head))) == {"alg": "HS256", "typ": "JWT", "kid": "kid1"}
    assert _json.loads(base64.urlsafe_b64decode(pad(payload)))["aud"] == "/admin/"
    want = hmac.new(bytes.fromhex(secret), f"{head}.{payload}".encode(), hashlib.sha256).digest()
    assert base64.urlsafe_b64decode(pad(sig)) == want


def test_index_drops_names_that_appear_in_most_chapters_and_merges_possessives():
    from blogwriter.pipeline import index_md
    chapters = [f"## C{i}\n\nTalks held in {n}, said analysts. Officials in Tehran agreed. The {n}'s view."
                for i, n in enumerate(["Oman"] * 2 + ["Cairo"] * 4, 1)]
    chapters[0] += " Then the Nile Delta flooded, and the Nile Delta stayed wet."
    idx = index_md(chapters)
    assert "**Tehran**" not in idx                    # in all 6 chapters: too general to index
    assert "**Oman** — chapters 1, 2" in idx and "**Nile Delta**" in idx and "Oman’s" not in idx


def test_closing_chapter_title_is_not_repeated_in_its_body():
    from blogwriter.writer import Writer

    class Echo:
        def complete(self, *a, **k):
            return "## Summary and Conclusion\n\n**Summary and Conclusion**\n\n- **One** - a finding about T."
    w = Writer(Echo(), log=lambda m: None)
    out = w.conclusion(_dossier(), [{"title": "One"}], ["## One\n\nText about T."], __import__("blogwriter.config", fromlist=["MODES"]).MODES["fast"])
    assert out.count("Summary and Conclusion") == 1 and out.startswith("## Summary and Conclusion\n\n- **One**")


def test_zip_run_bundles_existing_files_only(tmp_path):
    import zipfile
    from blogwriter.storage import zip_run
    (tmp_path / "documentary_report.pdf").write_bytes(b"%PDF-1.4 x")
    (tmp_path / "blog.md").write_text("# b", encoding="utf-8")
    name = zip_run(str(tmp_path), ["documentary_report.pdf", "blog.md", "article.md"])
    assert name == tmp_path.name + ".zip"
    with zipfile.ZipFile(tmp_path / name) as z:
        assert sorted(z.namelist()) == ["blog.md", "documentary_report.pdf"]
        assert z.read("documentary_report.pdf") == b"%PDF-1.4 x"


def test_gumroad_price_defaults_to_3_90(monkeypatch):
    from blogwriter.config import Settings
    monkeypatch.delenv("GUMROAD_PRICE_CENTS", raising=False)
    assert Settings().gumroad_price_cents == 390 and Settings.from_env().gumroad_price_cents == 390


def test_stock_phrases_detected_as_whole_words_only():
    from blogwriter.writer import stock_phrases
    assert set(stock_phrases("Moreover, this pivotal deal will delve into the landscape of trade.")) >= \
        {"moreover", "pivotal", "delve", "landscape of"}
    assert stock_phrases("The harnessed horse ran. Fostering is fine? Notablyx.") == []   # no partial-word hits


def test_plain_words_simplifies_prose_but_not_headings_or_quotes():
    from blogwriter.writer import plain_words
    text = ("## Moreover, a heading — kept\n\nThey utilised the port. Moreover, talks commenced on Monday — "
            "late.\n\n> \"We will utilise every tool\" - Minister")
    out = plain_words(text)
    assert out.startswith("## Moreover, a heading — kept")
    assert "They used the port. Talks started on Monday, late." in out
    assert "utilise every tool" in out          # a quotation is never altered


def test_key_findings_carry_counted_confidence_labels():
    from blogwriter.pipeline import confidence, key_findings_md
    assert [confidence({"corroboration": c}) for c in (0, 1, 2, 5)] == ["Low", "Moderate", "High", "High"]
    md = key_findings_md(_dossier())
    assert "**High confidence.** Fact one." in md and "(3 independent sources)" in md
    assert "**Low confidence.**" in md and "(1 independent source)" in md and "Confidence is counted" in md


def test_blog_cta_links_product_after_opening_and_at_the_end():
    from blogwriter.pipeline import add_cta, blog_cta
    teaser, closing = blog_cta({"url": "https://x.gumroad.com/l/abc", "published": True}, 390, 9, 41, 18)
    assert "US$3.90" in closing and "18-page" in closing and "9 chapters" in closing and "41 verified facts" in closing
    out = add_cta("# Headline\n\nFirst paragraph.\n\n## Section\n\nMore.", teaser, closing)
    paras = out.strip().split("\n\n")
    assert paras[0] == "# Headline" and paras[1] == "First paragraph." and paras[2] == teaser
    assert out.rstrip().endswith("(https://x.gumroad.com/l/abc)**") and out.count("x.gumroad.com") == 2


def test_number_check_drops_table_rows_with_untraceable_numbers():
    from blogwriter.writer import strip_unsupported_numbers
    table = ("| Who | How they are affected | When |\n|---|---|---|\n| Farmers | Lost 40% of exports | Now |\n"
             "| Shippers | Paid 999 more per box | Now |\n| Banks | Face new rules | Longer term |")
    out = strip_unsupported_numbers(table, "Farmers lost 40% of their exports.")
    assert "Farmers" in out and "Banks" in out and "999" not in out and out.startswith("| Who |")


def test_impact_table_keeps_only_fact_checked_rows():
    from blogwriter.writer import Writer

    class Tabler:
        def __init__(self):
            self.calls = 0

        def complete(self, prompt, *a, **k):
            self.calls += 1
            rows = ("| Who | How they are affected | When |\n|---|---|---|\n| Farmers | Lost exports | Now |\n"
                    "| Shippers | Pay more | Now |\n| Banks | New rules | Longer term |\n| Ports | Paid 777 | Now |\n"
                    "| Airlines | Rerouted flights | Now |")
            return rows if self.calls == 1 else rows.replace("| Banks | New rules | Longer term |\n", "")
    w = Writer(Tabler(), log=lambda m: None)
    out = w.impact_table(_dossier())
    assert out.splitlines()[0] == "| Who | How they are affected | When |"
    assert "Farmers" in out and "Airlines" in out
    assert "Banks" not in out and "777" not in out             # removed by the fact-check and by the number check
    assert out.count("\n") == 4                                # header, separator, three rows

    class TooFew(Tabler):
        def complete(self, prompt, *a, **k):
            return "| Who | How they are affected | When |\n|---|---|---|\n| Farmers | Lost exports | Now |"
    assert Writer(TooFew(), log=lambda m: None).impact_table(_dossier()) == ""


def test_brief_lines_get_callout_class_in_html():
    from blogwriter.render import to_html
    md = "# T\n\n## One\n\n**In brief:** The main point.\n\nBody text.\n"
    html = to_html(md, "T")
    assert "<p class=\"brief\"><strong>In brief:</strong>" in html


def test_groq_keys_are_rotated_per_request_but_provider_order_is_kept():
    from blogwriter import llm as L
    from blogwriter.config import Settings
    c = L.LLMClient(Settings(), log=lambda m: None)
    eps = [("groq#1", 1), ("groq#2", 2), ("groq#3", 3), ("nvidia:m#1", 4), ("ollama", 5)]
    firsts = []
    for turn in range(1, 5):
        c._turn = turn
        order = [n for n, _ in c._rotated(eps)]
        assert order[3:] == ["nvidia:m#1", "ollama"] and sorted(order[:3]) == ["groq#1", "groq#2", "groq#3"]
        firsts.append(order[0])
    assert firsts == ["groq#2", "groq#3", "groq#1", "groq#2"]


def test_limit_detail_names_the_limit_without_the_org_id():
    from blogwriter.llm import limit_detail
    body = ('{"error":{"message":"Rate limit reached for model `openai/gpt-oss-20b` in organization `org_01abc` '
            'service tier `on_demand` on tokens per minute (TPM): Limit 8000, Used 7100, Requested 1900. '
            'Please try again in 7.5s."}}')
    out = limit_detail(body)
    assert out == "TPM: used 7100 + requested 1900 of 8000" and "org_" not in out


def test_page_target_sizes_the_report():
    from blogwriter.config import MODES, mode_for_pages
    assert mode_for_pages(3).name == "fast" and mode_for_pages(5).name == "standard"
    assert mode_for_pages(40).name == "deep"
    m = mode_for_pages(20)
    assert m.chapters == 14 and m.chapter_words == MODES["standard"].chapter_words
    small, big = mode_for_pages(10), mode_for_pages(40)
    assert small.chapters * small.chapter_words < m.chapters * m.chapter_words < big.chapters * big.chapter_words
    assert 3 <= mode_for_pages(1).chapters and mode_for_pages(200).chapters == 16


def test_new_providers_are_used_only_with_keys_and_rotate_per_provider(monkeypatch):
    import requests
    from blogwriter import llm as L
    from blogwriter.config import Settings
    s = Settings(groq_keys=["g1"], cerebras_keys=["c1", "c2"], gemini_keys=["m1"], github_keys=["t1"],
                 providers=["groq", "cerebras", "gemini", "openrouter", "github"])
    c = L.LLMClient(s, log=lambda m: None)
    names = [n for n, _ in c._endpoints()]
    assert names == ["groq#1", "cerebras#1", "cerebras#2", "gemini#1", "github#1"]      # no OpenRouter keys
    c._turn = 1
    assert [n for n, _ in c._rotated(c._endpoints())][1:3] == ["cerebras#2", "cerebras#1"]

    sent = []

    class Resp:
        status_code, text = 200, ""

        def json(self):
            return {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]}
    monkeypatch.setattr(requests, "post", lambda url, **kw: (sent.append((url, kw["json"])), Resp())[1])
    dict(c._endpoints())["github#1"]("", "hi", 8000, 0.2)
    dict(c._endpoints())["gemini#1"]("", "hi", 1000, 0.2)
    assert "models.github.ai" in sent[0][0] and sent[0][1]["max_tokens"] == 4000       # the free tier's cap
    assert "generativelanguage" in sent[1][0] and sent[1][1]["reasoning_effort"] == "low"


def test_usage_is_counted_per_provider_and_cerebras_leads_by_default(monkeypatch):
    import requests
    from blogwriter import llm as L
    from blogwriter.config import Settings
    assert Settings().providers[0] == "cerebras"
    c = L.LLMClient(Settings(cerebras_keys=["c1", "c2"], providers=["cerebras"]), log=lambda m: None)

    class Resp:
        status_code, text = 200, ""

        def json(self):
            return {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                    "usage": {"total_tokens": 120}}
    monkeypatch.setattr(requests, "post", lambda url, **kw: Resp())
    c.complete("a")
    c.complete("b")
    assert c.usage == {"cerebras": {"calls": 2, "tokens": 240}}       # both keys counted under one provider


def test_reader_level_and_niche_reach_the_writer_and_bad_inputs_are_refused():
    import pytest
    from blogwriter.pipeline import BlogPipeline, PipelineError
    from blogwriter.writer import audience
    assert audience() == ""
    text = audience("advanced", "upsc")
    assert "UPSC" in text and "expert" in text
    p = BlogPipeline.__new__(BlogPipeline)
    with pytest.raises(PipelineError):
        BlogPipeline.run(p, "x", lang="fr")
    with pytest.raises(PipelineError):
        BlogPipeline.run(p, "x", source="tweets")


def test_topic_seed_prefers_a_relevant_encyclopedia_page_then_the_web(monkeypatch):
    from blogwriter import research as R
    r = R.Researcher(llm=None, log=lambda m: None)
    lead = "India and the Maldives have close relations shaped by trade, tourism and security. " * 10
    monkeypatch.setattr(R, "wikipedia_leads", lambda q, n: [("India–Maldives relations",
                                                             "https://en.wikipedia.org/wiki/IM", lead)])
    article, text = r.seed("india maldives relations")
    assert article.url.endswith("/IM") and text == lead and article.api == "topic"
    assert article.title == "India maldives relations"

    monkeypatch.setattr(R, "wikipedia_leads", lambda q, n: [("Cricket", "https://en.wikipedia.org/wiki/C", "A bat and ball game. " * 40)])
    monkeypatch.setattr(R, "web_search", lambda q, n: [R.Source("Maldives india ties", "https://reddit.com/x", "s"),
                                                       R.Source("India Maldives relations explained",
                                                                "https://news.example/im", "india maldives")])
    monkeypatch.setattr(R, "fetch_text", lambda url, limit: "Full page text. " * 50)
    article, text = r.seed("india maldives relations")
    assert article.url == "https://news.example/im" and text.startswith("Full page")


def test_translation_keeps_a_failed_section_in_english_and_headings_are_read_back():
    from blogwriter.llm import LLMError
    from blogwriter.pipeline import heading_of
    from blogwriter.writer import Writer

    class FakeLLM:
        def complete(self, prompt, **kw):
            if "SECOND" in prompt:
                raise LLMError("down")
            return "## అనువాదం\n\nతెలుగు వచనం ఇక్కడ ఉంది మరియు ఇది పొడవుగా ఉంది"
    w = Writer(FakeLLM(), log=lambda m: None)
    assert w.translate("anything", "en") == "anything"
    out = w.translate("## First\n\nSome text here.\n\n## SECOND\n\nMore text here.", "te")
    assert out.startswith("## అనువాదం") and "## SECOND\n\nMore text here." in out
    assert heading_of(out, "x") == "అనువాదం" and heading_of("no heading", "fallback") == "fallback"
