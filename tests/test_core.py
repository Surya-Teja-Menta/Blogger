import json
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


def test_video_figures_are_shortened_never_cut():
    from blogwriter.video import _figure
    allowed = "UPI handled 241.62 billion transactions worth ₹314 trillion, up 1,234,567,890.5 units"
    assert _figure("241.62 billion", allowed) == "241.62B"
    assert _figure("₹ 314 trillion", allowed) == "₹ 314T"
    assert _figure("1,234,567,890.5 units", allowed) == ""      # too long to show whole: dropped, not cut


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


def test_gumroad_price_defaults_to_99_rupees(monkeypatch):
    from blogwriter.config import Settings
    from blogwriter.gumroad import parse_price
    monkeypatch.delenv("GUMROAD_PRICE", raising=False)
    assert Settings().gumroad_price == "99 INR" and Settings.from_env().gumroad_price == "99 INR"
    assert parse_price("99 INR") == (99.0, "inr") and parse_price("3.90 usd") == (3.9, "usd")
    assert parse_price("149") == (149.0, "inr") and parse_price("nonsense") == (99.0, "inr")


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
    teaser, closing = blog_cta({"url": "https://x.gumroad.com/l/abc", "published": True}, "99 INR", 9, 41, 18)
    assert "₹99" in closing and "18-page" in closing and "9 chapters" in closing and "41 verified facts" in closing
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


def test_a_video_run_makes_only_the_video_no_report_and_no_report_email(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from blogwriter import pipeline as P
    from blogwriter.config import Settings
    from blogwriter.news import Article
    sent, written, made = [], [], []
    monkeypatch.setattr(P, "send_email", lambda *a, **k: sent.append(a[1]) or True)
    p = P.BlogPipeline.__new__(P.BlogPipeline)
    p.s, p.log = Settings(output_dir=str(tmp_path)), lambda m: None
    p.llm = SimpleNamespace(last_endpoint="x", usage={})
    p.history = SimpleNamespace(add=lambda *a: None)
    p.news = SimpleNamespace(pool=None)
    art = Article(title="Central limit theorem", url="https://en.wikipedia.org/wiki/Central_limit_theorem",
                  source="Wikipedia", published=None, description="d", api="topic")
    dossier = SimpleNamespace(facts=[{"claim": "c"}], sources=[{"url": "u"}], rejected=0, to_dict=lambda: {"facts": [], "sources": []})
    p.researcher = SimpleNamespace(seed=lambda t: (art, "text " * 200), run=lambda *a, **k: dossier)
    p.writer = SimpleNamespace(reader="", plan_documentary=lambda *a: written.append("report") or [])
    monkeypatch.setattr(P, "scaled_mode", lambda m, d: m)
    import blogwriter.video as V
    monkeypatch.setattr(V.VideoMaker, "__init__", lambda self, *a: None)
    monkeypatch.setattr(V.VideoMaker, "make", lambda self, d, **k: made.append(d) or {"long": "x.mp4"})
    r = P.BlogPipeline.run(p, "Central Limit Theorem", source="topic", publish=False, video=True, style="education")
    assert written == [] and sent == [] and made == [r["dir"]] and r["report"] is False
    assert sorted(os.listdir(r["dir"])) == ["candidates.json", "metadata.json", "research.json"]
    meta = json.load(open(os.path.join(r["dir"], "metadata.json"), encoding="utf-8"))
    assert meta["title"] == "Central limit theorem" and meta["verified_facts"] == 1 and meta["source"] == "topic"
    # publishing (Gumroad, blogs) needs the report, and --report asks for it: then the report is written
    for kw in ({"publish": True}, {"publish": False, "report": True}):
        written.clear()
        try:
            P.BlogPipeline.run(p, "Central Limit Theorem", source="topic", video=True, **kw)
        except Exception:
            pass                                   # the fake writer stops right after planning the report
        assert written == ["report"]


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


def test_video_captions_are_split_and_timed_and_srt_is_well_formed():
    from blogwriter.video import chunks, srt
    lines = chunks("one two three four five six seven eight", 10.0, 14.0, 15)
    assert [l[2] for l in lines] == ["one two three", "four five six", "seven eight"]
    assert lines[0][0] == 10.0 and abs(lines[-1][1] - 14.0) < 1e-9
    assert srt([(61.5, 62.25, "hi")]) == "1\n00:01:01,500 --> 00:01:02,250\nhi\n"


def test_video_script_keeps_only_verified_numbers_and_adds_the_closing_scene():
    from blogwriter.config import Settings
    from blogwriter.video import VideoMaker

    class FakeLLM:
        def complete_json(self, prompt, **kw):
            return {"title": "T", "thumb_text": "Big deal", "description": "D", "tags": ["a"],
                    "scenes": [{"kind": "hook", "narration": "A 115 billion dollar deal.", "number": "$115B",
                                "subjects": ["Marvell Technology"], "facts": [1]},
                               {"kind": "fact", "narration": "Shares rose 7 percent. It was big.", "number": "7%",
                                "subjects": [], "facts": [1]},
                               {"kind": "fact", "narration": "Talks began in 2024.", "number": "", "facts": []},
                               {"kind": "quote", "narration": "He said it fits.", "number": "", "facts": [1]},
                               {"kind": "fact", "narration": "Lumentum makes optics.", "number": "", "facts": []},
                               {"kind": "map", "narration": "Both firms are American.", "countries": ["USA"]}],
                    "short": [{"scene": 0, "narration": "A 115 billion dollar deal."}, {"scene": 9, "narration": "x"}]}

    facts = [{"claim": "Marvell agreed to buy Lumentum for $115 billion", "quote": "", "source": "1"}]
    sources = [{"url": "https://www.reuters.com/x"}]
    plan = VideoMaker(Settings(), FakeLLM(), log=lambda m: None).script("T", facts, sources)
    narr = [s["narration"] for s in plan["scenes"]]
    assert plan["scenes"][0]["number"] == "$115B" and plan["scenes"][0]["source"] == "reuters.com"
    assert plan["scenes"][1]["number"] == "" and narr[1] == "It was big."      # 7 is not a verified number
    assert "Talks began in 2024." not in narr                                   # nor is 2024
    assert plan["scenes"][-1]["kind"] == "outro" and "every source is linked" in narr[-1]
    assert plan["scenes"][-1]["kicker"] == "Sources below" and "report" not in narr[-1]     # no report to promise
    assert [b["scene"] for b in plan["short"]] == [0, len(plan["scenes"]) - 1]   # bad index dropped, ending added
    sold = VideoMaker(Settings(), FakeLLM(), log=lambda m: None).script("T", facts, sources, report=True)
    assert "1 verified facts" in sold["scenes"][-1]["narration"] and sold["scenes"][-1]["kicker"] == "Full report below"


def test_posting_guide_lists_the_sources_and_only_the_languages_made():
    from blogwriter.video import posting_guide
    plan = {"title": "T", "tags": ["a"]}
    guide = posting_guide(plan, {"en": ["line", "Title", "Desc"]}, 1, [], "", {"sources": 2, "verified_facts": 3},
                          [{"url": "https://a.org/x"}, {"url": "https://b.com/y"}, {"url": "https://a.org/x"}, {"url": ""}])
    assert "Add language" not in guide and "short_en.mp4" in guide
    assert guide.count("- https://a.org/x") == 1 and "- https://b.com/y" in guide


def test_video_translation_must_keep_the_line_count_or_the_language_is_skipped():
    from blogwriter.config import Settings
    from blogwriter.video import VideoMaker

    class FakeLLM:
        def __init__(self, reply):
            self.reply = reply

        def complete_json(self, prompt, **kw):
            return self.reply

    good = VideoMaker(Settings(), FakeLLM(["एक", "दो"]), log=lambda m: None)
    assert good.translate_lines(["one", "two"], "hi") == ["एक", "दो"]
    bad = VideoMaker(Settings(), FakeLLM(["एक"]), log=lambda m: None)
    assert bad.translate_lines(["one", "two"], "hi") is None


def test_video_scene_visuals_need_verified_data_or_fall_back_to_a_photo():
    from blogwriter.video import check_scene
    allowed = "Marvell paid $115 billion in 2024; revenue rose 46% in 2025 and 13% in 2026"
    quotes = "we are building the future of light"
    countries = {"india": "India", "united states of america": "United States of America"}
    stat = check_scene({"kind": "stat", "number": "$115B", "label": "deal value", "headline": "A huge bet"}, allowed,
                       quotes, countries)
    assert stat["kind"] == "stat" and stat["number"] == "$115B"
    assert check_scene({"kind": "stat", "number": "$999B"}, allowed, quotes, countries)["kind"] == "photo"
    cmp = check_scene({"kind": "compare", "items": [{"label": "2025", "display": "46%"}, {"label": "2026", "display": "13%"},
                                                    {"label": "x", "display": "77%"}]}, allowed, quotes, countries)
    assert cmp["kind"] == "compare" and [i["value"] for i in cmp["items"]] == [46.0, 13.0]   # 77% is not verified
    tl = check_scene({"kind": "timeline", "events": [{"date": "2024", "label": "deal"}, {"date": "2025", "label": "growth"},
                                                     {"date": "2031", "label": "invented"}]}, allowed, quotes, countries)
    assert tl["kind"] == "photo"                                   # only two verified dates left
    m = check_scene({"kind": "map", "countries": ["USA", "India", "Atlantis"]}, allowed, quotes, countries)
    assert m["countries"] == ["United States of America", "India"]
    q = check_scene({"kind": "quote", "quote": "We are building the future of light.", "speaker": "CEO"}, allowed,
                    quotes, countries)
    assert q["kind"] == "quote" and q["speaker"] == "CEO"
    assert check_scene({"kind": "quote", "quote": "Made up words here"}, allowed, quotes, countries)["kind"] == "photo"
    assert check_scene({"kind": "quote", "quote": "We are building the future of light.", "speaker": "Wikipedia"},
                       allowed, quotes, countries)["kind"] == "photo"           # an encyclopedia line is no quote
    h = check_scene({"kind": "photo", "headline": "A $300B rival appears", "highlight": "rival"}, allowed, quotes, countries)
    assert "$300B" not in h["headline"] and h["highlight"] == "rival"


def test_video_timeline_overlaps_scenes_by_the_transition():
    from blogwriter.video import FPS, TRANSITION, timeline
    frames, starts, total = timeline([2.0, 0.0, 3.0], ["hook", "chapter", "photo"])
    assert frames[1] == 75 and starts[1] == frames[0] - TRANSITION
    assert total == sum(frames) - 2 * TRANSITION and frames[0] >= 2 * FPS + TRANSITION


def test_video_charts_are_drawn_only_as_the_verified_figures_allow():
    from blogwriter.video import check_scene
    allowed = "Revenue was $4.5B in 2022, $5.9B in 2023 and $7.1B in 2024; data centers are 74% and carriers 12%"
    chk = lambda sc: check_scene(sc, allowed, "", {})
    line = chk({"kind": "line", "items": [{"label": "2022", "display": "$4.5B"}, {"label": "2023", "display": "$5.9B"},
                                          {"label": "2024", "display": "$7.1B"}]})
    assert line["kind"] == "line" and [i["value"] for i in line["items"]] == [4.5, 5.9, 7.1]
    # an invented year label drops its point, and two points are not a trend: they become a comparison
    short = chk({"kind": "line", "items": [{"label": "2022", "display": "$4.5B"}, {"label": "2031", "display": "$5.9B"},
                                           {"label": "2024", "display": "$7.1B"}]})
    assert short["kind"] == "compare" and len(short["items"]) == 2
    donut = chk({"kind": "donut", "items": [{"label": "Data centers", "display": "74%"}, {"label": "Carriers", "display": "12%"}]})
    assert donut["kind"] == "donut"
    mixed = chk({"kind": "bars", "items": [{"label": "Revenue", "display": "$7.1B"}, {"label": "Share", "display": "74%"},
                                           {"label": "Other", "display": "12%"}]})
    assert mixed["kind"] == "kpis"                      # different units cannot share one axis
    steps = chk({"kind": "steps", "items": [{"label": "Chip sends data"}, {"label": "Laser makes light"},
                                            {"label": "Fiber carries it"}]})
    assert steps["kind"] == "steps" and len(steps["items"]) == 3
    assert chk({"kind": "steps", "items": [{"label": "one"}, {"label": "two"}]})["kind"] == "photo"


def test_video_plan_shapes_the_script_and_acts_become_stings():
    from blogwriter.config import Settings
    from blogwriter.video import KICKERS, VideoMaker, check_brief

    brief = check_brief({"style": "story", "structure": "a mystery told clue by clue", "minutes": 4, "maths": True,
                         "acts": [{"title": "The missing ship", "job": "set up the mystery"}],
                         "opening": "Start on the empty harbour."}, "auto")
    assert brief["style"] == "story" and brief["minutes"] == 4 and brief["maths"]
    assert check_brief(None, "education")["style"] == "education"          # a failed plan keeps the asked style
    assert check_brief({"minutes": "lots"}, "auto")["minutes"] == 4.0
    assert check_brief({"minutes": "lots"}, "education")["minutes"] == 9.0 and check_brief({"minutes": 30}, "auto")["minutes"] == 12

    class FakeLLM:
        def complete_json(self, prompt, **kw):
            if prompt.startswith(("These are the narration lines", "You are the comedy writer")):      # the lengthening pass: lines kept as they are
                return {"lines": json.loads(prompt.split("Lines (JSON): ", 1)[1].split("\n")[0])}
            assert "Lemmino" in prompt and "clue by clue" in prompt and "Start on the empty harbour." in prompt
            assert "MATHS INTUITION" in prompt and r"\frac{1}{n}" in prompt and "28 to 40 scenes" in prompt
            assert "{shape}" not in prompt and "{shots}" not in prompt and "{{" not in prompt
            return {"title": "T", "thumb_text": "x", "description": "D", "tags": [],
                    "outro": "So the ship was never lost. Every source is in the description, so check it yourself.",
                    "scenes": [{"kind": "hook", "narration": "Why does light win?"},
                               {"kind": "chapter", "narration": "Part one.", "headline": "The idea"},
                               {"kind": "photo", "narration": "Light is fast."},
                               {"kind": "photo", "narration": "Copper is slow.", "act": "How it works"},
                               {"kind": "photo", "narration": "So data goes optical."},
                               {"kind": "photo", "narration": "That is the answer."}],
                    "short": []}

    plan = VideoMaker(Settings(), FakeLLM(), log=lambda m: None).script("T", [], [], brief=brief)
    kicker = plan["scenes"][1]["chapter"]["kicker"]
    assert [s["narration"] for s in plan["scenes"]][:2] == ["Why does light win?", "Light is fast."]   # no title shot
    assert plan["scenes"][1]["chapter"]["title"] == "The idea" and kicker in [k(0) for k in KICKERS]
    assert plan["scenes"][2]["chapter"]["kicker"] != kicker and "chapter" not in plan["scenes"][3]
    assert plan["scenes"][-1]["narration"].startswith("So the ship was never lost.")


def test_every_video_gets_its_own_readable_design():
    from blogwriter import design

    good = {"palette": {"bg": "#0b1020", "panel": "#131a30", "line": "#2a3352", "text": "#f5f3ee", "muted": "#9aa3b8",
                        "accent": "#ffb000", "hot": "#ff5a5f", "cool": "#3ec9f0", "violet": "#a77bff"},
            "display": "Fraunces", "body": "Inter", "upper": False, "background": "waves",
            "cuts": ["iris", "sweep", "nope"], "pace": "calm"}
    d = design.check(good)
    assert d and d["named_cuts"] == ["iris", "sweep"] and d["cuts"] == d["fx"]["transitions"] and not d["light"] and d["speed"] < 1 and d["weight"] == 900
    faint = design.check({**good, "palette": {**good["palette"], "text": "#20263a", "accent": "#3a2a10"}})
    assert design.contrast(faint["text"], faint["bg"]) >= 7 and design.contrast(faint["accent"], faint["bg"]) >= 3
    assert design.check({**good, "palette": {**good["palette"], "panel": "#ffffff"}}) is None    # cards vanish
    assert design.check({**good, "body": "RobotoSlab"})["body"] == "RobotoSlab"
    assert design.check({**good, "body": "BebasNeue"}) is None                                   # one weight only
    assert design.check({**good, "display": "Comic Sans"}) is None and design.check("no") is None
    looks = set()
    for k in range(40):                     # the fallback is new every time and always passes the same checks
        g = design.generate(f"title {k}")
        raw = {"palette": {c: g[c] for c in design.COLOURS}, "display": g["display"], "body": g["body"],
               "background": g["back"], "cuts": g["named_cuts"], "pace": g["pace"]}
        assert design.check(raw), g
        looks.add((g["bg"], g["display"], g["back"]))
    assert len(looks) == 40
    logs = []
    got = design.design(lambda *a, **k: good, "T", "story", "", logs.append)
    assert got["source"] == "designed" and logs
    boom = design.design(lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")), "T", "story", "", logs.append)
    assert boom["source"] == "generated"


def test_graphics_take_the_nearest_real_icon():
    from blogwriter import graphics
    assert graphics.icon("chart line") == "chart-line" and graphics.icon("brain") == "brain"
    assert graphics.icon("conditional-probability") == "dice-5"              # an idea word names its icon
    assert graphics.icon("valley-icon", "Error valley") == "mountain" and graphics.icon("", "Advertising") == "megaphone"
    assert graphics.icon("xqzv", "zzz") == "sparkles"
    every = graphics.all_icons()
    assert not [n for n in graphics.ICONS | set(graphics.CONCEPTS.values()) if n not in every]


def test_video_dubbed_lines_are_sped_up_to_fit_the_english_picture():
    from blogwriter.sound import mix_filter
    graph, _ = mix_filter([0.2, 3.0], [], [], [1.25, 1.0])
    assert "atempo=1.250,adelay=delays=200" in graph and graph.count("atempo") == 1




def test_graphics_are_checked_timed_and_translated():
    from blogwriter import graphics
    from blogwriter.video import _verified, on_screen, with_text
    scenes = [
        {"kind": "photo", "headline": "Your phone pays the shop", "number": "", "label": "", "kicker": "", "quote": "",
         "narration": "Your phone sends money through NPCI to the shop in two seconds."},
        {"kind": "stat", "headline": "UPI dominates", "number": "84%", "label": "of digital payments", "kicker": "",
         "quote": "", "narration": "UPI carries 84% of digital payments."},
        {"kind": "photo", "headline": "Same again", "number": "", "label": "", "kicker": "", "quote": "",
         "narration": "Phones and shops again."},
        {"kind": "bars", "headline": "Not eligible", "number": "", "label": "", "kicker": "", "quote": "", "narration": "x"},
    ]
    flow = {"type": "flow", "nodes": [{"icon": "smartphone", "label": "Your phone"}, {"icon": "network", "label": "NPCI"},
                                      {"icon": "store", "label": "The shop"}]}
    reply = [{"scene": 0, **flow}, {"scene": 1, "type": "grid", "icon": "users"}, {"scene": 2, **flow},
             {"scene": 3, **flow},
             {"scene": 0, "type": "flow", "nodes": [{"icon": "not-an-icon", "label": "x"}]}]
    assert graphics.assign(scenes, reply, _verified, lambda m: None) == 3
    assert scenes[1]["graphic"] == {"type": "grid", "icon": "users", "number": "84%", "label": "of digital payments"}
    assert "graphic" not in scenes[3]                                  # charts keep their templates
    assert graphics.check({"type": "versus", "nodes": [{"icon": "user", "label": "500 rivals"},
                                                       {"icon": "user", "label": "B"}]}, scenes[0], _verified) is None
    words = [(0.0, 0.3, "Your"), (0.3, 0.7, "phone"), (0.7, 1.0, "sends"), (1.0, 1.2, "money"), (1.2, 1.6, "through"),
             (1.6, 2.0, "NPCI"), (2.0, 2.2, "to"), (2.2, 2.4, "the"), (2.4, 2.8, "shop")]
    g = graphics.timed(scenes[0]["graphic"], scenes[0]["headline"], words, 120, 30, 6)
    assert [n["at"] for n in g["nodes"]] == [12, 51, 75] and "at" not in scenes[0]["graphic"]["nodes"][0]
    texts = on_screen(scenes[0])
    assert texts[-3:] == ["Your phone", "NPCI", "The shop"]
    hindi = with_text(scenes[0], texts[:-3] + ["आपका फ़ोन", "एनपीसीआई", "दुकान"])
    assert [n["label"] for n in hindi["graphic"]["nodes"]] == ["आपका फ़ोन", "एनपीसीआई", "दुकान"]


def test_queue_adds_plans_and_retries_topics(tmp_path, monkeypatch):
    from blogwriter import videoqueue as queue
    monkeypatch.setattr(queue, "QUEUE", str(tmp_path / "topics.jsonl"))
    monkeypatch.setattr(queue, "DONE", str(tmp_path / "done.jsonl"))
    assert queue.split_topics(" Linear regression ;; the Titanic\nlinear REGRESSION ") == \
        ["Linear regression", "the Titanic"]
    new = queue.add(["Linear regression", "The Titanic"], style="education", level="basic")
    assert [i["source"] for i in new] == ["topic", "topic"] and queue.add(["linear regression"]) == []
    jobs = queue.plan(["geopolitics", "technology"], take=1)
    assert [j["topic"] for j in jobs] == ["geopolitics", "technology", "Linear regression"]
    assert jobs[0]["style"] == "news" and jobs[0]["publish"] and jobs[2]["style"] == "education"
    first = new[0]["id"]
    assert [queue.done(first, ok=False) for _ in range(2)] == ["retry", "retry"]
    assert queue.done(first, ok=False) == "gave up" and [i["topic"] for i in queue.read()] == ["The Titanic"]
    assert queue.done(new[1]["id"], ok=True) == "made" and queue.read() == []
    assert [d["status"] for d in queue.read(queue.DONE)] == ["gave up", "made"]
    assert queue.done("nope", ok=True) == "missing"


def test_graph_expressions_are_parsed_safely_and_checked():
    from blogwriter import mathexpr
    f = mathexpr.compile_expr("a*x^2 - 2*sin(pi*x) + exp(-x^2/2)")
    assert abs(f(1.0, 2.0) - (2 - 0 + 2.718281828 ** -0.5)) < 1e-6
    assert mathexpr.compile_expr("-x^2")(3, 0) == -9
    for bad in ("__import__('os')", "x y", "2x", "sin x", "x +", "foo(x)", "open(x)", ""):
        try:
            mathexpr.compile_expr(bad)
            raise AssertionError(bad)
        except ValueError:
            pass
    g = mathexpr.check_graph({"curves": [{"fn": "a*x^2", "tex": "y=ax^2"}, {"fn": "nope(x)"}], "x": [-3, 3],
                              "param": {"from": 0.5, "to": 2}, "mark": "tangent"})
    assert g == {"curves": [{"fn": "a*x^2", "tex": "y=ax^2"}], "x": [-3.0, 3.0], "mark": "tangent",
                 "param": {"from": 0.5, "to": 2.0}}
    assert mathexpr.check_graph({"curves": [{"fn": "1/(x-x)"}], "x": [0, 1]}) is None     # never finite
    assert mathexpr.check_graph({"curves": [{"fn": "x"}], "x": [2, 1]}) is None
    assert "param" not in mathexpr.check_graph({"curves": [{"fn": "exp(x)"}], "x": [0, 2], "param": {"from": 1, "to": 2}})


def test_derive_and_graph_shots_are_checked_timed_and_translated():
    from blogwriter import graphics
    from blogwriter.video import check_scene, on_screen, with_text
    base = {"narration": "n", "headline": "", "kicker": ""}
    d = check_scene({**base, "kind": "derive", "steps": [{"tex": "J = (y - wx)^2", "note": "the cost"},
                                                        "\frac{dJ}{dw} = -2x(y - wx)", {"tex": "\href{x}{y}"}]},
                    "", "", set())
    assert d["kind"] == "derive" and [s["note"] for s in d["steps"]] == ["the cost", ""]
    one = check_scene({**base, "kind": "derive", "steps": [{"tex": "x", "note": "start"}]}, "", "", set())
    assert one["kind"] == "equation" and one["parts"] == [{"tex": "x", "label": "start"}] and "steps" not in one
    assert check_scene({**base, "kind": "derive", "steps": []}, "", "", set())["kind"] == "photo"
    assert check_scene({**base, "kind": "equation", "parts": [{"tex": "w \\leftarrow w - \\alpha g", "label": "step"}]},
                       "", "", set())["kind"] == "equation"
    g = check_scene({**base, "kind": "graph", "graph": {"curves": [{"fn": "x^2", "tex": "y=x^2"}], "x": [-2, 2]},
                     "xlabel": "time", "ylabel": "distance"}, "", "", set())
    assert g["kind"] == "graph" and g["xlabel"] == "time"
    assert check_scene({**base, "kind": "graph", "graph": {"curves": [{"fn": "import os"}]}}, "", "", set())["kind"] == "photo"
    texts = on_screen(d)
    assert texts[-2:] == ["the cost", ""]
    assert [s["note"] for s in with_text(d, texts[:-2] + ["लागत", ""])["steps"]] == ["लागत", ""]
    assert with_text(g, on_screen(g)[:-2] + ["समय", "दूरी"])["ylabel"] == "दूरी"
    steps = graphics.timed_steps([{"tex": "a", "note": ""}, {"tex": "b", "note": "derivative"},
                                  {"tex": "c", "note": ""}], [(0.2, 0.5, "derivative")], 300, 30, 6)
    ats = [s["at"] for s in steps]
    assert ats == sorted(ats) and all(b - a >= 20 for a, b in zip(ats, ats[1:])) and ats[-1] <= 300


def test_lessons_use_type_not_unrelated_stock_photos():
    from blogwriter import graphics
    scenes = [{"kind": "photo", "headline": "Guessing line"}, {"kind": "photo", "headline": "x", "graphic": {"type": "hub"}},
              {"kind": "plot", "headline": "Fit"}, {"kind": "hook", "headline": ""}]
    assert graphics.no_stock_photos(scenes) == 1
    assert scenes[0]["graphic"] == {"type": "kinetic", "nodes": []} and scenes[1]["graphic"]["type"] == "hub"
    assert "graphic" not in scenes[2] and "graphic" not in scenes[3]
    assert graphics.timed(scenes[0]["graphic"], "Guessing line", [], 120, 30, 6)["words"]


def test_nothing_waits_long_for_its_spoken_word():
    from blogwriter import design, graphics
    late = [(5.0, 5.4, "robust"), (6.0, 6.3, "line")]
    parts = graphics.timed_parts([{"tex": "J", "label": "robust loss"}], late, 300, 30, 6)
    assert parts[0]["at"] <= 30
    k = graphics.timed({"type": "kinetic", "nodes": []}, "Can a line predict", late, 300, 30, 6)
    assert max(k["words"]) <= 6 + 16 + 5 * 3 + 3
    pal = {"bg": "#f7fafc", "panel": "#ffffff", "line": "#d0d7de", "text": "#111827", "muted": "#4b5563",
           "accent": "#d92d20", "hot": "#b54708", "cool": "#1570ef", "violet": "#6941c6"}
    d = design.check({"palette": pal, "display": "Inter", "body": "Inter", "background": "grid", "cuts": ["iris", "wipe"]})
    assert d["light"] and d["back"] == "dots"


def test_unfinished_formulas_are_dropped():
    from blogwriter.video import check_scene, tex_complete
    good = [r"J = \frac{1}{n}\sum_{i=1}^{n}(y_i - \hat{y}_i)^2", r"w \leftarrow w - \alpha \frac{\partial J}{\partial w}",
            r"\hat{y}", "-x"]
    bad = [r"w \leftarrow w - \alpha \frac{\partial}{\partial}", r"\frac{1}{n", "y = ", r"x^{}", r"w \leftarrow"]
    assert all(tex_complete(t) for t in good) and not any(tex_complete(t) for t in bad)
    base = {"narration": "n", "headline": "", "kicker": ""}
    d = check_scene({**base, "kind": "derive", "steps": [{"tex": good[0], "note": "cost"}, {"tex": bad[0], "note": "x"},
                                                        {"tex": good[1], "note": "step"}]}, "", "", set())
    assert [s["tex"] for s in d["steps"]] == [good[0], good[1]]
    e = check_scene({**base, "kind": "equation", "parts": [{"tex": "w", "label": ""}, {"tex": r"\leftarrow", "label": ""}]},
                    "", "", set())
    assert e["kind"] == "photo"


def test_narration_is_speakable_and_typed_hats_are_repaired():
    from blogwriter import graphics
    from blogwriter.video import fix_tex, speakable
    assert fix_tex(r"\betâ = (X^{T}X)^{-1}X^{T}y") == r"\hat{\beta} = (X^{T}X)^{-1}X^{T}y"
    assert fix_tex("ŷ = wx + b") == r"\hat{y} = wx + b"
    assert speakable(r"We model the predicted price \hat y as w times x") == "We model the predicted price y hat as w times x"
    assert speakable(r"so \betâ shrinks, and \lambda grows; a rôle") == "so beta hat shrinks, and lambda grows; a rôle"
    assert "\\" not in speakable(r"the cost \frac{1}{n} of it")
    g = graphics.timed({"type": "versus", "nodes": [{"icon": "x", "label": "inflated slope"}, {"icon": "y", "label": "true slope"}]},
                       "", [(9.0, 9.5, "inflated"), (9.6, 10.0, "true")], 400, 30, 6)
    assert all(n["at"] <= 6 + 6 + 240 // 2 + 30 for n in g["nodes"]) and g["nodes"][0]["at"] < 200


def test_grid_graphic_times_its_number():
    from blogwriter import graphics
    g = graphics.timed({"type": "grid", "icon": "users", "number": "46%", "label": "share"}, "", [(2.0, 2.4, "46")],
                       200, 30, 6)
    assert g["at"] == 66


def test_motion_language_is_clamped_and_never_a_preset():
    from blogwriter import design
    fx = design.check_fx({"layers": [{"shape": "star", "count": 500, "size": 9, "speed": "fast", "drift": "orbit",
                                      "opacity": -1, "color": "pink", "blur": 999}],
                          "transitions": [{"shape": "circle", "angle": 400, "blur": 3}], "camera": 50,
                          "text": {"enter": "mask"}, "cards": {"radius": 1000, "fill": "outline"}}, "t")
    L = fx["layers"][0]
    assert L["shape"] in design.SHAPES and L["count"] == 80 and L["size"] == 0.7 and L["drift"] == "orbit"
    assert L["opacity"] == 0.02 and L["color"] in design.FX_COLOURS and L["blur"] == 60
    assert fx["transitions"][0]["shape"] == "circle" and fx["transitions"][0]["angle"] == 60 and len(fx["transitions"]) >= 2
    assert fx["camera"] == 2 and fx["text"]["enter"] == "mask" and fx["cards"] == {**fx["cards"], "radius": 48, "fill": "outline"}
    looks = {str(design.check_fx(None, f"title {k}")) for k in range(30)}
    assert len(looks) == 30                                   # every video its own recipe
    assert design.check_fx(None, "same") == design.check_fx(None, "same")   # and each render of one video identical


def test_thumbnail_uses_the_strongest_visual():
    from blogwriter.video import TRANSITION, hero_shot
    scenes = [{"kind": "hook", "frames": 100, "graphic": {"type": "kinetic"}}, {"kind": "plot", "frames": 150},
              {"kind": "photo", "frames": 120, "graphic": {"type": "hub"}}, {"kind": "graph", "frames": 200}]
    starts = [0, 85, 220, 325]
    assert hero_shot(scenes, starts) == 325 + 200 - TRANSITION - 12           # the graph, fully drawn
    assert hero_shot(scenes[:3], starts) == 85 + 150 - TRANSITION - 12        # else the plot
    assert hero_shot([scenes[0], scenes[2]], [0, 85]) == 85 + 120 - TRANSITION - 12   # else a real graphic
    assert hero_shot([scenes[0]], [0]) is None                                # kinetic type is not a picture


def test_diagrams_are_checked_and_timed_to_their_words():
    from blogwriter import diagram
    from blogwriter.video import _verified, tex_complete
    scene = {"headline": "One outlier drags the line",
             "narration": "When a single outlier appears far above the rest, it drags the whole line toward itself."}
    raw = {"elements": [
        {"type": "dots", "color": "cool", "r": 2.4, "points": [[12, 78], [20, 70], [27, 73], "bad"]},
        {"type": "line", "x1": 8, "y1": 80, "x2": 80, "y2": 40, "move": {"on": "drags", "y2": 26}},
        {"type": "dot", "color": "hot", "x": 188, "y": 12, "r": 3.6, "on": "Outlier,", "glow": {"on": "drags"}},
        {"type": "label", "x": 40, "y": 92, "text": "costs 400 dollars"},          # a number the narration never says
        {"type": "teleport", "x": 1}, {"type": "tex", "x": 50, "y": 50, "tex": r"\frac{1}{"},
        {"type": "icon", "x": 50, "y": 20, "name": "chart line", "size": 99}]}
    d = diagram.check(raw, scene, _verified, tex_complete)
    types = [e["type"] for e in d["elements"]]
    assert types == ["dots", "line", "dot", "icon"]
    dot = d["elements"][2]
    assert dot["x"] == 97 and dot["on"] == "outlier" and dot["glow"] == {"on": "drags"}
    assert d["elements"][1]["move"] == {"on": "drags", "y2": 26.0} and d["elements"][3]["name"] == "chart-line"
    assert d["elements"][3]["size"] == 30 and len(d["elements"][0]["points"]) == 3
    assert diagram.check({"elements": raw["elements"][:2]}, scene, _verified, tex_complete) is None     # too thin
    crowded = {"elements": [{"type": "label", "x": 50, "y": 50, "text": "the whole line"},
                            {"type": "label", "x": 51, "y": 51, "text": "toward itself"}, {"type": "dot", "x": 9, "y": 9}]}
    assert diagram.check(crowded, scene, _verified, tex_complete) is None                         # labels collide
    why = []
    assert diagram.check(crowded, scene, _verified, tex_complete, why) is None
    assert why == ['label "the whole line" and label "toward itself" overlap; move them apart']
    why = []
    diagram.check(raw, scene, _verified, tex_complete, why)
    assert any("costs 400 dollars" in w for w in why) and any("typesets" in w for w in why)
    words = [(0.1 * k, 0.1 * k + 0.08, w) for k, w in enumerate(scene["narration"].split())]
    t = diagram.timed(d, words, 300, 30, 6)
    at = {e["type"]: e["at"] for e in t["elements"]}
    outlier = next(k for k, (_, _, w) in enumerate(words) if w == "outlier")
    assert at["dot"] == min(round(0.1 * outlier * 30) + 6, at["dot"])
    assert t["elements"][1]["move"]["at"] > t["elements"][1]["at"] and "at" not in d["elements"][1]
    assert diagram.texts({"elements": [{"text": "a"}, {"type": "dot"}, {"text": "b"}]}) == ["a", "b"]


def test_diagram_boxes_fit_their_words_and_pieces_never_pile_up():
    from blogwriter import diagram
    from blogwriter.video import _verified, tex_complete
    sc = {"narration": "we show the model an example and the answer", "headline": ""}
    box = {"type": "box", "x": 40, "y": 30, "w": 12, "h": 10, "text": "example"}
    on_top = [box, {"type": "icon", "x": 53, "y": 35, "name": "brain", "size": 12}, {"type": "dot", "x": 10, "y": 10}]
    assert diagram.check({"elements": on_top}, sc, _verified, tex_complete) is None
    apart = [{**box, "x": 10}, {"type": "icon", "x": 53, "y": 35, "name": "brain", "size": 12}, {"type": "dot", "x": 80, "y": 10}]
    d = diagram.check({"elements": apart}, sc, _verified, tex_complete)
    assert d and d["elements"][0]["w"] >= len("example") * 1.45 + 4
    edge = diagram.check({"elements": [{**box, "x": 90, "text": "the answer"}, {"type": "dot", "x": 10, "y": 80},
                                       {"type": "dot", "x": 20, "y": 80}]}, sc, _verified, tex_complete)
    assert edge["elements"][0]["x"] + edge["elements"][0]["w"] <= 97


def test_thumbnail_hero_is_cut_out_by_its_transparency(tmp_path):
    from PIL import Image
    from blogwriter.video import crop_to_content, hero_shot
    im = Image.new("RGBA", (400, 200), (0, 0, 0, 0))
    for x in range(100, 300):
        for y in range(80, 120):
            im.putpixel((x, y), (255, 80, 60, 255))
    path = str(tmp_path / "hero.png")
    im.save(path)
    aspect = crop_to_content(path, "#fafafd")
    out = Image.open(path)
    assert out.mode == "RGBA" and 200 < out.size[0] < 260 and 40 < out.size[1] < 80 and aspect > 3
    scenes = [{"kind": "photo", "frames": 90, "diagram": {"elements": []}}, {"kind": "bars", "frames": 90},
              {"kind": "photo", "frames": 90, "graphic": {"type": "hub"}}]
    assert hero_shot(scenes, [0, 90, 180]) == 90 - 15 - 12            # a kept diagram outranks a chart


def test_each_video_draws_its_own_arrival_curve_and_stagger():
    from blogwriter import design
    picks = {design.check_fx(None, seed)["motion"]["ease"] for seed in "abcdefghijklmnop"}
    assert len(picks) >= 4 and picks <= set(design.EASES)                  # varies from video to video
    m = design.check_fx({"motion": {"ease": "outElastic", "frames": 3, "bounce": 7, "from": "sideways"}}, "x")["motion"]
    assert m["ease"] == "outElastic" and m["frames"] >= 18 and m["bounce"] == 1 and m["from"] in design.FROMS


def test_surface_shots_are_checked_and_carry_their_labels():
    from blogwriter.mathexpr import check_surface
    from blogwriter.video import check_scene, on_screen
    bowl = check_surface({"fn": "x^2 + 3*y^2", "tex": "J = w^2 + 3b^2", "mark": "descent", "start": [2.5, -9]})
    assert bowl["start"] == [2.5, -3.0] and bowl["points"] == []
    assert check_surface({"fn": "x + a"}) is None and check_surface({"fn": "4"}) is None    # unknown symbol, flat
    plane = check_surface({"fn": "0.5*x + 0.3*y", "mark": "residuals", "points": [[1, 1, 2], [9, 9, 9], "bad"]})
    assert plane["mark"] == "" and plane["points"] == []                    # too few points to show residuals
    sc = check_scene({"kind": "surface", "surface": {"fn": "x^2 - y^2", "mark": "minimum"}, "xlabel": "w",
                      "ylabel": "b", "zlabel": "cost"}, "", "", {})
    assert sc["kind"] == "surface" and on_screen(sc)[-3:] == ["w", "b", "cost"]
    assert check_scene({"kind": "surface", "surface": {"fn": "y +"}}, "", "", {})["kind"] == "photo"


def test_diagram_curves_reshape_and_dots_ride_curves():
    from blogwriter import diagram
    from blogwriter.video import _verified, tex_complete
    sc = {"narration": "the ball rolls down until the slope is flat", "headline": ""}
    raw = {"elements": [
        {"type": "curve", "id": "bowl", "points": [[8, 14], [30, 70], [50, 82], [70, 70], [92, 14]],
         "move": {"on": "flat", "points": [[8, 50], [50, 50], [92, 50]]}},
        {"type": "dot", "x": 10, "y": 20, "r": 3, "on": "ball", "move": {"on": "rolls", "along": "bowl", "x": 50, "y": 82}},
        {"type": "dot", "x": 90, "y": 20, "r": 2, "move": {"on": "rolls", "along": "missing"}},
        {"type": "dot", "x": 60, "y": 20, "r": 2, "move": {"on": "rolls", "along": 0}}]}
    d = diagram.check(raw, sc, _verified, tex_complete)
    els = d["elements"]
    assert els[0]["move"]["points"] == [[8.0, 50.0], [50.0, 50.0], [92.0, 50.0]]
    assert els[1]["move"]["along"] == 0 and "move" not in els[2] and els[3]["move"]["along"] == 0
    t = diagram.timed(d, [(0.1 * k, 0.1 * k + 0.08, w) for k, w in enumerate(sc["narration"].split())], 300, 30, 6)
    assert t["elements"][1]["move"]["along"] == 0 and t["elements"][1]["move"]["at"] > t["elements"][1]["at"]


def test_diagram_parts_for_any_topic_samples_physics_counters_crowds_shapes_and_marks():
    from blogwriter import diagram
    from blogwriter.video import _verified, tex_complete
    scene = {"headline": "Averages pile into a bell",
             "narration": "Grab 30 random orders, average them, repeat 400 times, and the averages pile into a bell."}
    raw = {"elements": [
        {"type": "samples", "x": 4, "y": 6, "w": 60, "h": 99, "source": "volcano", "n": 300, "count": 9999, "lo": 70,
         "hi": 10, "unit": "minutes", "text": "averages of 30 orders", "on": "average", "fit": {"on": "bell"}},
        {"type": "counter", "x": 84, "y": 20, "from": 0, "to": 400, "text": "times", "on": "repeat"},
        {"type": "shape", "x": 84, "y": 50, "size": 12, "shape": "blob", "move": {"on": "bell", "shape": "heart", "size": 99}},
        {"type": "crowd", "x": 72, "y": 70, "w": 22, "h": 22, "name": "pizza", "count": 30, "highlight": 300,
         "glow": {"on": "average"}, "fit": {"on": "bell"}},
        {"type": "label", "x": 84, "y": 36, "text": "random orders", "mark": {"on": "random", "style": "zigzag"}}]}
    why = []
    d = diagram.check(raw, scene, _verified, tex_complete, why)
    assert d, why
    s, c, sh, cr, lab = d["elements"]
    # bad values are pulled into range, an unknown source or shape becomes a known one, an upside-down axis resets
    assert (s["source"], s["n"], s["count"], s["h"], s["lo"], s["hi"]) == ("skewed", 100, 600, 91, 0, 100)
    assert s["fit"] == {"on": "bell"} and c["to"] == 400 and c["from"] == 0
    assert sh["shape"] == "circle" and sh["move"] == {"on": "bell", "shape": "heart", "size": 40}
    assert cr["highlight"] == 30 and "fit" not in cr                 # only samples and physics fit a bell
    assert lab["mark"] == {"on": "random", "style": "circle"}
    # a counter may only count to a number the narration says
    why = []
    bad = {"elements": raw["elements"][:1] + [{**raw["elements"][1], "to": 999}] + raw["elements"][2:]}
    assert len(diagram.check(bad, scene, _verified, tex_complete, why)["elements"]) == 4
    assert any("999" in w for w in why)
    # a label on top of a live region is refused
    why = []
    over = {"elements": [raw["elements"][0], {"type": "label", "x": 30, "y": 50, "text": "random orders"},
                         raw["elements"][1]]}
    assert diagram.check(over, scene, _verified, tex_complete, why) is None and any("overlap" in w for w in why)
    # the bell only comes once the pile is nearly complete, whenever its word is said
    words = [(0.1 * k, 0.1 * k + 0.08, w) for k, w in enumerate(scene["narration"].split())]
    t = diagram.timed(d, words, 300, 30, 6)
    ts = t["elements"][0]
    assert ts["fit"]["at"] >= ts["at"] + int(0.75 * (300 - ts["at"])) and t["elements"][4]["mark"]["at"] >= t["elements"][4]["at"]
    physics = diagram.check({"elements": [{"type": "physics", "x": 30, "y": 4, "w": 40, "h": 92, "pegs": 99, "balls": 5,
                                           "bins": "0", "drop": "sideways"},
                                          {"type": "dot", "x": 10, "y": 10}, {"type": "dot", "x": 90, "y": 10}]},
                            scene, _verified, tex_complete)
    p = physics["elements"][0]
    assert (p["pegs"], p["balls"], p["bins"], p["drop"]) == (12, 20, 0, "center")


def test_the_writer_asks_for_pictures_and_lessons_get_the_voice():
    from blogwriter import diagram, video
    sc = video.check_scene({"kind": "diagram", "headline": "Averages pile up", "narration": "x",
                            "picture": "single delivery times fall into a lopsided histogram, then averages pile into a bell"},
                           "", "", {})
    assert sc["kind"] == "diagram" and sc["picture"].startswith("single delivery times")
    rows = diagram.prompt([{"headline": "h", "narration": "n"}, {**sc, "narration": "the averages pile up"}], [1], "t", "m")
    assert "WANTED: single delivery times" in rows
    brief = video.check_brief({"minutes": 10, "examples": "pizza delivery times; cricket scores", "acts": [{"title": "A"}]},
                              "education")
    rules, _ = video.shape_prompt(brief, "education", "Central Limit Theorem", "(none)")
    assert "pizza delivery times; cricket scores" in rules and "sarcastic" in rules and "12-year-old" in rules
    news, _ = video.shape_prompt(video.check_brief({}, "news"), "news", "t", "(none)")
    assert "sarcastic" not in news and video.check_brief({}, "education")["examples"]


def test_long_videos_draw_more_diagrams_and_the_pictures_asked_for_come_first():
    from blogwriter import video
    scenes = [{"kind": "hook", "headline": "h", "narration": "n"}] + \
             [{"kind": "diagram" if k % 3 == 0 else "photo", "headline": f"h{k}", "narration": f"n{k}"} for k in range(60)]
    seen = []

    class Maker(video.VideoMaker):
        def __init__(self):
            self.log = lambda m: None
            self.design_json = None

    import blogwriter.diagram as dg
    real = dg.design
    dg.design = lambda complete, scs, idx, *a, **k: seen.append(list(idx)) or 0
    try:
        Maker().draw_diagrams(scenes, {"style": "education", "minutes": 10, "mood": "", "tone": ""}, "t")
        Maker().draw_diagrams(scenes, {"style": "education", "minutes": 4, "mood": "", "tone": ""}, "t")
    finally:
        dg.design = real
    long, short = seen
    asked = [i for i, s in enumerate(scenes) if s["kind"] == "diagram"]
    assert len(long) == video.DIAGRAM_MAX_LONG and set(asked) <= set(long)
    assert len(short) == video.DIAGRAM_MAX and set(short) <= set(range(1, 61))


def test_subscribe_card_lands_on_a_settled_shot_about_a_third_in():
    from blogwriter.video import subscribe_at
    starts = [0, 400, 900, 1500, 2100, 2700]
    kinds = ["hook", "photo", "graph", "photo", "equation", "outro"]
    assert subscribe_at(starts, kinds, 3000) == 900 + 30
    assert subscribe_at([0, 300], ["hook", "outro"], 600) is None                # too short for one


def test_short_scripts_are_lengthened_line_by_line_and_the_outro_names_the_channel():
    from blogwriter.config import Settings
    from blogwriter.video import VideoMaker

    class FakeLLM:
        def complete_json(self, prompt, **kw):
            if prompt.startswith(("These are the narration lines", "You are the comedy writer")):
                lines = json.loads(prompt.split("Lines (JSON): ", 1)[1].split("\n")[0])
                return {"lines": [line + " and here is why that matters to you" for line in lines]}
            return {"title": "T", "thumb_text": "x", "description": "D", "tags": [], "outro": "",
                    "scenes": [{"kind": "hook", "narration": "Why does light win?"},
                               {"kind": "photo", "narration": "Light is fast."},
                               {"kind": "photo", "narration": "Copper is slow."},
                               {"kind": "photo", "narration": "So data goes optical."},
                               {"kind": "photo", "narration": "That is the answer."}], "short": []}

    plan = VideoMaker(Settings(), FakeLLM(), log=lambda m: None).script("T", [], [])
    narr = [s["narration"] for s in plan["scenes"]]
    assert narr[1] == "Light is fast. and here is why that matters to you"
    assert "subscribe to Adyora" in narr[-1] and plan["scenes"][-1]["channel"] == "Adyora"
    assert plan["short"][-1]["narration"].endswith("on Adyora.")


def test_narration_never_claims_a_life_the_narrator_does_not_have():
    from blogwriter.video import strip_persona
    assert strip_persona("I'm in my garage lab with a messy spreadsheet. Here is the scatter. Let's draw a line.") == \
        "Here is the scatter. Let's draw a line."
    assert strip_persona("In my years as an engineer I saw this. We can check it ourselves.") == "We can check it ourselves."
    assert strip_persona("I'll show you why the line tilts.") == "I'll show you why the line tilts."


def test_worked_examples_keep_their_numbers_only_when_the_arithmetic_is_right():
    from blogwriter.video import arithmetic_ok, check_scene, maths_shown
    assert arithmetic_ok([r"\hat{y} = 2 \cdot 3 + 1 = 7", r"J = \frac{1}{2}(3-1)^2 = 2", r"\frac{1}{3} \approx 0.33"])
    assert not arithmetic_ok([r"\hat{y} = 2 \cdot 3 + 1 = 8"])
    assert arithmetic_ok([r"w \leftarrow w - \alpha \frac{\partial J}{\partial w}"])              # symbols are not judged
    good = check_scene({"kind": "derive", "steps": [{"tex": r"\hat{y} = w x + b", "note": "the model"},
                                                    {"tex": r"\hat{y} = 2 \cdot 3 + 1 = 7", "note": "plug in"}]}, "", "", {})
    assert good["kind"] == "derive" and "7" in maths_shown(good)
    bad = check_scene({"kind": "derive", "steps": [{"tex": r"\hat{y} = w x + b", "note": "the model"},
                                                   {"tex": r"\hat{y} = 2 \cdot 3 + 1 = 9", "note": "plug in"}]}, "", "", {})
    assert bad["kind"] == "photo"


def test_check_shots_need_a_question_options_and_a_real_answer():
    from blogwriter.video import check_scene, on_screen, with_text
    sc = check_scene({"kind": "check", "question": "Which way does w move if the slope is negative?",
                      "options": ["Up", "Down", "It stays"], "answer": 0, "why": "We step against the slope"}, "", "", {})
    assert sc["kind"] == "check" and sc["answer"] == 0 and len(sc["options"]) == 3
    assert on_screen(sc)[-5:] == [sc["question"], sc["why"], "Up", "Down", "It stays"]
    moved = with_text(sc, on_screen(sc)[:-5] + ["Q", "W", "A", "B", "C"])
    assert moved["question"] == "Q" and moved["options"] == ["A", "B", "C"]
    assert check_scene({"kind": "check", "question": "Q?", "options": ["a", "b"], "answer": 5}, "", "", {})["kind"] == "photo"


def test_long_lessons_are_written_part_by_part_from_an_outline():
    from blogwriter.config import Settings
    from blogwriter.video import VideoMaker, check_brief
    asked = []

    class FakeLLM:
        def complete_json(self, prompt, **kw):
            asked.append(prompt)
            if "THIS IS A LONG VIDEO" in prompt:
                return {"title": "Gradient descent", "thumb_text": "Roll downhill", "thumb_highlight": "downhill",
                        "description": "D", "tags": ["a"], "outro": "",
                        "parts": [{"title": "The bowl", "beats": ["graph: the cost bowl", "check: which way?"]},
                                  {"title": "The step", "beats": ["derive: one step with numbers"]}]}
            if "Now write ONLY part" in prompt:
                part = 1 if 'part 1 of 2' in prompt else 2
                return {"scenes": [{"kind": "photo", "narration": f"Shot {'abc'[k]} of part {'xy'[part - 1]} explains the idea."}
                                   for k in range(3)]}
            if prompt.startswith("These are the shots of a video"):
                return {"short": [{"scene": 1, "narration": "Watch the ball roll."}]}
            if prompt.startswith(("These are the narration lines", "You are the comedy writer")):
                return {"lines": json.loads(prompt.split("Lines (JSON): ", 1)[1].split("\n")[0])}
            raise AssertionError("unexpected prompt")

    brief = check_brief({"style": "education", "minutes": 10, "acts": [{"title": "The bowl", "job": "x"}]}, "education")
    lesson = {"course": "Machine Learning", "module": "Optimisation", "number": 3, "total": 20, "title": "Gradient descent",
              "goal": "You can take a gradient step.", "key_ideas": ["slope", "step size"], "visuals": ["a bowl"],
              "previous": [{"title": "Cost functions", "key_ideas": ["squared error"]}], "next": "Learning rates"}
    plan = VideoMaker(Settings(), FakeLLM(), log=lambda m: None).script("Gradient descent", [], [], "education", brief,
                                                                         lesson=lesson)
    # 10 minutes need ~70 shots: part 1 (2 of 3 beats) is written in 4 pieces, part 2 in 2, at most 14 shots a request
    assert len(plan["scenes"]) == 19 and plan["scenes"][12]["chapter"]["title"] == "The step"   # 6 x 3 shots + outro
    assert sum("Now write ONLY part" in p for p in asked if "piece" in p) >= 6
    assert any('lesson 3 of 20 in the course "Machine Learning"' in p and "Cost functions" in p and "Learning rates" in p
               for p in asked)
    assert plan["short"][0] == {"scene": 1, "narration": "Watch the ball roll."}


def test_a_thin_outline_still_gives_a_full_length_lesson():
    from blogwriter.config import Settings
    from blogwriter.video import VideoMaker, check_brief
    asked = []

    class FakeLLM:
        def complete_json(self, prompt, **kw):
            asked.append(prompt)
            if "THIS IS A LONG VIDEO" in prompt:          # 4 beats for a 10 minute lesson: far too few
                return {"title": "CLT", "outro": "", "parts": [{"title": "One", "beats": ["a", "b"]},
                                                               {"title": "Two", "beats": ["c", "d"]}]}
            if "Now write ONLY part" in prompt:
                n = 32 if "far too short" in prompt else 4     # short at first, full once told
                return {"scenes": [{"kind": "diagram", "narration": " ".join(["word"] * 24)} for _ in range(n)]}
            if prompt.startswith("These are the shots of a video"):
                return {"short": []}
            if prompt.startswith(("These are the narration lines", "You are the comedy writer")):
                return {"lines": json.loads(prompt.split("Lines (JSON): ", 1)[1].split("\n")[0])}
            raise AssertionError("unexpected prompt")

    brief = check_brief({"minutes": 10, "acts": [{"title": "One"}]}, "education")
    plan = VideoMaker(Settings(), FakeLLM(), log=lambda m: None).script("CLT", [], [], "education", brief)
    parts = [p for p in asked if "Now write ONLY part" in p]
    assert "Write 12 to 16 shots" in parts[0] and "piece 1 of 3" in parts[0]   # 35 shots: three requests
    assert any("far too short: 4 shots" in p for p in parts) and len(plan["scenes"]) >= 64


def test_a_long_video_is_always_written_part_by_part_even_without_a_usable_outline():
    from blogwriter.config import Settings
    from blogwriter.video import VideoMaker, check_brief, outline_parts
    assert outline_parts({"acts": [{"name": "A", "beats": "graph: a bell; check: which way?"}]}) == \
        [{"title": "A", "beats": ["graph: a bell", "check: which way?"]}]
    assert outline_parts({"parts": [{"title": "B", "shots": [{"beat": "diagram: dots"}, ""]}]})[0]["beats"] == ["diagram: dots"]
    assert outline_parts({"title": "no parts at all"}) == [] and outline_parts("text") == []
    asked, logs = [], []

    class FakeLLM:
        def complete_json(self, prompt, **kw):
            asked.append(prompt)
            if "THIS IS A LONG VIDEO" in prompt:
                return {"title": "CLT", "scenes": [{"narration": "an outline that is really a script"}]}   # no parts
            if "Now write ONLY part" in prompt:
                return {"scenes": [{"kind": "diagram", "narration": " ".join(["word"] * 24)} for _ in range(30)]}
            if prompt.startswith(("These are the shots of a video", "You are the comedy writer", "These are the narration")):
                return {"short": []} if "shots of a video" in prompt else \
                    {"lines": json.loads(prompt.split("Lines (JSON): ", 1)[1].split("\n")[0])}
            raise AssertionError("one request for a long video must never happen")

    brief = check_brief({"minutes": 10, "acts": [{"title": "Setup", "job": "the jar of sweets"},
                                                {"title": "Twist", "job": "averages make a bell"}]}, "education")
    plan = VideoMaker(Settings(), FakeLLM(), log=logs.append).script("CLT", [], [], "education", brief)
    assert sum("THIS IS A LONG VIDEO" in p for p in asked) == 2                     # asked once more
    assert any("from the plan's acts" in m for m in logs) and len(plan["scenes"]) >= 60


def test_llm_skips_a_provider_a_request_is_too_big_for(monkeypatch):
    import blogwriter.llm as L
    calls = []

    def too_big(name):
        def call(system, prompt, max_tokens, temperature):
            calls.append(name)
            raise L._TooBig("HTTP 413 request too large")
        return call
    c, slept = _clocked_llm(monkeypatch, [("groq#1", too_big("groq#1")), ("groq#2", too_big("groq#2")),
                                          ("gemini#1", lambda *a: calls.append("gemini#1") or "the answer")])
    assert c.complete("a very long prompt") == "the answer"
    assert calls[0].startswith("groq#") and calls[1:] == ["gemini#1"] and slept == []   # one Groq key, then on
    assert c.complete("short") == "the answer" and calls[2].startswith("groq#")       # small requests still go to Groq
    assert L._over_limit("Limit 8000, Used 0, Requested 9200") is False                # needs the full phrase
    assert L._over_limit("on tokens per minute (TPM): Limit 8000, Used 10, Requested 9200") is True
    assert L._over_limit("on tokens per minute (TPM): Limit 8000, Used 7900, Requested 900") is False


def test_vision_models_rest_when_busy_and_replies_are_read_leniently(monkeypatch):
    from blogwriter import footage as F
    from blogwriter.config import Settings
    monkeypatch.setattr(F, "_down", {})
    monkeypatch.setenv("DIAGRAM_MODELS", "busy-model,good-model")
    calls, logs = [], []

    def fake_post(url, key, body, timeout=90):
        calls.append((body["model"], key))
        if body["model"] == "busy-model":
            return [{"error": {"code": 503, "message": "This model is currently experiencing high demand."}}]
        if key == "k1":
            return {"error": '429 {"error": {"code": 429, "details": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel"}]}}'}
        if body["model"].startswith("qwen"):
            return {"error": "500 nope"}
        return {"choices": [{"message": {"content": '```json\n{"score": 8, "problem": "a\nb"}\n```'}}]}
    monkeypatch.setattr(F, "post_json", fake_post)
    s = Settings(gemini_keys=["k1", "k2"], groq_keys=["g1"])
    assert F.gemini_json(s, "judge", [b"img"]) == {"score": 8, "problem": "a\nb"}
    assert calls == [("busy-model", "k1"), ("good-model", "k1"), ("good-model", "k2")]
    calls.clear()
    assert F.gemini_json(s, "judge", [b"img"])["score"] == 8
    assert calls == [("good-model", "k2")]                     # the busy model and the spent key are resting
    monkeypatch.setattr(F, "post_json", lambda *a, **k: {"error": "timeout"})
    assert F.gemini_json(s, "judge", log=logs.append) is None and "no model answered" in logs[0]


def test_a_diagram_no_vision_model_could_review_is_kept_and_one_that_cannot_draw_is_dropped(monkeypatch, tmp_path):
    from blogwriter import video
    from blogwriter.config import Settings
    els = [{"type": "dot", "x": 20, "y": 50, "r": 2, "color": "accent", "on": "", "anim": ""},
           {"type": "dot", "x": 50, "y": 50, "r": 2, "color": "accent", "on": "", "anim": ""},
           {"type": "dot", "x": 80, "y": 50, "r": 2, "color": "accent", "on": "", "anim": ""}]
    scenes = [{"kind": "diagram", "headline": f"h{k}", "narration": "n", "diagram": {"elements": [dict(e) for e in els]}}
              for k in range(2)]
    long = [{**s, "frames": 120, "diagram": video.diagram.timed(s["diagram"], [], 120, 30, 6)} for s in scenes]
    look = tmp_path / "look.jpg"
    look.write_bytes(b"jpeg")
    logs = []
    maker = video.VideoMaker(Settings(), None, log=logs.append)
    monkeypatch.setattr(maker, "stills", lambda shots, job: {0: str(look)})        # shot 1 never draws
    monkeypatch.setattr(video, "gemini_json", lambda *a, **k: None)               # no vision model answers
    maker.polish_diagrams(scenes, long, {}, {}, str(tmp_path))
    assert scenes[0].get("diagram") and long[0]["diagram"] and not scenes[1].get("diagram") and long[1]["diagram"] is None
    assert any("kept unreviewed" in m and "0" in m for m in logs) and any("preview did not render" in m for m in logs)


def test_the_reviewer_sees_three_moments_and_fair_or_corrected_diagrams_stay(monkeypatch, tmp_path):
    from blogwriter import video
    from blogwriter.config import Settings
    els = [{"type": "dot", "x": x, "y": 50, "r": 2, "color": "accent", "on": "", "anim": ""} for x in (20, 50, 80)]
    scenes = [{"kind": "diagram", "headline": f"h{k}", "narration": "n", "diagram": {"elements": [dict(e) for e in els]}}
              for k in range(3)]
    long = [{**s, "frames": 120, "diagram": video.diagram.timed(s["diagram"], [], 120, 30, 6)} for s in scenes]
    look = tmp_path / "look.jpg"
    look.write_bytes(b"jpeg")
    frames_asked, images_seen, logs = [], [], []
    maker = video.VideoMaker(Settings(), None, log=logs.append)

    def stills(shots, job):
        frames_asked.extend((k, f) for k, _, f in shots)
        return {k: str(look) for k, _, _ in shots}
    calls = {0: 0, 1: 0, 2: 0}
    better = [{"type": "dot", "x": x, "y": 40, "r": 3, "color": "hot"} for x in (15, 50, 85)]

    def judge(settings, ask, images, **kw):
        i = int(ask.split('Headline (drawn above the canvas): "h')[1][0])
        images_seen.append(len(images))
        calls[i] += 1
        if i == 0:
            return {"score": 5, "problem": "fair", "elements": []}       # fair: stays as it is
        if i == 1:                                                       # weak, corrected, then nobody answers
            return {"score": 4, "problem": "weak", "elements": better} if calls[i] == 1 else None
        return {"score": 3, "problem": "names, does not show", "elements": []}
    monkeypatch.setattr(maker, "stills", stills)
    monkeypatch.setattr(video, "gemini_json", judge)
    maker.polish_diagrams(scenes, long, {}, {}, str(tmp_path))
    assert ("0a", 42) in frames_asked and ("0b", 78) in frames_asked and (0, 100) in frames_asked
    assert set(images_seen) == {3}
    assert scenes[0]["diagram"]["elements"][0]["x"] == 20                # kept at 5/10
    assert scenes[1]["diagram"]["elements"][0]["x"] == 15                # its correction stands
    assert not scenes[2].get("diagram") and long[2]["diagram"] is None   # 3/10 is dropped
    assert any("kept 2 of 3" in m and "1:5*" in m for m in logs)


def test_no_empty_boxes_words_in_formulas_keep_spaces_and_the_level_reaches_the_writer():
    from blogwriter import diagram, video
    scene = {"headline": "The sum", "narration": "Add them all up and divide by the count."}
    raw = {"elements": [{"type": "box", "x": 10, "y": 30, "w": 30, "h": 30},                     # empty: dropped
                        {"type": "curve", "id": "c", "points": [[50, 80], [60, 40], [70, 80]]},
                        {"type": "dot", "x": 50, "y": 80, "move": {"on": "divide", "along": "c", "x": 70, "y": 80}},
                        {"type": "box", "x": 75, "y": 10, "w": 20, "h": 30},                     # holds the label
                        {"type": "label", "x": 85, "y": 25, "text": "the count", "size": "s"}]}
    why = []
    d = diagram.check(raw, scene, video._verified, video.tex_complete, why)
    assert [e["type"] for e in d["elements"]] == ["curve", "dot", "box", "label"]
    assert d["elements"][1]["move"]["along"] == 0 and any("empty box" in w for w in why)
    assert video.words_tex("Normal density") == r"\text{Normal density}"
    assert video.words_tex(r"\bar{X}_n \to N(0,1)") == r"\bar{X}_n \to N(0,1)"
    assert video.words_tex("mean of n draws = 5") == r"\text{mean of n draws} = 5"
    brief = video.check_brief({"minutes": 10, "maths": True, "acts": [{"title": "A"}]}, "education")
    basic, _ = video.shape_prompt({**brief, "level": "basic"}, "education", "CLT", "(none)")
    advanced, _ = video.shape_prompt({**brief, "level": "advanced"}, "education", "CLT", "(none)")
    assert "complete beginners" in basic and "complete beginners" not in advanced and "full picture" in advanced
    assert "never symbol by symbol" in basic


def test_the_comedy_pass_lands_jokes_but_never_changes_numbers_or_repeats_a_joke():
    from blogwriter.config import Settings
    from blogwriter.video import VideoMaker
    lines = ["Thirty orders make one average.", "The bell gets narrower.", "Pizza takes 30 minutes.",
             "The spread shrinks.", "That is the theorem."]

    class FakeLLM:
        def complete_json(self, prompt, **kw):
            assert "deadpan" in prompt and "pizza" in prompt
            return {"lines": ["Thirty orders make one average. Democracy, but for numbers.",     # a joke: kept
                              "The bell gets narrower. Democracy, but for numbers.",            # the same joke: no
                              "Pizza takes 45 minutes. Allegedly.",                             # a changed number: no
                              "The spread shrinks. " + "very " * 60,                            # far too long: no
                              "That is the theorem... no applause needed."]}                    # kept
    plan = {"scenes": [{"narration": l} for l in lines]}
    logs = []
    VideoMaker(Settings(), FakeLLM(), log=logs.append).punch_up(plan, {"examples": "pizza delivery"})
    got = [s["narration"] for s in plan["scenes"]]
    assert got == ["Thirty orders make one average. Democracy, but for numbers.", "The bell gets narrower.",
                   "Pizza takes 30 minutes.", "The spread shrinks.", "That is the theorem... no applause needed."]
    assert "2 of 5 lines punched up" in logs[-1]


def test_numbers_said_in_words_count_and_a_formula_inside_a_box_is_its_content():
    from blogwriter import diagram
    from blogwriter.video import _verified, check_brief, spelled_numbers, tex_complete
    assert spelled_numbers("forty orders, six hundred and fifty more, twenty-five times") == ["40", "650", "25"]
    assert _verified("averages of 40 samples", "average forty samples") and not _verified("41 samples", "forty samples")
    scene = {"headline": "The sum", "narration": "Add them all up and divide by the count."}
    boxed = {"elements": [{"type": "box", "x": 10, "y": 30, "w": 40, "h": 40},
                          {"type": "tex", "x": 30, "y": 50, "tex": r"\frac{1}{n}\sum x_i", "size": "m"},
                          {"type": "arrow", "x1": 52, "y1": 50, "x2": 80, "y2": 50}]}
    assert diagram.check(boxed, scene, _verified, tex_complete) is not None
    half_out = {"elements": [boxed["elements"][0], {**boxed["elements"][1], "x": 49}, boxed["elements"][2]]}
    assert diagram.check(half_out, scene, _verified, tex_complete) is None
    assert "sarcastic" in check_brief({"narrator": "A patient teacher."}, "education")["narrator"]
    assert check_brief({"narrator": "A deadpan guide."}, "education")["narrator"] == "A deadpan guide."
    assert "sarcastic" not in check_brief({"narrator": "A calm anchor."}, "news")["narrator"]


def test_the_video_is_encoded_once_with_the_best_codec_and_never_lost(monkeypatch, tmp_path):
    from blogwriter import video
    monkeypatch.setattr(video, "ffmpeg_exe", lambda: "ffmpeg")
    monkeypatch.delenv("VIDEO_CODEC", raising=False)
    for listing, best in (("libsvtav1 libx265 libx264", "av1"), ("libx265 libx264", "hevc"), ("libx264", "h264"), ("", "h264")):
        monkeypatch.setattr(video, "footage_encoders", lambda exe, l=listing: l)
        assert video.final_codec() == best
    monkeypatch.setattr(video, "footage_encoders", lambda exe: "libsvtav1 libx265 libx264")
    monkeypatch.setenv("VIDEO_CODEC", "hevc")
    assert video.final_codec() == "hevc"
    monkeypatch.setenv("VIDEO_CODEC", "av1")
    calls, logs = [], []
    dest = tmp_path / "long.mp4"

    def fake_ffmpeg(args, timeout=0):
        calls.append(args)
        if "libsvtav1" in args:
            raise RuntimeError("encoder crashed")
        dest.write_bytes(b"x" * 2_000_000)
    monkeypatch.setattr(video, "ffmpeg", fake_ffmpeg)
    assert video.final_encode("parts.txt", "s.mp3", str(dest), 3840 * 2160, logs.append, concat=True) == "h264"
    first, second = calls
    assert first[:6] == ["-f", "concat", "-safe", "0", "-i", "parts.txt"] and "yuv420p10le" in first
    assert first[first.index("-preset") + 1] == "8"                       # 4K: the faster AV1 preset
    assert second[second.index("-c:v") + 1] == "copy"                     # the rendered pictures are kept
    assert any("AV1 encode failed" in m for m in logs) and "H264, 2 MB" in logs[-1]


def test_the_resolution_is_4k_by_default_and_8k_on_request(monkeypatch):
    import importlib
    from blogwriter import video
    try:
        for value, height, scale, chunk in ((None, 2160, "2.0", 1200), ("8k", 4320, "4.0", 300), ("1440", 1440, None, 2700),
                                            ("huh", 2160, "2.0", 1200)):
            if value is None:
                monkeypatch.delenv("VIDEO_RESOLUTION", raising=False)
            else:
                monkeypatch.setenv("VIDEO_RESOLUTION", value)
            importlib.reload(video)
            assert video.RESOLUTION == height and video.CHUNK_FRAMES == chunk
            assert scale is None or video.LONG_SCALE == scale
    finally:
        monkeypatch.delenv("VIDEO_RESOLUTION", raising=False)
        importlib.reload(video)


def test_a_quiz_answer_lights_up_when_the_voice_says_it_not_before():
    from blogwriter.video import FPS, LEAD, answer_moment, check_cues
    scene = {"kind": "check", "options": ["It grows larger", "It shrinks", "It stays the same"], "answer": 1}
    words = [(0.0, 0.3, "Sound"), (0.3, 0.6, "familiar?"), (0.7, 0.9, "What"), (0.9, 1.1, "happens"), (1.1, 1.3, "to"),
             (1.3, 1.5, "the"), (1.5, 1.9, "spread?"), (2.0, 2.3, "Well,"), (2.3, 2.5, "here's"), (2.5, 2.7, "the"),
             (2.7, 3.0, "twist:"), (3.0, 3.2, "it"), (3.2, 3.7, "shrinks.")]
    assert answer_moment(words, 2.0, scene) == 3.2                     # on "shrinks", not on "Well,"
    assert answer_moment(words, 2.0, {**scene, "answer": 9}) == 2.0     # no valid answer: where the answer starts
    line = "Sound familiar? What happens to the spread? Well, here's the twist: it shrinks."
    cues = check_cues(line, words, scene, 300)
    assert cues["think"] == LEAD + round(1.9 * FPS)                    # after the LAST question mark
    assert cues["reveal"] == LEAD + round(3.2 * FPS)
    assert check_cues("No question here.", words, scene, 300) == {"think": 120, "reveal": 180}


def test_captions_keep_the_script_words_timed_by_the_cloned_voice(monkeypatch, tmp_path):
    from blogwriter import video
    from blogwriter.config import Settings
    heard = [[0.0, 0.4, "Averages"], [0.4, 0.6, "of"], [0.6, 1.0, "thirty"], [1.0, 1.5, "orders"], [1.5, 2.0, "pile"],
             [2.0, 2.2, "up."]]
    got = video.align_words("Averages of 30 orders pile up.", heard)
    assert [w for _, _, w in got] == ["Averages", "of", "30", "orders", "pile", "up."]
    assert got[2] == (0.6, 1.0, "30") and got[3][0] == 1.0             # "30" was heard as "thirty": it takes the gap
    monkeypatch.setattr(video, "speak_all", lambda jobs: [[(0.0, 1.0, "x")] for _ in jobs])
    logs = []
    monkeypatch.delenv("VOICE_PYTHON", raising=False)
    out = video.speak_cloned([("Hi there.", "v", str(tmp_path / "a.mp3"))], Settings(), str(tmp_path), logs.append)
    assert out == [[(0.0, 1.0, "x")]] and any("not installed" in m for m in logs)   # no clone: the standard voice
    monkeypatch.setenv("NARRATOR_VOICE", "standard")
    logs.clear()
    assert video.speak_cloned([("Hi.", "v", str(tmp_path / "b.mp3"))], Settings(), str(tmp_path), logs.append) and not logs


def test_a_cloned_take_that_garbles_its_script_is_caught():
    import importlib.util
    import os
    spec = importlib.util.spec_from_file_location("clone_voice", os.path.join("blogwriter", "clone_voice.py"))
    cv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cv)                       # no models are loaded: only the checking helpers are used
    script = "Ever notice how your pizza app promises thirty minutes, and somehow it is always forty?"
    assert cv.match(script, "Ever notice how your pizza app promises 30 minutes and somehow it is always 40?") == 1.0
    assert cv.match(script, "Ever notice how your PISA app promises 30 minutes and somehow it is always 4D.") < 0.92
    assert cv.tokens("forty two and a hundred") == ["42", "and", "a", "hundred"]
    assert cv.sentences("One. Two? Three!") == ["One.", "Two?", "Three!"]


def test_cloning_that_would_take_too_long_is_stopped_and_the_standard_voice_speaks(monkeypatch, tmp_path):
    import sys
    from blogwriter import video
    tool = tmp_path / "slow_tool.py"
    tool.write_text("import time, sys\nprint('[clone] models ready in 1s', flush=True)\n"
                    "for k in range(1, 11):\n    time.sleep(0.05)\n    print(f'[clone] {k}/10 ok', flush=True)\n",
                    encoding="utf-8")
    monkeypatch.setattr(video, "CLONE_TOOL", str(tool))
    logs = []
    monkeypatch.setenv("CLONE_BUDGET_MINUTES", "0.001")             # far less than the projected time
    assert video.clone_with_budget(sys.executable, "spec", "ref", ["a line of narration"] * 10, logs.append) is True
    assert any("standard voice speaks this video" in m for m in logs)
    monkeypatch.setenv("CLONE_BUDGET_MINUTES", "60")
    logs.clear()
    assert video.clone_with_budget(sys.executable, "spec", "ref", ["a line"] * 10, logs.append) is False
    assert any("models ready" in m for m in logs) and not any("standard voice" in m for m in logs)


def test_the_document_is_sold_for_99_rupees_and_never_mispriced(monkeypatch):
    from blogwriter import gumroad as G
    from blogwriter.config import Settings
    calls = []

    class R:
        def __init__(self, data, status=200):
            self.data, self.status_code, self.text = data, status, json.dumps(data)

        def json(self):
            return self.data

        def raise_for_status(self):
            pass

    def post(url, timeout=0, data=None, json=None):
        calls.append(("POST", url, data))
        return R({"success": True, "product": {"id": "p1", "short_url": "https://g.co/l/x", "currency": currency[0]}})

    def put(url, timeout=0, data=None, json=None):
        calls.append(("PUT", url, data or json))
        return R({"success": True})
    monkeypatch.setattr(G.requests, "post", post)
    monkeypatch.setattr(G.requests, "put", put)
    monkeypatch.setattr(G, "_upload", lambda token, path: "https://files/x.pdf")
    monkeypatch.setattr(G, "convert", lambda amount, frm, to: 1.12)
    s = Settings(gumroad_token="t", gumroad_publish=True)
    currency = ["inr"]
    assert G.list_product(s, "CLT notes", "d", "x.pdf", log=lambda m: None)["url"] == "https://g.co/l/x"
    created = calls[0][2]
    assert created["price"] == 9900 and created["price_currency_type"] == "inr"
    assert not any(c[0] == "PUT" and isinstance(c[2], dict) and "price" in c[2] for c in calls)     # already right
    calls.clear()
    currency[0] = "usd"                                  # the account sells in dollars: converted, never $99
    logs = []
    G.list_product(s, "CLT notes", "d", "x.pdf", log=logs.append)
    fixed = [c[2] for c in calls if c[0] == "PUT" and isinstance(c[2], dict) and "price" in c[2]]
    assert fixed == [{"access_token": "t", "price": 112}] and any("sells in USD" in m for m in logs)


def test_a_video_run_sells_its_document_but_sends_only_the_video_email(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from blogwriter import pipeline as P
    from blogwriter import video
    from blogwriter.config import Settings
    seen = []
    p = P.BlogPipeline.__new__(P.BlogPipeline)
    p.writer, p.log = SimpleNamespace(reader=""), lambda m: None
    monkeypatch.setattr(P.BlogPipeline, "_run", lambda self, *a, **k: seen.append((a, k)) or {"dir": "x"})
    import blogwriter.video as V
    monkeypatch.setattr(V.VideoMaker, "__init__", lambda self, *a: None)
    monkeypatch.setattr(V.VideoMaker, "make", lambda self, d, **k: {})
    for token, publish, video_on, sells, report, mails in (("t", False, True, True, True, False),   # the default
                                                           ("", False, True, False, False, False),  # no Gumroad key
                                                           ("t", True, True, True, True, False),    # also posts
                                                           ("t", True, False, True, True, True)):   # report-only run
        p.s = Settings(gumroad_token=token)
        seen.clear()
        P.BlogPipeline.run(p, "CLT", source="topic", publish=publish, video=video_on)
        a, k = seen[0]
        assert (k["sell"], k["report"], k["report_email"], a[8]) == (sells, report, mails, publish)
    guide = tmp_path / "posting_guide.txt"
    guide.write_text("POSTING GUIDE\n===== ENGLISH =====\nTitle: The CLT\nDescription:\nAverages behave.\n\n"
                     "Full study notes (PDF): https://g.co/l/x\nSources: 3 sources.\n- https://a\n"
                     "Photo and footage credits (required by the licences):\n- none\n", encoding="utf-8")
    block = video.youtube_block(str(guide))
    assert block.startswith("Title: The CLT") and "https://g.co/l/x" in block and "Photo and footage" not in block
    assert video.youtube_block(str(tmp_path / "missing.txt")) == ""


def test_a_film_look_from_the_library_is_chosen_for_the_subject(monkeypatch):
    from blogwriter import design, looks
    logs = []
    pick = looks.choose(lambda *a, **k: {"look": "Chalkboard", "accent": "pink chalk", "why": "a lesson"},
                        "Central Limit Theorem", "education", "playful", logs.append)
    assert pick == ("chalkboard", "#f48fb1") and "Chalkboard" in logs[-1]
    assert looks.choose(lambda *a, **k: {"look": "free"}, "t", "news", "") is None
    assert looks.choose(lambda *a, **k: {"look": "volcano"}, "t", "news", "", logs.append) is None
    t = looks.theme_for("chalkboard", "#f48fb1", design._finish, design.check_fx, "seed")
    assert t["look"] == {"slug": "chalkboard", "surface": "slate", "stroke": "chalk", "overlay": "", "misregister": "",
                         "mono": False}
    assert t["accent"] == "#f48fb1" and t["display"] == "Kalam" and t["hand"] == "Kalam" and t["light"] is False
    assert t["fx"]["text"]["enter"] == "write" and {c["shape"] for c in t["fx"]["transitions"]} == {"fade", "split"}
    news = looks.theme_for("newsreel", "#efe7d6", design._finish, design.check_fx, "s")
    assert news["look"]["mono"] and news["upper"]
    monkeypatch.setenv("FILM_LOOK", "blueprint")
    d = design.design(lambda *a, **k: {}, "How a jet engine works", "education", "", logs.append)
    assert d["look"]["surface"] == "blueprint" and d["source"] == "look:blueprint"
    monkeypatch.setenv("FILM_LOOK", "free")
    d = design.design(lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")), "t", "news", "", logs.append)
    assert "look" not in d                                           # a design of its own
    assert "Kalam" not in design.OPEN_FONTS and "Inter" in design.OPEN_FONTS   # free designs never pick a look's hand
    for key, L in looks.LOOKS.items():                               # every look uses fonts the renderer loads
        assert all(f in design.FONTS for f in (L["display"], L["body"], L["hand"])), key
        assert design.contrast(L["palette"]["text"], L["palette"]["bg"]) >= 7, key


def test_a_long_render_is_split_evenly_into_parts_for_parallel_machines():
    from blogwriter.video import CHUNK_FRAMES, part_args, render_parts
    parts = render_parts(18000)
    assert parts[0][0] == 0 and parts[-1][1] == 17999 and len(parts) == -(-18000 // CHUNK_FRAMES)
    assert all(b + 1 == c for (_, b), (c, _) in zip(parts, parts[1:]))          # no gap, no overlap
    assert render_parts(100) == [(0, 99)]
    assert "--frames=0-99" in part_args(0, 99, "parts/part00.mp4") and "--props=public/job/long.json" in part_args(0, 1, "x")


def test_a_course_is_planned_sized_and_handed_out_in_waves(tmp_path, monkeypatch):
    import pytest
    from blogwriter import course as c
    monkeypatch.setattr(c, "COURSES", str(tmp_path))
    raw = {"course": "Machine Learning from Zero", "description": "You will build models.",
           "modules": [{"title": "Foundations", "lessons": [
               {"title": "What is a model", "goal": "Say what a model is.", "key_ideas": ["inputs", "outputs"],
                "visuals": ["a box"], "maths": False, "minutes": 9},
               {"title": "What is a model", "goal": "duplicate"},
               {"title": "Linear regression", "key_ideas": ["line", "error"], "maths": True, "minutes": 40}]},
               {"title": "Optimisation", "lessons": [{"title": "Gradient descent", "maths": True}]}]}
    course = c.plan("Machine Learning", "basic", "", lambda *a, **k: raw)
    assert [x["id"] for x in course["lessons"]] == ["L01", "L02", "L03"] and course["lessons"][1]["minutes"] == 12
    c.save(course)
    ctx = c.context(c.load("machine-learning"), "L02")
    assert ctx["number"] == 2 and ctx["total"] == 3 and ctx["previous"][0]["title"] == "What is a model"
    assert ctx["next"] == "Gradient descent"
    wave = c.take_next(course, 2)
    assert [j["id"] for j in wave] == ["L01", "L02"] and wave[0]["topic"] == "What is a model (Machine Learning from Zero)"
    c.mark(course, "L01", True)
    c.mark(course, "L02", False)
    assert c.remaining(course) == 2                                   # L02 is tried again, L03 is still to come
    assert [j["id"] for j in c.take_next(course, 5)] == ["L02", "L03"]
    assert c.budget(30, 4, 0)["per_day"] >= 1 and c.budget(30, 4, 3)["days"] == 10
    assert "Machine Learning from Zero" in c.summary(course)
    with pytest.raises(ValueError):
        c.plan("X", "basic", "", lambda *a, **k: {"modules": []})
