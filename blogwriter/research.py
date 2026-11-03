"""Evidence-first research.

Pipeline: LLM-written search queries -> web search -> read the pages -> extract atomic facts that each carry a
verbatim quote -> mechanically verify every quote against the page text -> count independent corroboration.
Only verified facts reach the writers, so nothing in the output rests on a model's memory or paraphrase."""
import re
import time
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

from .config import Mode
from .llm import LLMClient, LLMError
from .news import Article, similar
from .web import Source, fetch_text, web_search, wikipedia_leads

# Ordered so a smaller mode (which takes the first N) still gets the 4W1H core: what/when (Timeline), who
# (Stakeholders), why (Causes), how (Mechanism); then impacts, effects and reactions; where is Geographic.
PERSPECTIVES = [
    ("Timeline", "what exactly happened and when, in order, with dates and numbers"),
    ("Stakeholders", "who is involved: the main actors, their interests and positions"),
    ("Causes", "why it happened: the causes, motives, triggers and drivers behind it, as the sources state them"),
    ("Mechanism", "how it happened or how it works: the method, process, technology or steps involved"),
    ("Political", "political and diplomatic impact and implications"),
    ("Economic", "economic and market consequences, with figures"),
    ("Social", "social and human impact: who is affected and how"),
    ("Expert views", "what named experts, analysts or officials say"),
    ("Future outlook", "likely next developments and scenarios"),
    ("Geographic", "where: regional and geographic significance"),
    ("Short-term effects", "immediate effects and consequences in the first days and weeks"),
    ("Long-term effects", "long-term and structural consequences, expected or already visible"),
    ("Reactions", "reactions from governments, organisations, markets and the public, at home and abroad"),
    ("Security", "security, military or safety implications"),
    ("Comparisons", "comparable cases and benchmarks"),
    ("Winners and losers", "who benefits and who loses, and by how much"),
    ("Legal", "legal, regulatory and treaty implications"),
    ("Risks", "risks, threats and worst-case scenarios that analysts warn about"),
    ("Historical", "historical background and precedents"),
]
MONTHS = {"january", "february", "march", "april", "june", "july", "august", "september", "october",
          "november", "december", "today", "analysis", "news", "latest", "report", "update"}
# pages that are rarely a trustworthy basis for facts
LOW_QUALITY = ("pinterest.", "quora.", "facebook.", "instagram.", "tiktok.", "youtube.", "youtu.be", "reddit.",
               "twitter.", "x.com", "linkedin.", "medium.com", "blogspot.")
NUM = re.compile(r"\d[\d,]*\.?\d*")


def norm(text: str) -> str:
    """Lower-case, accent-free, quote/dash-normalised, single-spaced text for substring comparison."""
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    t = t.replace("’", "'").replace("`", "'")
    return re.sub(r"\s+", " ", re.sub(r"[‐-―\"“”]", " ", t)).strip()


def numbers(text: str) -> set:
    return {n.replace(",", "").rstrip(".") for n in NUM.findall(text or "")}


def domain(url: str) -> str:
    try:
        return urlsplit(url).netloc.lower().removeprefix("www.")
    except ValueError:
        return url


def _terms(text: str) -> set:
    """Lower-case, accent-free word tokens (len>=4) minus generic words."""
    plain = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    return {w for w in re.findall(r"[a-z]{4,}", plain) if w not in MONTHS}


def story_vocab(article: Article, article_text: str = "") -> set:
    """Distinctive words describing the story: headline + summary + start of the real article."""
    return _terms(f"{article.title} {article.title} {article.description} {article_text[:1500]}")


def story_entities(article_text: str) -> set:
    """Named places/people/organisations in the article body: capitalised words that appear mid-sentence."""
    found = re.findall(r"(?<=[a-z,;] )[A-Z][a-zA-Z]{3,}", article_text or "")
    return {norm(w) for w in found if norm(w) not in MONTHS}


def is_relevant_hit(hit: Source, vocab: set, entities: frozenset = frozenset()) -> bool:
    """Keep a search hit only if it is about THIS story, not just one with similar words.
    It needs enough shared distinctive words and, when the article body names specific entities
    (countries, places, people), at least one of them."""
    need = 3 if len(vocab) >= 20 else 2
    text = f"{hit.title} {hit.snippet}"
    if len(vocab & _terms(text)) < need:
        return False
    if len(entities) >= 2:
        body = norm(text)
        return any(re.search(rf"\b{re.escape(e)}\b", body) for e in entities)
    return True


def quote_supported(quote: str, source_text: str, threshold: float = 0.85) -> bool:
    """True if `quote` appears in `source_text` (exactly, or with at most light edits)."""
    q, s = norm(quote), norm(source_text)
    if len(q) < 25 or not s:
        return False
    if q in s:
        return True
    block = SequenceMatcher(None, q, s, autojunk=False).find_longest_match(0, len(q), 0, len(s))
    return block.size >= threshold * len(q)


def same_fact(a: str, b: str) -> bool:
    """True if two claims state the same thing in different words: near-identical text, or the same
    figures with a good share of the same distinctive words."""
    if similar(a, b):
        return True
    na, nb = numbers(a), numbers(b)
    if na and na == nb:
        ta, tb = _terms(a), _terms(b)
        return len(ta & tb) / max(len(ta | tb), 1) >= 0.4
    return False


def verify_fact(fact: dict, source_text: str) -> Optional[str]:
    """Return None if the fact is acceptable, else the reason it was rejected."""
    if not quote_supported(fact["quote"], source_text):
        return "quote not found in source"
    if not numbers(fact["claim"]) <= numbers(fact["quote"]):
        return "claim contains numbers absent from its quote"
    return None


@dataclass
class Dossier:
    article: dict
    article_text: str
    sources: List[dict] = field(default_factory=list)     # citation number == index + 1
    facts: List[dict] = field(default_factory=list)       # verified: claim, quote, source, angle, corroboration
    angles: Dict[str, dict] = field(default_factory=dict)  # name -> {questions, sources, facts, rejected}
    rejected: int = 0

    # ---- views handed to the writers ---------------------------------------
    def _line(self, f: dict) -> str:
        extra = f", corroborated by {f['corroboration']} other source(s)" if f.get("corroboration") else ""
        return f"- {f['claim']} (source: {domain(self.sources[f['source'] - 1]['url'])}{extra})"

    def facts_text(self, angle=None, max_chars: int = 3500) -> str:
        """Fact lines for one angle name, a list of names, or (None) everything - best-confirmed first."""
        wanted = None if angle is None else ({angle} if isinstance(angle, str) else set(angle))
        pool = [f for f in self.facts if wanted is None or f["angle"] in wanted]
        pool.sort(key=lambda f: -f.get("corroboration", 0))
        out, size = [], 0
        for f in pool:
            line = self._line(f)
            if size + len(line) > max_chars:
                break
            out.append(line)
            size += len(line) + 1
        return "\n".join(out)

    def core(self) -> str:
        return (self.article_text or self.article.get("description", ""))[:1500]

    def brief(self, max_chars: int = 5000) -> str:
        head = (f"STORY: {self.article['title']}\nPUBLISHED: {self.article['published'][:10]} by "
                f"{self.article['source']}\nARTICLE TEXT: {self.core()}\n\nVERIFIED FACTS:\n")
        return head + self.facts_text(None, max(500, max_chars - len(head)))

    def notes_for(self, angle, max_chars: int = 7000) -> str:
        """Notes for a chapter: its own angle(s) in full; if they hold nothing, everything verified."""
        own = self.facts_text(angle, max_chars - 1800)
        rest = "" if own else self.facts_text(None, max_chars - 1800)
        head = (f"STORY: {self.article['title']}\nPUBLISHED: {self.article['published'][:10]}\n"
                f"ARTICLE TEXT: {self.core()[:1200]}\n\nVERIFIED FACTS:\n")
        return head + (own or rest)

    def count(self, angles) -> int:
        wanted = {angles} if isinstance(angles, str) else set(angles)
        return sum(1 for f in self.facts if f["angle"] in wanted)

    def usable_angles(self) -> List[str]:
        return [n for n, a in self.angles.items() if a["facts"]]

    def key_facts(self, n: int = 8) -> List[dict]:
        """Best-corroborated facts, at most two per angle so the list is varied."""
        picked, per_angle = [], {}
        for f in sorted(self.facts, key=lambda f: -f.get("corroboration", 0)):
            if per_angle.get(f["angle"], 0) < 2:
                picked.append(f)
                per_angle[f["angle"]] = per_angle.get(f["angle"], 0) + 1
            if len(picked) == n:
                break
        return picked

    def allowed_text(self) -> str:
        """Everything a writer may legitimately cite numbers from."""
        return f"{self.article['title']} {self.core()} " + " ".join(f"{f['claim']} {f['quote']}" for f in self.facts)

    def to_dict(self) -> dict:
        return {"article": self.article, "article_text": self.article_text, "sources": self.sources,
                "facts": self.facts, "angles": self.angles, "rejected_facts": self.rejected}


class Researcher:
    def __init__(self, llm: LLMClient, log: Callable[[str], None] = print):
        self.llm = llm
        self.log = log

    def read_article(self, article: Article) -> str:
        """Full text of the chosen story. Google News links are redirects that can't be scraped, so
        find the publisher's real URL by searching for the headline."""
        url = article.url
        if "news.google.com" in url:
            wanted = _terms(article.title)
            for query in (article.title, f"{article.title} {article.source}"):   # source may be non-Latin
                for hit in web_search(query, n=6):
                    overlap = len(wanted & _terms(hit.title)) / max(len(wanted), 1)
                    if "news.google.com" not in hit.url and (similar(hit.title, article.title) or overlap >= 0.6):
                        url = article.real_url = hit.url
                        break
                if article.real_url:
                    break
        text = fetch_text(url, 6000) if "news.google.com" not in url else ""
        self.log(f"[research] article text: {len(text)} chars from {url[:80]}")
        return text

    def seed(self, topic: str) -> Tuple[Article, str]:
        """Topic mode: the requested subject is researched directly instead of today's news. The best encyclopedia
        page on it (else the best readable web page) stands in for the news article, so every later research pass
        has a core text, names and vocabulary to stay on topic with. Returns (article, its text); the text is
        empty when nothing relevant could be read."""
        wanted = _terms(topic)
        need = max(1, (len(wanted) + 1) // 2)              # at least half the topic's distinctive words

        def on_topic(text: str) -> bool:
            return len(wanted & _terms(text)) >= need

        url, text = "", ""
        for title, link, lead in wikipedia_leads(topic, 2):
            if on_topic(f"{title} {lead[:600]}") and len(lead) >= 400:
                url, text = link, lead
                break
        if not text:
            for hit in web_search(topic, n=6):
                if any(b in hit.url for b in LOW_QUALITY) or not on_topic(f"{hit.title} {hit.snippet}"):
                    continue
                page = fetch_text(hit.url, 6000)
                if len(page) >= 500:
                    url, text = hit.url, page
                    break
        title = topic.strip()[:1].upper() + topic.strip()[1:]
        article = Article(title, text[:300], url or f"topic:{topic}", datetime.now(timezone.utc),
                          domain(url) if url else "requested topic", "topic")
        self.log(f"[research] topic seed: {len(text)} chars from {url or 'nowhere'}")
        return article, text

    def _queries(self, article: Article, angles, per_angle: int) -> Dict[str, List[str]]:
        """One LLM call for every angle's search queries; deterministic fallback if it fails."""
        topic_words = " ".join(re.findall(r"[\w'-]+", article.title)[:9])
        fallback = {n: [f"{topic_words} {n.lower()}", f"{topic_words} {d.split(',')[0]}"][:per_angle]
                    for n, d in angles}
        lines = "\n".join(f'- "{n}": {d}' for n, d in angles)
        prompt = (f"Today is {datetime.now():%d %B %Y}. News story: {article.title}\nSummary: {article.description}\n\n"
                  f"For each research angle write {per_angle} short web-search query/queries (3-8 words, plain keywords, "
                  f"include the key names/places/companies from the story). Do NOT put a year in any query unless the "
                  f"story itself names that year - we want current coverage.\nAngles:\n{lines}\n\n"
                  'Return JSON: {"<angle name>": ["query", ...], ...}')
        try:
            data = self.llm.complete_json(prompt, max_tokens=min(3500, 250 + 110 * len(angles) * per_angle))
            out = {}
            for n, _ in angles:
                qs = [q for q in data.get(n, []) if isinstance(q, str) and q.strip()]
                out[n] = qs[:per_angle] or fallback[n]
            return out
        except (LLMError, AttributeError, TypeError) as exc:
            self.log(f"[research] query generation fell back to templates ({str(exc)[:80]})")
            return fallback

    def _extract(self, article: Article, angle: str, desc: str, evidence: List[dict],
                 limit: int = 6, chars: int = 2500) -> List[dict]:
        """Ask for atomic facts with verbatim quotes; keep only those the page text actually supports."""
        if not evidence:
            return []
        published = article.published.strftime("%d %B %Y") if article.published else "recently"
        block = "\n\n".join(f"[SOURCE {s['id']}] {s['title']} ({domain(s['url'])})\n{s['text'][:chars]}"
                            for s in evidence)
        prompt = (f"Story: {article.title} (published {published})\nAngle: {angle} - {desc}\n\n{block}\n\n"
                  f"Extract up to {limit} concrete, relevant facts for this angle. For each fact give: "
                  '"claim" (one plain, SELF-CONTAINED sentence: name the subject and place explicitly and '
                  'never use "the crisis", "it", "this" or "the war" without saying which one - a reader who sees '
                  'only this sentence must not be misled about what it refers to. NEVER add a date, year or number '
                  'that is not in your quote; if the quote gives no date, write the claim without one), "quote" (the EXACT words copied from the source, 25-250 characters, '
                  'no editing), "source" (the SOURCE number). Include names, figures and dates only as the source '
                  "writes them; never add a year the source does not state; ignore cut-off fragments and do not use "
                  "background knowledge. If nothing relevant exists, return [].\n"
                  'Return JSON: [{"claim": "...", "quote": "...", "source": 2}, ...]')
        try:
            raw = self.llm.complete_json(prompt, system="You are a meticulous fact-extraction assistant.",
                                         max_tokens=1500, temperature=0.1)
        except LLMError as exc:
            self.log(f"[research] {angle}: extraction failed ({str(exc)[:80]})")
            return []
        by_id = {s["id"]: s for s in evidence}
        verified = []
        for item in raw if isinstance(raw, list) else []:
            try:
                fact = {"claim": str(item["claim"]).strip(), "quote": str(item["quote"]).strip(),
                        "source": int(item["source"]), "angle": angle, "corroboration": 0}
            except (KeyError, TypeError, ValueError):
                self.dossier.rejected += 1
                self.reasons["malformed item"] += 1
                continue
            src = by_id.get(fact["source"])
            reason = verify_fact(fact, src["text"]) if src else "unknown source"
            if reason:
                self.dossier.rejected += 1
                self.reasons[reason] += 1
                continue
            verified.append(fact)
        return verified[:limit]

    def _corroboration(self, fact: dict, texts: Dict[int, str]) -> int:
        """Other sources, on other domains, whose text contains most of the fact's distinctive terms."""
        wanted = _terms(fact["claim"]) | numbers(fact["claim"])
        if len(wanted) < 3:
            return 0
        own = domain(self.dossier.sources[fact["source"] - 1]["url"])
        seen = set()
        for sid, text in texts.items():
            d = domain(self.dossier.sources[sid - 1]["url"])
            if sid == fact["source"] or d == own or d in seen:
                continue
            body = norm(text)
            if sum(1 for w in wanted if w in body) / len(wanted) >= 0.7:
                seen.add(d)
        return len(seen)

    # ---- searching, reading and extracting -------------------------------------
    def _register(self, url: str, title: str, snippet: str) -> int:
        """Source id for a URL (one id per page across all research passes)."""
        if url not in self.by_url:
            self.by_url[url] = len(self.dossier.sources) + 1
            self.dossier.sources.append({"id": self.by_url[url], "title": title, "url": url, "text": snippet})
        return self.by_url[url]

    def _gather(self, article: Article, jobs, vocab, entities, pages: int, limit: int, chars: int,
                with_article: bool = True, timelimit: str = None) -> None:
        """For each job (name, description, queries): search, read the best pages once each, extract and
        verify facts, and add them to the dossier."""
        d = self.dossier

        def search(job):
            hits: List[Source] = []
            for q in job[2]:
                hits += web_search(q, n=5, timelimit=timelimit)
                time.sleep(0.3)
            seen, unique = set(), []
            for h in hits:
                if (h.url not in seen and h.url != article.url and not any(b in h.url for b in LOW_QUALITY)
                        and is_relevant_hit(h, vocab, entities)):
                    seen.add(h.url)
                    unique.append(h)
            return job[0], unique[:pages + 2]

        with ThreadPoolExecutor(max_workers=3) as pool:
            found = dict(pool.map(search, jobs))

        to_fetch = []
        for name, hits in found.items():
            for rank, hit in enumerate(hits):
                sid = self._register(hit.url, hit.title, hit.snippet)
                if rank < pages and len(d.sources[sid - 1]["text"]) < 600 and hit.url not in to_fetch:
                    to_fetch.append(hit.url)
        with ThreadPoolExecutor(max_workers=6) as pool:
            for url, text in zip(to_fetch, pool.map(lambda u: fetch_text(u, chars), to_fetch)):
                if text:
                    d.sources[self.by_url[url] - 1]["text"] = text

        for name, desc, queries in jobs:
            evidence = ([d.sources[0]] if with_article else []) + [d.sources[self.by_url[h.url] - 1]
                                                                    for h in found[name]]
            self._extract_into(article, name, desc, evidence[:pages + 3], limit, chars, queries, len(found[name]))

    def _extract_into(self, article: Article, name: str, desc: str, evidence: List[dict], limit: int, chars: int,
                      queries=(), n_sources: int = 0) -> None:
        """Extract verified facts from the given sources and add the new ones to the dossier."""
        d = self.dossier
        facts = self._extract(article, name, desc, [s for s in evidence if s["text"]], limit=limit, chars=chars)
        fresh = []
        for f in facts:                                  # drop re-statements of a fact we already hold
            if not any(same_fact(f["claim"], g["claim"]) or norm(f["quote"]) == norm(g["quote"])
                       for g in d.facts + fresh):
                fresh.append(f)
        d.facts += fresh
        a = d.angles.setdefault(name, {"questions": [], "sources": 0, "facts": 0})
        a["questions"] += list(queries)
        a["sources"] += n_sources or len(evidence)
        a["facts"] += len(fresh)
        self.log(f"[research] {name}: {n_sources or len(evidence)} sources -> {len(fresh)} verified facts")

    # ---- the different ways of researching ----------------------------------------
    def _wikipedia_pass(self, article: Article, vocab, entities) -> None:
        """Encyclopedia background on the people, places and events involved."""
        names = re.findall(r"\b[A-Z][a-z]{2,}\b", article.title)[:3]
        queries = [article.title] + ([" ".join(names)] if len(names) >= 2 else [])
        seen, evidence = set(), []
        for q in queries:
            for title, url, text in wikipedia_leads(q, 3):
                hit = Source(title, url, text[:300])
                if url not in seen and is_relevant_hit(hit, vocab, entities):
                    seen.add(url)
                    sid = self._register(url, title, text)
                    self.dossier.sources[sid - 1]["text"] = text
                    evidence.append(self.dossier.sources[sid - 1])
        self._extract_into(article, "Historical", "background and history from the encyclopedia", evidence[:4], 8,
                           4000, ["wikipedia: " + q for q in queries], len(evidence))

    def _feed_pass(self, article: Article, pool: List[Article], vocab, entities, limit_items: int = 6) -> None:
        """Other items from the collected news/RSS pool that are about this same story: read them in full."""
        related = [c for c in pool if c.url != article.url and not similar(c.title, article.title)
                   and is_relevant_hit(Source(c.title, c.url, c.description), vocab, entities)][:limit_items]
        with ThreadPoolExecutor(max_workers=4) as ex:
            texts = list(ex.map(self.read_article, related))
        evidence = []
        for c, text in zip(related, texts):
            if len(text) >= 400:
                url = c.real_url or c.url
                sid = self._register(url, c.title, text)
                self.dossier.sources[sid - 1]["text"] = text
                evidence.append(self.dossier.sources[sid - 1])
        if related:
            self._extract_into(article, "Story", "what other outlets in the news and RSS feeds report about this story",
                               evidence[:5], 10, 4000, ["news/RSS pool"], len(evidence))

    def _score_corroboration(self) -> None:
        texts = {s["id"]: s["text"] for s in self.dossier.sources}
        for f in self.dossier.facts:
            f["corroboration"] = self._corroboration(f, texts)

    def _gaps(self, article: Article, names: List[str], n: int) -> List[tuple]:
        """What would a reader still ask? Returns [(angle, search query)] for the unanswered questions."""
        prompt = (f"Today is {datetime.now():%d %B %Y}. We are writing a complete documentary report on this story. "
                  f"Verified material so far:\n{self.dossier.brief(4500)}\n\n"
                  f"List the {n} most important questions about the story that this material does NOT yet answer "
                  "(who, what, when, where, why, how, consequences, reactions, what comes next). For each give the "
                  f"best-fitting angle from [{', '.join(names)}] and a short web-search query (3-8 words, plain "
                  "keywords, key names included, no year unless the story names it).\n"
                  'Return JSON: [{"angle": "...", "query": "..."}]')
        try:
            raw = self.llm.complete_json(prompt, max_tokens=700)
        except LLMError:
            return []
        out = []
        for item in raw if isinstance(raw, list) else []:
            try:
                angle, query = str(item["angle"]), str(item["query"]).strip()
            except (KeyError, TypeError):
                continue
            if query:
                out.append((angle if angle in names else names[0], query))
        return out[:n]

    def run(self, article: Article, article_text: str, mode: Mode, pool: Optional[List[Article]] = None) -> Dossier:
        angles = PERSPECTIVES[:mode.perspectives]
        desc_of = dict(PERSPECTIVES)
        self.reasons = Counter()
        self.by_url = {}
        self.dossier = dossier = Dossier(article=article.to_dict(), article_text=article_text)
        dossier.sources.append({"id": 1, "title": article.title, "url": article.real_url or article.url,
                                "text": article_text or article.description})
        self.by_url[dossier.sources[0]["url"]] = 1
        vocab = story_vocab(article, article_text)
        entities = frozenset(story_entities(article_text))

        # 1. the original article is the richest source: read all of it, not a 2,500-character slice
        story = self._extract(article, "Story", "what the original article itself reports",
                              [dossier.sources[0]] if dossier.sources[0]["text"] else [], limit=14, chars=6000)
        unique_story = []
        for f in story:
            if not any(same_fact(f["claim"], g["claim"]) for g in unique_story):
                unique_story.append(f)
        story = unique_story
        dossier.facts += story
        dossier.angles["Story"] = {"questions": [], "sources": 1, "facts": len(story)}
        self.log(f"[research] Story (original article): {len(story)} verified facts")

        # 2. what other outlets report about the same story (completeness + independent confirmation)
        if mode.coverage_pages:
            self._gather(article, [("Story", "what other outlets report about this same story",
                                    [article.title, f"{article.title} latest"])], vocab, entities,
                         mode.coverage_pages, 14, 4000, with_article=False)

        # 2b. other ways in: the news/RSS pool, encyclopedia background, and older coverage from the archives
        if mode.background:
            self._feed_pass(article, pool or [], vocab, entities)
            self._wikipedia_pass(article, vocab, entities)
            core = " ".join(re.findall(r"[\w'-]+", article.title)[:7])
            self._gather(article, [("Historical", "older coverage and earlier events leading up to this story",
                                    [f"{core} background history", f"{core} previous events timeline"])],
                         vocab, entities, mode.fetch_pages, mode.facts_per_angle, 2500, timelimit="y")

        # 3. the research angles
        queries = self._queries(article, angles, mode.questions)
        self._gather(article, [(n, d, queries[n]) for n, d in angles], vocab, entities,
                     mode.fetch_pages, mode.facts_per_angle, 2500)

        # 4. fill the gaps: ask what is still unanswered and search for exactly that
        for rnd in range(mode.gap_rounds):
            self._score_corroboration()
            gaps = self._gaps(article, ["Story"] + [n for n, _ in angles], mode.gap_queries)
            if not gaps:
                break
            before = len(dossier.facts)
            grouped: Dict[str, List[str]] = {}
            for angle, query in gaps:
                grouped.setdefault(angle, []).append(query)
            self.log(f"[research] gap round {rnd + 1}: {[q for _, q in gaps]}")
            self._gather(article, [(a, desc_of.get(a, "what the story's coverage reports"), qs)
                                   for a, qs in grouped.items()], vocab, entities,
                         mode.fetch_pages, mode.facts_per_angle, 2500)
            if len(dossier.facts) == before:
                break

        self._score_corroboration()
        self.log(f"[research] {len(dossier.facts)} verified facts kept, {dossier.rejected} rejected as unsupported, "
                 f"{sum(1 for f in dossier.facts if f['corroboration'])} corroborated by a second source")
        if self.reasons:
            self.log(f"[research] rejection reasons: {dict(self.reasons)}")
        return dossier
