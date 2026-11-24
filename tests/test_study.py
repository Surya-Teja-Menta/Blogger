"""Research beyond the encyclopedia (web.pdf_text, wiki_study, arxiv; research._study_pass)."""
import io

from blogwriter import research, web


class Resp:
    def __init__(self, content=b"", text="", status=200, js=None):
        self.content, self.text, self.status_code, self._js = content, text, status, js

    def json(self):
        return self._js


def make_pdf(pages):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    w = PdfWriter()
    for body in pages:
        page = w.add_blank_page(width=300, height=300)
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 9 Tf 10 280 Td ({body}) Tj ET".encode())
        page[NameObject("/Contents")] = w._add_object(stream)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                                 NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): w._add_object(font)})})
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def test_a_pdf_gives_the_pages_that_talk_about_the_topic(monkeypatch):
    on = "engine piston cylinder combustion exhaust ignition " * 12
    off = "preface thanks acknowledgements copyright publisher dedication " * 12
    monkeypatch.setattr(web, "get", lambda *a, **k: Resp(content=make_pdf([off, on, off])))
    text = web.pdf_text("http://x/book.pdf", {"engine", "piston", "cylinder", "combustion"}, 3000)
    assert "piston" in text and "dedication" not in text.split("piston")[0][:5] or "piston" in text
    monkeypatch.setattr(web, "get", lambda *a, **k: Resp(content=b"<html>not a pdf</html>"))
    assert web.pdf_text("http://x/y.pdf", {"engine"}) == ""
    monkeypatch.setattr(web, "get", lambda *a, **k: (_ for _ in ()).throw(OSError("down")))
    assert web.pdf_text("http://x/y.pdf", {"engine"}) == "" and web.wiki_study("en.wikibooks.org", "x") == [] and web.arxiv("x") == []


def test_the_study_pass_collects_textbooks_pdfs_and_papers_and_skips_off_topic_ones(monkeypatch):
    from datetime import datetime, timezone
    from collections import Counter
    from blogwriter.news import Article
    monkeypatch.setattr(research, "time", type("T", (), {"sleep": staticmethod(lambda s: None)}))
    on = "An internal combustion engine burns fuel in a cylinder and the piston turns the crankshaft; exhaust leaves through a catalyst. " * 6
    monkeypatch.setattr(research, "wiki_study", lambda host, q, n=2: [("Engine lesson", f"https://{host}/wiki/E", on)])
    monkeypatch.setattr(research, "web_search", lambda q, n=5, timelimit=None: [
        web.Source("Engine notes (PDF)", "http://uni.edu/engine.pdf", "internal combustion engine piston cylinder notes"),
        web.Source("Cat photos", "http://cats.example/x", "cute cats everywhere")])
    monkeypatch.setattr(research, "pdf_text", lambda url, keep, limit=4500: on)
    monkeypatch.setattr(research, "fetch_text", lambda url, limit=4500: "")
    monkeypatch.setattr(research, "arxiv", lambda q, n=3: [("Engine paper", "http://arxiv.org/abs/1", on)])
    r = research.Researcher(type("L", (), {"complete_json": lambda *a, **k: {}})(), lambda m: None)
    art = Article("Internal combustion engine", "", "topic:x", datetime.now(timezone.utc), "x", "topic")
    r.dossier = research.Dossier(article=art.to_dict(), article_text="")
    r.dossier.sources.append({"id": 1, "title": "x", "url": "topic:x", "text": ""})
    r.by_url, r.reasons = {"topic:x": 1}, Counter()
    got = {}
    r._extract_into = lambda article, name, desc, evidence, limit, chars, queries=(), n=0: got.update(name=name, urls=[e["url"] for e in evidence])
    r._study_pass(art, research.story_vocab(art, on), frozenset())
    assert got["name"] == "Study materials"
    assert "http://uni.edu/engine.pdf" in got["urls"] and "http://arxiv.org/abs/1" in got["urls"]
    assert any("wikibooks" in u for u in got["urls"]) and not any("cats" in u for u in got["urls"])
