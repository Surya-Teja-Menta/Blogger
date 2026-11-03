"""Content generation (chapters, blog, video scripts) plus output cleaning and validation, so model
chatter, planning notes and off-topic text never reach the saved files."""
import re
from typing import Callable, List, Optional

from .config import Mode
from .llm import LLMClient, LLMError
from .research import Dossier, quote_supported

# ---- cleaning ---------------------------------------------------------------
PREAMBLE = re.compile(r"^\W*(okay|ok|sure|certainly|alright|absolutely|here(?:'|’)?s|here is|here are|let(?:'|’)?s|"
                      r"i(?:'|’)?ll|i will|i(?:'|’)?m (?:going|launching|starting)|first,? i|below is)\b", re.I)
TAIL = re.compile(r"^[\W_]*(\(?notes?\b|next steps|word count|end of|revision|do you have|would you like|"
                  r"let me know|ready to|\(this is|\(i(?:'|’)?ve|i(?:'|’)?ll now|i will now)", re.I)
INLINE = [re.compile(r"\(\s*word count:?\s*~?\d+\s*\)", re.I), re.compile(r"\(\s*~?\d+\s*words?\s*\)", re.I),
          re.compile(r"\[\d+(?:\s*,\s*\d+)*\]")]                      # [3] / [2, 5] citation markers
META_LEFTOVER = re.compile(r"\bnext steps\b|\bword count\b|as an ai\b|\bfeedback\b|\bthe user\b|\bchapter plan\b", re.I)


def clean_output(text: str) -> str:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text.replace("\r", "")) if p.strip()]
    while paras and (PREAMBLE.match(paras[0]) or re.fullmatch(r"[-*_\s]+", paras[0])):
        paras.pop(0)
    for i in range(max(1, len(paras) // 3), len(paras)):        # never cut the opening third
        if TAIL.match(paras[i]):
            paras = paras[:i]
            break
    out = "\n\n".join(paras)
    for pat in INLINE:
        out = pat.sub("", out)
    out = re.sub(r"[ \t]+([.,;:])", r"\1", out)
    out = re.sub(r"(?:\n\s*---\s*)+$", "", out)                 # trailing rule left after a cut
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def words(text: str) -> int:
    return len(re.findall(r"\b[\w'’-]+\b", text))


def keywords(title: str) -> set:
    stop = {"that", "with", "from", "this", "will", "have", "after", "their", "about", "could", "would", "into", "over"}
    return {w for w in re.findall(r"[a-z]{4,}", title.lower()) if w not in stop}


def validate(text: str, min_w: int, max_w: int, title: str) -> List[str]:
    issues, n = [], words(text)
    if n < min_w:
        issues.append(f"too short ({n} words; need at least {min_w})")
    if n > max_w:
        issues.append(f"too long ({n} words; keep under {max_w})")
    if keywords(title) and not any(k in text.lower() for k in keywords(title)):
        issues.append("does not mention the story's subject")
    if META_LEFTOVER.search(text):
        issues.append("contains meta-commentary instead of just the piece")
    return issues


NUM = re.compile(r"\d[\d,]*\.?\d*")
# sentence end: .!? + space + capital, but not after common abbreviations ("St. Lawrence", "U.S. Customs")
SENTENCE_END = re.compile(r"(?<=[.!?])(?<!\bSt\.)(?<!\bMr\.)(?<!\bMrs\.)(?<!\bMs\.)(?<!\bDr\.)(?<!\bMt\.)"
                          r"(?<!\bvs\.)(?<!\bNo\.)(?<!\bInc\.)(?<!\bCo\.)(?<!\bLtd\.)(?<!U\.S\.)(?<!U\.K\.)"
                          r"(?<!U\.N\.)(?<!\bJr\.)(?<!\bSr\.)\s+(?=[A-Z\"“'‘(\[])")


def _nums(text: str) -> set:
    return {n.replace(",", "").rstrip(".") for n in NUM.findall(text or "")}


def strip_unsupported_numbers(text: str, allowed_text: str) -> str:
    """Mechanical guard against invented figures and dates: delete every sentence that contains a number
    (or year) found nowhere in the verified material. Headings are left alone; in a table, a body row with an
    untraceable number is dropped (the header and separator rows stay)."""
    allowed = _nums(allowed_text)
    out = []
    for para in text.split("\n\n"):
        if para.lstrip().startswith("#"):
            out.append(para)
            continue
        if para.lstrip().startswith("|"):
            rows = para.strip().splitlines()
            out.append("\n".join(rows[:2] + [r for r in rows[2:] if _nums(r) <= allowed]))
            continue
        kept = [s for s in SENTENCE_END.split(para) if _nums(s) <= allowed]
        if kept:
            out.append(" ".join(kept))
    return "\n\n".join(out)


def strip_unverified_quotes(text: str, allowed_text: str) -> str:
    """Drop '> "..."' pull quotes whose words are not found in the verified material."""
    out = []
    for para in text.split("\n\n"):
        if para.lstrip().startswith(">"):
            quoted = re.findall(r"[\"“]([^\"”]{25,})[\"”]", para)
            if not quoted or not all(quote_supported(q, allowed_text) for q in quoted):
                continue
        out.append(para)
    return "\n\n".join(out)


def trim_to_words(text: str, limit: int) -> str:
    """Hard cap at a paragraph (then sentence) boundary."""
    if words(text) <= limit:
        return text
    out = ""
    for para in text.split("\n\n"):
        if words(out + para) > limit:
            break
        out += para + "\n\n"
    if not out:
        for sent in re.split(r"(?<=[.!?])\s+", text):
            if words(out + sent) > limit:
                break
            out += sent + " "
    return out.strip()


# ---- plain, human style --------------------------------------------------------
# Words and phrases that make text read as machine-written; a draft that leans on them is sent back.
STOCK_PHRASES = ["delve", "tapestry", "testament to", "navigate the", "navigating the", "multifaceted", "intricate",
                 "pivotal", "crucial role", "underscore", "underscores", "underscoring", "realm", "landscape of",
                 "ever-evolving", "fast-paced", "in today's world", "game-changer", "game changer", "stark reminder",
                 "it is worth noting", "it's worth noting", "it is important to note", "plays a key role",
                 "a significant milestone", "seamless", "leverage", "bolster", "foster", "robust", "paradigm",
                 "in conclusion", "in summary", "moreover", "furthermore", "additionally", "notably", "nuanced",
                 "shed light", "sheds light", "unwavering", "resonate", "embark", "harness", "myriad", "plethora",
                 "a new era", "at the heart of", "only time will tell", "remains to be seen", "serves as a reminder"]

PLAIN_STYLE = (
    "STYLE - write like an experienced human reporter explaining the story to a smart friend:\n"
    "- Simple, everyday words. Pick the short common word: 'use' not 'utilise', 'help' not 'facilitate', "
    "'start' not 'commence', 'show' not 'underscore'. If a technical term is needed, explain it in a few plain words.\n"
    "- Mostly short sentences, one idea each, with an occasional longer one so it does not sound choppy. "
    "Readable by a 15-year-old.\n"
    "- Say things directly: 'Oil prices rose 8%', not 'Oil prices experienced a significant upward movement'. "
    "Active voice. Concrete names, numbers, places and dates instead of abstractions.\n"
    "- Never use these stock phrases or anything like them: " + ", ".join(f"'{p}'" for p in STOCK_PHRASES[:30]) +
    ". Do not start sentences with 'Moreover', 'Furthermore', 'Additionally' or 'Notably'.\n"
    "- No em dashes; use a full stop or a comma. No 'not only... but also', no 'it's not X, it's Y', no lists of "
    "three adjectives, no rhetorical questions you answer yourself, no grand closing line about the future.\n"
    "- Vary how paragraphs start. Not every paragraph needs a transition word.")


def stock_phrases(text: str) -> List[str]:
    """The machine-sounding stock phrases a text uses (whole words, case-insensitive)."""
    low = text.lower()
    return [p for p in STOCK_PHRASES if re.search(r"(?<![a-z])" + re.escape(p) + r"(?![a-z])", low)]


PLAIN_SWAPS = [(r"\butili[sz]e\b", "use"), (r"\butili[sz]es\b", "uses"), (r"\butili[sz]ed\b", "used"),
               (r"\butili[sz]ing\b", "using"), (r"\bcommence\b", "start"), (r"\bcommences\b", "starts"),
               (r"\bcommenced\b", "started"), (r"\bfacilitate\b", "help"), (r"\bfacilitates\b", "helps"),
               (r"\bfacilitated\b", "helped"), (r"(?<=\w) ?— ?(?=\w)", ", ")]
OPENER = re.compile(r"(^|\n|[.!?] )(?:Moreover|Furthermore|Additionally|Notably), (\w)")


def plain_words(text: str) -> str:
    """Mechanical last pass: swap a few stiff words for plain ones and drop filler sentence openers.
    Headings and quoted lines are left alone."""
    out = []
    for para in text.split("\n\n"):
        if not para.lstrip().startswith(("#", ">", "|")):
            for pat, rep in PLAIN_SWAPS:
                para = re.sub(pat, rep, para)
            para = OPENER.sub(lambda m: m.group(1) + m.group(2).upper(), para)
        out.append(para)
    return "\n\n".join(out)


# ---- prompts ----------------------------------------------------------------
SYSTEM = ("You are an experienced news reporter who writes clear, plain English that real people enjoy reading. "
          "Accuracy comes first, then clarity.\n" + PLAIN_STYLE + "\n"
          "HARD RULES: use ONLY the VERIFIED FACTS and article text in the research notes; never invent people, quotes, statistics, "
          "scenes or dialogue; never add a year or date the notes do not state; never describe what 'the article' or "
          "'the outlet' says unless ARTICLE TEXT is actually provided in the notes; if a detail is not in the notes, "
          "leave it out. Make no predictions or recommendations of your own: say what will or may happen only when "
          "the notes attribute that forecast to a named source, and otherwise say it is not yet known. Output ONLY the requested piece - no "
          "preamble, no notes, no word counts, no questions to the reader, no bracketed source numbers.")


# who the piece is for: added to the writer's instructions (the empty entries are the default reader)
LEVELS = {
    "basic": "LEVEL: a beginner. Assume no background: explain every term and acronym the first time it appears, "
             "give the context before the detail, and keep paragraphs short.",
    "intermediate": "",
    "advanced": "LEVEL: an expert. Skip basic explanations, use the precise terms of the field without defining "
                "common ones, and pack more figures, comparisons and analysis into each paragraph (still only from "
                "the notes).",
}
NICHES = {
    "general": "",
    "upsc": "READER: a UPSC / State PSC civil-services aspirant. Make it exam-ready: name the constitutional "
            "articles, laws, schemes, government bodies, reports and indices involved whenever the notes state them, "
            "set out both sides of every debate, and keep facts crisp enough to revise from.",
    "business": "READER: a founder or business manager. Bring out what the facts mean for costs, prices, demand, "
                "competitors, supply chains and regulation, as far as the notes support it.",
    "tech": "READER: an engineer or product builder. Explain how the technology works and what it changes for "
            "people who build products, as far as the notes support it.",
}
LANGS = {"en": "English", "hi": "Hindi", "te": "Telugu", "kn": "Kannada", "ta": "Tamil"}


def audience(level: str = "intermediate", niche: str = "general") -> str:
    """Extra writer instructions for the requested reader level and niche ('' for the default reader)."""
    parts = [p for p in (NICHES.get(niche, ""), LEVELS.get(level, "")) if p]
    return ("\n" + "\n".join(parts)) if parts else ""


class Writer:
    def __init__(self, llm: LLMClient, log: Callable[[str], None] = print, reader: str = ""):
        self.llm = llm
        self.log = log
        self.reader = reader          # from audience(): level and niche instructions for every piece

    def translate(self, text: str, lang: str) -> str:
        """Translate a finished, fact-checked markdown piece section by section (facts are checked in English
        first, so translation never adds claims). A section that fails to translate stays in English."""
        if lang == "en" or not text.strip():
            return text
        name = LANGS.get(lang, lang)
        out = []
        for part in re.split(r"\n(?=#{1,3} )", text):
            if not part.strip():
                continue
            prompt = (f"Translate this markdown into {name}. Keep every markdown mark (#, **, >, |, -, links) and the "
                      "paragraph breaks exactly as they are. Keep all numbers as digits. Write names of people, "
                      f"places and organisations in {name} script, followed by the English name in brackets the first "
                      "time each appears. Translate faithfully: add, drop or explain nothing. Output only the "
                      f"translation.\n\n{part}")
            try:
                done = clean_output(self.llm.complete(prompt, max_tokens=max(800, words(part) * 5), temperature=0.2))
                out.append(done if words(done) >= 0.3 * words(part) else part)
            except LLMError:
                self.log(f"[writer] translation to {name} failed for one section; it stays in English")
                out.append(part)
        return "\n\n".join(out)

    def _generate(self, prompt: str, title: str, target: int, lo=0.7, hi=1.35, system=SYSTEM,
                  check_length=True) -> str:
        """Generate -> clean -> validate; retry once with the concrete problems fed back."""
        feedback, text = "", ""
        for attempt in range(2):
            raw = self.llm.complete(prompt + feedback, system=system + self.reader,
                                    max_tokens=max(600, int(target * 2.2)), temperature=0.75)
            text = clean_output(raw)
            issues = validate(text, int(target * lo) if check_length else 20,
                              int(target * hi) if check_length else 10 ** 6, title)
            stock = stock_phrases(text)
            if len(stock) >= 3:
                issues.append("sounds machine-written: replace these stock phrases with plain words - " + ", ".join(stock))
            if not issues:
                return text
            self.log(f"[writer] retry: {'; '.join(issues)}")
            feedback = ("\n\nYour previous attempt was rejected: " + "; ".join(issues) +
                        ". Rewrite the full piece fixing this.")
        return trim_to_words(text, int(target * hi)) if check_length else text

    def ground(self, text: str, notes: str, title: str, allowed: str = "", strict: bool = False) -> str:
        """Fact-check: an LLM pass deletes claims the notes do not support, then a mechanical pass deletes
        sentences with figures/dates that appear nowhere in the verified material."""
        checked = self._ground_llm(text, notes, title, strict)
        cleaned = strip_unsupported_numbers(strip_unverified_quotes(checked, allowed or notes), allowed or notes)
        if words(cleaned) < words(checked):
            self.log(f"[writer] number check removed {words(checked) - words(cleaned)} words with unverified figures")
        return plain_words(cleaned if (words(cleaned) >= 60 or strict) else checked)

    def _ground_llm(self, text: str, notes: str, title: str, strict: bool = False) -> str:
        """LLM fact-check pass: delete or rewrite every claim the research notes do not support.
        The result is kept only if it is still a substantial piece of writing."""
        prompt = (f"RESEARCH NOTES (the only allowed source of facts):\n{notes}\n\nDRAFT:\n{text}\n\n"
                  "Edit the DRAFT: remove or rewrite any sentence containing a fact, figure, date, name, motive, "
                  "interpretation (what an action 'signals', 'underscores' or 'positions'), invented scene-setting, "
                  "causal claim or background statement that is NOT supported by the RESEARCH NOTES (for example "
                  "who funds whom, historical comparisons, market data that the notes do not mention). Remove "
                  "references to text being cut off or to other chapters, and delete any sentence that only repeats a "
                  "fact already stated earlier in the draft. Keep every supported fact, the voice and "
                  "the heading. Do not add anything new. Return only the full edited piece.")
        try:
            edited = clean_output(self.llm.complete(prompt, system=SYSTEM, max_tokens=int(words(text) * 2.2) + 400,
                                                    temperature=0.2))
        except LLMError:
            self.log("[writer] grounding pass unavailable; keeping draft")
            return text
        # A shorter, supported piece beats a full-length one with invented facts, so only reject
        # results that are fragments or broken (not merely shorter).
        # an edit pass may only remove: growth means the model added unvetted material
        # (no topic-keyword check: this pass only removes, and a chapter on e.g. the people involved may name
        # them rather than the headline's words - rejecting it would ship the unchecked draft instead)
        issues = validate(edited, 20 if strict else 60, int(words(text) * 1.05), "")
        if not issues:
            self.log(f"[writer] grounding: {words(text)} -> {words(edited)} words")
            return edited
        if strict and words(edited) < 20:            # a chapter whose draft the fact-check emptied is dropped
            self.log("[writer] grounding left almost nothing; chapter dropped")
            return ""
        self.log(f"[writer] grounding result rejected ({'; '.join(issues)}); keeping draft")
        return text

    # The documentary follows a fixed story arc, so it is complete end to end: what happened, how it unfolded,
    # who is involved, where it comes from, what is at stake, what experts say, and what happens next.
    # (section role, research angles feeding it, what the chapter must achieve, minimum facts to earn a chapter)
    SECTIONS = [
        ("The Story", ["Story"], "What happened, told in full: every fact the reporting establishes.", 1),
        ("How It Unfolded", ["Timeline"], "The sequence of events, in order, with dates.", 3),
        ("The People and Powers Involved", ["Stakeholders"], "Who the actors are and what each wants.", 3),
        ("Why It Happened", ["Causes"], "The causes, motives and triggers behind the events.", 3),
        ("How It Works", ["Mechanism"], "The method, process or machinery behind the events.", 3),
        ("Roots: Background and Precedent", ["Historical", "Comparisons"], "How the situation came about.", 3),
        ("The Political Stakes", ["Political"], "Political and diplomatic consequences.", 3),
        ("The Economic Stakes", ["Economic"], "Economic and market consequences.", 3),
        ("The Human and Regional Impact", ["Social", "Geographic"], "Who is affected and where.", 3),
        ("Security and Legal Implications", ["Security", "Legal"], "Security, military, legal and regulatory consequences.", 3),
        ("Reactions at Home and Abroad", ["Reactions"], "How governments, markets and the public responded.", 3),
        ("The Immediate Effects", ["Short-term effects"], "What changed in the first days and weeks.", 3),
        ("The Long-Term Effects", ["Long-term effects"], "Lasting and structural consequences.", 3),
        ("Winners, Losers and Risks", ["Winners and losers", "Risks"], "Who gains, who loses, and what could go wrong.", 3),
        ("What the Experts Say", ["Expert views"], "Named analysts and officials, and what they argue.", 3),
        ("What Happens Next", ["Future outlook"], "Likely developments and open questions.", 3),
    ]

    # who / what / when / where / why / how, each answered from its own research angle
    FIVE_W = [("What happened", "Story"), ("Who is involved", "Stakeholders"), ("When it happened", "Timeline"),
              ("Where it matters", "Geographic"), ("Why it happened", "Causes"), ("How it happened", "Mechanism")]

    def at_a_glance(self, dossier: Dossier) -> Optional[dict]:
        """The opening chapter: the whole story in the six classic questions. None if the research cannot
        answer at least three of them."""
        groups = [(label, angle, dossier.facts_text(angle, 1300)) for label, angle in self.FIVE_W]
        groups = [g for g in groups if g[2]]
        if len(groups) < 3:
            return None
        notes = (f"STORY: {dossier.article['title']}\nPUBLISHED: {dossier.article['published'][:10]}\n"
                 f"ARTICLE TEXT: {dossier.core()[:1200]}\n\nVERIFIED FACTS, grouped by the question they answer:\n" +
                 "\n\n".join(f"{label.upper()}:\n{text}" for label, _, text in groups))
        labels = ", ".join(f"'### {label}'" for label, _, _ in groups)
        return {"title": "The Story at a Glance: Who, What, When, Where, Why and How",
                "focus": "The whole story in six questions.", "angles": [a for _, a, _ in groups],
                "facts": sum(dossier.count(a) for _, a, _ in groups), "notes": notes,
                "structure": f"Structure: one '### ' subheading per question, in this order: {labels}. Under each, "
                             "answer that question directly in one to three tight paragraphs using only the facts "
                             "listed under it. Skip any question whose facts are missing - do not guess."}

    def plan_documentary(self, dossier: Dossier, mode: Mode) -> List[dict]:
        """Chapters for the documentary: the fixed arc, minus sections the research could not support."""
        plan, thin = [], []
        for role, angles, focus, minimum in self.SECTIONS:
            n = dossier.count(angles)
            if n >= minimum:
                plan.append({"title": role, "focus": focus, "angles": angles, "facts": n})
            elif n:
                thin += angles                       # too little for its own chapter, but still verified
        if dossier.count(thin) >= 3:                 # ...so pool those facts into one closing chapter
            plan.append({"title": "Other Developments and Perspectives", "angles": thin, "facts": dossier.count(thin),
                         "focus": "Further verified facts and viewpoints that do not fit the chapters above."})
        plan = plan[:mode.chapters]
        if not plan:                                  # nothing section-specific: one chapter on everything verified
            plan = [{"title": "The Story", "focus": "Everything the research verified.", "angles": list(dossier.angles),
                     "facts": len(dossier.facts)}]
        # story-specific chapter titles (the role stays as the fallback if the model misbehaves)
        try:
            roles = "\n".join(f"{i + 1}. {c['title']} - {c['focus']}" for i, c in enumerate(plan))
            titles = self.llm.complete_json(
                f"{dossier.brief(1500)}\n\nGive each documentary chapter below a specific title in plain everyday words "
                f"that names the real people, places or events of THIS story (max 12 words), keeping its role. A title may only "
                f"claim what the chapter's role supports: no drama words (clash, battle, crisis, collapse) unless the "
                f"story itself uses them.\n{roles}\n\n"
                f"Return a JSON array of exactly {len(plan)} title strings.", max_tokens=500)
            if isinstance(titles, list) and len(titles) == len(plan) and all(isinstance(t, str) and t.strip() for t in titles):
                for c, t in zip(plan, titles):
                    c["title"] = t.strip().strip('"')
        except LLMError:
            self.log("[writer] chapter titles fell back to the standard documentary headings")
        return plan

    def chapter(self, dossier: Dossier, ch: dict, idx: int, plan: List[dict], mode: Mode) -> str:
        title = dossier.article["title"]
        prior = "; ".join(c["title"] for c in plan[:idx]) or "none"
        later = "; ".join(c["title"] for c in plan[idx + 1:]) or "none"
        # as long as the verified material for THIS chapter supports, up to the mode's ceiling
        target = max(150, min(mode.chapter_words, 40 * ch.get("facts", 5)))
        notes = ch.get("notes") or dossier.notes_for(ch["angles"])
        prompt = (f"{notes}\n\nWrite chapter {idx + 1} of a documentary report: \"{ch['title']}\".\n"
                  f"Role: {ch.get('focus', '')}\n"
                  f"Other chapters (do not repeat their material): before - {prior}; after - {later}\n\n"
                  f"Requirements: about {target} words; start with the line '## {ch['title']}', then on its own line "
                  "'**In brief:** ' followed by ONE plain sentence giving the chapter's main takeaway (a fact, not a "
                  "teaser), then the chapter itself. Cover EVERY fact "
                  "listed under VERIFIED FACTS - this chapter must leave nothing out - weaving them into a "
                  "coherent narrative (chronological where dates exist, grouping related facts).\n"
                  "Voice: a calm documentary narrator talking to an ordinary viewer, in simple everyday words. Open "
                  "on the single most striking verified detail, not a summary - no invented atmosphere (light, "
                  "weather, mood, 'tremors', 'tableaux') and no interpretation of motives or meaning the notes do not "
                  "state. Tell it the way a person would tell it: one point at a time, each paragraph moving the "
                  "story on; vary sentence length; active voice.\n"
                  "State each fact ONCE - never restate a fact already told in this chapter, even reworded. Do not "
                  "attribute every sentence: state established facts plainly, and attribute only quotes, opinions, "
                  "estimates and disputed claims - to the named person, government or organisation, never to a "
                  "website address. Sources are listed at the end of the report. If the notes contain a memorable "
                  "direct quote from a named person, you may set it once on its own line as '> \"quote\" - Name', "
                  "copied word for word. No closing summary paragraph ('In sum', 'In conclusion', 'Ultimately'); end "
                  "on a concrete fact or an open question. Where the facts are thin, say what is not yet known "
                  f"instead of inventing detail. Every paragraph must tie back to \"{title}\"."
                  + (f"\n{ch['structure']}" if ch.get("structure") else ""))
        draft = self._generate(prompt, title, target)
        return self.ground(draft, notes, title, dossier.allowed_text(), strict=True)

    def executive_summary(self, dossier: Dossier, chapters: List[str]) -> str:
        """One page at the front that tells the whole story, written from the finished chapters."""
        title = dossier.article["title"]
        notes = (f"STORY: {title}\n\nTHE CHAPTERS (your only source):\n" +
                 "\n\n".join(c[:1100] for c in chapters)[:9000] +
                 f"\n\nMOST RELIABLE VERIFIED FACTS:\n{dossier.facts_text(None, 2500)}")
        prompt = (f"{notes}\n\nWrite the EXECUTIVE SUMMARY of this documentary report: about 280 words, no headings. "
                  "Start with '**Bottom line:** ' and ONE sentence a busy reader could stop after: the single most "
                  "important verified point. Then three or four short paragraphs. Paragraph one: what happened, to whom, when and where. Paragraph two: why "
                  "and how. Paragraph three: the effects and impacts, now and later. Last paragraph: what to watch "
                  "next - only decisions, events or forecasts the chapters name, never your own advice. Lead with the most important verified fact. Simple everyday words, short sentences; no hype. Use only facts "
                  "from the chapters; say each fact once.")
        try:
            draft = self._generate(prompt, title, 280, lo=0.5, hi=1.5)
        except LLMError:
            self.log("[writer] executive summary unavailable")
            return ""
        return self.ground(draft, notes, title, dossier.allowed_text())

    def impact_table(self, dossier: Dossier) -> str:
        """'Who is affected' table for the front of the report: each affected group, how, and when - built only
        from verified facts, fact-checked like the prose. Empty when the facts name fewer than three groups."""
        title = dossier.article["title"]
        notes = f"STORY: {title}\n\nVERIFIED FACTS:\n{dossier.facts_text(None, 7000)}"
        prompt = (f"{notes}\n\nMake a table of who is affected by this story, using ONLY the verified facts above.\n"
                  "Exactly this header:\n| Who | How they are affected | When |\n|---|---|---|\n"
                  "Then 4 to 8 rows, one per country, group, industry or organisation the facts name as affected. "
                  "'How' is one short plain sentence taken from the facts. 'When' is one of: Now, Coming months, "
                  "Longer term, Not yet known - pick 'Not yet known' unless a fact states the timing. No numbers "
                  "unless that exact number appears in the facts. Output only the table.")
        try:
            raw = clean_output(self.llm.complete(prompt, system=SYSTEM, max_tokens=900, temperature=0.2))
        except LLMError:
            self.log("[writer] impact table unavailable")
            return ""
        def rows_of(text: str) -> List[str]:
            rows = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("|") and ln.strip().endswith("|")]
            return [r for r in rows if r.count("|") == 4 and not set(r) <= set("|-: ")
                    and not r.lower().startswith("| who |")]
        body = rows_of(raw)
        if len(body) < 3:
            return ""
        header = ["| Who | How they are affected | When |", "|---|---|---|"]
        # the same fact-check as the prose: unsupported rows are removed, then untraceable numbers
        checked = rows_of(self._ground_llm("\n".join(header + body), notes, title, strict=True))
        table = strip_unsupported_numbers("\n".join(header + checked), dossier.allowed_text())
        return table if table.count("\n") >= 4 else ""      # header + separator + at least three rows

    def conclusion(self, dossier: Dossier, plan: List[dict], chapters: List[str], mode: Mode) -> str:
        """Closing chapter: what each chapter established, then what to watch."""
        title = dossier.article["title"]
        recap = "\n\n".join(f"CHAPTER {i + 1} - {c['title']}:\n{t[:900]}" for i, (c, t) in enumerate(zip(plan, chapters)))
        notes = f"STORY: {title}\n\n{recap[:10000]}"
        names = "; ".join(c["title"] for c in plan)
        prompt = (f"{notes}\n\nWrite the closing chapter of the documentary report, titled '## Summary and Conclusion'. "
                  f"First, a bulleted recap: one bullet per chapter ({names}) - the chapter title in bold, then its "
                  "single most important established finding in one sentence. Then a closing section of about 150 "
                  "words: what the evidence adds up to, what remains unknown, and what to watch next. Use only what "
                  "the chapters state; add no new facts. No hype.")
        try:
            draft = self._generate(prompt, title, min(mode.chapter_words, 120 + 45 * len(plan)), lo=0.5, hi=1.6)
        except LLMError:
            self.log("[writer] closing chapter unavailable")
            return ""
        out = self.ground(draft, notes, title, dossier.allowed_text())
        lines = [ln for ln in out.strip().splitlines()]
        while lines and (not lines[0].strip() or re.fullmatch(r"[#*\s]*summary and conclusion[*:\s]*", lines[0], re.I)):
            lines.pop(0)                     # the model repeats the title as a heading and/or a bold line
        return "## Summary and Conclusion\n\n" + "\n".join(lines).strip()

    @staticmethod
    def _source(dossier: Dossier, report: str, max_chars: int = 15000) -> str:
        """What the blog/article are written from: the finished documentary report (step 4), topped up with
        the best-confirmed verified facts. Falls back to the facts alone if there is no report.
        The report is long, so every chapter gets an equal share of the room: cutting off the end would lose
        the effects, impacts and outlook, which the blog and article must cover."""
        if not report:
            return dossier.brief(max_chars)
        head = f"STORY: {dossier.article['title']}\nPUBLISHED: {dossier.article['published'][:10]}\n\n"
        facts = dossier.facts_text(None, 3000)
        room = max(2000, max_chars - len(head) - len(facts) - 160)
        parts = [p for p in re.split(r"\n(?=## )", report) if p.strip()]
        share = max(300, room // max(len(parts), 1))
        body = "\n\n".join(p[:share].rsplit(" ", 1)[0] if len(p) > share else p for p in parts)
        return (f"{head}DOCUMENTARY REPORT (your source: condense and re-shape it for a new audience; add nothing "
                f"it does not contain):\n{body}\n\nMOST RELIABLE VERIFIED FACTS:\n{facts}")

    def blog(self, dossier: Dossier, mode: Mode, report: str = "") -> str:
        title = dossier.article["title"]
        source = self._source(dossier, report)
        prompt = (f"{source}\n\nWrite a {mode.blog_words}-word blog post about \"{title}\".\n"
                  "Voice: a friendly, well-informed person writing their own blog - relaxed and conversational, "
                  "contractions are fine (it's, didn't, they're), simple words, no showing off. Open with the single "
                  "most striking verified fact in the first sentence. Mostly short sentences. Speak directly to the "
                  "reader. Every paragraph must carry concrete detail from the facts above - a name, "
                  "figure, date or place - and move the story forward. No filler adjectives, no clichés ('in today's "
                  "world', 'game-changer', 'buckle up'), no padding questions.\n"
                  "Cover, in this order: within the first 150 words, who did what, when and where; then why it "
                  "happened and how; then who is hit and who gains; then the effects now and later; end with what to "
                  "watch next and one sharp closing line. Where a point has no verified fact behind it, leave it out.\n"
                  "Format: '# headline' on the first line, then 3-5 '## ' subheadings. Each subheading is a specific "
                  "statement about THIS story that carries a fact (for example 'Soybean exports to China fell by "
                  "four-fifths'), never a generic label such as 'Why it happened' or 'Who, what, when'. No bullet points. Say each fact once - never repeat a claim. Stay strictly on this story.")
        draft = self._generate(prompt, title, mode.blog_words)
        return self.ground(draft, source, title, dossier.allowed_text())

    def article(self, dossier: Dossier, mode: Mode, report: str = "") -> str:
        """A reported news feature: headline, standfirst, sections, and an honest 'what we don't know'."""
        title = dossier.article["title"]
        source = self._source(dossier, report)
        prompt = (f"{source}\n\nWrite a {mode.article_words}-word news feature article about \"{title}\".\n"
                  "Build every paragraph from specific VERIFIED FACTS above (use as many as fit; no filler, no "
                  "generalities the facts do not support).\n"
                  "Voice: clear and calm, like a good newspaper story written for everyone - simple words, short "
                  "sentences, concrete detail in every paragraph (names, figures, dates, places); no filler, no hype, "
                  "no clichés.\n"
                  "Structure: '# headline' on the first line; one italic standfirst sentence summarising the story; "
                  "a lede paragraph that answers who, what, when and where; then '## ' sections in this order, "
                  "skipping any the facts cannot support: '## Why it happened', '## How it unfolded', '## Who is "
                  "affected', '## The effects now and later' (separate the immediate from the long-term), '## What "
                  "comes next' (only scheduled events or forecasts a named source makes - if there are none, skip "
                  "it); and a final '## What we still don't know' listing open questions the facts leave "
                  "unanswered. Attribute quotes, opinions, estimates and disputed claims to the named person, "
                  "government or organisation (never a website address); state established facts plainly, and never "
                  "repeat a fact. No speculation beyond clearly-labelled open questions.")
        draft = self._generate(prompt, title, mode.article_words, lo=0.65, hi=1.4)
        return self.ground(draft, source, title, dossier.allowed_text())

    def blog_meta(self, blog: str, dossier: Dossier) -> dict:
        title = dossier.article["title"]
        try:
            m = self.llm.complete_json(
                f"Blog post:\n{blog[:2500]}\n\nReturn JSON with keys title (max 70 chars), description (max 155 "
                "chars), tags (5-8 lowercase keywords).", max_tokens=300)
            return {"title": str(m["title"]), "description": str(m["description"]), "tags": list(m["tags"])}
        except (LLMError, KeyError, TypeError):
            return {"title": title, "description": dossier.article.get("description", "")[:155],
                    "tags": sorted(keywords(title))[:8]}
