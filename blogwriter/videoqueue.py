"""The video queue: topics waiting to be made, kept in the repo as queue/topics.jsonl (one JSON object per line),
so they survive between GitHub Actions runs. The repo is public, so nothing private (no email addresses)
is ever stored here. The "Make a video" workflow adds to it; the daily run takes the oldest
few and makes them in parallel with the news; a made topic moves to queue/done.jsonl. A topic that fails stays
queued and is tried again next day, up to MAX_TRIES times.

CLI (used by the workflows):
  python blogwriter/videoqueue.py add "Topic one; Topic two" --style education --level basic --mode standard
  python blogwriter/videoqueue.py plan --news "geopolitics,technology" --take 2     (prints the run matrix as JSON)
  python blogwriter/videoqueue.py now "Topic one; Topic two" --style story ...      (matrix for an immediate run)
  python blogwriter/videoqueue.py done ID --ok | --failed
"""
import argparse
import hashlib
import json
import os
import sys
import time
from typing import List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE = os.path.join(ROOT, "queue", "topics.jsonl")
DONE = os.path.join(ROOT, "queue", "done.jsonl")
STYLES = ("auto", "news", "story", "education", "concept")
LEVELS = ("basic", "intermediate", "advanced")
MODES = ("fast", "standard", "deep")
MAX_TRIES = 3
FIELDS = ("id", "topic", "source", "style", "level", "mode", "publish")   # what a run needs


def read(path: str = QUEUE) -> List[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write(items: List[dict], path: str = QUEUE) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(i, ensure_ascii=False) + "\n" for i in items)


def split_topics(text: str) -> List[str]:
    """'a; b' or one topic per line -> clean topics (at most 200 characters each, no duplicates)."""
    seen, out = set(), []
    for t in str(text or "").replace("\n", ";").split(";"):
        t = " ".join(t.split())[:200]
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def entry(topic: str, style: str = "auto", level: str = "intermediate", mode: str = "standard",
          publish: bool = False) -> dict:
    added = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {"id": hashlib.sha1(f"{topic}|{added}".encode()).hexdigest()[:10], "topic": topic,
            "source": "news" if style == "news" else "topic",
            "style": style if style in STYLES else "auto", "level": level if level in LEVELS else "intermediate",
            "mode": mode if mode in MODES else "standard", "publish": bool(publish),
            "added": added, "tries": 0}


def add(topics: List[str], **opts) -> List[dict]:
    items = read()
    queued = {i["topic"].lower() for i in items}
    new = [entry(t, **opts) for t in topics if t.lower() not in queued]
    write(items + new)
    return new


def plan(news: List[str], take: int) -> List[dict]:
    """The daily matrix: one job per news topic, then the oldest `take` queued topics."""
    jobs = [{"id": "", "topic": t, "source": "news", "style": "news", "level": "intermediate", "mode": "standard",
             "publish": True} for t in news]
    return jobs + [{k: i[k] for k in FIELDS}
                   for i in read()[:max(0, take)]]


def done(item_id: str, ok: bool) -> str:
    items, left, status = read(), [], "missing"
    for i in items:
        if i["id"] != item_id:
            left.append(i)
            continue
        i["tries"] = i.get("tries", 0) + 1
        if ok or i["tries"] >= MAX_TRIES:
            status = "made" if ok else "gave up"
            write(read(DONE) + [{**i, "status": status, "finished": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}],
                  DONE)
        else:
            status = "retry"
            left.append(i)
    write(left)
    return status


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(prog="python blogwriter/videoqueue.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("add", "now"):
        p = sub.add_parser(name)
        p.add_argument("topics")
        p.add_argument("--style", default="auto", choices=STYLES)
        p.add_argument("--level", default="intermediate", choices=LEVELS)
        p.add_argument("--mode", default="standard", choices=MODES)
        p.add_argument("--publish", action="store_true")
    p = sub.add_parser("plan")
    p.add_argument("--news", default="")
    p.add_argument("--take", type=int, default=2)
    p = sub.add_parser("done")
    p.add_argument("id")
    p.add_argument("--ok", action="store_true")
    p.add_argument("--failed", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd in ("add", "now"):
        opts = dict(style=a.style, level=a.level, mode=a.mode, publish=a.publish)
        topics = split_topics(a.topics)
        if not topics:
            print("no topic given", file=sys.stderr)
            return 2
        if a.cmd == "add":
            for i in add(topics, **opts):
                print(f"queued: {i['topic']} ({i['style']})", file=sys.stderr)
            print(f"{len(read())} topic(s) waiting", file=sys.stderr)
        else:
            jobs = [{**entry(t, **opts), "id": ""} for t in topics]
            print(json.dumps([{k: j[k] for k in FIELDS} for j in jobs]))
    elif a.cmd == "plan":
        news = [t.strip() for t in a.news.split(",") if t.strip()]
        print(json.dumps(plan(news, a.take)))
    else:
        print(done(a.id, a.ok and not a.failed))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
