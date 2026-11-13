"""The video email as a clean HTML page: buttons to upload, a table of downloads (link text, never a pasted URL), the
YouTube title, description and tags ready to copy, and the quality check. Plain inline styles and tables, because
mail apps ignore style sheets. A plain-text copy goes with it for mail apps that show no HTML."""
import html
import os
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

# what each delivered file is, in the order the table lists them
FILES = [("long_video_en.mp4", "Long video (2K)", "the one to upload"),
         ("short_en.mp4", "Short", "vertical, under a minute"),
         ("thumbnail.png", "Thumbnail", "for the long video"),
         ("subtitles_en.srt", "Captions", "optional, already burned in"),
         ("study_notes.pdf", "Study notes (PDF)", ""),
         ("contact_sheet.jpg", "Contact sheet", "12 frames at a glance"),
         ("posting_guide.txt", "Posting guide", "the same text, as a file")]

INK, MUTED, LINE, BRAND, SOFT = "#1f2328", "#59636e", "#d1d9e0", "#c4302b", "#f6f8fa"


def upload_url(repo: str, what: str, run: str, title: str) -> str:
    """A ready-filled 'new issue' page in the owner's repository. Pressing Create there starts the upload job (only
    the owner's own issues do); opening the page alone does nothing, so a mail scanner that follows links cannot
    upload anything."""
    body = (f"Press **Create** to upload the {'video and its Short' if what == 'both' else what} of "
            f"\"{title}\" to YouTube.\n\nThe upload job answers here with the YouTube link.")
    return (f"https://github.com/{repo}/issues/new?title={quote(f'upload {what} {run}')}&body={quote(body)}")


def _button(href: str, label: str, filled: bool) -> str:
    style = (f"background:{BRAND};color:#ffffff;border:1px solid {BRAND};" if filled
             else f"background:#ffffff;color:{BRAND};border:1px solid {BRAND};")
    return (f'<a href="{html.escape(href)}" style="{style}display:inline-block;padding:10px 18px;border-radius:6px;'
            f'font-weight:600;text-decoration:none;margin:0 8px 8px 0">{html.escape(label)}</a>')


def _rows(rows: List[Tuple[str, str]]) -> str:
    return "".join(f'<tr><td style="padding:8px 12px;border-top:1px solid {LINE};color:{MUTED};width:130px;'
                   f'vertical-align:top">{html.escape(k)}</td><td style="padding:8px 12px;border-top:1px solid {LINE};'
                   f'color:{INK};white-space:pre-wrap">{v}</td></tr>' for k, v in rows)


def _section(title: str, inner: str) -> str:
    return (f'<h3 style="margin:28px 0 8px;font-size:15px;color:{INK}">{html.escape(title)}</h3>'
            f'<table role="presentation" cellspacing="0" cellpadding="0" style="width:100%;border-collapse:collapse;'
            f'border:1px solid {LINE};border-radius:6px">{inner}</table>')


def build(title: str, links: Dict[str, str], yt: Optional[dict], quality: str, notes: List[str], repo: str,
          run: str, keep: int) -> Tuple[str, str]:
    """(html, text) of the video email. links: file name -> download URL. yt: youtube.json (title, description,
    tags, short title). Upload buttons appear only when the repository is known and the video was stored."""
    stored = bool(links.get("long_video_en.mp4"))
    buttons = ""
    if repo and run and stored:
        buttons = (_button(upload_url(repo, "video", run, title), "Upload video to YouTube", True)
                   + (_button(upload_url(repo, "short", run, title), "Upload Short", False) if links.get("short_en.mp4") else "")
                   + (_button(upload_url(repo, "both", run, title), "Upload both", False) if links.get("short_en.mp4") else "")
                   + f'<div style="color:{MUTED};font-size:12px;margin-top:4px">Each button opens a ready-filled '
                     f'GitHub page: press <b>Create</b> there to upload. Nothing is posted until you do.</div>')
    files = "".join(
        f'<tr><td style="padding:8px 12px;border-top:1px solid {LINE};color:{INK};font-weight:600">{html.escape(label)}</td>'
        f'<td style="padding:8px 12px;border-top:1px solid {LINE};color:{MUTED}">{html.escape(what)}</td>'
        f'<td style="padding:8px 12px;border-top:1px solid {LINE};text-align:right">'
        f'<a href="{html.escape(links[name])}" style="color:{BRAND};font-weight:600;text-decoration:none">Download</a></td></tr>'
        for name, label, what in FILES if links.get(name))
    page = [f'<div style="font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;font-size:14px;line-height:1.5;'
            f'color:{INK};max-width:680px;margin:0 auto;padding:8px">',
            f'<div style="color:{MUTED};font-size:12px;letter-spacing:.06em;text-transform:uppercase">Adyora &middot; ready to review</div>',
            f'<h2 style="margin:4px 0 16px;font-size:22px">{html.escape(title)}</h2>',
            buttons]
    if files:
        page.append(_section("Downloads", files))
    if yt:
        page.append(_section("For YouTube (copy and paste)", _rows([
            ("Title", html.escape(yt.get("title", ""))),
            ("Description", html.escape(yt.get("description", ""))),
            ("Tags", html.escape(", ".join(yt.get("tags", [])))),
            ("Short title", html.escape(yt.get("short_title", "")))])))
    if quality.strip():
        page.append(_section("Quality check", _rows([("Result", html.escape(quality.strip()))])))
    if notes:
        page.append(_section("Study notes", _rows([("About", html.escape("\n".join(notes)))])))
    page.append(f'<p style="color:{MUTED};font-size:12px;margin-top:24px">Download links work for 7 days. Storage keeps '
                f'the {keep} newest videos; older ones are removed after each new video (PDFs stay).</p></div>')
    # the plain-text copy, for mail apps without HTML
    text = [f"{title}: ready to review. Nothing has been posted.", ""]
    if repo and run and stored:
        text += [f"Upload the video: {upload_url(repo, 'video', run, title)}", ""]
    text += [f"{label}: {links[name]}" for name, label, _ in FILES if links.get(name)]
    if yt:
        text += ["", f"Title: {yt.get('title', '')}", "Description:", yt.get("description", ""),
                 f"Tags: {', '.join(yt.get('tags', []))}", f"Short title: {yt.get('short_title', '')}"]
    text += ["", quality.strip()] + ([""] + notes if notes else [])
    return "".join(page), "\n".join(text) + "\n"


def repository() -> str:
    """owner/name of this repository on GitHub (set inside GitHub Actions; UPLOAD_REPO overrides)."""
    return (os.environ.get("UPLOAD_REPO") or os.environ.get("GITHUB_REPOSITORY") or "").strip()
