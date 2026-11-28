"""Hashtag research: which tags people actually search and follow for this topic right now.

Two free sources, no key needed:
  * YouTube's own search suggestions (what viewers type for the topic, in the order YouTube ranks them), asked for the topic
    and for a few ways people phrase it ("explained", "for beginners", "interview", "vs");
  * Google Trends' "trending now" list (country by country): a trending search is only used when it is about this topic,
    because a tag that has nothing to do with the video is spam and costs reach.
The result (plan["trend"]) feeds the hashtags under the title of the video and of its Short, and the hidden tags. Never
raises: with no network the video keeps the tags its writer chose."""
import re
from typing import Callable, Dict, List

from .web import get

SUGGEST = "https://suggestqueries.google.com/complete/search"
TRENDS = "https://trends.google.com/trending/rss"
GEOS = ("US", "IN", "GB")
FORMS = ("{t}", "{t} explained", "{t} for beginners", "{t} interview", "how {t} works", "{t} vs")
STOP = {"the", "a", "an", "of", "and", "or", "to", "in", "on", "for", "with", "is", "are", "how", "why", "what", "your", "you", "do", "does"}


def core(title: str) -> str:
    """The topic's key words, short enough for a search ("System Design: Consistent Hashing, Rings and Keys: How Data Finds
    Its Server" -> "Consistent Hashing"; "Mean, Median and Mode: Which Average Lies?" -> "Mean Median and Mode")."""
    parts = [p.strip() for p in re.split(r"\s*[:|—]\s*", title) if p.strip()]
    if not parts:
        return ""
    lead = len(parts) > 2 or (len(parts) == 2 and len(parts[0].split()) <= 2)       # "System Design: Consistent Hashing, ..."
    pick = re.split(r",\s", parts[1])[0] if lead else parts[0]
    return " ".join(re.findall(r"[A-Za-z0-9'+#.]+", pick)[:5])


def hashtag(phrase: str, longest: int = 28) -> str:
    """"standard deviation" -> "#StandardDeviation" ("" if it is too long or has nothing to say)."""
    words = re.findall(r"[A-Za-z0-9]+", phrase)
    h = "#" + "".join(w[:1].upper() + w[1:] for w in words)
    return h if 3 < len(h) <= longest and not h[1:].isdigit() else ""


def suggestions(query: str) -> List[str]:
    """YouTube's search suggestions for a query, best first ([] on any failure)."""
    try:
        r = get(SUGGEST, params={"client": "firefox", "ds": "yt", "q": query}, timeout=8, tries=1)
        data = r.json()
        return [str(x) for x in data[1]] if isinstance(data, list) and len(data) > 1 else []
    except Exception:
        return []


def trending(geo: str) -> List[str]:
    """What is trending in a country's Google searches today ([] on any failure)."""
    try:
        r = get(TRENDS, params={"geo": geo}, timeout=10, tries=1)
        return [re.sub(r"<!\[CDATA\[|\]\]>", "", t).strip() for t in re.findall(r"<item>\s*<title>(.*?)</title>", r.text, re.S)]
    except Exception:
        return []


def words_of(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP and len(w) > 1}


# words a suggestion may add to the topic and still be a fair hashtag (never a channel's or a person's name)
SAFE = {"explained", "algorithm", "algorithms", "interview", "questions", "system", "design", "python", "java", "basics", "beginners",
        "introduction", "examples", "example", "practice", "tutorial", "vs", "intuition", "formula", "formulas", "statistics",
        "machine", "learning", "data", "science", "architecture", "distributed", "database", "databases", "cache", "caching"}


def rank(topic: str, found: Dict[str, List[str]], trends: List[str], track: str = "") -> List[str]:
    """Hashtags, best first: the topic itself, the course's own tag ("System Design" -> #SystemDesign), then the phrases YouTube
    suggests most often and highest, with a bonus for one that is also trending now. A suggestion is used only when it is
    the topic plus plain descriptive words (no names, no questions), and short enough to read."""
    key = words_of(topic)
    score: Dict[str, float] = {}
    for query, phrases in found.items():
        for pos, p in enumerate(phrases[:8]):
            w = words_of(p)
            extra = w - key
            if not (w & key) or p.lower().split()[0] in ("how", "what", "why", "when") or len(p.split()) > 4 or not extra <= SAFE:
                continue
            score[p.strip().lower()] = score.get(p.strip().lower(), 0.0) + 1.0 / (pos + 1)
    for phrase in list(score):
        if any(words_of(t) >= key and (words_of(phrase) - key) & words_of(t) for t in trends):          # trending, about the topic, and says what this phrase adds
            score[phrase] += 1.5
    out = [hashtag(topic), hashtag(track)]
    for phrase, _ in sorted(score.items(), key=lambda kv: -kv[1]):
        out.append(hashtag(phrase))
    seen: List[str] = []
    for h in out:
        if h and h.lower() not in {x.lower() for x in seen}:
            seen.append(h)
    return seen


def research(title: str, tags: List[str], log: Callable[[str], None] = print, asked: str = "") -> dict:
    """{"hashtags": [...up to 8, best first...], "phrases": [...the suggestions people type...], "trending": [...]} for the
    video titled `title`. Never raises."""
    topic = core(title)
    if not topic:
        return {}
    found = {q: suggestions(q) for q in dict.fromkeys(f.format(t=topic) for f in FORMS)}
    trends = [t for geo in GEOS for t in trending(geo)]
    mine = words_of(topic + " " + " ".join(tags))
    about = [t for t in trends if len(words_of(t) & mine) >= min(2, max(1, len(words_of(t))))]      # trending AND about this topic
    first = re.split(r"\s*[:|—]\s*", asked or title)[0].strip()      # the topic asked for keeps its course ("Statistics: ...")
    track = first if 0 < len(first.split()) <= 3 and first != topic else ""             # "System Design", "Statistics"
    tagged = rank(topic, found, about, track)[:8]
    phrases = [p for ps in found.values() for p in ps[:3]]
    out = {"hashtags": tagged, "phrases": list(dict.fromkeys(phrases))[:10], "trending": about[:5]}
    log(f"[tags] searched for {topic!r}: {len(phrases)} suggestions, {len(trends)} trending searches ({len(about)} on topic) -> "
        + (" ".join(tagged) or "nothing found"))
    return out
