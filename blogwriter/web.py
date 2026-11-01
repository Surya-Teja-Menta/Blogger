"""Web access helpers: text cleaning, page fetching and search (DuckDuckGo, Wikipedia fallback)."""
import html
import re
import time
from dataclasses import dataclass
from typing import List
from urllib.parse import urlsplit, urlunsplit

import requests

UA = {"User-Agent": "Mozilla/5.0 (compatible; BlogWriterBot/2.0)"}


def strip_html(text: str) -> str:
    text = re.sub(r"<(script|style).*?</\1>", " ", text or "", flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def normalize_url(url: str) -> str:
    """Canonical form for duplicate detection (drops query, fragment, www, trailing slash)."""
    try:
        p = urlsplit((url or "").strip())
    except ValueError:
        return (url or "").strip().lower()
    host = p.netloc.lower().removeprefix("www.")
    return urlunsplit(("", host, p.path.rstrip("/").lower(), "", "")).lstrip("/")


def get(url: str, params: dict = None, timeout: int = 15, tries: int = 2) -> requests.Response:
    """GET with a short backoff on rate limits / server errors."""
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 504) and i < tries - 1:
                time.sleep(2 * (i + 1))
                continue
            return r
        except requests.RequestException as exc:
            last = exc
            time.sleep(1)
    raise last or RuntimeError("request failed")


def fetch_text(url: str, limit: int = 6000) -> str:
    """Best-effort readable text of an article page; '' when unavailable."""
    try:
        r = get(url, timeout=12, tries=1)
        if r.status_code != 200 or "html" not in r.headers.get("content-type", ""):
            return ""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "aside", "form", "header"]):
            tag.decompose()
        paras = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        text = " ".join(p for p in paras if len(p) > 60)
        return text[:limit] if len(text) > 400 else ""
    except Exception:
        return ""


@dataclass
class Source:
    title: str
    url: str
    snippet: str


def wikipedia_leads(query: str, n: int = 3) -> List[tuple]:
    """Encyclopedia background: (title, url, lead-section text) for the best Wikipedia matches. Never raises."""
    try:
        r = get("https://en.wikipedia.org/w/api.php", params={
            "action": "query", "format": "json", "generator": "search", "gsrsearch": query, "gsrlimit": n,
            "prop": "extracts|info", "exintro": 1, "explaintext": 1, "exlimit": n, "inprop": "url"})
        pages = r.json().get("query", {}).get("pages", {})
        found = sorted(pages.values(), key=lambda p: p.get("index", 99))
        return [(p["title"], p.get("fullurl", ""), (p.get("extract") or "")[:6000])
                for p in found if p.get("extract") and p.get("fullurl")]
    except Exception:
        return []


def web_search(query: str, n: int = 5, timelimit: str = None) -> List[Source]:
    """DuckDuckGo text + news search, falling back to Wikipedia. `timelimit` is d/w/m/y (day..year) to restrict
    how old results may be. Never raises."""
    results: List[Source] = []
    try:
        from ddgs import DDGS
        d = DDGS()
        for hit in (d.text(query, max_results=n, timelimit=timelimit) or []):
            results.append(Source(hit.get("title", ""), hit.get("href", ""), strip_html(hit.get("body", ""))))
        if timelimit in (None, "d", "w", "m"):           # the news index only supports up to a month
            for hit in (d.news(query, max_results=max(2, n // 2), timelimit=timelimit) or []):
                results.append(Source(hit.get("title", ""), hit.get("url", ""), strip_html(hit.get("body", ""))))
    except Exception:
        pass
    if not results:
        try:
            r = get("https://en.wikipedia.org/w/api.php", params={
                "action": "query", "list": "search", "srsearch": query, "srlimit": n, "format": "json"})
            for hit in r.json().get("query", {}).get("search", []):
                title = hit["title"]
                results.append(Source(title, "https://en.wikipedia.org/wiki/" + title.replace(" ", "_"),
                                      strip_html(hit.get("snippet", ""))))
        except Exception:
            pass
    seen, unique = set(), []
    for s in results:
        key = normalize_url(s.url)
        if s.url.startswith("http") and key not in seen and (s.snippet or s.title):
            seen.add(key)
            unique.append(s)
    return unique[:n + 2]
