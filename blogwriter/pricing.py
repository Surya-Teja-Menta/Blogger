"""What a study-notes report is worth. The price follows the topic's level and the size of the work behind it (printed
pages, verified facts), so a basic explainer is free and a deep, advanced report costs what the effort and the demand
justify. A fixed GUMROAD_PRICE (for example "99 INR") still overrides it."""
from typing import Tuple

# the prices a document may have, in rupees: a clean ladder instead of 117 or 283
LADDER = (0, 19, 29, 49, 79, 99, 149, 199, 299, 399, 499, 699, 999)
CAP = {"basic": 49, "intermediate": 199, "advanced": 999}
NICHE_DEMAND = {"general": 1.0, "tech": 1.15, "upsc": 1.2, "business": 1.25}   # exam and professional readers pay more


def snap(raw: float, cap: int = 999) -> int:
    """The nearest price on the ladder (a tie goes up), never above `cap`."""
    steps = [p for p in LADDER if p <= cap] or [0]
    return min(steps, key=lambda p: (abs(p - raw), -p))


def is_auto(text: str) -> bool:
    return str(text or "").strip().lower() in ("", "auto")


def price_for(level: str, niche: str, pages: int, facts: int, words: int = 0) -> Tuple[int, str]:
    """(price in rupees, the reason in one plain sentence). `pages` is the printed length (estimated from the
    word count when it is unknown), `facts` the number of verified facts the report stands on."""
    level = level if level in CAP else "intermediate"
    pages = pages or round(words / 300)
    if level == "basic":
        raw = 0 if pages <= 35 else 19
        why = ("a basic topic, explained for beginners: free, so the notes bring viewers to the channel" if raw == 0 else
               f"a basic topic, but a long {pages}-page report: a token price")
        return snap(raw, CAP[level]), why
    if level == "intermediate":
        raw = 29 + 3 * max(0, pages - 10) + 0.5 * max(0, facts - 25)
        base = "an intermediate topic"
    else:
        raw = 99 + 6 * max(0, pages - 10) + 2 * max(0, facts - 30)
        base = "an advanced topic"
    demand = NICHE_DEMAND.get(niche, 1.0)
    price = snap(raw * demand, CAP[level])
    extra = f", {niche} readers" if demand != 1.0 else ""
    return price, f"{base}: {pages} pages and {facts} verified facts{extra}"


def label(amount: float, currency: str = "inr") -> str:
    """"Free", "₹149" or "USD 3"."""
    if not amount:
        return "Free"
    return f"{'₹' if currency == 'inr' else currency.upper() + ' '}{amount:g}"
