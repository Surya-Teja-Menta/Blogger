"""News collection from NewsAPI, GNews, Google News RSS and publisher RSS feeds, with
de-duplication, coverage-based 'hotness' ranking and history-aware story selection."""
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from typing import Callable, List, Optional
from urllib.parse import quote_plus

import feedparser

from .config import Settings
from .web import get, normalize_url, strip_html

RSS_FEEDS = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://www.theguardian.com/world/rss",
    "https://feeds.npr.org/1004/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "http://rss.cnn.com/rss/edition.rss",
]
CREDIBLE = {"bbc": .15, "reuters": .15, "associated press": .15, "guardian": .12, "nytimes": .12,
            "new york times": .12, "npr": .12, "al jazeera": .12, "cnn": .1, "washington post": .1,
            "bloomberg": .12, "financial times": .12, "the hindu": .1, "wsj": .12}
# advertorial / listicle headlines make poor subjects for an investigative report
FLUFF = re.compile(r"\b(stocks? (to buy|that could)|could soar|best stocks|top \d+|\d+ (stocks|ways|things)|"
                   r"sponsored|how to|you need to know|price prediction|"
                   r"(movie|film|tv|album|game|book|show) review|box office|trailer|season finale|"
                   r"review:)\b", re.I)
# daily market wraps ("UAE Stocks Rose...", "WTI Crude Holds...", "EUR/USD in the Red...") are not stories
MARKET_WRAP = re.compile(r"\b[a-z]{3}/[a-z]{3}\b|\b(stocks?|shares|futures|crude|wti|brent|forex|gold|bitcoin|"
                         r"dollar|yields?)\b.*\b(rose|fell|rise|falls?|gains?|holds?|slips?|climbs?|drops?|"
                         r"higher|lower|in the red|in the green|edges?)\b|"
                         r"\b[A-Z]{3}(?:USD|EUR|AUD|GBP|JPY|CAD|CHF|INR)\b|\b(?:USD|EUR|AUD|GBP|JPY)[A-Z]{3}\b|"
                         r"\b(moved|moves|jumps?|surges?|plunges?|tumbles?|rallies|slides?) (sharply|higher|lower)\b|"
                         r"market movers|price (today|forecast|analysis)", re.I)
STOP = {"the", "a", "an", "of", "and", "in", "on", "for", "to", "news", "latest"}


@dataclass
class Article:
    title: str
    description: str
    url: str
    published: Optional[datetime]
    source: str
    api: str
    coverage: int = 1
    score: float = 0.0
    real_url: str = ""      # publisher URL when `url` is a redirect (Google News)
    audience: float = 0.0   # 0-10 appeal to readers, set by rank.audience_rank
    why: str = ""           # short reason behind the audience score

    def to_dict(self) -> dict:
        d = asdict(self)
        d["published"] = self.published.isoformat() if self.published else ""
        return d


def parse_date(value) -> Optional[datetime]:
    """Any ISO / RFC-2822 string or feedparser struct_time -> aware UTC datetime (or None)."""
    if not value:
        return None
    try:
        if isinstance(value, time.struct_time):
            return datetime(*value[:6], tzinfo=timezone.utc)
        s = str(value).strip()
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            dt = parsedate_to_datetime(s)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _tokens(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP and len(w) > 1}


def similar(a: str, b: str) -> bool:
    ta, tb = _tokens(a), _tokens(b)
    jac = len(ta & tb) / len(ta | tb) if ta and tb else 0
    return jac >= 0.6 or SequenceMatcher(None, a.lower(), b.lower()).ratio() >= 0.8


def deduplicate(articles: List[Article]) -> List[Article]:
    """Merge duplicates; `coverage` counts how many outlets ran the same story."""
    clusters: List[Article] = []
    for a in articles:
        for c in clusters:
            if normalize_url(a.url) == normalize_url(c.url) or similar(a.title, c.title):
                c.coverage += 1
                if len(a.description) > len(c.description):
                    c.description = a.description
                break
        else:
            clusters.append(a)
    return clusters


def topic_hit(topic: str, text: str) -> bool:
    """True if any topic word (or its 6-letter stem, so 'geopolitics' ~ 'geopolitical') occurs in text."""
    words_in_text = _tokens(text)
    for t in _tokens(topic):
        if len(t) >= 4 and any(w.startswith(t[:6]) for w in words_in_text):
            return True
    return False


def relevant(query: str, text: str) -> bool:
    words = [w for w in _tokens(query)]
    if not words:
        return True
    text = text.lower()
    return query.lower() in text or sum(w in text for w in words) / len(words) >= 0.5


def score(a: Article, topic: str, window_hours: float, now: datetime) -> float:
    age = (now - a.published).total_seconds() / 3600 if a.published else window_hours
    s = 0.35 * max(0.0, 1 - age / window_hours)
    s += 0.35 * min(a.coverage, 5) / 5
    s += next((w for k, w in CREDIBLE.items() if k in a.source.lower()), 0.03)
    s += 0.1 * min(len(a.description), 200) / 200
    if topic_hit(topic, a.title):          # on-topic stories must beat merely popular ones
        s += 0.2
    elif topic_hit(topic, a.description):
        s += 0.1
    if FLUFF.search(a.title) or MARKET_WRAP.search(a.title):
        s -= 0.5      # must outweigh the topic bonus a clickbait headline earns by name-dropping the topic
    return round(s, 4)


class NewsCollector:
    def __init__(self, settings: Settings, log: Callable[[str], None] = print):
        self.s = settings
        self.log = log
        self.pool: List[Article] = []

    # ---- sources (failures are logged by _safe, never silent) --------------
    @staticmethod
    def _ok(r):
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code} (check API key / quota)")
        return r

    def _newsapi(self, topic, since):
        if not self.s.newsapi_key:
            return []
        r = get("https://newsapi.org/v2/everything", {
            "q": topic, "from": since.strftime("%Y-%m-%dT%H:%M:%S"), "sortBy": "popularity",
            "language": "en", "pageSize": 30, "apiKey": self.s.newsapi_key})
        return [Article(a["title"], strip_html(a.get("description") or ""), a["url"], parse_date(a.get("publishedAt")),
                        (a.get("source") or {}).get("name") or "NewsAPI", "newsapi")
                for a in self._ok(r).json().get("articles", []) if a.get("title") and a["title"] != "[Removed]"]

    def _gnews(self, topic, since):
        if not self.s.gnews_key:
            return []
        r = get("https://gnews.io/api/v4/search", {
            "q": topic, "lang": "en", "max": 30, "token": self.s.gnews_key,
            "from": since.strftime("%Y-%m-%dT%H:%M:%SZ")})
        return [Article(a.get("title", ""), strip_html(a.get("description") or ""), a.get("url", ""),
                        parse_date(a.get("publishedAt")), (a.get("source") or {}).get("name", "GNews"), "gnews")
                for a in self._ok(r).json().get("articles", [])]

    def _arxiv(self, topic, since):
        """Latest research papers on the topic (no key needed). Papers appear in batches, so look back a week."""
        q = quote_plus(f'all:"{topic}"')
        r = get(f"https://export.arxiv.org/api/query?search_query={q}&start=0&max_results=6"
                "&sortBy=submittedDate&sortOrder=descending", timeout=20, tries=1)
        week = datetime.now(timezone.utc) - timedelta(days=7)
        out = []
        for e in feedparser.parse(self._ok(r).content).entries:
            published = parse_date(getattr(e, "published", None))
            if published and published >= min(since, week):
                out.append(Article(strip_html(e.title), strip_html(getattr(e, "summary", "")), e.link,
                                   published, "arXiv (research)", "arxiv"))
        return out

    def _feed(self, url, topic, check_relevance, label=None):
        r = get(url, timeout=12, tries=1)
        out = []
        for e in feedparser.parse(r.content).entries[:40]:
            title = strip_html(getattr(e, "title", ""))
            desc = strip_html(getattr(e, "summary", "") or getattr(e, "description", ""))
            if not title or (check_relevance and not relevant(topic, f"{title} {desc}")):
                continue
            src = label or (e.get("source") or {}).get("title") or url.split("/")[2]
            if label:  # Google News appends " - Publisher" to titles
                title = re.sub(r"\s+-\s+[^-]+$", "", title)
                desc = "" if similar(desc, title) else desc
            out.append(Article(title, desc, getattr(e, "link", ""),
                               parse_date(getattr(e, "published_parsed", None) or getattr(e, "published", None)),
                               (e.get("source") or {}).get("title") or src, "rss"))
        return out

    def _rss(self, topic, days):
        gn = f"https://news.google.com/rss/search?q={quote_plus(topic)}+when:{max(1, days)}d&hl=en-US&gl=US&ceid=US:en"
        jobs = [(gn, False, "Google News")] + [(u, True, None) for u in RSS_FEEDS]
        return jobs

    def _safe(self, name, fn, *args):
        try:
            items = fn(*args)
            self.log(f"[news] {name}: {len(items)}")
            return items
        except Exception as exc:
            self.log(f"[news] {name} failed: {type(exc).__name__}: {str(exc)[:100]}")
            return []

    # ---- public -----------------------------------------------------------
    def collect(self, topic: str, days: int) -> List[Article]:
        now = datetime.now(timezone.utc)
        since = now - timedelta(days=days)
        with ThreadPoolExecutor(max_workers=8) as pool:
            api_jobs = [pool.submit(self._safe, n, f, topic, since)
                        for n, f in (("NewsAPI", self._newsapi), ("GNews", self._gnews), ("arXiv", self._arxiv))]
            feed_jobs = [pool.submit(self._safe, u.split("/")[2], self._feed, u, topic, chk, lab)
                         for u, chk, lab in self._rss(topic, days)]
            articles = [a for j in api_jobs + feed_jobs for a in j.result()]
        articles = [a for a in articles if a.title and a.url and (a.published is None or a.published >= since)]
        articles = deduplicate(sorted(articles, key=lambda a: a.published or since, reverse=True))
        for a in articles:
            a.score = score(a, topic, days * 24, now)
        return sorted(articles, key=lambda a: a.score, reverse=True)

    def pick(self, topic: str, history, days: int = 1, limit: int = 20, max_papers: int = 4) -> List[Article]:
        """Step 1: the top `limit` latest news items and research papers not yet covered. Widens the time
        window if nothing fresh is found. The whole fresh pool is kept in `self.pool` for later research."""
        for window in sorted({days, days * 3, 7}):
            ranked = self.collect(topic, window)
            fresh = [a for a in ranked if not history.is_processed(a.url, a.title)]
            self.log(f"[news] window={window}d: {len(ranked)} unique, {len(fresh)} not yet covered")
            if fresh:
                self.pool = fresh
                top, papers = [], 0
                for a in fresh:                          # news first; only a few papers, so they don't crowd it out
                    if a.api == "arxiv":
                        if papers >= max_papers:
                            continue
                        papers += 1
                    top.append(a)
                    if len(top) == limit:
                        break
                return top
        self.pool = []
        return []
