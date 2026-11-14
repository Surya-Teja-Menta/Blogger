"""The visual-technique library: 168 animated diagram parts (video/src/viz/*.jsx draws them) the diagram designer
can drop into a shot, beside the eleven older parts in diagram.py. Each technique is a moving picture of one kind
of idea: charts (waffle, sankey, ridgeline...), system design (hash rings, Raft elections, caches, queues, sequence
diagrams...), machine learning, deep learning, LLMs and GenAI architecture (attention, KV cache, RLHF, RAG...), Kubernetes
and MLOps (rollouts, autoscaling, drift...), design patterns, research papers, data structures and general explainers
(iceberg, see-saw, chat, dominoes...).

Every technique is declared once here: when to use it, its fields (checked and cleaned by `fill`), the smallest
region it reads well in, and a worked example (used by the tests and the render bench). Numbers follow the
channel's rule: a number appears on screen only if the narration says it (`show` is set only then); otherwise
values only shape the picture. Each video is offered a different selection (`pick`), topic first, so videos do
not look alike, and a technique is used at most once per video."""
import random
import re
from typing import Callable, Dict, List, Optional, Tuple

from . import graphics

# field kinds: ("text", words) ("texts", words, lo, hi) ("num", lo, hi, default) ("int", lo, hi, default)
# ("choice", options, default) ("bool", default) ("nums", lo, hi) ("icon",) ("list", lo, hi, {sub}) ("ref", field)
TECH: Dict[str, dict] = {}


def _t(name: str, fam: str, use: str, fields: dict, sample: dict, tags: str = "", size: Tuple[int, int] = (40, 45),
       need: Tuple[str, ...] = ()) -> None:
    TECH[name] = {"fam": fam, "use": use, "fields": fields, "sample": sample, "size": size,
                  "tags": set(tags.split()) | set(re.findall(r"[a-z]+", use.lower())), "need": need}


ITEMS = lambda lo, hi, w=2: ("list", lo, hi, {"text": ("text", w), "value": ("num", -1e9, 1e9, 1)})   # noqa: E731

# ---------------------------------------------------------------------------------------------------- charts (31)
_t("waffle", "chart", "a 10x10 grid of squares filling in by category: shares of a whole the viewer can count",
   {"items": ITEMS(2, 5)}, {"items": [{"text": "mobile", "value": 62}, {"text": "desktop", "value": 30},
                                     {"text": "other", "value": 8}]}, "share percent proportion part whole split")
_t("treemap", "chart", "nested rectangles sized by value that split the canvas: how a total divides into parts",
   {"items": ITEMS(3, 9)}, {"items": [{"text": "storage", "value": 40}, {"text": "compute", "value": 30},
                                     {"text": "network", "value": 18}, {"text": "other", "value": 12}]},
   "share budget cost breakdown composition hierarchy")
_t("sankey", "chart", "bands flowing from sources on the left to destinations on the right, widths by amount: "
   "where things go", {"flows": ("list", 2, 8, {"from": ("text", 2), "to": ("text", 2), "value": ("num", 0, 1e9, 1)})},
   {"flows": [{"from": "requests", "to": "cache", "value": 80}, {"from": "requests", "to": "database", "value": 20},
              {"from": "database", "to": "disk", "value": 5}]}, "flow traffic routing energy money where", (50, 55))
_t("funnel", "chart", "a funnel narrowing stage by stage with the drop at each step",
   {"items": ITEMS(3, 6, 3)}, {"items": [{"text": "visitors", "value": 1000}, {"text": "sign ups", "value": 300},
                                         {"text": "buyers", "value": 40}]}, "conversion drop loss stages pipeline")
_t("radar", "chart", "a spider chart: two options scored on 3-7 qualities, the shapes compared",
   {"axes": ("texts", 2, 3, 7), "a": ("nums", 3, 7), "b": ("nums", 0, 7), "names": ("texts", 2, 0, 2)},
   {"axes": ["speed", "cost", "safety", "scale", "ease"], "a": [8, 4, 6, 9, 5], "b": [5, 8, 8, 4, 7],
    "names": ["option A", "option B"]}, "compare tradeoff qualities profile strengths", (40, 55))
_t("heatmap", "chart", "a labelled matrix whose cells light up by value: patterns across two dimensions",
   {"rows": ("texts", 2, 2, 6), "cols": ("texts", 2, 2, 6), "values": ("nums", 4, 36)},
   {"rows": ["mon", "tue", "wed"], "cols": ["morning", "noon", "night"], "values": [2, 8, 3, 1, 9, 4, 3, 7, 2]},
   "matrix pattern correlation intensity table")
_t("histogram", "chart", "bars rising bin by bin into the shape of a distribution, one bin can be marked",
   {"values": ("nums", 5, 20), "xlabel": ("text", 3), "highlight": ("int", -1, 19, -1)},
   {"values": [1, 3, 7, 12, 15, 11, 6, 3, 1], "xlabel": "response time", "highlight": 4},
   "distribution frequency spread shape bins")
_t("boxplot", "chart", "box-and-whisker plots drawn for 1-4 groups: median, quartiles and range compared",
   {"groups": ("list", 1, 4, {"text": ("text", 2), "min": ("num", -1e9, 1e9, 0), "q1": ("num", -1e9, 1e9, 1),
                              "median": ("num", -1e9, 1e9, 2), "q3": ("num", -1e9, 1e9, 3),
                              "max": ("num", -1e9, 1e9, 4)})},
   {"groups": [{"text": "group A", "min": 2, "q1": 4, "median": 5, "q3": 7, "max": 10},
               {"text": "group B", "min": 1, "q1": 5, "median": 7, "q3": 8, "max": 9}]},
   "median quartile spread range outlier distribution compare")
_t("ridgeline", "chart", "stacked bell-shaped curves, one per group, drifting into place: how distributions shift",
   {"groups": ("list", 2, 5, {"text": ("text", 2), "mean": ("num", -1e9, 1e9, 0), "sd": ("num", 0.01, 1e9, 1)})},
   {"groups": [{"text": "2019", "mean": 10, "sd": 2}, {"text": "2021", "mean": 13, "sd": 3},
               {"text": "2023", "mean": 17, "sd": 2.5}]}, "distribution shift groups compare change over time")
_t("bubble", "chart", "packed circles sized by value that pop in and settle: relative sizes at a glance",
   {"items": ITEMS(3, 10)}, {"items": [{"text": "videos", "value": 70}, {"text": "images", "value": 20},
                                      {"text": "text", "value": 6}, {"text": "code", "value": 4}]},
   "size relative big small share magnitude")
_t("slope", "chart", "lines from a left column to a right column: how each item changed between two moments",
   {"items": ("list", 2, 7, {"text": ("text", 2), "a": ("num", -1e9, 1e9, 0), "b": ("num", -1e9, 1e9, 0)}),
    "left": ("text", 2, True), "right": ("text", 2, True)},
   {"items": [{"text": "SQL", "a": 60, "b": 45}, {"text": "NoSQL", "a": 25, "b": 35}, {"text": "graph", "a": 5, "b": 12}],
    "left": "before", "right": "after"}, "change before after rise fall rank shift two moments")
_t("dumbbell", "chart", "two dots per item joined by a bar: the gap between two values for each item",
   {"items": ("list", 2, 7, {"text": ("text", 2), "a": ("num", -1e9, 1e9, 0), "b": ("num", -1e9, 1e9, 0)}),
    "left": ("text", 2, True), "right": ("text", 2, True)},
   {"items": [{"text": "reads", "a": 2, "b": 9}, {"text": "writes", "a": 5, "b": 7}], "left": "single node",
    "right": "cluster"}, "gap difference range improvement before after")
_t("lollipop", "chart", "stems with a ball on top, rising one by one: ranked values, clean",
   {"items": ITEMS(3, 8)}, {"items": [{"text": "Redis", "value": 9}, {"text": "Postgres", "value": 6},
                                     {"text": "S3", "value": 3}]}, "rank values compare top")
_t("area", "chart", "stacked areas over time: how a total and its parts grow",
   {"series": ("list", 2, 4, {"text": ("text", 2), "values": ("nums", 4, 12)})},
   {"series": [{"text": "reads", "values": [2, 3, 5, 8, 12, 15]}, {"text": "writes", "values": [1, 1, 2, 3, 4, 6]}]},
   "growth over time trend composition total traffic", (45, 50))
_t("bump", "chart", "ranks over time, lines crossing as items overtake each other",
   {"series": ("list", 3, 6, {"text": ("text", 2), "values": ("nums", 3, 8)})},
   {"series": [{"text": "MySQL", "values": [9, 8, 6, 5]}, {"text": "Postgres", "values": [6, 7, 8, 9]},
               {"text": "MongoDB", "values": [7, 9, 7, 6]}]}, "rank race overtake popularity over time", (45, 50))
_t("gauge", "chart", "a dial whose needle swings to a level, with coloured zones: how full, how risky, how fast",
   {"value": ("num", 0, 1, 0.7), "text": ("text", 3), "zones": ("texts", 1, 0, 3)},
   {"value": 0.85, "text": "CPU load", "zones": ["low", "ok", "high"]}, "level utilisation load meter risk speed")
_t("rings", "chart", "concentric progress rings filling to their share",
   {"items": ("list", 1, 4, {"text": ("text", 2), "value": ("num", 0, 100, 0.5)})},
   {"items": [{"text": "hit rate", "value": 0.92}, {"text": "uptime", "value": 0.999}]},
   "progress share goal completion percent")
_t("normal", "chart", "a bell curve drawn on, then its 1, 2 and 3 standard-deviation bands fill in",
   {"sigma": ("bool", True), "unit": ("text", 2), "text": ("text", 4)},
   {"sigma": True, "unit": "height", "text": "most values sit near the middle"},
   "normal bell standard deviation average spread", (40, 50))
_t("cdf", "chart", "a cumulative S-curve with a percentile marker sliding up it",
   {"percentile": ("num", 1, 99.9, 95), "text": ("text", 4)}, {"percentile": 99, "text": "slowest requests"},
   "percentile cumulative tail p99 share below")
_t("intervals", "chart", "many confidence intervals stacked around the true value, a few missing it",
   {"count": ("int", 10, 30, 20), "miss": ("int", 0, 6, 1), "text": ("text", 4)},
   {"count": 20, "miss": 1, "text": "true value"}, "confidence interval uncertainty sampling estimate", (40, 55))
_t("calendar", "chart", "a GitHub-style calendar of days lighting up by activity",
   {"weeks": ("int", 8, 26, 16), "text": ("text", 4)}, {"weeks": 20, "text": "daily deploys"},
   "activity daily habit streak frequency over time")
_t("butterfly", "chart", "a population pyramid: bars to the left and right of a centre line, level by level",
   {"rows": ("texts", 2, 3, 8), "left": ("nums", 3, 8), "right": ("nums", 3, 8), "lname": ("text", 2, True),
    "rname": ("text", 2, True)},
   {"rows": ["0-20", "20-40", "40-60", "60+"], "left": [20, 30, 25, 10], "right": [18, 28, 27, 14],
    "lname": "men", "rname": "women"}, "population two groups compare age distribution mirror", (45, 50))
_t("numberline", "chart", "points dropping onto a number line, then the mean or median marker sliding into place",
   {"values": ("nums", 2, 12), "lo": ("num", -1e9, 1e9, 0), "hi": ("num", -1e9, 1e9, 10),
    "marker": ("choice", ("mean", "median", "none"), "mean"), "unit": ("text", 2)},
   {"values": [2, 3, 3, 4, 5, 9], "lo": 0, "hi": 10, "marker": "median", "unit": "seconds"},
   "average mean median position scale outlier")
_t("beeswarm", "chart", "every data point as a dot settling into a swarm, by group: the whole distribution",
   {"groups": ("texts", 2, 1, 3), "n": ("int", 20, 120, 60), "text": ("text", 4)},
   {"groups": ["cache", "database"], "n": 60, "text": "response time"},
   "distribution every point spread compare groups")
_t("scatter", "chart", "a cloud of points that tightens from no pattern into a correlation (or loosens)",
   {"corr": ("num", -1, 1, 0.8), "start": ("num", -1, 1, 0), "xlabel": ("text", 3), "ylabel": ("text", 3)},
   {"corr": 0.85, "start": 0, "xlabel": "users", "ylabel": "load"}, "correlation relationship trend scatter variables")
_t("confusion", "chart", "a 2x2 confusion matrix whose cells fill with counts: right and wrong guesses",
   {"values": ("nums", 4, 4), "pos": ("text", 2), "neg": ("text", 2)},
   {"values": [40, 5, 10, 45], "pos": "spam", "neg": "not spam"},
   "classification accuracy error false positive negative precision recall")
_t("multiples", "chart", "small multiples: 2-6 mini charts side by side, each with its own trend",
   {"items": ("list", 2, 6, {"text": ("text", 2), "trend": ("choice", ("up", "down", "flat", "spike", "cycle"), "up")})},
   {"items": [{"text": "CPU", "trend": "spike"}, {"text": "memory", "trend": "up"}, {"text": "errors", "trend": "flat"}]},
   "compare many metrics trends dashboard monitoring")
_t("variance", "chart", "points around their mean with their deviations drawn, then squared into growing squares",
   {"values": ("nums", 5, 12), "squares": ("bool", True)}, {"values": [3, 5, 6, 7, 9, 12], "squares": True},
   "variance deviation spread squared error mean", (40, 50))
_t("pie", "chart", "a pie whose slices pull apart as they are named",
   {"items": ITEMS(2, 6)}, {"items": [{"text": "reads", "value": 80}, {"text": "writes", "value": 20}]},
   "share part whole proportion split")
_t("waterfall", "chart", "a waterfall: each step adds or takes away from a running total",
   {"items": ITEMS(3, 8)}, {"items": [{"text": "start", "value": 100}, {"text": "cache", "value": -40},
                                     {"text": "index", "value": -25}, {"text": "network", "value": 10}]},
   "running total change contribution add subtract budget latency breakdown")
_t("stacked", "chart", "100% stacked bars: the make-up of several groups compared side by side",
   {"groups": ("list", 2, 6, {"text": ("text", 2), "parts": ("nums", 2, 5)}), "legend": ("texts", 2, 2, 5)},
   {"groups": [{"text": "startup", "parts": [70, 30]}, {"text": "enterprise", "parts": [30, 70]}],
    "legend": ["cloud", "on premises"]}, "composition share compare groups mix")

# ---------------------------------------------------------------------------------------------- system design (51)
_t("architecture", "system", "tiers of a system left to right (users, load balancer, servers, cache, database) "
   "with requests travelling through and answers coming back",
   {"tiers": ("list", 2, 5, {"text": ("text", 2), "icon": ("icon",), "count": ("int", 1, 4, 1)})},
   {"tiers": [{"text": "users", "icon": "users", "count": 1}, {"text": "load balancer", "icon": "split", "count": 1},
              {"text": "servers", "icon": "server", "count": 3}, {"text": "database", "icon": "database", "count": 1}]},
   "architecture request system design servers database client tiers", (55, 55))
_t("sequence", "system", "a sequence diagram: actors with lifelines and messages arrowing between them in order",
   {"actors": ("texts", 2, 2, 5), "messages": ("list", 2, 8, {"from": ("ref", "actors"), "to": ("ref", "actors"),
                                                             "text": ("text", 4)})},
   {"actors": ["client", "server", "database"],
    "messages": [{"from": 0, "to": 1, "text": "GET /user"}, {"from": 1, "to": 2, "text": "query"},
                 {"from": 2, "to": 1, "text": "row"}, {"from": 1, "to": 0, "text": "response"}]},
   "sequence protocol request response order message api call", (50, 60))
_t("loadbalancer", "system", "requests spread across servers by a load balancer (round robin, least busy or hash), "
   "each server's load bar filling", {"servers": ("int", 2, 6, 3), "algo": ("choice", ("round-robin", "least-busy", "hash"),
                                                                                     "round-robin"), "text": ("text", 3)},
   {"servers": 3, "algo": "round-robin", "text": "load balancer"}, "load balancer distribute traffic servers scale")
_t("cache", "system", "requests checking a cache first: hits bounce straight back, misses travel to the slow store "
   "and fill the cache; a hit-rate counter climbs",
   {"hit": ("num", 0, 1, 0.8), "cache": ("text", 2), "store": ("text", 2)},
   {"hit": 0.8, "cache": "cache", "store": "database"}, "cache hit miss latency memory fast slow redis", (50, 50))
_t("queue", "system", "producers dropping messages into a queue and consumers taking them; a burst fills it, "
   "then it drains", {"producers": ("int", 1, 3, 2), "consumers": ("int", 1, 4, 2), "text": ("text", 3),
                      "burst": ("bool", True)},
   {"producers": 2, "consumers": 2, "text": "message queue", "burst": True},
   "queue buffer async message broker backlog burst producer consumer", (50, 50))
_t("pubsub", "system", "a publisher sends one message to a topic and it fans out to every subscriber",
   {"topic": ("text", 2, True), "publisher": ("text", 2), "subscribers": ("texts", 2, 2, 5)},
   {"topic": "orders", "publisher": "checkout", "subscribers": ["email", "billing", "analytics"]},
   "publish subscribe event fan out topic broadcast notification")
_t("log", "system", "an append-only log: entries added at the end with offsets, readers' pointers advancing at "
   "their own pace", {"entries": ("texts", 2, 4, 10), "readers": ("texts", 2, 1, 3)},
   {"entries": ["signup", "login", "order", "pay", "ship"], "readers": ["search", "analytics"]},
   "log append offset kafka stream event sourcing replay", (50, 50))
_t("hashring", "system", "consistent hashing: nodes and keys on a ring, each key going to the next node clockwise; "
   "a new node arrives and only a few keys move",
   {"nodes": ("texts", 2, 2, 6), "keys": ("int", 4, 16, 10), "add": ("text", 2)},
   {"nodes": ["A", "B", "C"], "keys": 10, "add": "D"}, "consistent hashing ring sharding partition keys rebalance", (40, 60))
_t("shards", "system", "keys routed into shards by range or by hash; one hot shard glows under load",
   {"shards": ("int", 2, 6, 3), "by": ("choice", ("range", "hash"), "hash"), "keys": ("texts", 2, 3, 10),
    "hot": ("bool", False)},
   {"shards": 3, "by": "range", "keys": ["alice", "bob", "carol", "dave", "erin", "zara"], "hot": True},
   "shard partition split data key range hash hot spot", (50, 50))
_t("replication", "system", "a write lands on the leader and copies to followers (sync or async); a lagging follower "
   "still answers with the old value", {"followers": ("int", 1, 4, 2), "mode": ("choice", ("sync", "async"), "async"),
                                        "text": ("text", 4)},
   {"followers": 2, "mode": "async", "text": "replication lag"}, "replication leader follower copy lag consistency", (50, 50))
_t("quorum", "system", "N replicas; a write reaches W of them, a read asks R, and the overlap lights up (W + R > N)",
   {"n": ("int", 3, 7, 5), "writes": ("int", 1, 7, 3), "reads": ("int", 1, 7, 3)}, {"n": 5, "writes": 3, "reads": 3},
   "quorum replicas read write overlap leaderless consistency")
_t("raft", "system", "a Raft cluster: the leader's heartbeats, then the leader fails, a timeout fires, votes are "
   "cast and a new leader takes over", {"nodes": ("int", 3, 7, 5)}, {"nodes": 5},
   "consensus raft paxos leader election vote heartbeat failure", (40, 55))
_t("partition", "system", "a network partition splits the cluster in two; messages across the cut are lost",
   {"nodes": ("int", 4, 8, 6), "left": ("text", 2), "right": ("text", 2)}, {"nodes": 6, "left": "side A", "right": "side B"},
   "network partition split brain cap failure distributed")
_t("clocks", "system", "two or three clocks ticking at slightly different speeds and drifting apart, events "
   "landing out of order", {"names": ("texts", 2, 2, 3), "text": ("text", 4)},
   {"names": ["server A", "server B"], "text": "clock skew"}, "clock time skew drift ordering timestamp")
_t("lamport", "system", "process timelines with messages between them and Lamport counters ticking up",
   {"processes": ("int", 2, 4, 3)}, {"processes": 3}, "logical clock lamport ordering causality events messages", (45, 55))
_t("lsm", "system", "an LSM tree: writes fill a memtable, it flushes into sorted files, and the files compact into "
   "bigger levels", {"text": ("text", 4)}, {"text": "writes"}, "lsm memtable sstable compaction storage write", (50, 55))
_t("btree", "system", "a B-tree: a key is found by walking from the root down one path of sorted pages",
   {"keys": ("nums", 7, 20), "find": ("num", -1e9, 1e9, 0)},
   {"keys": [3, 8, 12, 17, 21, 25, 30, 34, 40, 45, 51], "find": 34}, "btree index search page tree database lookup", (50, 55))
_t("index", "system", "a full table scan crawling every row versus an index jumping straight to the row",
   {"rows": ("int", 6, 14, 10), "mode": ("choice", ("scan", "index", "both"), "both"), "find": ("text", 2)},
   {"rows": 10, "mode": "both", "find": "carol"}, "index scan lookup search table query fast slow database", (50, 50))
_t("table", "system", "a database table drawn row by row; a query lights up the rows it selects",
   {"columns": ("texts", 2, 2, 5), "rows": ("list", 2, 6, {"cells": ("texts", 3, 1, 5)}), "where": ("nums", 0, 4)},
   {"columns": ["id", "name", "city"], "rows": [{"cells": ["1", "Ana", "Pune"]}, {"cells": ["2", "Raj", "Delhi"]},
                                                {"cells": ["3", "Mei", "Pune"]}], "where": [0, 2]},
   "table rows columns sql query select database relational", (45, 50))
_t("schema", "system", "entity boxes with their fields, joined by relationship lines",
   {"entities": ("list", 2, 4, {"text": ("text", 2), "fields": ("texts", 2, 1, 5)}),
    "links": ("list", 0, 5, {"a": ("ref", "entities"), "b": ("ref", "entities")})},
   {"entities": [{"text": "user", "fields": ["id", "name"]}, {"text": "order", "fields": ["id", "user id", "total"]}],
    "links": [{"a": 0, "b": 1}]}, "schema entity relationship model tables foreign key join normalization", (50, 50))
_t("transactions", "system", "two transactions on parallel timelines, their reads and writes interleaving into a "
   "conflict", {"a": ("text", 2, True), "b": ("text", 2, True),
                "ops": ("list", 3, 10, {"t": ("choice", ("a", "b"), "a"), "text": ("text", 4)})},
   {"a": "Alice", "b": "Bob", "ops": [{"t": "a", "text": "read balance"}, {"t": "b", "text": "read balance"},
                                     {"t": "a", "text": "write balance"}, {"t": "b", "text": "write balance"}]},
   "transaction isolation race condition lost update write skew conflict concurrency", (50, 55))
_t("mvcc", "system", "one row with a stack of versions; each reader sees the version from its own snapshot",
   {"versions": ("texts", 2, 2, 5), "readers": ("texts", 2, 1, 3)},
   {"versions": ["balance 100", "balance 70", "balance 90"], "readers": ["report", "checkout"]},
   "mvcc snapshot isolation version reader writer")
_t("twopc", "system", "two-phase commit: the coordinator asks to prepare, everyone votes, then all commit (or one "
   "no-vote aborts all)", {"participants": ("int", 2, 5, 3), "fail": ("bool", False)}, {"participants": 3, "fail": False},
   "two phase commit distributed transaction coordinator vote abort atomic", (45, 55))
_t("tokenbucket", "system", "a token bucket: tokens drip in at a fixed rate, each request spends one, and requests "
   "with no token left are turned away", {"capacity": ("int", 3, 12, 6), "text": ("text", 3)},
   {"capacity": 6, "text": "rate limiter"}, "rate limit throttle token bucket burst requests api")
_t("circuit", "system", "a circuit breaker going closed, open after repeated failures, then half-open to test again",
   {"text": ("text", 4)}, {"text": "payment service"}, "circuit breaker failure resilience fallback retry")
_t("backoff", "system", "retries on a timeline with the wait doubling each time (and jitter spreading them)",
   {"retries": ("int", 3, 6, 5), "jitter": ("bool", True)}, {"retries": 5, "jitter": True},
   "retry backoff exponential wait jitter timeout failure")
_t("cdn", "system", "a world map with edge servers; users connect to the nearest edge instead of the far origin",
   {"edges": ("int", 3, 7, 5), "text": ("text", 3)}, {"edges": 5, "text": "origin"},
   "cdn edge cache latency geography global content delivery", (50, 55))
_t("latency", "chart", "a latency distribution with its long tail and markers at p50, p95 and p99",
   {"unit": ("text", 2), "text": ("text", 4)}, {"unit": "ms", "text": "tail latency"},
   "latency percentile tail p99 response time slow requests", (45, 50))
_t("queueing", "system", "load rising toward capacity while the waiting line explodes near 100%",
   {"load": ("num", 0.3, 1.2, 0.95)}, {"load": 0.95}, "queueing utilisation capacity overload waiting latency", (45, 50))
_t("fanout", "system", "one post copied into every follower's timeline (fan-out on write) or gathered on read",
   {"followers": ("int", 3, 12, 6), "mode": ("choice", ("write", "read"), "write")}, {"followers": 6, "mode": "write"},
   "fan out timeline feed followers social write read", (45, 55))
_t("statemachine", "system", "states as circles and transitions as arrows; a token hops from state to state",
   {"states": ("texts", 2, 2, 6), "moves": ("list", 1, 10, {"from": ("ref", "states"), "to": ("ref", "states"),
                                                           "text": ("text", 3)})},
   {"states": ["pending", "paid", "shipped", "done"], "moves": [{"from": 0, "to": 1, "text": "pay"},
                                                               {"from": 1, "to": 2, "text": "ship"},
                                                               {"from": 2, "to": 3, "text": "deliver"}]},
   "state machine workflow status transition lifecycle", (50, 50))
_t("dag", "system", "a workflow graph of tasks with dependencies, running in order and ticking off",
   {"tasks": ("texts", 2, 3, 9), "deps": ("list", 1, 14, {"from": ("ref", "tasks"), "to": ("ref", "tasks")})},
   {"tasks": ["extract", "clean", "join", "train", "report"],
    "deps": [{"from": 0, "to": 1}, {"from": 1, "to": 2}, {"from": 2, "to": 3}, {"from": 2, "to": 4}]},
   "dag workflow pipeline dependency task orchestration etl", (50, 50))
_t("mapreduce", "system", "map, shuffle, reduce: words split across workers, grouped by key, then counted",
   {"words": ("texts", 1, 4, 10)}, {"words": ["cat", "dog", "cat", "fish", "dog", "cat"]},
   "mapreduce batch map shuffle reduce parallel spark count", (55, 55))
_t("windows", "system", "a stream of events on a timeline grouped into tumbling, sliding or session windows",
   {"kind": ("choice", ("tumbling", "sliding", "session"), "tumbling"), "text": ("text", 4)},
   {"kind": "tumbling", "text": "clicks per minute"}, "stream window event time aggregate real time", (50, 45))
_t("cdc", "system", "change data capture: each change to a database becomes an event flowing to other systems",
   {"db": ("text", 2, True), "targets": ("texts", 2, 1, 4)}, {"db": "orders db", "targets": ["search", "cache", "warehouse"]},
   "change data capture sync replicate event stream database")
_t("bloom", "system", "a Bloom filter: each item sets a few bits through hash arrows; a lookup says maybe or no",
   {"bits": ("int", 12, 32, 20), "items": ("texts", 2, 1, 4), "query": ("text", 2)},
   {"bits": 20, "items": ["apple", "pear"], "query": "plum"}, "bloom filter probabilistic membership bits hash", (50, 45))
_t("invindex", "system", "an inverted index: each word points to the documents that contain it",
   {"docs": ("texts", 6, 2, 5), "terms": ("texts", 1, 2, 6)},
   {"docs": ["fast cache for reads", "cache invalidation is hard", "reads and writes"], "terms": ["cache", "reads"]},
   "inverted index search full text documents terms", (50, 50))
_t("encoding", "system", "the same record as wordy JSON and as compact bytes; the binary version is far shorter",
   {"fields": ("texts", 2, 2, 6)}, {"fields": ["user id", "name", "email"]},
   "encoding json protobuf avro binary serialization size bytes")
_t("evolve", "system", "schema evolution: an old reader and a new writer, extra fields ignored, missing ones defaulted",
   {"old": ("texts", 2, 2, 5), "new": ("texts", 2, 2, 6)}, {"old": ["id", "name"], "new": ["id", "name", "phone"]},
   "schema evolution compatibility backward forward version fields")
_t("quadtree", "system", "points on a map; any square holding too many splits into four, until each is small",
   {"n": ("int", 10, 60, 36), "cap": ("int", 2, 6, 4)}, {"n": 36, "cap": 4},
   "quadtree geohash spatial location nearby map index", (40, 55))
_t("dns", "system", "a DNS lookup hopping from resolver to root to TLD to the authoritative server, then the "
   "address coming back", {"domain": ("text", 1)}, {"domain": "example.com"},
   "dns domain lookup resolver address internet", (55, 50))
_t("handshake", "system", "a TCP or TLS handshake: the opening messages between client and server, in order",
   {"kind": ("choice", ("tcp", "tls"), "tcp")}, {"kind": "tcp"}, "handshake tcp tls connection protocol network", (45, 55))
_t("packets", "system", "packets crossing a network, some lost and sent again",
   {"count": ("int", 4, 12, 8), "loss": ("num", 0, 0.5, 0.2)}, {"count": 8, "loss": 0.25},
   "packet loss retransmit network unreliable tcp")
_t("scaling", "system", "scaling up (one bigger machine) versus scaling out (more machines) as load grows",
   {"mode": ("choice", ("vertical", "horizontal", "both"), "both")}, {"mode": "both"},
   "scaling vertical horizontal scale up out machines load", (50, 50))
_t("failover", "system", "the primary dies, its heartbeat stops, and a replica is promoted to take over",
   {"replicas": ("int", 2, 4, 2)}, {"replicas": 2}, "failover primary replica promote outage availability")
_t("heartbeat", "system", "nodes pulsing heartbeats; one goes quiet, its timeout fills and it is marked dead",
   {"nodes": ("int", 3, 8, 5)}, {"nodes": 5}, "heartbeat failure detection timeout health check node")
_t("idempotency", "system", "a request retried with the same key: the server sees the key and returns the stored "
   "result instead of doing it twice", {"text": ("text", 4)}, {"text": "charge card"},
   "idempotency retry duplicate key exactly once payment")
_t("saga", "system", "a saga: steps across services run in order; one fails and the earlier steps are undone",
   {"steps": ("texts", 2, 2, 6), "fail": ("int", -1, 5, 2)}, {"steps": ["reserve", "charge", "ship"], "fail": 2},
   "saga compensation microservices transaction rollback undo", (50, 45))
_t("gossip", "system", "gossip: one node hears news and tells a few random others until every node knows",
   {"nodes": ("int", 4, 9, 7)}, {"nodes": 7}, "gossip eventual consistency spread replicas converge epidemic")
_t("expiry", "system", "cached items with draining timers; when a timer runs out the item drops away",
   {"items": ("texts", 2, 2, 6), "ttl": ("text", 2)}, {"items": ["user", "cart", "feed"], "ttl": "TTL"},
   "ttl expiry cache timeout eviction stale")
_t("lock", "system", "a distributed lock with a lease: one client holds it, pauses too long, the lease expires and "
   "a fencing token stops the stale write", {"text": ("text", 4)}, {"text": "lock service"},
   "lock lease fencing token mutual exclusion pause", (50, 50))

_t("lru", "system", "an LRU cache: items are used, a used item jumps to the front, and when the cache is full the "
   "least recently used one falls off the end", {"items": ("texts", 1, 4, 12), "capacity": ("int", 2, 6, 3)},
   {"items": ["A", "B", "C", "A", "D", "B", "E"], "capacity": 3}, "lru cache eviction recently used memory policy", (50, 40))

# ---------------------------------------------------------------------------------------------- machine learning (15)
_t("neuron", "ml", "a neuron: inputs times weights flow into a sum, through an activation, to the output",
   {"inputs": ("texts", 2, 2, 5), "output": ("text", 2, True)}, {"inputs": ["size", "rooms", "age"], "output": "price"},
   "neuron weights activation neural network perceptron", (50, 50))
_t("attention", "ml", "attention: one word looks at every other word, lines thick where it pays attention",
   {"tokens": ("texts", 1, 3, 10), "focus": ("int", 0, 9, 0)},
   {"tokens": ["the", "cat", "sat", "because", "it", "was", "tired"], "focus": 4},
   "attention transformer token weights context llm", (55, 45))
_t("tokenize", "ml", "a sentence breaking into token chips, the way a language model reads it",
   {"text": ("text", 12, True)}, {"text": "Tokenization splits unbelievable words"},
   "token tokenizer llm text words split")
_t("boundary", "ml", "two classes of points and the boundary between them: a straight line, a curve, or an "
   "overfitted wiggle", {"mode": ("choice", ("line", "curve", "overfit"), "curve")}, {"mode": "curve"},
   "classification boundary classifier overfit decision", (40, 50))
_t("kmeans", "ml", "k-means: centres jump around and points recolour until the clusters settle",
   {"k": ("int", 2, 5, 3), "n": ("int", 30, 120, 80)}, {"k": 3, "n": 80},
   "clustering kmeans groups unsupervised centroid", (40, 50))
_t("losscurve", "ml", "training and validation loss falling; with overfitting the validation curve turns back up",
   {"overfit": ("bool", True)}, {"overfit": True}, "loss training validation overfit epochs learning curve", (40, 45))
_t("softmax", "ml", "raw scores turning into probabilities that add up to 1",
   {"items": ITEMS(2, 6)}, {"items": [{"text": "cat", "value": 3.2}, {"text": "dog", "value": 1.5},
                                     {"text": "fish", "value": 0.2}]}, "softmax probability scores classes logits")
_t("diffusion", "ml", "a picture of pure noise cleaned step by step until a shape appears",
   {"steps": ("int", 3, 6, 5), "shape": ("choice", ("circle", "heart", "star", "square"), "heart")},
   {"steps": 5, "shape": "star"}, "diffusion noise denoise image generation generative", (50, 40))
_t("nexttoken", "ml", "a language model scoring candidate next words and appending the winner",
   {"prefix": ("text", 6, True), "items": ITEMS(2, 5)},
   {"prefix": "The cat sat on the", "items": [{"text": "mat", "value": 0.6}, {"text": "sofa", "value": 0.25},
                                              {"text": "moon", "value": 0.02}]},
   "next token prediction language model llm probability generation", (50, 45))
_t("context", "ml", "a long strip of tokens with a fixed-size window sliding along it; what falls out is forgotten",
   {"tokens": ("int", 30, 120, 60), "window": ("int", 8, 40, 20)}, {"tokens": 60, "window": 20},
   "context window memory tokens limit llm", (55, 35))
_t("rag", "ml", "retrieval-augmented generation: the question fetches documents, they join the prompt, the model "
   "answers", {"query": ("text", 6, True), "docs": ("texts", 3, 2, 5), "answer": ("text", 6, True)},
   {"query": "What is our refund policy?", "docs": ["policy page", "FAQ", "old email"], "answer": "30 days, full refund"},
   "rag retrieval documents search llm grounding embeddings", (55, 50))
_t("dropout", "ml", "a layered network whose neurons blink off at random while training (dropout)",
   {"layers": ("nums", 2, 5)}, {"layers": [3, 5, 5, 2]}, "dropout regularization neural network training", (45, 50))
_t("contour", "ml", "gradient descent on a contour map: a small step creeps, a good one converges, a large one "
   "zigzags or blows up", {"lr": ("choice", ("small", "good", "large"), "good")}, {"lr": "large"},
   "gradient descent learning rate optimisation contour loss", (40, 55))
_t("pca", "ml", "a tilted cloud of points, its main direction found, every point projected onto it",
   {"n": ("int", 20, 80, 40)}, {"n": 40}, "pca principal component dimension reduction projection", (40, 50))
_t("vectors", "ml", "words as points in an embedding space; a query lands and its nearest neighbours light up",
   {"words": ("texts", 1, 4, 12), "query": ("text", 1)},
   {"words": ["king", "queen", "prince", "apple", "banana", "pear"], "query": "princess"},
   "embedding vector similarity search semantic nearest neighbours", (45, 50))

# ------------------------------------------------------------------------------------------------- explainers (20)
_t("split", "explain", "a before/after split: a divider wipes across from one side to the other",
   {"left": ("text", 3, True), "right": ("text", 3, True), "licon": ("icon",), "ricon": ("icon",)},
   {"left": "one big server", "right": "many small servers", "licon": "server", "ricon": "boxes"},
   "before after compare contrast old new")
_t("magnifier", "explain", "a lens sweeping across a crowd of icons until it finds the odd one out",
   {"icon": ("icon",), "find": ("text", 2), "count": ("int", 20, 80, 48)}, {"icon": "file-text", "find": "the row", "count": 48},
   "search find needle haystack scan lookup")
_t("iceberg", "explain", "an iceberg: the little you see above the water and the much bigger part hidden below",
   {"top": ("texts", 3, 1, 3), "below": ("texts", 3, 2, 5)},
   {"top": ["the API"], "below": ["retries", "caching", "replication", "monitoring"]},
   "hidden complexity iceberg surface beneath unseen", (40, 55))
_t("balance", "explain", "a see-saw weighing one side against the other until it tips",
   {"left": ("texts", 2, 1, 3), "right": ("texts", 2, 1, 3), "tip": ("choice", ("left", "right", "level"), "left")},
   {"left": ["consistency"], "right": ["availability"], "tip": "right"}, "tradeoff balance weigh compare cost benefit")
_t("staircase", "explain", "a staircase climbed one level at a time, each step a stage",
   {"steps": ("texts", 2, 3, 6)}, {"steps": ["nominal", "ordinal", "interval", "ratio"]},
   "levels progression steps hierarchy maturity climb", (45, 50))
_t("quadrant", "explain", "a 2x2 map with two axes; items drop into their quadrants",
   {"xlo": ("text", 2, True), "xhi": ("text", 2, True), "ylo": ("text", 2, True), "yhi": ("text", 2, True),
    "items": ("list", 2, 8, {"text": ("text", 2), "x": ("num", 0, 1, 0.5), "y": ("num", 0, 1, 0.5)})},
   {"xlo": "slow", "xhi": "fast", "ylo": "cheap", "yhi": "costly",
    "items": [{"text": "RAM", "x": 0.9, "y": 0.9}, {"text": "SSD", "x": 0.6, "y": 0.5}, {"text": "tape", "x": 0.1, "y": 0.1}]},
   "quadrant matrix tradeoff two axes position compare", (45, 55))
_t("spectrum", "explain", "a scale from one extreme to the other with items sliding to their place on it",
   {"left": ("text", 2, True), "right": ("text", 2, True), "items": ("list", 2, 7, {"text": ("text", 2), "at": ("num", 0, 1, 0.5)})},
   {"left": "strong", "right": "eventual", "items": [{"text": "linearizable", "at": 0.05},
                                                     {"text": "causal", "at": 0.5}, {"text": "DNS", "at": 0.95}]},
   "spectrum scale range continuum degree between", (50, 40))
_t("checklist", "explain", "a checklist ticking off one item after another (one can be crossed out)",
   {"items": ("texts", 4, 3, 6), "fail": ("int", -1, 5, -1)},
   {"items": ["atomic", "consistent", "isolated", "durable"], "fail": -1}, "checklist requirements criteria rules", (40, 50))
_t("terminal", "explain", "a terminal window: commands typed at the prompt and their output scrolling up",
   {"lines": ("texts", 8, 1, 8)}, {"lines": ["$ curl api/users", "200 OK", "$ redis-cli GET user", "(nil)"]},
   "terminal command line shell output developer", (45, 50))
_t("chat", "explain", "a chat conversation with bubbles arriving from each side",
   {"left": ("text", 2, True), "right": ("text", 2, True),
    "messages": ("list", 2, 6, {"side": ("choice", ("left", "right"), "left"), "text": ("text", 10)})},
   {"left": "client", "right": "server", "messages": [{"side": "left", "text": "Are you alive?"},
                                                      {"side": "right", "text": "Yes, still here"}]},
   "chat conversation dialogue message request reply", (40, 55))
_t("browser", "explain", "a browser window loading a page: the address, the spinner, then the content",
   {"url": ("text", 3), "lines": ("texts", 6, 1, 4)}, {"url": "shop.example.com", "lines": ["Your cart", "3 items"]},
   "browser web page website load user", (45, 55))
_t("phone", "explain", "a phone screen with notifications stacking up one after another",
   {"items": ("texts", 5, 2, 5)}, {"items": ["Order shipped", "Payment received", "New follower"]},
   "phone notification mobile app alert push", (30, 60))
_t("dashboard", "explain", "a monitoring dashboard of live metric tiles with sparklines; one tile turns red",
   {"metrics": ("list", 2, 4, {"text": ("text", 2), "trend": ("choice", ("up", "down", "flat", "spike"), "flat")})},
   {"metrics": [{"text": "latency", "trend": "spike"}, {"text": "errors", "trend": "up"}, {"text": "traffic", "trend": "flat"}]},
   "dashboard monitoring metrics observability alert", (50, 50))
_t("dominoes", "explain", "a row of dominoes falling in a chain: one failure knocking over the next",
   {"items": ("texts", 2, 3, 8)}, {"items": ["database", "API", "web", "users"]},
   "cascade chain reaction failure domino effect", (50, 40))
_t("tug", "explain", "a tug of war between two forces, the rope shifting toward the winner",
   {"left": ("text", 2, True), "right": ("text", 2, True), "winner": ("choice", ("left", "right", "none"), "none")},
   {"left": "speed", "right": "safety", "winner": "none"}, "tradeoff tension conflict forces opposing")
_t("hourglass", "explain", "an hourglass whose sand runs out: a timeout or a deadline",
   {"text": ("text", 3)}, {"text": "timeout"}, "time timeout deadline wait expire ttl", (30, 55))
_t("pyramid", "explain", "a pyramid built level by level, the base widest",
   {"levels": ("texts", 3, 3, 6)}, {"levels": ["data", "information", "knowledge", "wisdom"]},
   "pyramid hierarchy levels foundation", (40, 55))
_t("onion", "explain", "concentric layers peeling outward, from the core to the outermost layer",
   {"layers": ("texts", 2, 2, 6)}, {"layers": ["data", "service", "API", "gateway"]},
   "layers onion abstraction security core shell", (40, 55))
_t("puzzle", "explain", "puzzle pieces sliding in and snapping together into one whole",
   {"pieces": ("texts", 2, 2, 6)}, {"pieces": ["storage", "compute", "network", "cache"]},
   "parts together combine components fit")
_t("paper", "explain", "a research paper or book card sliding in with its title, authors and one highlighted line",
   {"title": ("text", 10, True), "who": ("text", 6), "when": ("text", 2), "quote": ("text", 14)},
   {"title": "Dynamo: Amazon's Highly Available Key-value Store", "who": "DeCandia et al.", "when": "2007",
    "quote": "always writeable"}, "paper book reference source research citation", (45, 55))

# ---------------------------------------------------------------------------------------------- data structures (5)
_t("hashtable", "data", "keys hashed into buckets, collisions chaining in the same bucket",
   {"keys": ("texts", 1, 3, 10), "buckets": ("int", 3, 8, 5)}, {"keys": ["ana", "raj", "mei", "tom", "zoe"], "buckets": 4},
   "hash table map bucket collision dictionary lookup", (50, 50))
_t("stackqueue", "data", "a stack (last in, first out) or a queue (first in, first out): items pushed and popped",
   {"kind": ("choice", ("stack", "queue"), "stack"), "items": ("texts", 2, 3, 6)},
   {"kind": "queue", "items": ["job 1", "job 2", "job 3"]}, "stack queue lifo fifo push pop")
_t("linkedlist", "data", "a linked list of nodes and pointers; a new node is spliced in",
   {"items": ("texts", 2, 3, 6), "insert": ("text", 2)}, {"items": ["A", "B", "D"], "insert": "C"},
   "linked list pointer node insert", (50, 35))
_t("sorting", "data", "bars swapping places until they are sorted",
   {"values": ("nums", 5, 12)}, {"values": [5, 2, 8, 1, 9, 3, 7]}, "sort sorting order algorithm swap", (45, 45))
_t("binarysearch", "data", "binary search: the range halves again and again until the target is found",
   {"values": ("nums", 7, 16), "target": ("num", -1e9, 1e9, 0)},
   {"values": [2, 5, 8, 12, 16, 23, 38, 56, 72, 91], "target": 23}, "binary search sorted halve lookup log n", (55, 35))

# ---------------------------------------------------------------------------------------------- deep learning (6)
_t("backprop", "dl", "backpropagation: the forward pass lights the network left to right, the error is measured, "
   "and gradients flow back right to left adjusting every weight", {"layers": ("nums", 3, 5), "text": ("text", 3)},
   {"layers": [3, 4, 4, 2], "text": "loss"}, "backpropagation gradient chain rule training weights neural network", (50, 50))
_t("cnn", "dl", "a convolutional network: an image passes through stacks of feature maps that shrink and deepen, "
   "ending in a class", {"stages": ("texts", 2, 2, 5), "output": ("text", 2, True)},
   {"stages": ["edges", "shapes", "parts"], "output": "cat"}, "cnn convolution feature map image vision layers", (55, 45))
_t("rnn", "dl", "a recurrent network unrolled in time: each word updates a hidden state passed to the next step",
   {"tokens": ("texts", 1, 3, 7)}, {"tokens": ["I", "love", "deep", "learning"]},
   "rnn lstm recurrent sequence hidden state memory time", (55, 40))
_t("transformer", "dl", "a transformer block: tokens go through attention and a feed-forward layer, with residual "
   "paths around each and a norm after; stacked N times", {"blocks": ("int", 1, 4, 2), "text": ("text", 3)},
   {"blocks": 2, "text": "decoder"}, "transformer block attention feed forward residual layer norm architecture", (45, 55))
_t("gan", "dl", "a GAN: the generator turns noise into fakes, the discriminator judges real versus fake, and both "
   "improve until the fakes fool it", {"text": ("text", 3)}, {"text": "faces"},
   "gan generator discriminator adversarial fake real generative", (55, 45))
_t("autoencoder", "dl", "an autoencoder: input squeezed through a narrow bottleneck code and rebuilt on the other side",
   {"text": ("text", 3)}, {"text": "latent code"}, "autoencoder encoder decoder bottleneck latent compression vae", (50, 45))

# ---------------------------------------------------------------------------------------------- LLMs and GenAI (11)
_t("kvcache", "llm", "the KV cache: keys and values of earlier tokens are kept, so each new token only computes its "
   "own row instead of redoing the whole prompt", {"tokens": ("texts", 1, 3, 8)},
   {"tokens": ["The", "sky", "is", "blue", "today"]}, "kv cache inference attention keys values speed llm serving", (50, 50))
_t("moe", "llm", "mixture of experts: a router sends each token to its top experts out of many; most experts stay "
   "idle", {"experts": ("int", 4, 8, 6), "top": ("int", 1, 2, 2), "tokens": ("texts", 1, 2, 5)},
   {"experts": 6, "top": 2, "tokens": ["code", "poem", "math"]}, "mixture of experts moe router sparse llm", (50, 50))
_t("lora", "llm", "LoRA: the big weight matrix stays frozen and two thin trainable matrices add a small update beside it",
   {"text": ("text", 3)}, {"text": "fine-tuning"}, "lora fine tuning low rank adapter frozen weights peft", (50, 45))
_t("quantize", "llm", "quantization: weights in 32-bit floats squeezed to 8 or 4 bits, the model shrinking while the "
   "values round onto a coarser grid", {"bits": ("choice", ("8", "4"), "4")}, {"bits": "4"},
   "quantization bits precision compress model size memory int8 int4", (50, 45))
_t("rlhf", "llm", "RLHF: people rank two answers, a reward model learns their taste, and the model is tuned to score "
   "higher", {"text": ("text", 4)}, {"text": "helpful and harmless"},
   "rlhf alignment human feedback reward model preference dpo", (55, 50))
_t("agent", "llm", "an AI agent loop: think, pick a tool, act, observe the result, and repeat until the task is done",
   {"tools": ("texts", 2, 2, 5), "task": ("text", 6)}, {"tools": ["search", "calculator", "code"], "task": "plan a trip"},
   "agent tools loop reasoning act observe react autonomous", (50, 55))
_t("sampling", "llm", "temperature and top-p: the next-word distribution sharpening (low temperature) or flattening "
   "(high), and the low-probability tail cut off", {"items": ITEMS(3, 7), "temp": ("choice", ("low", "high"), "high")},
   {"items": [{"text": "mat", "value": 5}, {"text": "sofa", "value": 3}, {"text": "roof", "value": 2},
              {"text": "moon", "value": 0.5}], "temp": "high"}, "temperature top p sampling decoding randomness creativity")
_t("beam", "llm", "beam search: a tree of candidate continuations where only the best few branches survive each step",
   {"width": ("int", 2, 3, 2), "words": ("texts", 1, 4, 12)},
   {"width": 2, "words": ["the", "a", "cat", "dog", "sat", "ran", "down", "away"]}, "beam search decoding tree candidates", (50, 50))
_t("chunking", "llm", "a long document cut into overlapping chunks, each turned into an embedding vector",
   {"chunk": ("choice", ("small", "large"), "small"), "text": ("text", 4)}, {"chunk": "small", "text": "policy handbook"},
   "chunking chunks overlap rag document split embeddings", (50, 45))
_t("guardrails", "llm", "guardrails: the input is screened before the model and the output checked after it; unsafe "
   "ones are stopped", {"checks": ("texts", 2, 2, 4)}, {"checks": ["PII", "jailbreak", "toxicity"]},
   "guardrails safety filter moderation policy llm input output", (55, 45))
_t("llmtraining", "llm", "how a chat model is made: pretraining on huge text, then instruction fine-tuning, then "
   "alignment, the model growing at each stage", {"stages": ("texts", 2, 3, 4)},
   {"stages": ["pretraining", "fine-tuning", "alignment"]}, "pretraining fine tuning alignment llm training stages", (55, 40))
_t("prompt", "llm", "the anatomy of a prompt: system rules, retrieved context, conversation history and the question "
   "stacking into one context window", {"parts": ("texts", 3, 2, 5)},
   {"parts": ["system rules", "retrieved docs", "chat history", "user question"]},
   "prompt engineering context window system message template", (45, 55))

# ---------------------------------------------------------------------------------------------- GenAI architecture (4)
_t("llmgateway", "genai", "an LLM gateway: requests pass auth, a cache and a router that picks a model, with fallback "
   "to another model when one fails", {"models": ("texts", 2, 2, 4)}, {"models": ["GPT", "Claude", "Llama"]},
   "llm gateway router fallback model selection cost latency proxy", (55, 50))
_t("ingest", "genai", "a RAG ingestion pipeline: documents loaded, split into chunks, embedded and written into a "
   "vector database", {"sources": ("texts", 2, 1, 4)}, {"sources": ["PDFs", "wiki", "tickets"]},
   "ingestion pipeline rag embedding vector database index documents", (55, 45))
_t("semanticcache", "genai", "a semantic cache: a new question close in meaning to an old one gets the stored answer "
   "without calling the model", {"old": ("text", 8, True), "new": ("text", 8, True)},
   {"old": "How do I reset my password?", "new": "Forgot my password, what now?"},
   "semantic cache similarity embedding cost latency llm", (55, 45))
_t("multiagent", "genai", "multiple agents: a planner hands tasks to specialist agents who report back and the results "
   "are combined", {"agents": ("texts", 2, 2, 4), "task": ("text", 5)},
   {"agents": ["researcher", "coder", "reviewer"], "task": "build a feature"},
   "multi agent orchestration planner specialists collaboration", (50, 55))

# ---------------------------------------------------------------------------------------------- Kubernetes (6)
_t("k8scluster", "k8s", "a Kubernetes cluster: the scheduler places pods onto nodes that have room",
   {"nodes": ("int", 2, 4, 3), "pods": ("int", 3, 12, 8)}, {"nodes": 3, "pods": 8},
   "kubernetes cluster node pod scheduler control plane", (50, 55))
_t("rollout", "k8s", "a rolling update: new-version pods start one by one while old ones drain, with no downtime",
   {"replicas": ("int", 3, 6, 4)}, {"replicas": 4}, "rolling update deployment version zero downtime kubernetes", (50, 45))
_t("hpa", "k8s", "autoscaling: as CPU load crosses the target, more pods are added; when it falls, they are removed",
   {"most": ("int", 3, 8, 6)}, {"most": 6}, "autoscaling hpa horizontal pod autoscaler cpu load kubernetes", (50, 50))
_t("k8sservice", "k8s", "a Service: one stable address that spreads traffic over the pods matching its label, even as "
   "pods come and go", {"pods": ("int", 2, 5, 3), "text": ("text", 3)}, {"pods": 3, "text": "app: web"},
   "service label selector load balancing kubernetes pods stable address", (50, 50))
_t("selfheal", "k8s", "self-healing: the controller compares desired and actual pods; a crashed pod is replaced",
   {"desired": ("int", 2, 6, 3)}, {"desired": 3}, "reconcile desired state controller self healing restart kubernetes", (50, 50))
_t("containers", "k8s", "virtual machines versus containers: each VM carries a whole OS, containers share one kernel",
   {"apps": ("texts", 1, 2, 3)}, {"apps": ["App A", "App B", "App C"]}, "container docker virtual machine vm kernel isolation", (55, 50))

# ---------------------------------------------------------------------------------------------- MLOps, AIOps, LLMOps (7)
_t("mlpipeline", "ops", "an ML pipeline: data, train, evaluate, a quality gate, the model registry, deploy and monitor, "
   "with a loop back when quality drops", {"stages": ("texts", 2, 4, 7)},
   {"stages": ["data", "train", "evaluate", "registry", "deploy", "monitor"]},
   "mlops pipeline training deployment registry ci cd monitoring retrain", (55, 45))
_t("drift", "ops", "data drift: today's live data distribution slides away from the training one until an alert fires",
   {"feature": ("text", 3, True)}, {"feature": "user age"}, "drift data distribution shift monitoring alert mlops", (45, 50))
_t("featurestore", "ops", "a feature store: features computed once, kept offline for training and online for serving, "
   "so both use the same values", {"features": ("texts", 2, 2, 5)}, {"features": ["clicks 7d", "avg spend", "country"]},
   "feature store offline online training serving consistency mlops", (55, 50))
_t("abtest", "ops", "an A/B or canary test: traffic split between the old and new model, metrics compared, the winner "
   "taking all traffic", {"a": ("text", 2, True), "b": ("text", 2, True), "share": ("num", 0.01, 0.5, 0.1)},
   {"a": "model v1", "b": "model v2", "share": 0.1}, "ab test canary experiment traffic split rollout metrics", (50, 50))
_t("anomaly", "ops", "AIOps: a metric streams by, a learned normal band surrounds it, and the spike outside it opens "
   "an incident automatically", {"metric": ("text", 2, True)}, {"metric": "error rate"},
   "aiops anomaly detection incident monitoring alert observability", (50, 45))
_t("cicd", "ops", "a CI/CD pipeline: commit, build, test, scan and deploy stages lighting up in turn (one can fail)",
   {"stages": ("texts", 2, 3, 6), "fail": ("int", -1, 5, -1)}, {"stages": ["commit", "build", "test", "scan", "deploy"], "fail": -1},
   "ci cd pipeline build test deploy devops automation", (55, 35))
_t("evalloop", "ops", "LLMOps evaluation: two prompt or model versions scored over the same test cases, the better "
   "one promoted", {"a": ("text", 2, True), "b": ("text", 2, True), "cases": ("int", 4, 10, 6)},
   {"a": "prompt v1", "b": "prompt v2", "cases": 6}, "llmops evaluation eval test cases prompt version regression", (50, 50))

# ---------------------------------------------------------------------------------------------- design patterns (8)
_t("uml", "pattern", "a class diagram: classes with their methods, inheritance and composition arrows drawing in",
   {"classes": ("list", 2, 4, {"text": ("text", 2), "methods": ("texts", 2, 0, 3)}),
    "links": ("list", 1, 4, {"a": ("ref", "classes"), "b": ("ref", "classes"),
                             "kind": ("choice", ("inherits", "uses"), "inherits")})},
   {"classes": [{"text": "Shape", "methods": ["area()"]}, {"text": "Circle", "methods": ["area()"]},
                {"text": "Square", "methods": ["area()"]}],
    "links": [{"a": 1, "b": 0, "kind": "inherits"}, {"a": 2, "b": 0, "kind": "inherits"}]},
   "class diagram uml inheritance interface object oriented", (50, 50))
_t("observer", "pattern", "the observer pattern: observers subscribe to a subject; when its state changes every "
   "observer is notified", {"subject": ("text", 2, True), "observers": ("texts", 2, 2, 4)},
   {"subject": "weather station", "observers": ["phone app", "display", "logger"]},
   "observer pattern subscribe notify event listener", (50, 50))
_t("strategy", "pattern", "the strategy pattern: one context with a slot where interchangeable algorithms are swapped "
   "in at run time", {"context": ("text", 2, True), "strategies": ("texts", 2, 2, 4)},
   {"context": "checkout", "strategies": ["card", "UPI", "wallet"]}, "strategy pattern interchangeable algorithm plug", (50, 50))
_t("adapter", "pattern", "the adapter pattern: a plug that does not fit, and an adapter between that makes it fit",
   {"client": ("text", 2, True), "service": ("text", 2, True)}, {"client": "new app", "service": "old API"},
   "adapter pattern wrapper interface incompatible legacy", (55, 40))
_t("decorator", "pattern", "the decorator pattern: an object wrapped in layer after layer, each adding one behaviour",
   {"core": ("text", 2, True), "layers": ("texts", 2, 1, 4)}, {"core": "coffee", "layers": ["milk", "sugar", "whip"]},
   "decorator pattern wrap add behaviour layers", (40, 55))
_t("factory", "pattern", "the factory pattern: requests go into one factory and the right kind of object comes out",
   {"products": ("texts", 2, 2, 4)}, {"products": ["Car", "Truck", "Bike"]}, "factory pattern create object creation", (55, 45))
_t("singleton", "pattern", "the singleton pattern: many callers ask for the object and all get the very same one",
   {"text": ("text", 3)}, {"text": "config"}, "singleton pattern one instance global shared", (45, 50))
_t("facade", "pattern", "the facade pattern: one simple front door hiding a tangle of subsystems behind it",
   {"front": ("text", 2, True), "parts": ("texts", 2, 3, 6)}, {"front": "order()", "parts": ["stock", "payment", "shipping", "email"]},
   "facade pattern simple interface subsystem complexity", (55, 50))

# ---------------------------------------------------------------------------------------------- research papers (2)
_t("ablation", "paper", "an ablation study: the full model's score, then the drop when each component is removed",
   {"items": ITEMS(2, 6, 3), "full": ("text", 2)},
   {"items": [{"text": "no attention", "value": 61}, {"text": "no pretraining", "value": 70},
              {"text": "no dropout", "value": 79}], "full": "full model"},
   "ablation study components contribution research paper results", (50, 50))
_t("leaderboard", "paper", "a benchmark leaderboard: rows slide into rank order and the paper's own result is "
   "highlighted", {"items": ITEMS(3, 7, 3), "ours": ("text", 3)},
   {"items": [{"text": "baseline", "value": 71}, {"text": "prior best", "value": 84}, {"text": "this paper", "value": 89}],
    "ours": "this paper"}, "benchmark leaderboard results state of the art sota comparison research", (45, 50))

FAMILY_WORDS = {
    "system":"system design database server servers distributed cache api network scale scaling replication "
              "shard sharding queue kafka microservice microservices latency storage index transaction "
              "consensus cloud load web http dns tcp stream batch",
    "ml": "machine learning neural network deep model ai llm transformer gpt training embedding classification "
          "regression gradient diffusion attention token rag",
    "chart": "statistics data mean median mode distribution probability variance sample average percent survey "
             "regression correlation types",
    "data": "algorithm structure array list hash tree sort search stack queue",
    "dl": "deep learning neural network cnn rnn lstm transformer gan autoencoder backpropagation layers",
    "llm": "llm language model gpt claude token prompt fine tuning lora rlhf agent inference genai generative",
    "genai": "genai generative rag llm architecture gateway agent vector embedding system design",
    "k8s": "kubernetes k8s container docker pod cluster deployment devops cloud native helm",
    "ops": "mlops aiops llmops devops pipeline monitoring drift deployment evaluation ci cd production",
    "pattern": "design pattern patterns object oriented class gang four solid software architecture",
    "paper": "paper research arxiv study results benchmark ablation",
}


# keys every diagram element already uses (position, colour, timing, motions): a technique field must not reuse one
RESERVED = {"type", "id", "x", "y", "w", "h", "r", "color", "on", "anim", "at", "size", "points", "move", "glow",
            "hide", "mark", "fit", "click", "show"}
_clash = {f"{n}.{f}" for n, t in TECH.items() for f in t["fields"] if f in RESERVED}
assert not _clash, f"technique fields reuse reserved keys: {_clash}"


def _clean_num(v) -> Optional[float]:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) != float("inf") else None


def _show(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else f"{x:g}"


def _field(kind: tuple, v, allowed: str, verified: Callable[[str, str], bool], why: List[str], name: str):
    k = kind[0]
    if k == "text":
        t = " ".join(str(v or "").split()[:kind[1]])[:80]
        if t and not verified(t, allowed):
            why.append(f'"{name}" text "{t[:30]}" has a number the narration never says; left out')
            return ""
        return t
    if k == "texts":
        out = []
        for x in (v if isinstance(v, list) else [])[:kind[3]]:
            t = " ".join(str(x if isinstance(x, (str, int, float)) else "").split()[:kind[1]])[:60]
            if t and verified(t, allowed):
                out.append(t)
        return out
    if k == "num":
        x = _clean_num(v)
        return kind[3] if x is None else round(min(kind[2], max(kind[1], x)), 4)
    if k == "int":
        x = _clean_num(v)
        return kind[3] if x is None else int(min(kind[2], max(kind[1], round(x))))
    if k == "choice":
        return v if v in kind[1] else kind[2]
    if k == "bool":
        return bool(v) if v is not None else kind[1]
    if k == "nums":
        out = [x for x in (_clean_num(y) for y in (v if isinstance(v, list) else [])[:kind[2]]) if x is not None]
        return out
    if k == "icon":
        return graphics.icon(v or "")
    raise ValueError(k)


def _numbers_spoken(values: List[float], allowed: str, verified: Callable[[str, str], bool]) -> bool:
    return bool(values) and all(verified(_show(x), allowed) for x in values)


def fill(el: dict, e: dict, allowed: str, verified: Callable[[str, str], bool], why: List[str]) -> bool:
    """Copy the technique's own fields from the model's element e into el, cleaned; True when it cannot be drawn
    (the reason goes to why). Numbers are shown on screen (el["show"]) only when every one is spoken."""
    spec = TECH[el["type"]]
    shown: List[float] = []
    lists: Dict[str, list] = {}
    refs: List[tuple] = []
    for name, kind in spec["fields"].items():
        v = e.get(name)
        if kind[0] == "list":
            out = []
            for item in (v if isinstance(v, list) else [])[:kind[2]]:
                if isinstance(item, (list, tuple)) and len(item) >= 2 and "text" in kind[3] and "value" in kind[3]:
                    item = {"text": item[0], "value": item[1]}
                if not isinstance(item, dict):
                    continue
                rec, ok = {}, True
                for sub, sk in kind[3].items():
                    if sk[0] == "ref":
                        rec[sub] = item.get(sub)
                        refs.append((name, rec, sub, sk[1]))
                        continue
                    rec[sub] = _field(sk, item.get(sub), allowed, verified, why, f"{name}.{sub}")
                    if sk[0] == "num" and _clean_num(item.get(sub)) is not None:
                        shown.append(rec[sub])
                    if sk[0] == "nums":
                        shown.extend(rec[sub])
                    if sk[0] == "text" and sub == "text" and not rec[sub]:
                        ok = False
                    if sk[0] == "texts" and len(rec[sub]) < sk[2]:
                        ok = False
                if ok:
                    out.append(rec)
            lists[name] = out
            el[name] = out
            if len(out) < kind[1]:
                why.append(f'{el["type"]} needs at least {kind[1]} "{name}" (got {len(out)} usable)')
                return True
            continue
        val = _field(kind, v, allowed, verified, why, name)
        el[name] = val
        if kind[0] == "texts":
            lists[name] = val
            if len(val) < kind[2]:
                why.append(f'{el["type"]} needs at least {kind[2]} "{name}" (got {len(val)} usable)')
                return True
        if kind[0] == "nums":
            shown.extend(val)
            if len(val) < kind[1]:
                why.append(f'{el["type"]} needs at least {kind[1]} numbers in "{name}"')
                return True
        if kind[0] == "text" and len(kind) > 2 and kind[2] and not val:
            why.append(f'{el["type"]} needs "{name}"')
            return True
    # references to another list's entries: an index, or the entry's own text
    for name, rec, sub, target in refs:
        pool = lists.get(target) or []
        names = [str(x.get("text", "") if isinstance(x, dict) else x).lower() for x in pool]
        raw = rec.get(sub)
        idx = int(raw) if isinstance(raw, (int, float)) and not isinstance(raw, bool) else (
            names.index(str(raw).lower()) if str(raw).lower() in names else -1)
        rec[sub] = idx if 0 <= idx < len(pool) else -1
    for name, kind in spec["fields"].items():
        if kind[0] == "list" and any(sk[0] == "ref" for sk in kind[3].values()):
            el[name] = [r for r in el[name] if all(r[s] >= 0 for s, sk in kind[3].items() if sk[0] == "ref")]
            if len(el[name]) < kind[1]:
                why.append(f'{el["type"]} "{name}" must point at entries that exist (by index or by their text)')
                return True
    el["show"] = _numbers_spoken(shown, allowed, verified)
    el["text"] = el.get("text") if isinstance(el.get("text"), str) else ""
    return _special(el, why)


def _special(el: dict, why: List[str]) -> bool:
    """Checks one technique needs beyond its field kinds."""
    t = el["type"]
    if t == "radar":
        n = len(el["axes"])
        el["a"] = (el["a"] + [0] * n)[:n]
        el["b"] = (el["b"] + [0] * n)[:n] if el["b"] else []
    if t == "heatmap":
        need = len(el["rows"]) * len(el["cols"])
        if len(el["values"]) < need:
            el["values"] = (el["values"] * (need // max(1, len(el["values"])) + 1))[:need]
        el["values"] = el["values"][:need]
    if t == "butterfly":
        n = len(el["rows"])
        if len(el["left"]) < n or len(el["right"]) < n:
            why.append("butterfly needs a left and a right number for every row")
            return True
        el["left"], el["right"] = el["left"][:n], el["right"][:n]
    if t in ("area", "bump"):
        n = min(len(s["values"]) for s in el["series"])
        if n < 3:
            why.append(f"{t} needs at least 3 values in every series")
            return True
        for s in el["series"]:
            s["values"] = s["values"][:n]
    if t == "numberline" and el["hi"] <= el["lo"]:
        el["lo"], el["hi"] = min(el["values"]), max(el["values"])
        if el["hi"] <= el["lo"]:
            el["hi"] = el["lo"] + 1
    if t == "quorum":
        el["writes"], el["reads"] = min(el["writes"], el["n"]), min(el["reads"], el["n"])
    if t == "confusion":
        el["values"] = [abs(v) for v in el["values"][:4]]
    if t == "stacked":
        n = min(len(g["parts"]) for g in el["groups"])
        for g in el["groups"]:
            g["parts"] = [abs(v) for v in g["parts"][:n]]
        el["legend"] = el["legend"][:n]
    if t in ("waffle", "treemap", "bubble", "pie", "funnel", "lollipop", "softmax", "nexttoken", "rings"):
        if t != "softmax":
            for it in el["items"]:
                it["value"] = abs(it["value"])
        if t not in ("softmax",) and not any(it["value"] > 0 for it in el["items"]):
            why.append(f"{t} needs positive values")
            return True
    if t == "rings":
        for it in el["items"]:
            if it["value"] > 1:
                it["value"] = min(1.0, it["value"] / 100)
    if t == "attention":
        el["focus"] = min(el["focus"], len(el["tokens"]) - 1)
    if t == "saga":
        el["fail"] = el["fail"] if el["fail"] < len(el["steps"]) else -1
    if t == "checklist":
        el["fail"] = el["fail"] if el["fail"] < len(el["items"]) else -1
    if t in ("sorting", "binarysearch", "btree", "variance", "histogram", "dropout"):
        if t in ("binarysearch", "btree"):
            el["values" if t == "binarysearch" else "keys"] = sorted(set(el["values" if t == "binarysearch" else "keys"]))
        if t == "dropout":
            el["layers"] = [int(min(7, max(1, v))) for v in el["layers"]]
        if t == "histogram":
            el["values"] = [abs(v) for v in el["values"]]
            el["highlight"] = el["highlight"] if el["highlight"] < len(el["values"]) else -1
    if t == "table":
        n = len(el["columns"])
        for r in el["rows"]:
            r["cells"] = (r["cells"] + [""] * n)[:n]
        el["where"] = [int(w) for w in el["where"] if 0 <= w < len(el["rows"])]
    return False


def catalogue(names: List[str]) -> str:
    """The prompt lines describing these techniques and their fields."""
    def kind_text(kind) -> str:
        k = kind[0]
        if k == "text":
            return f"max {kind[1]} words{', required' if len(kind) > 2 and kind[2] else ''}"
        if k == "texts":
            return f"[{kind[2]}-{kind[3]} texts, each max {kind[1]} words]"
        if k in ("num", "int"):
            return f"{'whole ' if k == 'int' else ''}number {_show(kind[1])} to {_show(kind[2])}" if abs(kind[2]) < 1e8 \
                else "number"
        if k == "choice":
            return " | ".join(kind[1])
        if k == "bool":
            return "true/false"
        if k == "nums":
            return f"[{kind[1]}-{kind[2]} numbers]"
        if k == "icon":
            return "an icon name"
        if k == "ref":
            return f"index into {kind[1]}"
        return f"[{kind[1]}-{kind[2]} of {{" + ", ".join(f'"{s}": {kind_text(sk)}' for s, sk in kind[3].items()) + "}]"

    lines = []
    for n in names:
        t = TECH[n]
        fields = "; ".join(f'"{f}": {kind_text(k)}' for f, k in t["fields"].items())
        lines.append(f'- "{n}" (w at least {t["size"][0]}, h at least {t["size"][1]}): {t["use"]}. {fields}')
    return "\n".join(lines)


# Where each technique can be chosen (every one is also a part the diagram designer can draw):
# - PLOT_TYPES: new types for the "plot" shot (5 before, 20 now): statistics and ML charts on axes
# - GRAPHIC_TYPES: new motion graphics the art director picks for a shot (7 before, 35 now): icon-and-label explainers
#   and simple charts
# - SHOT_KINDS: every other technique is a shot kind of its own the script writer can choose (20 before)
PLOT_TYPES = ("histogram", "boxplot", "ridgeline", "normal", "cdf", "intervals", "numberline", "beeswarm", "scatter",
              "variance", "losscurve", "contour", "boundary", "kmeans", "pca")
GRAPHIC_TYPES = tuple(n for n, t in TECH.items() if t["fam"] == "explain") + (
    "rings", "gauge", "waffle", "pie", "bubble", "treemap", "lollipop", "funnel")
SHOT_KINDS = tuple(n for n in TECH if n not in PLOT_TYPES and n not in GRAPHIC_TYPES)


def pick(title: str, n: int = 28, used: Optional[set] = None, pool: Optional[tuple] = None) -> List[str]:
    """The techniques offered to one video: the ones that fit its subject best, then a seeded random share of the
    rest, so every video gets its own selection; techniques already used in this video are left out. pool limits
    the choice to one role (SHOT_KINDS, PLOT_TYPES, GRAPHIC_TYPES)."""
    used = used or set()
    words = set(re.findall(r"[a-z]+", title.lower()))

    def hits(tags) -> int:
        return sum(1 for t in tags if any(w == t or (min(len(w), len(t)) >= 4 and (w.startswith(t[:5]) or t.startswith(w[:5])))
                                          for w in words))
    fam_boost = {f: hits(set(w.split())) for f, w in FAMILY_WORDS.items()}
    rng = random.Random(re.sub(r"\W", "", title.lower()) or "x")
    scored = []
    for name, t in TECH.items():
        if name in used or (pool is not None and name not in pool):
            continue
        s = 3 * hits(t["tags"]) + 2 * fam_boost.get(t["fam"], 0) + (1 if t["fam"] == "explain" else 0)
        scored.append((s + rng.random(), name))
    scored.sort(reverse=True)
    top = [nm for _, nm in scored[: n * 3 // 5]]
    rest = [nm for _, nm in scored[n * 3 // 5:]]
    rng.shuffle(rest)
    return top + rest[: n - len(top)]
