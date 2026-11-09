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

from .config import MODES, Settings, mode_for_pages
from .gumroad import list_product, parse_price
from .plainmath import plain_math
from .pricing import is_auto, label, price_for
from .history import History
from .llm import LLMClient, LLMError
from .mailer import send_email
from .news import NewsCollector
from .publish import post_all
from .rank import audience_rank
from .render import pdf_pages, to_html, to_pdf
from .research import Researcher, domain
from .storage import upload_run, zip_run
from .writer import LANGS, LEVELS, NICHES, Writer, audience, words


class PipelineError(RuntimeError):
    pass


def heading_of(chapter: str, fallback: str) -> str:
    """A chapter's own '## ' heading (after translation it differs from the plan's English title)."""
    m = re.match(r"\s*#{1,3} +(.+)", chapter)
    return m.group(1).strip() if m else fallback


def slugify(text: str, limit: int = 40) -> str:
    return re.sub(r"[^\w]+", "_", text).strip("_")[:limit] or "topic"


def scaled_mode(mode, dossier):
    """Size the blog and article to the evidence. Asking for 600 words on two facts forces padding, which the
    fact-check then (rightly) deletes. (Documentary chapters size themselves from their own facts.)"""
    n = len(dossier.facts)
    evidence_words = 45 * n + len(dossier.article_text.split()) // 5     # prose the verified material can support
    return replace(mode, article_words=max(250, min(mode.article_words, evidence_words)),
                   blog_words=max(150, min(mode.blog_words, evidence_words // 2)))


def confidence(fact: dict) -> str:
    """Evidence strength, counted not guessed: how many independent websites report the fact."""
    n = fact.get("corroboration", 0) + 1
    return "High" if n >= 3 else "Moderate" if n == 2 else "Low"


def key_findings_md(dossier) -> str:
    rows = []
    for i, f in enumerate(dossier.key_facts(8), 1):
        src = dossier.sources[f["source"] - 1]
        n = f.get("corroboration", 0) + 1
        rows.append(f"{i}. **{confidence(f)} confidence.** {f['claim']} — [{domain(src['url'])}]({src['url']}) "
                    f"*({n} independent source{'s' if n > 1 else ''})*")
    if not rows:
        return "_No facts could be independently verified for this story._"
    return ("\n".join(rows) + "\n\n*Confidence is counted, not guessed: High = reported by three or more independent "
            "sources, Moderate = two, Low = one source only.*")


def blog_cta(product: dict, price_text: str, chapters: int, facts: int, pages: int) -> tuple:
    """(line after the opening paragraph, closing section) pointing blog readers to the full report on Gumroad.
    Built from the real numbers of this run, so it never promises more than the report contains."""
    amount, currency = parse_price(price_text)
    price = label(amount, currency)
    size = f"{pages}-page " if pages else ""
    teaser = f"*This post is the short version. The full {size}documentary report is [here]({product['url']}).*"
    closing = (f"## Want the full story?\n\nThis post covers the main points. The full documentary report goes much "
               f"deeper: a {size}PDF with {chapters} chapters and {facts} verified facts, each one linked to the source "
               f"it came from, plus a who-is-affected table and a confidence rating on every key finding.\n\n"
               f"**[{'Get the full report free on Gumroad' if price == 'Free' else f'Get the full report on Gumroad for {price}'}]({product['url']})**")
    return teaser, closing


def add_cta(blog: str, teaser: str, closing: str) -> str:
    """Put the teaser after the first prose paragraph (below the headline) and the closing section at the end."""
    paras = blog.strip().split("\n\n")
    at = next((i + 1 for i, p in enumerate(paras) if not p.lstrip().startswith(("#", ">", "*", "|", "-"))), len(paras))
    return "\n\n".join(paras[:at] + [teaser] + paras[at:] + ["---", closing]) + "\n"


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
    origin = (f"Its starting point was **{article.source}**." if article.api == "topic" else
              f"The story it follows was first reported by **{article.source}**.")
    return (f"This report stands on the work of reporters, editors and researchers who published before it. "
            f"{origin} {thanks}\n\n"
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
            term = re.sub(r"['’]s$", "", " ".join(parts).strip(".,;:'’"))      # "China’s" is "China"
            if len(term) >= 4:
                names[term] += 1
    rows = []
    for term in sorted((t for t, n in names.items() if n >= 2), key=str.lower):
        where = [str(i) for i, text in enumerate(prose, 1) if term in text]
        # a name in most chapters ("American", "Europe") points nowhere, so it is not worth indexing
        if where and not (len(prose) >= 5 and len(where) > 0.6 * len(prose)):
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
    if meta.get("source") == "topic":
        chosen = (f"REQUESTED TOPIC: {meta['topic']} ({meta.get('level', 'intermediate')} level, "
                  f"{meta.get('niche', 'general')} reader, {meta.get('lang', 'en')})\n"
                  f"  Starting text: {article.source} - {article.url}\n\n")
    else:
        chosen = (f"STORY CHOSEN: {article.title}\n  {article.source} - {article.real_url or article.url}\n"
                  f"  Audience appeal: {article.audience:g}/10 ({article.why or 'n/a'}); "
                  f"picked from {meta['candidates']} candidates.\n\n")
    stored = ("\nSTORED ONLINE:\n" + "\n".join(f"  {n}: {u}" for n, u in links.items()) + "\n") if links else ""
    if posts:
        stored += "\nPOSTED:\n" + "\n".join(f"  {p}: {u}" for p, u in posts.items()) + "\n"
    pages = f", {meta['pdf_pages']} pages" if meta.get("pdf_pages") else ""
    if product:
        stored += (f"\nGUMROAD ({'live' if product['published'] else 'DRAFT - review and publish it in your dashboard'}):"
                   f"\n  {product['url']}\n")
    return (f"Your {meta['mode']}-mode report on \"{meta['topic']}\" is ready.\n\n"
            f"{chosen}KEY FINDINGS\n{kf}\n\n"
            f"RESEARCH: {meta['verified_facts']} verified facts ({meta['corroborated_facts']} confirmed by a second "
            f"source) from {meta['sources']} sources.\n\n"
            f"ATTACHED: documentary report ({meta['report_words']} words{pages}), article ({meta['article_words']} words), "
            f"blog ({meta['blog_words']} words).\nAlso saved in: {report_dir}\n{stored}")


def is_concept(llm, topic: str, log=print) -> bool:
    """True when the topic is an idea to learn (a theorem, a method, how something works) rather than an event or a
    story, so its report is written as study notes. Any doubt or failure: False (the news-style report)."""
    try:
        reply = llm.complete_json(
            f'Is "{topic}" a concept, method, law, skill or subject a student would study (for example a theorem, an '
            'algorithm, how a vaccine works), as opposed to an event, a story, a person or a current news item? '
            'Reply with JSON: {"concept": true or false}', max_tokens=60, temperature=0)
        return bool(isinstance(reply, dict) and reply.get("concept") is True)
    except Exception as exc:
        log(f"[pipeline] could not classify the topic ({type(exc).__name__}); writing the news-style report")
        return False


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
            email: bool = True, source: str = "news", pages: int = 0, level: str = "intermediate",
            niche: str = "general", lang: str = "en", publish: bool = True, video: bool = False,
            style: str = "", lesson: Optional[dict] = None, report: Optional[bool] = None,
            sell: Optional[bool] = None) -> dict:
        """source: 'news' writes about today's hottest story on the topic; 'topic' researches the topic itself.
        pages: a page target that overrides the mode's size (0 = the mode decides). level / niche: who the report
        is written for. lang: the language of the finished pieces. publish: list on Gumroad and post to the blogs
        (off for private orders, which are only emailed). video: also make the videos for review (never posted).
        report: write the report, article and blog. sell: list the report on Gumroad (without posting anywhere).
        A video run sells its document by default whenever a Gumroad key is set: the report is written and listed
        first, so the video's description can link to it. Its only email is the video's; the "[Blog Writer]"
        email is for report-only runs."""
        if sell is None:
            sell = publish or (video and bool(self.s.gumroad_token))
        if report is None:
            report = not video or publish or sell
        for value, allowed, what in ((source, ("news", "topic"), "source"), (level, LEVELS, "level"),
                                     (niche, NICHES, "niche"), (lang, LANGS, "lang")):
            if value not in allowed:
                raise PipelineError(f"unknown {what} '{value}' (choose from {', '.join(allowed)})")
        self.writer.reader = audience(level, niche)
        self.writer.study = bool(lesson) or style in ("education", "concept") or (
            source == "topic" and style in ("", "auto") and is_concept(getattr(self, "llm", None), topic, self.log))
        try:
            result = self._run(topic, mode, days, make_pdf, email, source, pages, lang, publish,
                               {"level": level, "niche": niche, "lang": lang, "pages_requested": pages}, report=report,
                               sell=sell, report_email=email and not video, study=self.writer.study)
        except LLMError as exc:      # nothing is saved and the story is not marked as used
            raise PipelineError(f"no LLM provider could complete a request: {exc}") from exc
        if video:
            from .video import VideoMaker
            try:                     # the report is already saved and sent; a video failure must not undo that
                result["videos"] = VideoMaker(self.s, self.llm, self.log).make(result["dir"], email=email,
                                                                              style=style, lesson=lesson)
            except Exception as exc:
                self.log(f"[video] FAILED: {type(exc).__name__}: {str(exc)[:300]}")
        return result

    def _research_only(self, topic: str, mode: str, article, ranked, dossier, source: str, order: Optional[dict],
                       t0: float) -> dict:
        """A video run: keep the verified research the video is built from, and nothing else. No report, article
        or blog is written, nothing is listed or posted, and no report email is sent (the video is emailed)."""
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = os.path.join(self.s.output_dir, f"{stamp}_{slugify(topic)}")
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "research.json"), "w", encoding="utf-8") as f:
            json.dump(dossier.to_dict(), f, indent=2, ensure_ascii=False)
        with open(os.path.join(out, "candidates.json"), "w", encoding="utf-8") as f:
            json.dump([a.to_dict() for a in ranked], f, indent=2, ensure_ascii=False)
        metadata = {"topic": topic, "title": article.title, "mode": mode, "date": stamp, "article": article.to_dict(),
                    "report": False, "verified_facts": len(dossier.facts), "rejected_facts": dossier.rejected,
                    "sources": len(dossier.sources), "llm_endpoint": self.llm.last_endpoint,
                    "seconds": round(time.time() - t0, 1), "source": source, "email_sent": False, "stored": {},
                    "gumroad": {}, "posts": {}, "llm_usage": self.llm.usage, **(order or {})}
        with open(os.path.join(out, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        if source == "news":
            self.history.add(topic, article.url, article.title)
        self.log(f"\n[pipeline] research done in {metadata['seconds']}s: {metadata['verified_facts']} verified facts "
                 f"from {metadata['sources']} sources. Video only: no report, article, blog or report email.")
        return {"dir": out, **metadata}

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

    def _run(self, topic: str, mode: str, days: int, make_pdf: bool, email: bool, source: str = "news",
             target_pages: int = 0, lang: str = "en", publish: bool = True, order: Optional[dict] = None,
             report: bool = True, sell: bool = False, report_email: bool = True, study: bool = False) -> dict:
        if mode not in MODES:
            raise PipelineError(f"unknown mode '{mode}' (choose from {', '.join(MODES)})")
        m, t0 = MODES[mode], time.time()
        if target_pages:
            m = mode_for_pages(target_pages)
            mode = m.name
            self.log(f"[pipeline] {target_pages} pages requested: {mode} research, up to {m.chapters} chapters of "
                     f"~{m.chapter_words} words")

        if source == "topic":
            # ---- 1-2. a requested topic: no news to collect or rank, research the subject itself ----------
            self.log(f"\n=== 1-2/5 Topic mode: finding a starting text on '{topic}' ===")
            article, article_text = self.researcher.seed(topic)
            article.why = "requested topic"
            ranked = [article]
            if not (article_text or article.description):
                self.log("[pipeline] no starting text found; researching from web search alone")
        else:
            # ---- 1. the top 20 latest news items / research papers -------------------------------------
            self.log(f"\n=== 1/5 Collecting the top 20 latest news and research items on '{topic}' ===")
            candidates = self.news.pick(topic, self.history, days=days, limit=20)
            if not candidates:
                raise PipelineError("no new articles found (all recent ones already covered, or no news sources "
                                    "reachable)")
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
        dossier = self.researcher.run(article, article_text, m, pool=self.news.pool, study=study)
        if not dossier.facts and not (article_text or article.description):
            raise PipelineError("research found no verifiable facts; refusing to write from nothing")
        m = scaled_mode(m, dossier)
        if not report:
            return self._research_only(topic, mode, article, ranked, dossier, source, order, t0)

        # ---- 4. documentary report first, then the blog and article derived from it -------------------
        self.log("\n=== 4/5 Writing the documentary report, then the article and blog from it ===")
        plan = self.writer.plan_documentary(dossier, m)
        glance = self.writer.at_a_glance(dossier)             # who/what/when/where/why/how, opens the report
        if glance:
            plan.insert(0, glance)
        for i, c in enumerate(plan, 1):
            self.log(f"  {i}. {c['title']}  ({c['facts']} facts)")
        skipped = [role for role, angles, _, _ in (self.writer.STUDY_SECTIONS if study else self.writer.SECTIONS)
                   if dossier.count(angles) == 0]
        chapters = []
        for i, ch in enumerate(plan):
            self.log(f"[writer] chapter {i + 1}/{len(plan)}")
            chapters.append(self.writer.chapter(dossier, ch, i, plan, m))
        kept = [(c, t) for c, t in zip(plan, chapters) if t.strip()]       # chapters the fact-check emptied are dropped
        plan, chapters = [c for c, _ in kept], [t for _, t in kept]
        if not chapters:
            raise PipelineError("the fact-check left no usable documentary chapter; nothing was saved")

        self.log("[writer] executive summary, who-is-affected table and closing chapter")
        summary = self.writer.executive_summary(dossier, chapters)
        impact = "" if study else self.writer.impact_table(dossier)      # study notes have no "who is affected"
        closing = self.writer.conclusion(dossier, plan, chapters, m)
        if closing:
            plan.append({"title": "Summary and Conclusion"})
            chapters.append(closing)

        title = article.title
        body_of_report = "\n\n".join(chapters)            # the chapters only: what the blog/article adapt

        self.log("[writer] article (from the documentary)")
        article_md = self.writer.article(dossier, m, body_of_report)
        self.log("[writer] blog (from the documentary)")
        blog = self.writer.blog(dossier, m, body_of_report)

        chapters = [plain_math(c) for c in chapters]          # no LaTeX in a printed report or a blog
        summary, article_md, blog = plain_math(summary), plain_math(article_md), plain_math(blog)
        index = index_md(chapters)                          # names are indexed from the English text
        if lang != "en":
            self.log(f"[writer] translating the report, article and blog into {LANGS[lang]}")
            chapters = [self.writer.translate(c, lang) for c in chapters]
            summary, impact = self.writer.translate(summary, lang), self.writer.translate(impact, lang)
            article_md, blog = self.writer.translate(article_md, lang), self.writer.translate(blog, lang)
        meta = self.writer.blog_meta(blog, dossier)

        toc = "\n".join(f"{i}. {heading_of(t, c['title'])}" for i, (c, t) in enumerate(zip(plan, chapters), 1))
        report = (f"# {title}\n\n*{'Study notes' if study else 'A documentary report'}* ·**Research date:** {datetime.now():%B %d, %Y} · " +
                  ("**Researched on request**\n\n" if article.api == "topic" else
                   f"**Original story:** [{article.source}]({article.real_url or article.url})\n\n") +
                  f"## Acknowledgements\n\n{acknowledgements_md(article, dossier)}\n\n" +
                  (f"## Executive Summary\n\n{summary}\n\n" if summary else "") +
                  f"## Key findings\n\n{key_findings_md(dossier)}\n\n" +
                  (f"## Who is affected\n\n{impact}\n\n" if impact else "") +
                  f"## Contents\n\n{toc}\n\n---\n\n" +
                  "\n\n".join(chapters) +
                  f"\n\n---\n\n## Index\n\n{index}\n\n"
                  f"## Evidence register\n\n{evidence_md(dossier)}\n\n"
                  f"## How this report was researched\n\n{quality_md(dossier, mode, skipped)}\n\n"
                  f"## Sources\n\n{sources_md(dossier)}\n")

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
                                       "Sources": len(dossier.sources)}, "Study Notes" if study else "A Documentary Report")
        with open(os.path.join(out, "documentary_report.html"), "w", encoding="utf-8") as f:
            f.write(html)
        pdf = make_pdf and to_pdf(html, os.path.join(out, "documentary_report.pdf"))
        pages = pdf_pages(os.path.join(out, "documentary_report.pdf")) if pdf else 0
        if pdf:
            self.log(f"[render] PDF has {pages or 'an unknown number of'} pages" +
                     (f" - under the {target_pages or 20}-page target: the story did not yield enough verified material"
                      if 0 < pages < (target_pages or 20) else ""))
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
                    "seconds": round(time.time() - t0, 1), "source": source, **(order or {})}

        # ---- 5. store online, then email the three deliverables ---------------------------------------
        self.log("\n=== 5/5 Storing and emailing the results ===")
        deliverables = ("documentary_report.pdf", "documentary_report.html", "documentary_report.md",
                        "article.md", "blog.md")
        # the product comes first, so the blog can link to it before it is stored, posted and emailed
        sellable = "documentary_report.pdf" if pdf else "documentary_report.html"
        if not publish and not sell:
            self.log("[pipeline] private order: not listed on Gumroad and not posted anywhere")
        elif not publish:
            self.log("[pipeline] the document is sold on Gumroad; nothing is posted to the blogs")
        if is_auto(self.s.gumroad_price):
            amount, why = price_for(metadata.get("level", "intermediate"), metadata.get("niche", "general"), pages,
                                    len(dossier.facts), metadata["report_words"])
            price_text, metadata["price_reason"] = f"{amount} INR", why
        else:
            price_text, metadata["price_reason"] = self.s.gumroad_price, "fixed by GUMROAD_PRICE"
        if publish or sell:
            self.log(f"[gumroad] price {label(*parse_price(price_text))}: {metadata['price_reason']}")
        product = (publish or sell) and list_product(
            self.s, title,
            f"{meta['description']}\n\n**Key findings**\n\n{key_findings_md(dossier)}\n\n"
            f"**What you get:** a {metadata['report_words']}-word documentary report in {len(chapters)} chapters, "
            f"built on {metadata['verified_facts']} verified facts from {metadata['sources']} sources.",
            os.path.join(out, sellable), self.log, price_text) or {}
        if product.get("price") is not None:           # the price Gumroad really accepted
            price_text = f"{product['price']:g} {product['currency']}"
        if product and product.get("published"):
            teaser, closing = blog_cta(product, price_text, len(chapters), len(dossier.facts), pages)
            files["blog.md"] = add_cta(files["blog.md"], teaser, closing)
            with open(os.path.join(out, "blog.md"), "w", encoding="utf-8") as f:
                f.write(files["blog.md"])
            self.log(f"[gumroad] blog now links to the report: {product['url']}")
        elif product:
            self.log("[gumroad] product is a draft, so the blog carries no link (a draft link shows readers a 404); "
                     "set GUMROAD_PUBLISH=true to sell and link automatically")
        # one zip of the report, article and blog, uploaded next to the individual files
        bundle = zip_run(out, ["documentary_report.pdf" if pdf else "documentary_report.html", "article.md", "blog.md"])
        # research.json stays local: it holds the full text of the news articles read, which must not be republished
        links = upload_run(self.s, out, [bundle] + list(deliverables), self.log)
        posts = post_all(self.s, files["blog.md"], files["article.md"], meta, self.log) if publish else {}
        sent = False
        if email and report_email:
            sent = send_email(self.s, f"[Blog Writer] {title[:120]}",
                              email_body(metadata, article, dossier, out, links, product, posts),
                              [os.path.join(out, n) for n in deliverables], self.log)
        metadata["email_sent"] = sent
        metadata["stored"] = links
        metadata["gumroad"] = product
        metadata["posts"] = posts
        metadata["llm_usage"] = self.llm.usage
        with open(os.path.join(out, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        if source == "news":                                  # a requested topic may be ordered again
            self.history.add(topic, article.url, article.title)   # only after the files are safely saved
        self.log(f"\nDone in {metadata['seconds']}s -> {out}\n  documentary report {metadata['report_words']} words, "
                 f"article {metadata['article_words']} words, blog {metadata['blog_words']} words, "
                 f"{metadata['verified_facts']} verified facts, pdf={'yes' if pdf else 'no (no Chrome/Edge or WeasyPrint found)'}, "
                 f"stored={len(links)} file(s), email={'sent' if sent else 'not sent'}\n  llm usage: "
                 + ", ".join(f"{p} {u['calls']} calls/{u['tokens']} tokens" for p, u in self.llm.usage.items()))
        return {"dir": out, **metadata}
