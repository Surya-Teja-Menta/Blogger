"""The workflow, in five steps:
  1. collect the top 20 latest news items / research papers on the topic
  2. rank them by how hot they are (audience appeal and likely reaction) and choose the best
  3. research the chosen story several ways (article, other outlets, RSS pool, encyclopedia, archives, web search)
  4. write a documentary report, then derive the blog and the article from it
  5. store online, list the report on Gumroad, and email all three over SMTP"""
import json
import os
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime
from typing import Callable, Optional

from .config import MODES, Settings
from .gumroad import list_product
from .history import History
from .llm import LLMClient, LLMError
from .mailer import send_email
from .news import NewsCollector
from .publish import post_all
from .rank import audience_rank
from .render import pdf_pages, to_html, to_pdf
from .research import Researcher, domain
from .storage import upload_run
from .writer import Writer, words


class PipelineError(RuntimeError):
    pass


def slugify(text: str, limit: int = 40) -> str:
    return re.sub(r"[^\w]+", "_", text).strip("_")[:limit] or "topic"


def scaled_mode(mode, dossier):
    """Size the blog and article to the evidence. Asking for 600 words on two facts forces padding, which the
    fact-check then (rightly) deletes. (Documentary chapters size themselves from their own facts.)"""
    n = len(dossier.facts)
    evidence_words = 45 * n + len(dossier.article_text.split()) // 5     # prose the verified material can support
    return replace(mode, article_words=max(250, min(mode.article_words, evidence_words)),
                   blog_words=max(150, min(mode.blog_words, evidence_words // 2)))


def key_findings_md(dossier) -> str:
    rows = []
    for i, f in enumerate(dossier.key_facts(8), 1):
        src = dossier.sources[f["source"] - 1]
        tag = f" *(confirmed by {f['corroboration'] + 1} independent sources)*" if f["corroboration"] else ""
        rows.append(f"{i}. {f['claim']} — [{domain(src['url'])}]({src['url']}){tag}")
    return "\n".join(rows) or "_No facts could be independently verified for this story._"


def quality_md(dossier, mode: str, skipped=()) -> str:
    cited = {f["source"] for f in dossier.facts}
    corroborated = sum(1 for f in dossier.facts if f["corroboration"])
    empty = [n for n, a in dossier.angles.items() if not a["facts"]]
    lines = [f"- **Method:** the original article, other outlets and RSS feeds, encyclopedia background, archive "
             f"coverage and {len(dossier.angles) - 1} further research angles ({mode} mode); "
             f"{len(dossier.sources)} sources found, {len(cited)} cited.",
             f"- **Verified facts:** {len(dossier.facts)}. Each one is backed by a quote that was checked against the "
             f"text of its source page; {dossier.rejected} extracted claims failed that check and were discarded.",
             f"- **Independent confirmation:** {corroborated} of {len(dossier.facts)} facts appear on a second, "
             "unrelated website."]
    if skipped:
        lines.append(f"- **Not covered:** nothing verifiable was found for the sections {', '.join(skipped)}. "
                     "Treat those areas as unknown.")
    if empty:
        lines.append(f"- **Research gaps:** nothing verifiable was found for the angles: {', '.join(empty)}.")
    lines.append("- Figures and dates that could not be traced to a source were removed from the text.")
    return "\n".join(lines)


def sources_md(dossier) -> str:
    uses = {}
    for f in dossier.facts:
        uses[f["source"]] = uses.get(f["source"], 0) + 1
    rows = []
    for s in dossier.sources:
        n = uses.get(s["id"], 0)
        rows.append(f"{s['id']}. [{s['title'] or s['url']}]({s['url']})" + (f" — {n} fact(s) used" if n else ""))
    return "\n".join(rows)


def acknowledgements_md(article, dossier) -> str:
    """Thanks to the publishers whose reporting the verified facts came from (mechanical: no model, no invention)."""
    used = Counter(domain(dossier.sources[f["source"] - 1]["url"]) for f in dossier.facts)
    outlets = [d for d, _ in used.most_common(12)]
    thanks = (f"Its facts were verified against the published pages of {len(used)} sources, with particular thanks to "
              f"{', '.join(outlets[:-1])} and {outlets[-1]}." if len(outlets) > 1 else
              f"Its facts were verified against the published pages of {outlets[0]}." if outlets else "")
    return (f"This report stands on the work of reporters, editors and researchers who published before it. The story "
            f"it follows was first reported by **{article.source}**. {thanks}\n\n"
            "There is no original reporting here. Every statement traces to a passage quoted from a cited source, and "
            "the full list of passages is printed in the evidence register at the end. Any fault in how those facts "
            "are arranged belongs to this report, not to the outlets that gathered them.")


_INDEX_SKIP = {"The", "This", "That", "These", "Those", "There", "Here", "When", "Where", "While", "After", "Before",
               "Since", "Because", "However", "Meanwhile", "Although", "Despite", "According", "What", "Who", "Why",
               "How", "Which", "His", "Her", "Their", "Its", "Our", "And", "But", "For", "With", "From", "Some", "Many",
               "Several", "Both", "Each", "Another", "Such", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
               "Saturday", "Sunday", "January", "February", "March", "April", "June", "July", "August", "September",
               "October", "November", "December",
               # titles that precede a name ("Foreign Minister Abbas Araghchi" and "Abbas Araghchi" are one entry)
               "Foreign", "Defense", "Defence", "Finance", "Minister", "President", "Prime", "Secretary", "General",
               "Senator", "Chancellor", "King", "Queen", "Prince", "Supreme", "Leader", "Chairman", "Chair", "CEO",
               "Dr", "Mr", "Mrs", "Ms", "Gen", "Sen", "Rep", "Gov", "Judge", "Justice"}
_PROPER = re.compile(r"(?<=[a-z,;:)] )((?:[A-Z][\w.'’-]+)(?: (?:of |the |and |de |al-)?[A-Z][\w.'’-]+){0,3})")


def index_md(chapters: list) -> str:
    """Alphabetical index of the people, places and organisations named in the report, with the chapters that
    mention them. Chapter numbers match the Contents (PDF page numbers are not available when printing from HTML)."""
    prose = [" ".join(ln for ln in c.splitlines() if not ln.lstrip().startswith(("#", ">", "|"))) for c in chapters]
    names = Counter()
    for text in prose:
        for m in _PROPER.findall(text):
            parts = m.split(" ")
            while parts and parts[0] in _INDEX_SKIP:
                parts = parts[1:]
            term = " ".join(parts).strip(".,;:'’")
            if len(term) >= 4:
                names[term] += 1
    rows = []
    for term in sorted((t for t, n in names.items() if n >= 2), key=str.lower):
        where = [str(i) for i, text in enumerate(prose, 1) if term in text]
        if where:
            rows.append(f"- **{term}** — chapter{'s' if len(where) > 1 else ''} {', '.join(where)}")
    return "\n".join(rows[:120]) or "_No names recurred often enough to index._"


def evidence_md(dossier) -> str:
    """Every verified fact with the passage that proves it and where it came from."""
    rows = []
    ordered = sorted(dossier.facts, key=lambda f: (f["angle"], -f.get("corroboration", 0)))
    for i, f in enumerate(ordered, 1):
        src = dossier.sources[f["source"] - 1]
        rows.append(f"{i}. **{f['claim']}** “{f['quote']}” — [{domain(src['url'])}]({src['url']}) · "
                    f"{f['angle'].lower()}")
    return "\n".join(rows)


def email_body(meta: dict, article, dossier, report_dir: str, links: dict = None, product: dict = None,
               posts: dict = None) -> str:
    kf = "\n".join(f"  {i}. {f['claim']}" for i, f in enumerate(dossier.key_facts(5), 1))
    stored = ("\nSTORED ONLINE:\n" + "\n".join(f"  {n}: {u}" for n, u in links.items()) + "\n") if links else ""
    if posts:
        stored += "\nPOSTED:\n" + "\n".join(f"  {p}: {u}" for p, u in posts.items()) + "\n"
    pages = f", {meta['pdf_pages']} pages" if meta.get("pdf_pages") else ""
    if product:
        stored += (f"\nGUMROAD ({'live' if product['published'] else 'DRAFT - review and publish it in your dashboard'}):"
                   f"\n  {product['url']}\n")
    return (f"Your {meta['mode']}-mode report on \"{meta['topic']}\" is ready.\n\n"
            f"STORY CHOSEN: {article.title}\n  {article.source} - {article.real_url or article.url}\n"
            f"  Audience appeal: {article.audience:g}/10 ({article.why or 'n/a'}); "
            f"picked from {meta['candidates']} candidates.\n\n"
            f"KEY FINDINGS\n{kf}\n\n"
            f"RESEARCH: {meta['verified_facts']} verified facts ({meta['corroborated_facts']} confirmed by a second "
            f"source) from {meta['sources']} sources.\n\n"
            f"ATTACHED: documentary report ({meta['report_words']} words{pages}), article ({meta['article_words']} words), "
            f"blog ({meta['blog_words']} words).\nAlso saved in: {report_dir}\n{stored}")


class BlogPipeline:
    def __init__(self, settings: Optional[Settings] = None, log: Callable[[str], None] = print):
        self.s = settings or Settings.from_env()
        self.log = log
        self.llm = LLMClient(self.s, log)
        self.news = NewsCollector(self.s, log)
        self.researcher = Researcher(self.llm, log)
        self.writer = Writer(self.llm, log)
        self.history = History(os.path.join(self.s.output_dir, "history.jsonl"))

    def run(self, topic: str, mode: str = "standard", days: int = 1, make_pdf: bool = True,
            email: bool = True) -> dict:
        try:
            return self._run(topic, mode, days, make_pdf, email)
        except LLMError as exc:      # nothing is saved and the story is not marked as used
            raise PipelineError(f"no LLM provider could complete a request: {exc}") from exc

    def _choose_readable(self, ranked, tries: int = 14):
        """Best-ranked story whose full text we can read (tried in parallel, since many sites block scrapers).
        Researching from a bare headline lets the search drift onto a different story with similar words, so
        unreadable stories are skipped. Only if none is readable do we accept one with a substantial summary."""
        head = ranked[:tries]
        with ThreadPoolExecutor(max_workers=5) as pool:
            texts = list(pool.map(self.researcher.read_article, head))
        for cand, text in zip(head, texts):
            if len(text) >= 500:
                return cand, text
            self.log(f"[pipeline] skipping '{cand.title[:70]}': full article text could not be read")
        for cand in head:
            if len(cand.description) >= 200:
                self.log(f"[pipeline] falling back to summary-only story: {cand.title[:70]}")
                return cand, ""
        raise PipelineError("could not read the full text of any candidate story; try again later or another topic")

    def _run(self, topic: str, mode: str, days: int, make_pdf: bool, email: bool) -> dict:
        if mode not in MODES:
            raise PipelineError(f"unknown mode '{mode}' (choose from {', '.join(MODES)})")
        m, t0 = MODES[mode], time.time()

        # ---- 1. the top 20 latest news items / research papers -------------------------------------
        self.log(f"\n=== 1/5 Collecting the top 20 latest news and research items on '{topic}' ===")
        candidates = self.news.pick(topic, self.history, days=days, limit=20)
        if not candidates:
            raise PipelineError("no new articles found (all recent ones already covered, or no news sources reachable)")
        self.log(f"Collected {len(candidates)} candidates")

        # ---- 2. rank by hotness / audience appeal, choose the best readable one ---------------------
        self.log("\n=== 2/5 Ranking by audience appeal and likely reaction ===")
        ranked = audience_rank(self.llm, list(candidates), topic, self.log)
        for i, a in enumerate(ranked[:5], 1):
            self.log(f"  {i}. [{a.score:.2f} | appeal {a.audience:g}/10] {a.title[:90]}  ({a.why})")
        article, article_text = self._choose_readable(ranked)
        self.log(f"Selected: {article.title}  [{article.source}, appeal {article.audience:g}/10]")

        # ---- 3. research it several ways --------------------------------------------------------------
        self.log("\n=== 3/5 Researching: article, other outlets, RSS pool, encyclopedia, archives, web search ===")
        dossier = self.researcher.run(article, article_text, m, pool=self.news.pool)
        if not dossier.facts and not (article_text or article.description):
            raise PipelineError("research found no verifiable facts; refusing to write from nothing")
        m = scaled_mode(m, dossier)

        # ---- 4. documentary report first, then the blog and article derived from it -------------------
        self.log("\n=== 4/5 Writing the documentary report, then the article and blog from it ===")
        plan = self.writer.plan_documentary(dossier, m)
        glance = self.writer.at_a_glance(dossier)             # who/what/when/where/why/how, opens the report
        if glance:
            plan.insert(0, glance)
        for i, c in enumerate(plan, 1):
            self.log(f"  {i}. {c['title']}  ({c['facts']} facts)")
        skipped = [role for role, angles, _, _ in self.writer.SECTIONS if dossier.count(angles) == 0]
        chapters = []
        for i, ch in enumerate(plan):
            self.log(f"[writer] chapter {i + 1}/{len(plan)}")
            chapters.append(self.writer.chapter(dossier, ch, i, plan, m))
        kept = [(c, t) for c, t in zip(plan, chapters) if t.strip()]       # chapters the fact-check emptied are dropped
        plan, chapters = [c for c, _ in kept], [t for _, t in kept]
        if not chapters:
            raise PipelineError("the fact-check left no usable documentary chapter; nothing was saved")

        self.log("[writer] executive summary and closing chapter")
        summary = self.writer.executive_summary(dossier, chapters)
        closing = self.writer.conclusion(dossier, plan, chapters, m)
        if closing:
            plan.append({"title": "Summary and Conclusion"})
            chapters.append(closing)

        title = article.title
        toc = "\n".join(f"{i}. {c['title']}" for i, c in enumerate(plan, 1))
        report = (f"# {title}\n\n*A documentary report* · **Research date:** {datetime.now():%B %d, %Y} · "
                  f"**Original story:** [{article.source}]({article.real_url or article.url})\n\n"
                  f"## Acknowledgements\n\n{acknowledgements_md(article, dossier)}\n\n" +
                  (f"## Executive Summary\n\n{summary}\n\n" if summary else "") +
                  f"## Key findings\n\n{key_findings_md(dossier)}\n\n## Contents\n\n{toc}\n\n---\n\n" +
                  "\n\n".join(chapters) +
                  f"\n\n---\n\n## Index\n\n{index_md(chapters)}\n\n"
                  f"## Evidence register\n\n{evidence_md(dossier)}\n\n"
                  f"## How this report was researched\n\n{quality_md(dossier, mode, skipped)}\n\n"
                  f"## Sources\n\n{sources_md(dossier)}\n")
        body_of_report = "\n\n".join(chapters)            # the chapters only: what the blog/article adapt

        self.log("[writer] article (from the documentary)")
        article_md = self.writer.article(dossier, m, body_of_report)
        self.log("[writer] blog (from the documentary)")
        blog = self.writer.blog(dossier, m, body_of_report)
        meta = self.writer.blog_meta(blog, dossier)

        # ---- save -----------------------------------------------------------------------------------
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = os.path.join(self.s.output_dir, f"{stamp}_{slugify(topic)}")
        os.makedirs(out, exist_ok=True)
        files = {"documentary_report.md": report,
                 "article.md": article_md if article_md.lstrip().startswith("#") else f"# {title}\n\n{article_md}",
                 "blog.md": blog if blog.lstrip().startswith("#") else f"# {meta['title']}\n\n{blog}"}
        for name, content in files.items():
            with open(os.path.join(out, name), "w", encoding="utf-8") as f:
                f.write(content)
        html = to_html(report, title, {"Chapters": len(chapters), "Verified facts": len(dossier.facts),
                                       "Sources": len(dossier.sources)})
        with open(os.path.join(out, "documentary_report.html"), "w", encoding="utf-8") as f:
            f.write(html)
        pdf = make_pdf and to_pdf(html, os.path.join(out, "documentary_report.pdf"))
        pages = pdf_pages(os.path.join(out, "documentary_report.pdf")) if pdf else 0
        if pdf:
            self.log(f"[render] PDF has {pages or 'an unknown number of'} pages" +
                     (" - under the 20-page target: the story did not yield enough verified material" if 0 < pages < 20 else ""))
        with open(os.path.join(out, "research.json"), "w", encoding="utf-8") as f:
            json.dump(dossier.to_dict(), f, indent=2, ensure_ascii=False)
        with open(os.path.join(out, "candidates.json"), "w", encoding="utf-8") as f:
            json.dump([a.to_dict() for a in ranked], f, indent=2, ensure_ascii=False)

        metadata = {"topic": topic, "title": title, "mode": mode, "date": stamp, "article": article.to_dict(),
                    "candidates": len(ranked), "audience_score": article.audience, "audience_why": article.why,
                    "chapters": [c["title"] for c in plan], "blog_meta": meta,
                    "pdf_pages": pages, "report_words": words(report), "article_words": words(article_md), "blog_words": words(blog),
                    "verified_facts": len(dossier.facts), "rejected_facts": dossier.rejected,
                    "corroborated_facts": sum(1 for f in dossier.facts if f["corroboration"]),
                    "angles_with_data": len(dossier.usable_angles()), "angles_total": len(dossier.angles),
                    "sources": len(dossier.sources), "llm_endpoint": self.llm.last_endpoint,
                    "seconds": round(time.time() - t0, 1)}

        # ---- 5. store online, then email the three deliverables ---------------------------------------
        self.log("\n=== 5/5 Storing and emailing the results ===")
        deliverables = ("documentary_report.pdf", "documentary_report.html", "documentary_report.md",
                        "article.md", "blog.md")
        links = upload_run(self.s, out, list(deliverables) + ["research.json"], self.log)
        sellable = "documentary_report.pdf" if pdf else "documentary_report.html"
        product = list_product(
            self.s, title,
            f"{meta['description']}\n\n**Key findings**\n\n{key_findings_md(dossier)}\n\n"
            f"**What you get:** a {metadata['report_words']}-word documentary report in {len(chapters)} chapters, "
            f"built on {metadata['verified_facts']} verified facts from {metadata['sources']} sources.",
            os.path.join(out, sellable), self.log)
        posts = post_all(self.s, files["blog.md"], files["article.md"], meta, self.log)
        sent = False
        if email:
            sent = send_email(self.s, f"[Blog Writer] {title[:120]}",
                              email_body(metadata, article, dossier, out, links, product, posts),
                              [os.path.join(out, n) for n in deliverables], self.log)
        metadata["email_sent"] = sent
        metadata["stored"] = links
        metadata["gumroad"] = product
        metadata["posts"] = posts
        with open(os.path.join(out, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        self.history.add(topic, article.url, article.title)   # only after the files are safely saved
        self.log(f"\nDone in {metadata['seconds']}s -> {out}\n  documentary report {metadata['report_words']} words, "
                 f"article {metadata['article_words']} words, blog {metadata['blog_words']} words, "
                 f"{metadata['verified_facts']} verified facts, pdf={'yes' if pdf else 'no (no Chrome/Edge or WeasyPrint found)'}, "
                 f"stored={len(links)} file(s), email={'sent' if sent else 'not sent'}")
        return {"dir": out, **metadata}
