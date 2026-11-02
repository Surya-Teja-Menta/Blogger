"""Post the finished blog and article to blogging platforms and announce them on Telegram.

Each platform is used only when its credentials are set. A failure on one platform is logged and never stops the
others (or the run): the files are already saved and emailed by then.
  blog    -> Dev.to, Hashnode
  article -> WordPress, Ghost
  Telegram announces whatever went live."""
import base64
import hashlib
import hmac
import json
import re
import time
from typing import Callable, Dict, List, Tuple

import markdown
import requests

from .config import Settings

TIMEOUT = 60


def split_title(md: str, fallback: str = "") -> Tuple[str, str]:
    """('headline', body) from markdown whose first line is '# headline'."""
    lines = md.strip().splitlines()
    if lines and lines[0].startswith("# "):
        return lines[0][2:].strip(), "\n".join(lines[1:]).strip()
    return fallback, md.strip()


def _tags(tags: List[str], n: int, style: str = "alnum") -> List[str]:
    """style: 'alnum' (Dev.to: letters and digits only), 'slug' (Hashnode: hyphenated), 'name' (as written)."""
    out = []
    for t in tags:
        t = str(t).strip().lower()
        t = (re.sub(r"[^a-z0-9]", "", t) if style == "alnum" else
             re.sub(r"[^a-z0-9]+", "-", t).strip("-") if style == "slug" else t)
        if t and t not in out:
            out.append(t)
    return out[:n]


def _check(resp: requests.Response) -> dict:
    try:
        data = resp.json()
    except ValueError:
        data = {}
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code}: {str(data or resp.text)[:200]}")
    return data


# ---- one function per platform: (settings, title, body_md, description, tags) -> url ---------------------------
def devto(s: Settings, title: str, body: str, description: str, tags: List[str]) -> str:
    data = _check(requests.post("https://dev.to/api/articles", timeout=TIMEOUT, headers={"api-key": s.devto_api_key},
                                json={"article": {"title": title[:128], "body_markdown": body, "published": s.publish_live,
                                                  "description": description[:150], "tags": _tags(tags, 4)}}))
    return data.get("url") or f"https://dev.to/dashboard (draft id {data.get('id')})"


def hashnode(s: Settings, title: str, body: str, description: str, tags: List[str]) -> str:
    tag_objs = [{"slug": t, "name": t} for t in _tags(tags, 5, "slug")]
    if s.publish_live:
        query = ("mutation($i: PublishPostInput!) { publishPost(input: $i) { post { url } } }")
    else:
        query = ("mutation($i: CreateDraftInput!) { createDraft(input: $i) { draft { id slug } } }")
    inp = {"title": title[:250], "contentMarkdown": body, "publicationId": s.hashnode_publication_id, "tags": tag_objs}
    if s.publish_live:
        inp["subtitle"] = description[:250]
    data = _check(requests.post("https://gql.hashnode.com", timeout=TIMEOUT, headers={"Authorization": s.hashnode_token},
                                json={"query": query, "variables": {"i": inp}}))
    if data.get("errors"):
        raise RuntimeError(str(data["errors"][0].get("message"))[:200])
    node = data["data"].get("publishPost") or data["data"].get("createDraft")
    return (node.get("post") or {}).get("url") or "https://hashnode.com/drafts"


def wordpress(s: Settings, title: str, body: str, description: str, tags: List[str]) -> str:
    auth = base64.b64encode(f"{s.wordpress_user}:{s.wordpress_app_password}".encode()).decode()
    data = _check(requests.post(f"{s.wordpress_url}/wp-json/wp/v2/posts", timeout=TIMEOUT,
                                headers={"Authorization": f"Basic {auth}"},
                                json={"title": title, "content": markdown.markdown(body), "excerpt": description,
                                      "status": "publish" if s.publish_live else "draft"}))
    return data.get("link") or s.wordpress_url


def _ghost_token(admin_key: str) -> str:
    """Ghost Admin API auth: a short-lived HS256 JWT signed with the (hex) secret half of the admin key."""
    key_id, secret = admin_key.split(":", 1)

    def b64(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    now = int(time.time())
    signing = (b64(json.dumps({"alg": "HS256", "typ": "JWT", "kid": key_id}).encode()) + "." +
               b64(json.dumps({"iat": now, "exp": now + 300, "aud": "/admin/"}).encode()))
    return signing + "." + b64(hmac.new(bytes.fromhex(secret), signing.encode(), hashlib.sha256).digest())


def ghost(s: Settings, title: str, body: str, description: str, tags: List[str]) -> str:
    data = _check(requests.post(f"{s.ghost_url}/ghost/api/admin/posts/?source=html", timeout=TIMEOUT,
                                headers={"Authorization": f"Ghost {_ghost_token(s.ghost_admin_key)}"},
                                json={"posts": [{"title": title, "html": markdown.markdown(body),
                                                 "custom_excerpt": description[:300],
                                                 "tags": [{"name": t} for t in _tags(tags, 5, "name")],
                                                 "status": "published" if s.publish_live else "draft"}]}))
    return data["posts"][0].get("url") or s.ghost_url


def telegram(s: Settings, headline: str, description: str, links: Dict[str, str]) -> str:
    text = f"<b>{_esc(headline)}</b>\n\n{_esc(description)}\n\n" + "\n".join(
        f"<a href=\"{_esc(u)}\">Read on {_esc(p)}</a>" for p, u in links.items())
    _check(requests.post(f"https://api.telegram.org/bot{s.telegram_bot_token}/sendMessage", timeout=TIMEOUT,
                         json={"chat_id": s.telegram_chat_id, "text": text[:4000], "parse_mode": "HTML"}))
    return f"telegram:{s.telegram_chat_id}"


def _esc(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# platform name -> (which piece it gets, the function, is it configured?)
def _platforms(s: Settings):
    return [("Dev.to", "blog", devto, bool(s.devto_api_key)),
            ("Hashnode", "blog", hashnode, bool(s.hashnode_token and s.hashnode_publication_id)),
            ("WordPress", "article", wordpress,
             bool(s.wordpress_url and s.wordpress_user and s.wordpress_app_password)),
            ("Ghost", "article", ghost, bool(s.ghost_url and ":" in s.ghost_admin_key))]


def post_all(s: Settings, blog_md: str, article_md: str, meta: dict,
             log: Callable[[str], None] = print) -> Dict[str, str]:
    """Returns {platform: url} for everything that was posted. Never raises."""
    blog_title, blog_body = split_title(blog_md, meta.get("title", ""))
    art_title, art_body = split_title(article_md, meta.get("title", ""))
    pieces = {"blog": (blog_title, blog_body), "article": (art_title, art_body)}
    desc, tags = meta.get("description", ""), meta.get("tags", [])
    done: Dict[str, str] = {}
    for name, piece, fn, ready in _platforms(s):
        if not ready:
            continue
        title, body = pieces[piece]
        try:
            done[name] = fn(s, title, body, desc, tags)
            log(f"[publish] {name}: {'posted' if s.publish_live else 'draft saved'} ({piece}) {done[name]}")
        except Exception as exc:
            log(f"[publish] {name} FAILED: {type(exc).__name__}: {str(exc)[:200]}")
    if s.telegram_bot_token and s.telegram_chat_id and s.publish_live and done:
        try:
            telegram(s, blog_title, desc, done)
            log("[publish] Telegram: announced")
        except Exception as exc:
            log(f"[publish] Telegram FAILED: {type(exc).__name__}: {str(exc)[:200]}")
    if not done and not any(p[3] for p in _platforms(s)):
        log("[publish] no blogging platform configured - skipping")
    return done
