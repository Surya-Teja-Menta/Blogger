"""Markdown -> documentary-style HTML (always) and PDF (headless Chrome/Edge, else WeasyPrint).

Layout: a full-bleed dark cover, a key-findings + contents spread, one chapter per page with a large chapter
numeral and drop cap, and the method + sources as small-type end matter."""
import glob
import html as _html
import os
import re
import shutil
import subprocess
import tempfile

import markdown
from bs4 import BeautifulSoup

FONTS = ("https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,500;0,700;0,900;1,500"
         "&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400"
         "&family=Inter:wght@400;600;700&display=swap")

CSS = """
:root { --ink:#1b1b1b; --muted:#6b6459; --paper:#fbf9f5; --night:#0f0f10; --gold:#b8913a; --rule:#d9d2c3; }
@page { size: A4; margin: 22mm 20mm 24mm; background: #fbf9f5;
  @top-center { content: "__RUNNING_HEAD__"; font: 600 7.5pt Inter, Arial, sans-serif; letter-spacing: .18em;
                text-transform: uppercase; color: #9a9184; }
  @bottom-center { content: counter(page); font: 400 8.5pt Inter, Arial, sans-serif; color: #9a9184; } }
@page :first { margin: 0; @top-center { content: none; } @bottom-center { content: none; } }
* { -webkit-print-color-adjust: exact; print-color-adjust: exact; box-sizing: border-box; }
html { background: var(--paper); }
body { margin: 0; color: var(--ink); background: var(--paper);
       font: 400 10.8pt/1.68 "Source Serif 4", Georgia, serif; hyphens: auto; text-rendering: optimizeLegibility; }
a { color: inherit; text-decoration: none; border-bottom: 1px solid var(--rule); }

/* cover */
.cover { height: 297mm; background: var(--night); color: #f3efe6; padding: 30mm 22mm 24mm; display: flex;
         flex-direction: column; page-break-after: always; break-after: page; position: relative; overflow: hidden; }
.cover::before { content: ""; position: absolute; inset: 0;
         background: radial-gradient(ellipse at 80% 15%, rgba(184,145,58,.22), transparent 55%),
                     radial-gradient(ellipse at 10% 95%, rgba(255,255,255,.06), transparent 50%); }
.cover > * { position: relative; }
.kicker { font: 700 8.5pt Inter, Arial, sans-serif; letter-spacing: .32em; text-transform: uppercase; color: var(--gold); }
.cover h1 { font: 900 34pt/1.08 "Playfair Display", Georgia, serif; margin: auto 0 0; letter-spacing: -.01em;
            hyphens: manual; }
.cover .bar { width: 46mm; height: 3px; background: var(--gold); margin: 9mm 0 7mm; }
.cover .meta { font: 400 9.5pt/1.7 Inter, Arial, sans-serif; color: #c9c2b4; }
.cover .meta a { border-color: #4a463f; color: #e9e3d6; }
.cover .stats { margin-top: 14mm; display: flex; gap: 12mm; font: 400 8pt Inter, Arial, sans-serif; color: #9c9588;
                text-transform: uppercase; letter-spacing: .14em; }
.cover .stats b { display: block; font: 700 22pt "Playfair Display", Georgia, serif; color: #f3efe6;
                  letter-spacing: 0; text-transform: none; }

/* front matter */
.front { break-after: page; page-break-after: always; }
.front section.ack, .front section.summary { break-after: page; page-break-after: always; }
.front section.ack p, .front section.summary p { text-align: justify; margin: 0 0 3.6mm; }
.front section.summary p:first-of-type { font-size: 12pt; line-height: 1.6; }
.label { font: 700 8pt Inter, Arial, sans-serif; letter-spacing: .28em; text-transform: uppercase; color: var(--gold);
         margin: 0 0 3mm; }
.front h2 { font: 700 20pt/1.2 "Playfair Display", Georgia, serif; margin: 0 0 6mm; }
.findings ol { list-style: none; counter-reset: f; padding: 0; margin: 0 0 12mm; }
.findings li { counter-increment: f; position: relative; padding: 3.2mm 0 3.2mm 13mm; border-top: 1px solid var(--rule);
               break-inside: avoid; }
.findings li::before { content: counter(f, decimal-leading-zero); position: absolute; left: 0; top: 2.6mm;
               font: 700 13pt "Playfair Display", Georgia, serif; color: var(--gold); }
.findings li em { color: var(--muted); font-size: 9pt; }
.toc ol { list-style: none; counter-reset: c; padding: 0; margin: 0; columns: 1; }
.toc li { counter-increment: c; font: 500 12pt/1.4 "Playfair Display", Georgia, serif; padding: 2.4mm 0;
          border-bottom: 1px dotted var(--rule); }
.toc li::before { content: counter(c, decimal-leading-zero) "\\2003"; font: 700 9pt Inter, Arial, sans-serif;
          color: var(--gold); letter-spacing: .1em; }

/* chapters */
.chapter { break-before: page; page-break-before: always; }
.chapter .num { font: 900 64pt/0.9 "Playfair Display", Georgia, serif; color: var(--gold); margin: 6mm 0 2mm; }
.chapter .label { margin-bottom: 2mm; }
.chapter h2 { font: 700 23pt/1.15 "Playfair Display", Georgia, serif; margin: 0 0 4mm; letter-spacing: -.005em;
              hyphens: manual; }
.chapter .bar { width: 22mm; height: 2px; background: var(--ink); margin: 0 0 8mm; }
.chapter h3 { font: 700 13pt "Playfair Display", Georgia, serif; margin: 7mm 0 2mm; break-after: avoid; }
.chapter p { margin: 0 0 3.6mm; text-align: justify; orphans: 3; widows: 3; }
.chapter .bar + p::first-letter { float: left; font: 900 46pt/0.82 "Playfair Display", Georgia, serif;
              color: var(--gold); padding: 1.6mm 2.4mm 0 0; }
.chapter .bar + p::first-line { font-variant: small-caps; letter-spacing: .03em; }
/* "In brief" / "Bottom line" callouts: the chapter's one-sentence takeaway; the drop cap moves to the next paragraph */
p.brief { font: italic 400 11.5pt/1.55 "Source Serif 4", Georgia, serif; text-align: left !important;
          border-left: 3px solid var(--gold); padding: 1mm 0 1mm 5mm; margin: 0 0 6mm !important; color: #3a352d; }
p.brief strong { font: 700 7.8pt Inter, Arial, sans-serif; letter-spacing: .2em; text-transform: uppercase;
                 color: var(--gold); font-style: normal; margin-right: 2mm; }
.chapter .bar + p.brief::first-letter { float: none; font: inherit; color: inherit; padding: 0; }
.chapter .bar + p.brief::first-line { font-variant: normal; letter-spacing: 0; }
.chapter .bar + p.brief + p::first-letter { float: left; font: 900 46pt/0.82 "Playfair Display", Georgia, serif;
              color: var(--gold); padding: 1.6mm 2.4mm 0 0; }
.impact table { font-size: 9pt; } .impact td:first-child { font-weight: 600; width: 26%; }
.impact td:last-child { width: 16%; color: var(--muted); }
blockquote { margin: 7mm 0; padding: 4mm 0 4mm 7mm; border-left: 3px solid var(--gold);
             font: italic 500 14pt/1.45 "Playfair Display", Georgia, serif; color: #3a352d; break-inside: avoid; }
blockquote p { text-align: left !important; margin: 0; }
ul, ol { padding-left: 6mm; } li { margin-bottom: 1.5mm; }
table { width: 100%; border-collapse: collapse; font-size: 9.5pt; margin: 5mm 0; }
th, td { border-bottom: 1px solid var(--rule); padding: 2mm 3mm; text-align: left; }
th { font-family: Inter, Arial, sans-serif; font-size: 8pt; text-transform: uppercase; letter-spacing: .1em; }

/* end matter */
.endmatter { break-before: page; page-break-before: always; font: 400 8.6pt/1.55 Inter, Arial, sans-serif;
             color: #3d3a35; }
.endmatter h2 { font: 700 15pt "Playfair Display", Georgia, serif; margin: 0 0 4mm; color: var(--ink); }
.endmatter section + section { margin-top: 10mm; }
.endmatter ol { padding-left: 7mm; } .endmatter li { margin-bottom: 1.2mm; word-break: break-word; }
.endmatter li::marker { color: var(--gold); font-weight: 700; }
.endmatter section.newpage { break-before: page; page-break-before: always; }
.endmatter section.newpage:first-child { break-before: auto; page-break-before: auto; }
#index ul { list-style: none; padding: 0; columns: 2; column-gap: 10mm; }
#index li { margin: 0 0 1mm; break-inside: avoid; }
#evidence-register ol { font-size: 7.8pt; line-height: 1.45; }
.colophon { margin-top: 12mm; padding-top: 4mm; border-top: 1px solid var(--rule); color: var(--muted);
            font-size: 7.8pt; letter-spacing: .06em; }

/* on screen the pages become a centred column */
@media screen {
  body { max-width: 210mm; margin: 0 auto; box-shadow: 0 0 40px rgba(0,0,0,.08); }
  .front, .chapter, .endmatter { padding: 18mm 20mm; border-top: 1px solid var(--rule); }
  .cover { height: auto; min-height: 240mm; }
}
"""

ORDINALS = ["One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve"]
FRONT = {"acknowledgements": "ack", "executive summary": "summary", "key findings": "findings",
         "who is affected": "impact", "contents": "toc"}
END = {"index", "evidence register", "how this report was researched", "sources"}


def _sections(soup):
    """Split the flat markdown HTML into (heading, [nodes]) runs at each <h2>."""
    runs, cur = [], (None, [])
    for node in list(soup.children):
        if getattr(node, "name", None) == "h2":
            runs.append(cur)
            cur = (node, [])
        elif getattr(node, "name", None) != "hr" and str(node).strip():
            cur[1].append(node)
    runs.append(cur)
    return runs


def to_html(md_text: str, title: str, stats: dict = None) -> str:
    """stats: optional {"label": value} figures shown on the cover (e.g. sources, verified facts)."""
    soup = BeautifulSoup(markdown.markdown(md_text, extensions=["extra", "tables"]), "html.parser")
    h1 = soup.find("h1")
    subline = ""
    if h1:
        nxt = h1.find_next_sibling()
        if nxt is not None and nxt.name == "p":       # the "*A documentary report* · date · source" line
            for em in nxt.find_all("em"):
                if "documentary report" in em.get_text().lower():
                    em.decompose()
            subline = nxt.decode_contents().strip().lstrip("·").strip()
            nxt.decompose()
        h1.decompose()
    for p in soup.find_all("p"):                        # **In brief:** / **Bottom line:** takeaway lines
        first = p.find(True)
        if first is not None and first.name == "strong" and not (p.contents[0].strip() if isinstance(
                p.contents[0], str) else "") and re.match(r"(in brief|bottom line)\b", first.get_text().strip(), re.I):
            p["class"] = p.get("class", []) + ["brief"]

    stat_html = "".join(f"<div><b>{_html.escape(str(v))}</b>{_html.escape(k)}</div>" for k, v in (stats or {}).items())
    out = [f"<section class='cover'><div class='kicker'>A Documentary Report</div><h1>{_html.escape(title)}</h1>"
           f"<div class='bar'></div><div class='meta'>{subline}</div>"
           + (f"<div class='stats'>{stat_html}</div>" if stat_html else "") + "</section>"]

    front, chapters, end, n = [], [], [], 0
    for head, nodes in _sections(soup):
        body = "".join(str(x) for x in nodes)
        if head is None:
            if body.strip():
                front.append(f"<section>{body}</section>")
            continue
        name = head.get_text().strip()
        key = name.lower()
        if key in FRONT:
            front.append(f"<section class='{FRONT[key]}'><div class='label'>{_html.escape(name)}</div>{body}</section>")
        elif key in END:
            cls = " class='newpage'" if key in ("index", "evidence register") else ""
            end.append(f"<section{cls} id='{key.replace(' ', '-')}'><h2>{_html.escape(name)}</h2>{body}</section>")
        else:
            n += 1
            word = ORDINALS[n - 1] if n <= len(ORDINALS) else str(n)
            chapters.append(f"<section class='chapter'><div class='num'>{n:02d}</div>"
                            f"<div class='label'>Chapter {word}</div>{head}<div class='bar'></div>{body}</section>")
    if front:
        out.append(f"<div class='front'>{''.join(front)}</div>")
    out += chapters
    if end:
        out.append(f"<div class='endmatter'>{''.join(end)}<div class='colophon'>Every fact in this report is tied "
                   "to a quoted passage from a cited source. Figures that could not be traced were removed.</div></div>")
    head = title if len(title) <= 70 else title[:67].rsplit(" ", 1)[0] + "..."
    css = CSS.replace("__RUNNING_HEAD__", head.replace("\\", "").replace('"', "'").replace("<", ""))
    return (f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width, initial-scale=1'><title>{_html.escape(title)}</title>"
            f"<link rel='preconnect' href='https://fonts.gstatic.com' crossorigin><link rel='stylesheet' href='{FONTS}'>"
            f"<style>{css}</style></head><body>{''.join(out)}</body></html>")


def pdf_pages(path: str) -> int:
    """Number of pages in a PDF, or 0 when it cannot be counted (e.g. page objects inside compressed streams)."""
    try:
        with open(path, "rb") as f:
            return len(re.findall(rb"/Type\s*/Page(?![s\w])", f.read()))
    except OSError:
        return 0


def _browser() -> str:
    cands = [os.environ.get("CHROME_PATH", "")]
    for base in (os.environ.get("PROGRAMFILES", ""), os.environ.get("PROGRAMFILES(X86)", ""),
                 os.environ.get("LOCALAPPDATA", "")):
        if base:
            cands += [os.path.join(base, r"Google\Chrome\Application\chrome.exe"),
                      os.path.join(base, r"Microsoft\Edge\Application\msedge.exe")]
    cands += [shutil.which(n) or "" for n in ("google-chrome", "chromium", "chromium-browser", "chrome", "msedge")]
    cands += glob.glob("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    return next((c for c in cands if c and os.path.exists(c)), "")


def to_pdf(html_text: str, path: str) -> bool:
    """Print the HTML to PDF. Headless Chrome/Edge renders the web fonts and CSS exactly; WeasyPrint is the
    fallback. Returns False when neither is available (the HTML is still saved)."""
    exe = _browser()
    if exe:
        fd, tmp = tempfile.mkstemp(suffix=".html")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(html_text)
            with tempfile.TemporaryDirectory() as profile:
                subprocess.run([exe, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                                "--run-all-compositor-stages-before-draw", "--virtual-time-budget=15000",
                                f"--user-data-dir={profile}", f"--print-to-pdf={os.path.abspath(path)}",
                                "file:///" + tmp.replace("\\", "/")],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            if os.path.exists(path) and os.path.getsize(path) > 1000:
                return True
        except (OSError, subprocess.SubprocessError):
            pass
        finally:
            os.remove(tmp)
    try:
        from weasyprint import HTML
    except Exception:
        return False
    HTML(string=html_text).write_pdf(path)
    return True
