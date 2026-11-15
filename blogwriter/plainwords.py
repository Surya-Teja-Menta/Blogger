"""Plain spoken English, and a proper introduction.

The owner heard two things in a finished video: it went straight to the topic with no introduction, and the words were
bookish, "the AI way" ("experiments earn their status as the gold standard"). The writer's prompt already asks for
both (video.py VOICE and WELCOME), but the models ignore it, and nothing checked. Now the finished script is checked:
a lesson that does not welcome the viewer in its first two lines gets four introduction shots written for it, and every
line goes through a plain-English rewrite plus a fixed list of word swaps that no model can skip."""
import re
from typing import Dict, List

# word or phrase -> the plain one. Whole words only; the case of the first letter is kept.
SWAPS: Dict[str, str] = {
    "utilize": "use", "utilise": "use", "utilizes": "uses", "utilises": "uses", "utilizing": "using", "utilising": "using",
    "leverage": "use", "leverages": "uses", "leveraging": "using", "facilitate": "help", "facilitates": "helps",
    "demonstrate": "show", "demonstrates": "shows", "demonstrated": "showed", "commence": "start", "commences": "starts",
    "subsequently": "then", "consequently": "so", "furthermore": "also", "moreover": "also", "additionally": "also",
    "therefore": "so", "thus": "so", "hence": "so", "numerous": "many", "approximately": "about", "ascertain": "find out",
    "endeavor": "try", "endeavour": "try", "paramount": "the most important thing", "pivotal": "key", "crucial": "key",
    "robust": "solid", "comprehensive": "full", "seamless": "smooth", "seamlessly": "smoothly", "plethora": "lot",
    "myriad": "many", "tapestry": "mix", "realm": "world", "paradigm": "way of thinking", "delve into": "dig into",
    "delve": "dig", "delves": "digs", "in essence": "basically", "essentially": "basically", "fundamentally": "basically",
    "it is worth noting that": "", "it's worth noting that": "", "it is important to note that": "",
    "it's important to note that": "", "in conclusion": "so", "in summary": "so", "to summarize": "so",
    "a testament to": "proof of", "gold standard": "best test we have", "garner": "get", "garners": "gets",
    "bolster": "boost", "bolsters": "boosts", "underscore": "show", "underscores": "shows", "elucidate": "explain",
    "mitigate": "reduce", "mitigates": "reduces", "optimal": "best", "subsequent": "next", "prior to": "before",
    "in order to": "to", "whilst": "while", "amongst": "among", "ensure": "make sure", "ensures": "makes sure",
}
_SWAP = re.compile(r"\b(" + "|".join(sorted(map(re.escape, SWAPS), key=len, reverse=True)) + r")\b", re.I)


def plainer(text: str) -> str:
    """The text with the bookish words swapped for plain ones (a capital stays a capital; a removed opening phrase
    like "It is worth noting that" hands its capital to the next word)."""
    def swap(m):
        new = SWAPS[m.group(1).lower()]
        if not new:
            return "§" if m.group(1)[:1].isupper() else ""
        return new[:1].upper() + new[1:] if m.group(1)[:1].isupper() else new
    out = re.sub(r"§\s*(.)", lambda m: m.group(1).upper(), _SWAP.sub(swap, text))
    return re.sub(r"\s+([,.;:!?])", r"\1", re.sub(r"\s{2,}", " ", out).strip())


def has_welcome(lines: List[str]) -> bool:
    """Does the viewer get welcomed in the first two lines?"""
    return any(re.search(r"\bwelcome\b", line, re.I) for line in lines[:2])


PLAIN = """These are the narration lines of an explainer video, one per shot, in order, read aloud. Rewrite them in plain
spoken English: how a friendly person explains it to a friend over coffee.
- Short, common words. Say "use", not "utilise"; "show", not "demonstrate"; "big", not "significant"; "so", not
  "therefore". Most sentences under 15 words. Contractions are good (it's, don't, you're).
- No essay or textbook phrasing: no "moreover", "furthermore", "in essence", "it is worth noting", "plays a crucial
  role", "delve", "landscape", "realm", "tapestry", "leverage", "ensure", "robust". No list of three fancy adjectives.
- Keep what the line says: its meaning, every number, name and technical term (a term stays, with its short
  explanation if it had one), and any joke. Add no new facts or numbers. A line that is already plain stays as it is.
- No line over 55 words; the first line stays at most 28 words.
Lines (JSON): {lines}
Reply with JSON: {{"lines": [exactly {n} strings, in the same order]}}"""

INTRO = """Write the first four lines of an explainer video called "{title}" on the channel {channel}. They are read aloud
over the first four shots, in plain spoken English, warm and calm, a friend explaining it. Each line is one to three
short sentences, at most 30 words. No numbers, no dates, no history, no jokes at the viewer's cost.
  1. Welcome the viewer to {channel} and name the topic: "Welcome to {channel}. Today, ..."
  2. WHAT IT IS: say what the topic is in one or two simple sentences, with a small everyday comparison.
  3. WHY IT MATTERS: what it lets us do, or what goes wrong without it, and where the viewer meets it in daily life.
  4. THE ROAD: one sentence on where we are going: first this, then that.
Facts you may lean on (do not copy their wording, add nothing that is not true):
{facts}
Reply with JSON: {{"lines": [exactly 4 strings], "headlines": [exactly 4 strings of at most 5 words: the topic's name, "What it is", "Why it matters", "The road"]}}"""
