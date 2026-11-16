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
    "endeavor": "try", "endeavour": "try", "paramount": "most important", "pivotal": "key", "crucial": "key",
    "robust": "solid", "comprehensive": "full", "seamless": "smooth", "seamlessly": "smoothly", "plethora": "lot",
    "myriad": "many", "tapestry": "mix", "realm": "world", "paradigm": "way of thinking", "delve into": "dig into",
    "delve": "dig", "delves": "digs", "in essence": "basically", "essentially": "basically", "fundamentally": "basically",
    "it is worth noting that": "", "it's worth noting that": "", "it is important to note that": "",
    "it's important to note that": "", "in conclusion": "so", "in summary": "so", "to summarize": "so",
    "a testament to": "proof of", "garner": "get", "garners": "gets",
    "bolster": "boost", "bolsters": "boosts", "underscore": "show", "underscores": "shows", "elucidate": "explain",
    "mitigate": "reduce", "mitigates": "reduces", "optimal": "best", "subsequent": "next", "prior to": "before",
    "in order to": "to", "whilst": "while", "amongst": "among", "ensure that": "make sure that", "ensures that": "makes sure that",
    "typically": "usually", "primarily": "mostly", "obtain": "get", "obtains": "gets", "obtained": "got",
    "require": "need", "requires": "needs", "required": "needed", "requiring": "needing", "sufficient": "enough",
    "assist": "help", "assists": "helps", "attempt": "try", "attempts": "tries", "regarding": "about", "whereas": "but",
    "a sufficient": "enough", "an initial": "a first", "an optimal": "the best", "an attempt": "a try", "a notion": "an idea",
    "initial": "first", "initially": "at first", "various": "different",
    "in addition": "also", "a variety of": "lots of",
    "a number of": "some", "due to the fact that": "because", "in the event that": "if", "with respect to": "about",
    "is able to": "can", "has the ability to": "can", "as a result": "so",
    "reside": "live", "resides": "lives", "inquire": "ask", "terminate": "end", "terminates": "ends", "merely": "just",
    "notion": "idea", "concept of": "idea of", "implement": "build",
    "implements": "builds", "prevalent": "common", "predominantly": "mostly", "nevertheless": "still",
    "consequently,": "so,", "in other words": "put simply", "that is to say": "put simply",
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


EASY = set("""everything everyone everybody everywhere something anything another different probably usually interesting important
example together tomorrow yesterday favorite family animal beautiful computer internet telephone hospital restaurant camera
potato tomato banana energy memory average million billion probably actually basically obviously especially suddenly
definitely absolutely carefully completely exactly immediately seriously unfortunately generally eventually""".split())


def syllables(word: str) -> int:
    """A rough syllable count (vowel groups, a silent final e dropped); good enough to tell short words from long ones."""
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    n = len(re.findall(r"[aeiouy]+", w))
    if w.endswith("e") and not w.endswith(("le", "ee")) and n > 1:
        n -= 1
    if w.endswith("ed") and not w.endswith(("ted", "ded")) and n > 1:
        n -= 1
    return max(1, n)


def hard_words(text: str, keep: str = "") -> List[str]:
    """The words a ten-year-old would trip on: three or more syllables, not a common one, not a name in the middle of a
    sentence, and not part of `keep` (the topic's own terms, which stay, explained)."""
    own = set(re.findall(r"[a-z]+", keep.lower()))
    out = []
    for k, m in enumerate(re.finditer(r"[A-Za-z][A-Za-z'-]*", text)):
        w = m.group().lower().strip("'-")
        named = m.group()[0].isupper() and m.start() > 0 and not re.search(r"[.!?]\s*$", text[:m.start()])
        if syllables(w) >= 3 and w not in EASY and w not in own and not named:
            out.append(w)
    return out


def grade(text: str) -> float:
    """Flesch-Kincaid grade of the text: about 5 is how a friend talks, 10 and up is a textbook."""
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", text)
    if not words:
        return 0.0
    sentences = max(1, len(re.findall(r"[.!?]+(?:\s|$)", text)))
    return round(0.39 * len(words) / sentences + 11.8 * sum(syllables(w) for w in words) / len(words) - 15.59, 1)


STYLE = """How a line should sound (this is the most important rule of the whole video):
- Write for a curious 10-year-old, and for any normal adult who has never studied the subject. Short, everyday words. If a
  smaller word exists, use it: "use", "show", "get", "help", "start", "enough", "mostly", "a lot", "so", "but".
- Short sentences: most under 12 words, none over 22. One idea per sentence. Say it the way you would say it out loud.
- Talk TO the viewer: "you", "we", "let's". Contractions are good (it's, don't, you're, that's).
- A definition is never a textbook sentence. Not "X is a measure of the dispersion of Y", but "X tells you how spread out
  Y is". Start from something the viewer has seen, then name the idea.
- A technical word is allowed only when the topic needs it, and only after the idea is clear; explain it right there in
  plain words ("the median: the middle number when you line them up").
- Plain, not fancy: no "moreover", "furthermore", "thus", "hence", "in essence", "crucial", "pivotal", "robust", "utilise",
  "leverage", "facilitate", "demonstrate", "comprehensive", "fundamental", "significant" (unless it is the statistical term),
  "numerous", "various", "approximately", "subsequently", "individuals", "regarding", "in order to", "it is worth noting".
Bookish -> how you would say it:
  "Experiments earn their status as the gold standard by controlling variables."  ->  "Experiments are the fairest test, because you change one thing and keep everything else the same."
  "The mean is susceptible to distortion by outliers."  ->  "One huge number can drag the average way off."
  "This phenomenon occurs when the sample is insufficiently representative."  ->  "This happens when your sample doesn't look like everyone else."
  "We can utilise this to ascertain the underlying relationship."  ->  "We can use this to find out what's really going on."
  "Consequently, the probability diminishes substantially."  ->  "So the chance drops a lot."
"""

def has_welcome(lines: List[str]) -> bool:
    """Does the viewer get welcomed in the first two lines?"""
    return any(re.search(r"\bwelcome\b", line, re.I) for line in lines[:2])


PLAIN = """These are the narration lines of an explainer video, one per shot, in order, read aloud. Rewrite them in plain
spoken English: how a friendly person explains it to a friend over coffee.
""" + STYLE + """- Keep what the line says: its meaning, every number, name and technical term (a term stays, with its short
  explanation if it had one), and any joke. Add no new facts or numbers. A line that is already plain stays as it is.
- No line over 55 words; the first line stays at most 28 words.
Lines (JSON): {lines}
Reply with JSON: {{"lines": [exactly {n} strings, in the same order]}}"""

SIMPLER = """These are the narration lines of an explainer video, one per shot, in order, read aloud. They are STILL too hard
for a 10-year-old. Each line below is followed by the hard words in it. Rewrite every line so a child could follow it: swap
each hard word for a short everyday one (or say it with other words), cut long sentences in two, and turn textbook
definitions into "think of it like ...". The topic's own technical term may stay, but only with a plain explanation beside it.
""" + STYLE + """- Keep the meaning, every number and name, and any joke. Add no new facts. No line over 55 words; the first stays at most 28.
Lines with their hard words (JSON): {lines}
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

INTRO = INTRO.replace("Facts you may lean on", STYLE + "Facts you may lean on")      # the four opening lines follow the same rules
