"""The course planner. Give it a subject (and, if you like, your own syllabus): an AI curriculum planner lays out
the whole course - modules and lessons, as many as the subject really needs at that level, each lesson one
teachable idea for an 8-12 minute video - and works out what it costs in free API calls and machine time. The
lessons then go to video generation in order, a wave at a time, each wave as large as the free quotas allow.
Each lesson knows its place: what came before (so it recalls only what it needs) and what comes next.

The course lives in the repo as courses/<slug>.json (public: nothing private is stored).

CLI (used by the "Make a course" workflow):
  python blogwriter/course.py plan "Machine Learning" --level basic [--syllabus "topics; you; want"] [--max 0]
  python blogwriter/course.py next SLUG [--take N]       (marks the next lessons as started; prints the matrix)
  python blogwriter/course.py done SLUG LESSON_ID --ok | --failed
  python blogwriter/course.py lesson SLUG LESSON_ID      (the lesson's context, as JSON)
  python blogwriter/course.py pending                    (courses made automatically with lessons still to make)
  python blogwriter/course.py summary SLUG               (markdown, for the run summary)
"""
import argparse
import json
import math
import os
import re
import sys
import time
from typing import Callable, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COURSES = os.path.join(ROOT, "courses")
LEVELS = ("basic", "intermediate", "advanced")
MAX_LESSONS = 60
MAX_TRIES = 2
# what one 10-minute lesson costs, measured on the pipeline: vision-model calls (diagram design and review,
# the quality check), text-model calls (research, script, art direction) and GitHub machine hours (prepare,
# render parts, finish). GitHub machines are free for a public repository; the vision calls are the limit.
PER_LESSON = {"vision_calls": 60, "text_calls": 45, "machine_hours": 6.5}
VISION_CALLS_PER_DAY = 250          # assumed free daily allowance per Gemini key; set GEMINI_DAILY_CALLS to yours

PLAN = """You are the head of curriculum for a YouTube teaching channel whose lessons are animated, visual and
rigorous (3Blue1Brown, StatQuest, Khan Academy). Plan a complete course.

Subject: {subject}
Audience level: {level}
{syllabus}
Decide how many lessons this subject truly needs at this level to be taught properly: every important idea gets
its own lesson, nothing is padded, nothing essential is skipped (typically 10 to 40 lessons). Order the lessons
so each builds only on earlier ones, and group them into modules. Each lesson is ONE teachable idea that fits one
8 to 12 minute video.

Reply with JSON:
{{"course": "the course title", "description": "2 sentences: what the viewer will be able to do at the end",
 "modules": [{{"title": "module title", "lessons": [{{
   "title": "specific lesson title, at most 8 words",
   "goal": "After this lesson you can ... (one sentence)",
   "key_ideas": ["3 to 6 ideas it must cover"],
   "visuals": ["2 to 4 pictures that would make it click, e.g. a cost surface with a ball rolling to its lowest point"],
   "maths": true if it has formulas worth teaching, else false,
   "minutes": 8 to 12}}]}}]}}"""


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48] or "course"


def path_of(slug: str) -> str:
    return os.path.join(COURSES, f"{slugify(slug)}.json")


def load(slug: str) -> dict:
    with open(path_of(slug), encoding="utf-8") as f:
        return json.load(f)


def save(course: dict) -> str:
    os.makedirs(COURSES, exist_ok=True)
    path = path_of(course["slug"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(course, f, indent=1, ensure_ascii=False)
    return path


def check_plan(raw, subject: str, level: str, cap: int = 0) -> Optional[dict]:
    """The course as the pipeline can use it: lessons flattened in order with ids, short fields trimmed,
    duplicates dropped; None if no usable lesson came back."""
    if not isinstance(raw, dict):
        return None
    cap = min(MAX_LESSONS, cap or MAX_LESSONS)
    lessons, seen = [], set()
    words = lambda v, n: " ".join(str(v or "").split()[:n])            # noqa: E731
    for module in raw.get("modules") or []:
        if not isinstance(module, dict):
            continue
        mtitle = words(module.get("title"), 8)
        for raw_lesson in module.get("lessons") or []:
            if not isinstance(raw_lesson, dict) or len(lessons) >= cap:
                continue
            title = words(raw_lesson.get("title"), 10)
            if not title or title.lower() in seen:
                continue
            seen.add(title.lower())
            try:
                minutes = min(12, max(8, int(float(raw_lesson.get("minutes", 10)))))
            except (TypeError, ValueError):
                minutes = 10
            lessons.append({"id": f"L{len(lessons) + 1:02d}", "module": mtitle, "title": title,
                            "goal": words(raw_lesson.get("goal"), 40),
                            "key_ideas": [words(k, 16) for k in (raw_lesson.get("key_ideas") or [])[:6] if words(k, 16)],
                            "visuals": [words(v, 24) for v in (raw_lesson.get("visuals") or [])[:4] if words(v, 24)],
                            "maths": bool(raw_lesson.get("maths")), "minutes": minutes,
                            "status": "pending", "tries": 0, "started": 0, "finished": 0})
    if not lessons:
        return None
    name = words(raw.get("course"), 10) or subject
    return {"slug": slugify(subject), "subject": subject, "course": name, "level": level,
            "description": words(raw.get("description"), 60), "created": int(time.time()), "lessons": lessons}


def budget(n: int, vision_keys: int, per_day: int = 0) -> dict:
    """What n lessons cost, and how many the free vision-model allowance carries in a day (a wave)."""
    daily = int(os.environ.get("GEMINI_DAILY_CALLS") or 0) or VISION_CALLS_PER_DAY * max(1, vision_keys)
    wave = per_day or int(os.environ.get("COURSE_LESSONS_PER_DAY") or 0) or max(1, daily // PER_LESSON["vision_calls"])
    return {"lessons": n, "vision_calls": n * PER_LESSON["vision_calls"], "text_calls": n * PER_LESSON["text_calls"],
            "machine_hours": round(n * PER_LESSON["machine_hours"], 1), "per_day": wave, "days": math.ceil(n / wave)}


def plan(subject: str, level: str, syllabus: str, complete_json: Callable, cap: int = 0) -> dict:
    mine = f"The teacher's own syllabus (cover all of it, in a sensible order):\n{syllabus}\n" if syllabus.strip() else ""
    raw = complete_json(PLAN.format(subject=subject, level=level, syllabus=mine), max_tokens=12000, temperature=0.4)
    course = check_plan(raw, subject, level, cap)
    if not course:
        raise ValueError("the planner returned no usable lessons")
    return course


def context(course: dict, lesson_id: str) -> dict:
    """Everything a lesson's video needs to know about its place in the course."""
    lessons = course["lessons"]
    k = next(i for i, x in enumerate(lessons) if x["id"] == lesson_id)
    me = lessons[k]
    return {"course": course["course"], "module": me["module"], "number": k + 1, "total": len(lessons),
            "id": me["id"], "title": me["title"], "goal": me["goal"], "key_ideas": me["key_ideas"],
            "visuals": me["visuals"], "maths": me["maths"], "minutes": me["minutes"],
            "previous": [{"title": p["title"], "key_ideas": p["key_ideas"]} for p in lessons[:k]],
            "next": lessons[k + 1]["title"] if k + 1 < len(lessons) else ""}


def take_next(course: dict, take: int, now: Optional[float] = None) -> List[dict]:
    """The next lessons to make, in course order (a failed one is tried again, up to MAX_TRIES); they are
    marked as started. A lesson started over 8 hours ago that never reported back counts as failed."""
    now = now or time.time()
    for x in course["lessons"]:
        if x["status"] == "running" and now - x["started"] > 8 * 3600:
            x["status"] = "failed"
    todo = [x for x in course["lessons"] if x["status"] == "pending" or (x["status"] == "failed" and x["tries"] < MAX_TRIES)]
    picked = todo[:max(0, take)]
    for x in picked:
        x.update(status="running", started=int(now), tries=x["tries"] + 1)
    return [{"id": x["id"], "topic": f"{x['title']} ({course['course']})"} for x in picked]


def mark(course: dict, lesson_id: str, ok: bool) -> None:
    for x in course["lessons"]:
        if x["id"] == lesson_id:
            x.update(status="done" if ok else "failed", finished=int(time.time()))


def remaining(course: dict) -> int:
    return sum(1 for x in course["lessons"]
               if x["status"] == "pending" or (x["status"] == "failed" and x["tries"] < MAX_TRIES))


def summary(course: dict, vision_keys: int = 1) -> str:
    b = budget(len(course["lessons"]), vision_keys)
    rows, module = [], None
    for x in course["lessons"]:
        if x["module"] != module:
            module = x["module"]
            rows.append(f"\n**{module}**")
        mark_ = {"done": "[done]", "running": "[making]", "failed": "[failed]"}.get(x["status"], "")
        rows.append(f"- {x['id']} {x['title']} ({x['minutes']} min) {mark_}".rstrip())
    return (f"## {course['course']}\n{course['description']}\n\n{len(course['lessons'])} lessons; about "
            f"{b['vision_calls']} vision-model calls, {b['text_calls']} text-model calls and {b['machine_hours']} "
            f"machine hours in all. Made {b['per_day']} a day: about {b['days']} day(s).\n" + "\n".join(rows) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("subject")
    p.add_argument("--level", default="basic", choices=LEVELS)
    p.add_argument("--syllabus", default="")
    p.add_argument("--max", type=int, default=0)
    p.add_argument("--no-email", action="store_true")
    p.add_argument("--auto", action="store_true", help="continue the course by itself, a wave a day, until done")
    n = sub.add_parser("next")
    n.add_argument("slug")
    n.add_argument("--take", type=int, default=0)
    d = sub.add_parser("done")
    d.add_argument("slug")
    d.add_argument("lesson")
    d.add_argument("--ok", action="store_true")
    d.add_argument("--failed", action="store_true")
    les = sub.add_parser("lesson")
    les.add_argument("slug")
    les.add_argument("lesson")
    sub.add_parser("pending")
    s = sub.add_parser("summary")
    s.add_argument("slug")
    args = ap.parse_args()

    if args.cmd == "plan":
        sys.path.insert(0, ROOT)
        from blogwriter.config import Settings
        from blogwriter.llm import LLMClient
        from blogwriter.mailer import send_email
        settings = Settings.from_env()
        log = lambda m: print(m, file=sys.stderr)                     # noqa: E731
        course = plan(args.subject, args.level, args.syllabus, LLMClient(settings, log).complete_json, args.max)
        course["auto"] = args.auto
        save(course)
        text = summary(course, len(settings.gemini_keys))
        if not args.no_email:
            send_email(settings, f"[Course plan] {course['course']}: {len(course['lessons'])} lessons",
                       text.replace("**", "").replace("## ", "") +
                       "\nEach lesson is emailed for review when its video is ready. Nothing is posted.\n", [], log)
        print(course["slug"])
        return 0
    if args.cmd == "pending":
        for name in sorted(os.listdir(COURSES)) if os.path.isdir(COURSES) else []:
            if name.endswith(".json") and load(name[:-5]).get("auto") and remaining(load(name[:-5])):
                print(name[:-5])
        return 0
    course = load(args.slug)
    if args.cmd == "next":
        keys = len([k for k in os.environ.get("GEMINI_API_KEYS", "").split(",") if k.strip()])
        jobs = take_next(course, args.take or budget(len(course["lessons"]), keys)["per_day"])
        save(course)
        print(json.dumps(jobs))
    elif args.cmd == "done":
        mark(course, args.lesson, args.ok and not args.failed)
        save(course)
    elif args.cmd == "lesson":
        print(json.dumps(context(course, args.lesson), ensure_ascii=False))
    elif args.cmd == "summary":
        print(summary(course))
    return 0


if __name__ == "__main__":
    sys.exit(main())
