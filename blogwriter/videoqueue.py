"""The video queue: topics waiting to be made, kept in the repo as queue/topics.jsonl (one JSON object per line),
so they survive between GitHub Actions runs. The repo is public, so nothing private (no email addresses)
is ever stored here. The "Make a video" workflow adds to it; the daily run takes the oldest
few and makes them in parallel with the news; a made topic moves to queue/done.jsonl. A topic that fails stays
queued and is tried again next day, up to MAX_TRIES times.

CLI (used by the workflows):
  python blogwriter/videoqueue.py add "Topic one; Topic two" --style education --level basic --mode standard
  python blogwriter/videoqueue.py plan --news "geopolitics,technology" --take 2     (prints the run matrix as JSON)
  python blogwriter/videoqueue.py done ID --ok | --failed
  python blogwriter/videoqueue.py push "Any text: one video" --style education --notes "..."   ("Make a video": the line)
  python blogwriter/videoqueue.py next [--out FILE]      (the first video in the line, for the "Video queue" run)
  python blogwriter/videoqueue.py pop ID --ok | --failed  (that video is finished: it leaves the line)
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
from typing import List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE = os.path.join(ROOT, "queue", "topics.jsonl")
DONE = os.path.join(ROOT, "queue", "done.jsonl")
LINE = os.path.join(ROOT, "queue", "now.jsonl")      # the "Make a video" runs, made one after another, oldest first
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


MARKER = re.compile(r"^\s*(?:[-*•]\s*)?(?:\[[ xX]?\]\s*)?(?:\d{1,3}[.)]\s+)?")    # "- [ ] 14. " of a pasted checklist


def one_topic(text: str) -> List[str]:
    """Everything typed into "Make a video" as ONE topic (the owner pasted a topic plus a checklist line from the queue and
    got two videos): list markers are dropped, a line that only repeats another is left out, the rest is joined."""
    lines = [" ".join(MARKER.sub("", t).split()) for t in str(text or "").replace(";", "\n").splitlines()]
    lines = [t for t in lines if t]
    key = lambda t: re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()          # noqa: E731
    keep = [t for i, t in enumerate(lines)
            if not any(key(t) in key(u) and (key(t) != key(u) or j < i) for j, u in enumerate(lines) if j != i)]
    topic = ", ".join(keep)[:300]
    return [topic] if topic else []


def split_topics(text: str) -> List[str]:
    """'a; b' or one topic per line -> clean topics (at most 200 characters each, no duplicates)."""
    seen, out = set(), []
    for t in str(text or "").replace("\n", ";").split(";"):
        t = " ".join(MARKER.sub("", t).split())[:200]
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


def push(text: str, notes: str = "", **opts) -> dict:
    """One "Make a video" run: the whole text is one video, put at the end of the line (the same topic already waiting
    is not added twice). {} when there is no topic."""
    topics = one_topic(text)
    if not topics:
        return {}
    items = read(LINE)
    same = next((i for i in items if i["topic"].lower() == topics[0].lower()), None)
    if same:
        return same
    item = {**entry(topics[0], **opts), "notes": " ".join(str(notes or "").split())[:500]}
    write(items + [item], LINE)
    return item


def next_up() -> dict:
    """The first video in the line ({} when the line is empty)."""
    items = read(LINE)
    return {k: items[0].get(k, "") for k in FIELDS + ("notes",)} if items else {}


def pop(item_id: str, ok: bool) -> str:
    """A finished (or failed) video leaves the line and is listed in queue/done.jsonl."""
    items = read(LINE)
    gone = [i for i in items if i["id"] == item_id]
    write([i for i in items if i["id"] != item_id], LINE)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    write(read(DONE) + [{**i, "status": "made" if ok else "failed", "finished": stamp} for i in gone], DONE)
    return f"{'made' if ok else 'failed'}; {len(read(LINE))} waiting" if gone else "not in the line"


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(prog="python blogwriter/videoqueue.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("add", "push"):
        p = sub.add_parser(name)
        p.add_argument("topics")
        p.add_argument("--style", default="auto", choices=STYLES)
        p.add_argument("--level", default="intermediate", choices=LEVELS)
        p.add_argument("--mode", default="standard", choices=MODES)
        p.add_argument("--publish", action="store_true")
        p.add_argument("--notes", default="")
    p = sub.add_parser("next")
    p.add_argument("--out", default="")
    p = sub.add_parser("pop")
    p.add_argument("id")
    p.add_argument("--ok", action="store_true")
    p.add_argument("--failed", action="store_true")
    p = sub.add_parser("plan")
    p.add_argument("--news", default="")
    p.add_argument("--take", type=int, default=2)
    p = sub.add_parser("done")
    p.add_argument("id")
    p.add_argument("--ok", action="store_true")
    p.add_argument("--failed", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "push":
        item = push(a.topics, a.notes, style=a.style, level=a.level, mode=a.mode, publish=a.publish)
        if not item:
            print("no topic given", file=sys.stderr)
            return 2
        line = read(LINE)
        place = next(k for k, i in enumerate(line, 1) if i["id"] == item["id"])
        print(f"Video {place} of {len(line)} in the line: {item['topic']}")
    elif a.cmd == "next":
        item = next_up()
        if a.out:            # GitHub step outputs; a value may hold anything, so each one is fenced
            with open(a.out, "a", encoding="utf-8") as f:
                for k in FIELDS + ("notes",):
                    v = item.get(k, "")
                    f.write(f"{k}<<END_OF_VALUE\n{str(v).lower() if isinstance(v, bool) else v}\nEND_OF_VALUE\n")
        print(json.dumps(item, ensure_ascii=False) if item else "the line is empty")
    elif a.cmd == "pop":
        print(pop(a.id, a.ok and not a.failed))
    elif a.cmd == "add":
        topics = split_topics(a.topics)
        if not topics:
            print("no topic given", file=sys.stderr)
            return 2
        for i in add(topics, style=a.style, level=a.level, mode=a.mode, publish=a.publish):
            print(f"queued: {i['topic']} ({i['style']})", file=sys.stderr)
        print(f"{len(read())} topic(s) waiting", file=sys.stderr)
    elif a.cmd == "plan":
        news = [t.strip() for t in a.news.split(",") if t.strip()]
        print(json.dumps(plan(news, a.take)))
    else:
        print(done(a.id, a.ok and not a.failed))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
