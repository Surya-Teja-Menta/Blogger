"""Step 2: rank the candidate stories by how hot they are - which will attract the most readers and the most reaction."""
from typing import Callable, List

from .llm import LLMClient, LLMError
from .news import Article

CRITERIA = ("how strongly the story would ATTRACT readers and PROVOKE reactions (shares, comments, debate): "
            "conflict or controversy, human or emotional stakes, surprise or novelty, how many people it affects, "
            "urgency and timeliness, and whether people will have strong opinions about it")


def audience_rank(llm: LLMClient, items: List[Article], topic: str,
                  log: Callable[[str], None] = print, weight: float = 0.6) -> List[Article]:
    """Score every item 0-10 for audience appeal and combine it with the objective ranking
    (recency, how many outlets cover it, source credibility). Falls back to the objective ranking."""
    if not items:
        return items
    lines = "\n".join(f"{i}. {a.title} - {a.description[:200]} [{a.source}]" for i, a in enumerate(items, 1))
    prompt = (f"Topic: {topic}\nHere are {len(items)} current stories/research items:\n{lines}\n\n"
              f"Rate each from 0 to 10 for {CRITERIA}. Be discriminating: use the whole scale, and give low scores to "
              'routine, local or purely promotional items.\nReturn JSON: [{"id": 1, "score": 7, "why": "five words"}]')
    try:
        raw = llm.complete_json(prompt, max_tokens=2500, temperature=0.2)
    except LLMError as exc:
        log(f"[rank] audience scoring unavailable ({str(exc)[:80]}); using the objective ranking")
        return items
    by_id = {}
    for r in raw if isinstance(raw, list) else []:
        try:
            by_id[int(r["id"])] = (max(0.0, min(10.0, float(r["score"]))), str(r.get("why", ""))[:80])
        except (KeyError, TypeError, ValueError):
            continue
    for i, a in enumerate(items, 1):
        a.audience, a.why = by_id.get(i, (5.0, "not rated"))
        a.score = round((1 - weight) * min(a.score, 1.0) + weight * a.audience / 10, 4)
    return sorted(items, key=lambda a: a.score, reverse=True)
