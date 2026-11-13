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


def video_body(meta: dict, short: bool, privacy: str, synthetic: bool = True) -> dict:
    """The video's title, description, tags and settings: Education, not made for kids, English, and the
    disclosure that it contains synthetic media (the narration is a cloned voice)."""
    status = {"privacyStatus": privacy, "selfDeclaredMadeForKids": False, "embeddable": True}
    if synthetic:
        status["containsSyntheticMedia"] = True
    return {"snippet": {"title": (meta["short_title"] if short else meta["title"])[:100],
                        "description": (meta.get("short_description") if short else meta.get("description")) or "",
                        "tags": meta.get("tags", [])[:15], "categoryId": str(meta.get("category") or "27"),
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


def run(request: str, log=print, privacy: str = "") -> str:
    """Do what the button asked; returns the report (Markdown). Raises nothing: every problem becomes the report."""
    m = REQUEST.match(" ".join(str(request).split()))
    if not m:
        return "Not an upload request. The title must read `upload video|short|both <run folder>`."
    what, folder = m.groups()
    privacy = privacy or os.environ.get("YT_PRIVACY", "public").strip().lower()
    if privacy not in ("public", "unlisted", "private"):
        privacy = "public"
    wanted = ["youtube.json", "thumbnail.png", "subtitles_en.srt"]
    wanted += ["long_video_en.mp4"] if what in ("video", "both") else []
    wanted += ["short_en.mp4"] if what in ("short", "both") else []
    try:
        token = access_token()
        files = fetch(folder, wanted, os.path.join("yt_upload", folder), log)
        if "youtube.json" not in files:
            return (f"Nothing uploaded: `videos/{folder}` has no youtube.json. The video may be older than the "
                    "upload button, or storage has already removed it (it keeps the 4 newest videos).")
        with open(files["youtube.json"], encoding="utf-8") as f:
            meta = json.load(f)
        lines = []
        for name, short in (("long_video_en.mp4", False), ("short_en.mp4", True)):
            if name not in wanted:
                continue
            if name not in files:
                lines.append(f"- {'Short' if short else 'Video'}: not found in storage, not uploaded.")
                continue
            log(f"[youtube] uploading {name} ({os.path.getsize(files[name]) / 1e6:.0f} MB) as {privacy}")
            vid = upload_video(token, files[name], meta, short, privacy, log)
            extras = []
            if not short and "thumbnail.png" in files:
                extras.append("thumbnail " + ("set" if add_thumbnail(token, vid, files["thumbnail.png"], log)
                                              else "NOT set (a channel needs phone verification for custom thumbnails)"))
            if not short and "subtitles_en.srt" in files:
                extras.append("captions " + ("added" if add_captions(token, vid, files["subtitles_en.srt"], log)
                                             else "not added"))
            state = privacy_of(token, vid)
            note = (" YouTube kept it **private**: until Google audits the app, API uploads stay private. Open it "
                    "in YouTube Studio and set it to Public." if state == "private" and privacy != "private" else "")
            url = f"https://youtu.be/{vid}" if not short else f"https://youtube.com/shorts/{vid}"
            lines.append(f"- {'Short' if short else 'Video'}: [{meta['short_title' if short else 'title']}]({url}) "
                         f"is uploaded, now **{state}**{'; ' + ', '.join(extras) if extras else ''}.{note}")
        return "Uploaded to YouTube:\n\n" + "\n".join(lines)
    except SignInError as exc:
        return f"Nothing uploaded: {exc}."
    except Exception as exc:
        return f"The upload failed: {type(exc).__name__}: {str(exc)[:400]}"


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(__doc__)
        return 2
    report = run(argv[0])
    print(report)
    if len(argv) > 1:
        with open(argv[1], "w", encoding="utf-8") as f:
            f.write(report + "\n")
    return 0 if report.startswith("Uploaded") else 1


if __name__ == "__main__":
    sys.exit(main())
