"""Upload a finished video and/or its Short to the YouTube channel, when the owner presses an upload button in the
video email (see email_page.upload_url and .github/workflows/youtube-upload.yml).

    python -m blogwriter.youtube "upload video|short|both <run folder>" [result.md]

The files come from the run's folder in the private bucket (videos/<run>/): long_video_en.mp4, short_en.mp4,
thumbnail.png, subtitles_en.srt and youtube.json (the title, description and tags shown in the email). It signs in
with YT_CLIENT_ID, YT_CLIENT_SECRET and YT_REFRESH_TOKEN (GitHub Secrets), uploads (resumable, in chunks, retried),
adds the thumbnail and the captions, and writes a short report (Markdown) for the GitHub issue. It never prints a
secret. Until Google audits the app, YouTube keeps API uploads private: the report says so.
"""
import json
import os
import re
import sys
import time
from typing import Optional

import requests

REQUEST = re.compile(r"^upload (video|short|both) (\d{8}_\d{6}_[A-Za-z0-9_\-]{1,140})$")
TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3"
API_URL = "https://www.googleapis.com/youtube/v3"
CHUNK = 32 * 1024 * 1024


class SignInError(RuntimeError):
    pass


def access_token() -> str:
    """A fresh access token from the stored refresh token. SignInError when it is missing or no longer valid (an app
    in Testing loses its sign-in after 7 days)."""
    cid, secret, refresh = (os.environ.get(k, "").strip() for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))
    if not (cid and secret and refresh):
        raise SignInError("the YouTube sign-in is not set up (YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN are "
                          "missing from GitHub Secrets)")
    r = requests.post(TOKEN_URL, data={"client_id": cid, "client_secret": secret, "refresh_token": refresh,
                                       "grant_type": "refresh_token"}, timeout=30)
    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code != 200 or "access_token" not in data:
        raise SignInError(f"Google refused the sign-in ({data.get('error', r.status_code)}): it has expired or was "
                          "removed. Run the one-time sign-in again and update YT_REFRESH_TOKEN")
    return data["access_token"]


def safe_text(text: str, max_bytes: int = 5000, max_chars: int = 0) -> str:
    """Text YouTube's API accepts: it refuses '<' and '>' (a statistics lesson writes "p < 0.05") with an
    invalidTitle / invalidDescription error that costs the whole upload, so they become the look-alike single angle
    quotes; control characters go; and the length is cut at YouTube's limits (the description's is 5000 BYTES, so
    '₹' and curly quotes count more than one)."""
    text = str(text or "").replace("<", "‹").replace(">", "›")
    text = "".join(c for c in text if c in "\n\t" or ord(c) >= 32)
    if max_chars:
        text = text[:max_chars]
    while len(text.encode("utf-8")) > max_bytes:
        text = text[:-1]
    return text.strip()


def safe_tags(tags, limit: int = 450) -> list:
    """Up to 15 tags that fit YouTube's 500 characters in all (commas count), without angle brackets."""
    out, used = [], 0
    for tag in tags or []:
        tag = safe_text(tag, 100).replace(",", " ")
        if not tag or used + len(tag) + 1 > limit or len(out) == 15:
            continue
        out.append(tag)
        used += len(tag) + 1
    return out


def video_body(meta: dict, short: bool, privacy: str, synthetic: bool = True) -> dict:
    """The video's title, description, tags and settings: Education, not made for kids, English, and the
    disclosure that it contains synthetic media (the narration is a cloned voice)."""
    status = {"privacyStatus": privacy, "selfDeclaredMadeForKids": False, "embeddable": True}
    if synthetic:
        status["containsSyntheticMedia"] = True
    return {"snippet": {"title": safe_text(meta["short_title"] if short else meta["title"], 300, 100),
                        "description": safe_text((meta.get("short_description") if short else meta.get("description")) or ""),
                        "tags": safe_tags(meta.get("tags", [])), "categoryId": str(meta.get("category") or "27"),
                        "defaultLanguage": "en", "defaultAudioLanguage": "en"},
            "status": status}


def upload_file(token: str, path: str, body: dict, log=print) -> str:
    """A resumable upload in chunks; a dropped connection resumes where YouTube says it stopped. Returns the id."""
    size = os.path.getsize(path)
    head = {"Authorization": f"Bearer {token}"}
    r = requests.post(f"{UPLOAD_URL}/videos", params={"uploadType": "resumable", "part": "snippet,status"},
                      headers={**head, "Content-Type": "application/json; charset=UTF-8",
                               "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)},
                      data=json.dumps(body), timeout=60)
    if r.status_code != 200 or "Location" not in r.headers:
        raise RuntimeError(f"YouTube refused the upload ({r.status_code}): {r.text[:300]}")
    session, pos, tries = r.headers["Location"], 0, 0
    with open(path, "rb") as f:
        while True:
            f.seek(pos)
            data = f.read(CHUNK)
            try:
                rr = requests.put(session, headers={**head, "Content-Length": str(len(data)),
                                                    "Content-Range": f"bytes {pos}-{pos + len(data) - 1}/{size}"},
                                  data=data, timeout=600)
            except requests.RequestException as exc:
                rr, err = None, exc
            if rr is not None and rr.status_code in (200, 201):
                return rr.json()["id"]
            if rr is not None and rr.status_code == 308:            # chunk taken: carry on from what YouTube has
                got = rr.headers.get("Range", "")
                pos = int(got.rsplit("-", 1)[1]) + 1 if got else 0
                tries = 0
                log(f"[youtube] {pos / size:.0%} of {os.path.basename(path)}")
                continue
            tries += 1
            if tries > 6 or (rr is not None and rr.status_code < 500):
                raise RuntimeError(f"upload failed: {rr.status_code if rr is not None else err}: "
                                   f"{rr.text[:300] if rr is not None else ''}")
            time.sleep(min(60, 2 ** tries))
            q = requests.put(session, headers={**head, "Content-Range": f"bytes */{size}"}, timeout=60)
            if q.status_code in (200, 201):
                return q.json()["id"]
            got = q.headers.get("Range", "") if q.status_code == 308 else ""
            pos = int(got.rsplit("-", 1)[1]) + 1 if got else 0


def upload_video(token: str, path: str, meta: dict, short: bool, privacy: str, log=print) -> str:
    try:
        return upload_file(token, path, video_body(meta, short, privacy), log)
    except RuntimeError as exc:                # an API without the synthetic-media field: once more without it
        if "containsSyntheticMedia" not in str(exc):
            raise
        log("[youtube] the synthetic-media flag was not accepted; uploading without it (set it in Studio)")
        return upload_file(token, path, video_body(meta, short, privacy, synthetic=False), log)


def add_thumbnail(token: str, vid: str, png: str, log=print) -> bool:
    try:
        with open(png, "rb") as f:
            r = requests.post(f"{UPLOAD_URL}/thumbnails/set", params={"videoId": vid},
                              headers={"Authorization": f"Bearer {token}", "Content-Type": "image/png"},
                              data=f.read(), timeout=120)
        if r.status_code != 200:
            log(f"[youtube] thumbnail not set ({r.status_code}): {r.text[:200]}")
        return r.status_code == 200
    except (OSError, requests.RequestException) as exc:
        log(f"[youtube] thumbnail not set: {type(exc).__name__}")
        return False


def add_captions(token: str, vid: str, srt: str, log=print) -> bool:
    try:
        with open(srt, "rb") as f:
            text = f.read()
        boundary = "adyora-captions-boundary"
        meta = json.dumps({"snippet": {"videoId": vid, "language": "en", "name": "English", "isDraft": False}})
        body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n"
                f"--{boundary}\r\nContent-Type: application/octet-stream\r\n\r\n").encode() + text + \
               f"\r\n--{boundary}--\r\n".encode()
        r = requests.post(f"{UPLOAD_URL}/captions", params={"uploadType": "multipart", "part": "snippet"},
                          headers={"Authorization": f"Bearer {token}",
                                   "Content-Type": f"multipart/related; boundary={boundary}"}, data=body, timeout=120)
        if r.status_code != 200:
            log(f"[youtube] captions not added ({r.status_code}): {r.text[:200]}")
        return r.status_code == 200
    except (OSError, requests.RequestException) as exc:
        log(f"[youtube] captions not added: {type(exc).__name__}")
        return False


def privacy_of(token: str, vid: str) -> str:
    try:
        r = requests.get(f"{API_URL}/videos", params={"part": "status", "id": vid},
                         headers={"Authorization": f"Bearer {token}"}, timeout=30)
        items = r.json().get("items") or []
        return items[0]["status"]["privacyStatus"] if items else "unknown"
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return "unknown"


def fetch(run: str, names, dest: str, log=print) -> dict:
    """The run's files from the private bucket (name -> local path) for the names that exist there."""
    from .config import Settings
    from .storage import _client
    from boto3.s3.transfer import TransferConfig
    s = Settings.from_env()
    if not s.storage_configured:
        raise RuntimeError("storage is not configured, so the videos cannot be fetched")
    os.makedirs(dest, exist_ok=True)
    client, got = _client(s), {}
    cfg = TransferConfig(multipart_chunksize=16 * 1024 * 1024, max_concurrency=4)
    for name in names:
        path = os.path.join(dest, name)
        try:
            client.download_file(s.s3_bucket, f"videos/{run}/{name}", path, Config=cfg)
            got[name] = path
        except Exception as exc:                   # a missing file is reported by the caller
            log(f"[youtube] {name}: not in storage ({type(exc).__name__})")
    return got


def add_link_line(token: str, vid: str, line: str, url: str, log=print) -> str:
    """Put `line` at the top of the video's description, once: 'linked', 'already linked' or why not."""
    head = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(f"{API_URL}/videos", params={"part": "snippet", "id": vid}, headers=head, timeout=30)
        items = r.json().get("items") or []
        if r.status_code != 200 or not items:
            return f"not changed ({r.status_code}: video not found)"
        sn = items[0]["snippet"]
        if url in sn.get("description", ""):
            return "already linked"
        keep = {k: sn[k] for k in ("title", "categoryId", "tags", "defaultLanguage", "defaultAudioLanguage") if k in sn}
        keep["description"] = safe_text(line + "\n\n" + sn.get("description", ""))
        r = requests.put(f"{API_URL}/videos", params={"part": "snippet"},
                         headers={**head, "Content-Type": "application/json"},
                         data=json.dumps({"id": vid, "snippet": keep}), timeout=30)
        if r.status_code != 200:
            log(f"[youtube] description not updated ({r.status_code}): {r.text[:200]}")
        return "linked" if r.status_code == 200 else f"not changed ({r.status_code})"
    except (requests.RequestException, ValueError, KeyError) as exc:
        return f"not changed ({type(exc).__name__})"


def link_pair(token: str, video: dict, short: dict, log=print) -> list:
    """The long video and its Short point to each other from the top of their descriptions (skipped once done)."""
    a = add_link_line(token, video["id"], f"Short version, 30 seconds: {short['url']}", short["url"], log)
    b = add_link_line(token, short["id"], f"The full lesson: {video['url']}", video["url"], log)
    return [f"- Links: the video's description points to the Short ({a}); the Short's points to the full lesson ({b})."]


def _settings():
    from .config import Settings
    return Settings.from_env()


def run(request: str, log=print, privacy: str = "") -> str:
    """Do what the button asked; returns the report (Markdown). Raises nothing: every problem becomes the report.
    An item already on YouTube (uploads/<run>/<item>.json) is never uploaded again; the 'started' marks the button
    relay leaves (uploads/<run>/requested-<item>.json) are removed at the end, whatever happened."""
    m = REQUEST.match(" ".join(str(request).split()))
    if not m:
        return "Not an upload request. The title must read `upload video|short|both <run folder>`."
    what, folder = m.groups()
    privacy = privacy or os.environ.get("YT_PRIVACY", "public").strip().lower()
    if privacy not in ("public", "unlisted", "private"):
        privacy = "public"
    items = {"video": ["video"], "short": ["short"], "both": ["video", "short"]}[what]
    try:
        token = access_token()
        from .storage import get_text, put_text
        s = _settings()
        known = {}                                 # both items' markers: the pair is linked whenever both exist
        for item in ("video", "short"):
            try:
                mark = json.loads(get_text(s, f"uploads/{folder}/{item}.json") or "null")
            except ValueError:
                mark = None
            if isinstance(mark, dict) and mark.get("url") and mark.get("id"):
                known[item] = mark
        done = {item: known[item] for item in items if item in known}
        wanted = ["youtube.json", "thumbnail.png", "subtitles_en.srt"]
        wanted += ["long_video_en.mp4"] if "video" in items and "video" not in done else []
        wanted += ["short_en.mp4"] if "short" in items and "short" not in done else []
        files = fetch(folder, wanted, os.path.join("yt_upload", folder), log)
        if "youtube.json" not in files:
            return (f"Nothing uploaded: `videos/{folder}` has no youtube.json. The video may be older than the "
                    "upload button, or storage has already removed it (it keeps the 4 newest videos).")
        with open(files["youtube.json"], encoding="utf-8") as f:
            meta = json.load(f)
        lines = []
        for item, name, short in (("video", "long_video_en.mp4", False), ("short", "short_en.mp4", True)):
            label = "Short" if short else "Video"
            if item not in items:
                continue
            if item in done:
                lines.append(f"- {label}: already on YouTube as [{done[item].get('title') or done[item]['url']}]"
                             f"({done[item]['url']}), not uploaded again.")
                continue
            if name not in files:
                lines.append(f"- {label}: not found in storage, not uploaded.")
                continue
            log(f"[youtube] uploading {name} ({os.path.getsize(files[name]) / 1e6:.0f} MB) as {privacy}")
            token = access_token()                 # a sign-in lasts an hour: a fresh one for every upload
            vid = upload_video(token, files[name], meta, short, privacy, log)
            title = meta["short_title" if short else "title"]
            url = f"https://youtu.be/{vid}" if not short else f"https://youtube.com/shorts/{vid}"
            known[item] = {"id": vid, "url": url, "title": title, "at": int(time.time())}
            put_text(s, f"uploads/{folder}/{item}.json", json.dumps(known[item]), "application/json; charset=utf-8")
            extras = []
            token = access_token()                 # the upload itself may have taken most of the hour
            if not short and "thumbnail.png" in files:
                extras.append("thumbnail " + ("set" if add_thumbnail(token, vid, files["thumbnail.png"], log)
                                              else "NOT set (a channel needs phone verification for custom thumbnails)"))
            if not short and "subtitles_en.srt" in files:
                extras.append("captions " + ("added" if add_captions(token, vid, files["subtitles_en.srt"], log)
                                             else "not added"))
            state = privacy_of(token, vid)
            note = (" YouTube kept it **private**: until Google audits the app, API uploads stay private. Open it "
                    "in YouTube Studio and set it to Public." if state == "private" and privacy != "private" else "")
            lines.append(f"- {label}: [{title}]({url}) is uploaded, now **{state}**"
                         f"{'; ' + ', '.join(extras) if extras else ''}.{note}")
        if "video" in known and "short" in known:
            lines += link_pair(access_token(), known["video"], known["short"], log)
        head = "Uploaded to YouTube:" if any("is uploaded" in x for x in lines) else "Nothing new uploaded:"
        return head + "\n\n" + "\n".join(lines)
    except SignInError as exc:
        return f"Nothing uploaded: {exc}."
    except Exception as exc:
        return f"The upload failed: {type(exc).__name__}: {str(exc)[:400]}"
    finally:
        try:
            from .storage import remove
            s = _settings()
            for item in items:
                remove(s, f"uploads/{folder}/requested-{item}.json")
        except Exception:
            pass


LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")


def email_report(report: str, folder: str, log=print) -> bool:
    """The result, emailed to the owner (the button click has no GitHub page to answer on)."""
    import html as H
    from .mailer import send_email
    ok = report.startswith("Uploaded")
    subject = f"[{'Uploaded' if ok else 'Upload: nothing done' if report.startswith('Nothing') else 'Upload failed'}] {folder}"
    text = LINK.sub(lambda m: f"{m.group(1)}: {m.group(2)}", report).replace("**", "")
    body = H.escape(report)
    body = LINK.sub(lambda m: f'<a href="{m.group(2)}" style="color:#c4302b;font-weight:600">{m.group(1)}</a>', body)
    body = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", body).replace("\n", "<br>")
    page = (f'<div style="font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;font-size:14px;line-height:1.6;'
            f'color:#1f2328;max-width:620px;margin:0 auto;padding:8px">{body}</div>')
    return send_email(_settings(), subject, text, [], log, html=page)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(__doc__)
        return 2
    report = run(argv[0])
    print(report)
    m = REQUEST.match(" ".join(str(argv[0]).split()))
    if m and os.environ.get("UPLOAD_EMAIL", "on").strip().lower() not in ("off", "0", "false", "no"):
        email_report(report, m.group(2))
    if len(argv) > 1:
        with open(argv[1], "w", encoding="utf-8") as f:
            f.write(report + "\n")
    return 0 if report.startswith(("Uploaded", "Nothing new")) else 1


if __name__ == "__main__":
    sys.exit(main())
