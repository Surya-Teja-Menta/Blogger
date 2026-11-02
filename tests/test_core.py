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
