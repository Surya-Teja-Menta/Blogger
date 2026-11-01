"""Remembers which stories were already written so runs never repeat one."""
import json
import os
from datetime import datetime

from .news import similar
from .web import normalize_url


class History:
    def __init__(self, path: str = "output/history.jsonl"):
        self.path = path
        self.urls = set()
        self.titles = []
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue  # a corrupt line must not break the run
                    if row.get("url"):
                        self.urls.add(normalize_url(row["url"]))
                    if row.get("title"):
                        self.titles.append(row["title"])

    def is_processed(self, url: str, title: str = "") -> bool:
        return normalize_url(url) in self.urls or any(similar(title, t) for t in self.titles if title)

    def add(self, topic: str, url: str, title: str) -> None:
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"date": datetime.now().isoformat(), "topic": topic, "url": url, "title": title}) + "\n")
        self.urls.add(normalize_url(url))
        self.titles.append(title)
