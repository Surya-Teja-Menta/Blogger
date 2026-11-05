"""Real moving footage for the videos, from free sources that need no key: Wikimedia Commons video and the NASA
image and video library (plus Pixabay when PIXABAY_API_KEY is set). Only a short piece is cut straight from the
remote file, and a vision model checks one frame of it, so a talking head or an off-topic clip is never used.
The vision model is also the critic that looks at the finished video."""
import base64
import json
import os
import re
import subprocess
from typing import Callable, List, Optional
from urllib.parse import quote

import requests

from .config import Settings
from .web import UA

COMMONS = "https://commons.wikimedia.org/w/api.php"
GEMINI = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
CLIP_SECONDS = 10
MAX_BYTES = 150_000_000               # larger source files are skipped rather than downloaded


def download(url: str, path: str) -> bool:
    """Fetch a source file whole: ffmpeg's own HTTP reads from upload.wikimedia.org stop after a few bytes."""
    try:
        with requests.get(url, headers=UA, stream=True, timeout=30) as r:
            if not r.ok:
                return False
            got = 0
            with open(path, "wb") as f:
                for block in r.iter_content(1 << 20):
                    got += len(block)
                    if got > MAX_BYTES:
                        return False
                    f.write(block)
        return got > 50_000
    except requests.RequestException:
        return False


def ffmpeg_exe() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def post_json(url: str, key: str, body: dict, timeout: int = 90) -> dict:
    """POST with requests; on a TLS failure (some Windows Python builds drop Google's handshake) retry with curl."""
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        r = requests.post(url, headers=headers, json=body, timeout=timeout)
        return r.json() if r.ok else {"error": r.text[:200]}
    except requests.exceptions.Timeout:          # a slow answer is a missing answer, never a crash
        return {"error": "timeout"}
    except (requests.exceptions.SSLError, requests.exceptions.ConnectionError):
        r = subprocess.run(["curl", "-s", "-m", str(timeout), url, "-H", f"Authorization: Bearer {key}",
                            "-H", "Content-Type: application/json", "--data-binary", "@-"],
                           input=json.dumps(body), capture_output=True, text=True, encoding="utf-8")
        try:
            return json.loads(r.stdout or "{}")
        except ValueError:
            return {"error": (r.stdout or r.stderr)[:200]}


def vision(settings: Settings, prompt: str, jpegs: List[bytes]) -> Optional[dict]:
    """Ask the Gemini vision model about images; returns its JSON answer, or None when no key works."""
    content = [{"type": "text", "text": prompt + "\nReply with JSON only."}]
    content += [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(j).decode()}}
                for j in jpegs]
    for key in settings.gemini_keys:
        data = post_json(GEMINI, key, {"model": settings.gemini_model, "reasoning_effort": "low", "temperature": 0.2,
                                       "messages": [{"role": "user", "content": content}]})
        try:
            text = data["choices"][0]["message"]["content"]
            return json.loads(re.search(r"\{.*\}", text, re.S).group())
        except (KeyError, IndexError, TypeError, AttributeError, ValueError):
            continue
    return None


def photo_fits(settings: Settings, subject: str, path: str, log: Callable[[str], None] = print,
               sentence: str = "") -> bool:
    """Vision check of a found photo. People are always refused: a search by name returns look-alikes and
    namesakes (an actor for a CEO), and a wrong face beside a quote is the worst mistake a news video can make."""
    if not settings.gemini_keys:
        return True
    with open(path, "rb") as f:
        jpeg = f.read()
    verdict = vision(settings, (
        f'A photo found to illustrate "{subject}" in a video, shown while the narrator says: "{sentence}". '
        'Return {"fits": true or false, "reason": "short"}. '
        "Say false if a person or people's faces are the main content, if it shows an animal or plant (unless that is "
        "the subject), a logo, a document or screenshot, or anything that does not plausibly show the subject or "
        "that a viewer would find unrelated to the sentence (a landscape for a payments story, say)."),
        [jpeg])
    if verdict is None:          # the check is unavailable: keep the old behaviour rather than lose every photo
        return True
    if verdict.get("fits") is not True:
        log(f"[photo] '{subject}': skipped ({verdict.get('reason', '')})")
        os.remove(path)
        return False
    return True


def frame_jpeg(video: str, at: float, width: int = 640) -> bytes:
    r = subprocess.run([ffmpeg_exe(), "-v", "error", "-ss", f"{at:.2f}", "-i", video, "-frames:v", "1",
                        "-vf", f"scale={width}:-2", "-f", "image2", "-c:v", "mjpeg", "-"], capture_output=True, timeout=60)
    return r.stdout


def _candidates(query: str, settings: Settings) -> List[dict]:
    """Remote clips for a search phrase: url, duration, credit."""
    out = []
    stems = {w[:5] for w in re.findall(r"[a-z]{3,}", query.lower())}
    need = min(2, len(stems))         # "data center interior" must not match any file that merely says "center"
    try:
        pages = requests.get(COMMONS, headers=UA, timeout=15, params={
            "action": "query", "generator": "search", "gsrsearch": f"{query} filetype:video", "gsrnamespace": 6,
            "gsrlimit": 10, "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "format": "json"}
        ).json().get("query", {}).get("pages", {})
        for p in sorted(pages.values(), key=lambda h: h.get("index", 99)):
            info = (p.get("imageinfo") or [{}])[0]
            name = p.get("title", "").removeprefix("File:")
            if (info.get("duration", 0) or 0) >= 6 and info.get("width", 0) >= 640 \
                    and 0 < info.get("size", 0) <= MAX_BYTES \
                    and len(stems & {w[:5] for w in re.findall(r"[a-z]{3,}", name.lower())}) >= need:
                ext = info.get("extmetadata", {})
                out.append({"url": info["url"], "duration": float(info["duration"]),
                            "credit": {"subject": query, "file": info.get("descriptionurl", ""),
                                       "license": ext.get("LicenseShortName", {}).get("value", "see file page"),
                                       "author": re.sub(r"<[^>]+>", "", ext.get("Artist", {}).get("value", ""))[:80]}})
    except (requests.RequestException, ValueError, KeyError):
        pass
    if settings.pixabay_key:
        try:
            hits = requests.get("https://pixabay.com/api/videos/", timeout=15, params={
                "key": settings.pixabay_key, "q": query, "per_page": 5, "safesearch": "true"}).json().get("hits", [])
            for h in hits:
                v = h.get("videos", {}).get("medium") or h.get("videos", {}).get("small") or {}
                if v.get("url"):
                    out.append({"url": v["url"], "duration": float(h.get("duration", 10)),
                                "credit": {"subject": query, "file": h.get("pageURL", ""), "author": h.get("user", ""),
                                           "license": "Pixabay Content License"}})
        except (requests.RequestException, ValueError):
            pass
    try:
        items = requests.get("https://images-api.nasa.gov/search", headers=UA, timeout=15,
                             params={"q": query, "media_type": "video"}).json()["collection"]["items"][:3]
        for it in items:
            assets = requests.get(quote(it["href"], safe=":/"), headers=UA, timeout=15).json()
            mp4 = next((a for a in assets if a.endswith("~mobile.mp4")), None) or \
                next((a for a in assets if a.endswith(".mp4")), None)
            if mp4:
                nid = it["data"][0].get("nasa_id", "")
                out.append({"url": quote(mp4, safe=":/~"), "duration": 0.0,
                            "credit": {"subject": query, "file": f"https://images.nasa.gov/details/{quote(nid)}",
                                       "author": "NASA", "license": "Public domain (NASA)"}})
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
        pass
    return out


def find_clip(query: str, narration: str, dest: str, settings: Settings,
              log: Callable[[str], None] = print) -> Optional[dict]:
    """Cut a CLIP_SECONDS piece of the first candidate the vision check accepts; returns its credit."""
    if not query.strip() or not settings.gemini_keys:
        return None
    src = dest + ".src"
    for cand in _candidates(query, settings)[:5]:
        start = cand["duration"] * 0.3 if cand["duration"] > 60 else 1.0     # skip intros and title cards
        if not download(cand["url"], src):
            continue
        r = subprocess.run([ffmpeg_exe(), "-y", "-v", "error", "-ss", f"{start:.1f}", "-i", src,
                            "-t", str(CLIP_SECONDS), "-an", "-vf",
                            "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,fps=30",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", dest],
                           capture_output=True, timeout=180)
        os.remove(src)
        if r.returncode != 0 or not os.path.exists(dest) or os.path.getsize(dest) < 50_000:
            continue
        verdict = vision(settings, (
            f'Three frames from a stock clip we might show behind this sentence of a news video: "{narration}". '
            f'Visual brief: "{query}". Return {{"fits": true or false, "reason": "short"}}. Say false if the '
            "frames show a talking head or presenter, text slides, a logo or watermark, a mostly blank or dark "
            "picture, or anything unrelated to the brief."),
            [frame_jpeg(dest, t, 480) for t in (1.5, 5.0, 8.5)])
        if verdict and verdict.get("fits") is True:
            return cand["credit"]
        log(f"[footage] '{query}': skipped a clip ({(verdict or {}).get('reason', 'no vision answer')})")
        os.remove(dest)
    return None
