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
    (or year) found nowhere in the verified material. Headings and tables are left alone."""
    allowed = _nums(allowed_text)
    out = []
    for para in text.split("\n\n"):
        if para.lstrip().startswith(("#", "|")):
            out.append(para)
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


# ---- prompts ----------------------------------------------------------------
SYSTEM = ("You are an award-winning investigative journalist. You write direct, intense, tightly-reported prose: "
          "concrete detail, short sentences that land, no filler and no clichés. "
          "HARD RULES: use ONLY the VERIFIED FACTS and article text in the research notes; never invent people, quotes, statistics, "
          "scenes or dialogue; never add a year or date the notes do not state; never describe what 'the article' or "
          "'the outlet' says unless ARTICLE TEXT is actually provided in the notes; if a detail is not in the notes, "
          "leave it out. Make no predictions or recommendations of your own: say what will or may happen only when "
          "the notes attribute that forecast to a named source, and otherwise say it is not yet known. Output ONLY the requested piece - no "
          "preamble, no notes, no word counts, no questions to the reader, no bracketed source numbers.")


class Writer:
    def __init__(self, llm: LLMClient, log: Callable[[str], None] = print):
        self.llm = llm
        self.log = log

    def _generate(self, prompt: str, title: str, target: int, lo=0.7, hi=1.35, system=SYSTEM,
                  check_length=True) -> str:
        """Generate -> clean -> validate; retry once with the concrete problems fed back."""
        feedback, text = "", ""
        for attempt in range(2):
            raw = self.llm.complete(prompt + feedback, system=system,
                                    max_tokens=max(600, int(target * 2.2)), temperature=0.75)
            text = clean_output(raw)
            issues = validate(text, int(target * lo) if check_length else 20,
                              int(target * hi) if check_length else 10 ** 6, title)
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
        return cleaned if (words(cleaned) >= 60 or strict) else checked

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
                f"{dossier.brief(1500)}\n\nGive each documentary chapter below a specific, compelling title that names "
                f"the real people, places or events of THIS story (max 12 words), keeping its role. A title may only "
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
                  f"Requirements: about {target} words; start with the line '## {ch['title']}'. Cover EVERY fact "
                  "listed under VERIFIED FACTS - this chapter must leave nothing out - weaving them into a "
                  "coherent narrative (chronological where dates exist, grouping related facts).\n"
                  "Voice: the narration of a serious long-form documentary. Open on the single most striking verified "
                  "detail, not a summary - no invented atmosphere (light, weather, mood, 'tremors', 'tableaux') and "
                  "no interpretation of motives or meaning the notes do not state; let each paragraph move the story forward and hand off to the next with a "
                  "clear transition; vary sentence length; active voice; plain, concrete words.\n"
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
        prompt = (f"{notes}\n\nWrite the EXECUTIVE SUMMARY of this documentary report: about 280 words, three or four "
                  "paragraphs, no headings. Paragraph one: what happened, to whom, when and where. Paragraph two: why "
                  "and how. Paragraph three: the effects and impacts, now and later. Last paragraph: what to watch "
                  "next - only decisions, events or forecasts the chapters name, never your own advice. Lead with the most important verified fact. Plain, direct, intense; no hype. Use only facts "
                  "from the chapters; say each fact once.")
        try:
            draft = self._generate(prompt, title, 280, lo=0.5, hi=1.5)
        except LLMError:
            self.log("[writer] executive summary unavailable")
            return ""
        return self.ground(draft, notes, title, dossier.allowed_text())

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
                  "Voice: straight, intense, no throat-clearing. Open with the single most striking verified fact in "
                  "the first sentence. Short sentences that land, then one longer sentence to carry the detail. Speak "
                  "directly to the reader. Every paragraph must carry concrete detail from the facts above - a name, "
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
                  "Voice: direct and intense. Short, hard sentences; concrete detail in every paragraph (names, "
                  "figures, dates, places); no filler, no hype, no clichés.\n"
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
