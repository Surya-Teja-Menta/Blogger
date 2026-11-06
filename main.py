"""CLI:  python main.py "topic" [--source news|topic] [--mode fast|standard|deep] [--pages N]
                  [--level basic|intermediate|advanced] [--niche general|upsc|business|tech] [--lang en|hi|te|kn|ta]
                  [--days N] [--no-pdf] [--no-email] [--no-publish] [--email-to a@x.com,b@y.com] [--video]
                  [--style auto|news|story|education|concept]"""
import argparse
import sys
from dataclasses import replace

from blogwriter import BlogPipeline, PipelineError
from blogwriter.config import Settings, _split
from blogwriter.writer import LANGS, LEVELS, NICHES


def main() -> int:
    ap = argparse.ArgumentParser(description="Automatic news-driven blog / report generator")
    ap.add_argument("topic", nargs="*", help="topic, e.g. 'geopolitics'")
    ap.add_argument("--source", default="news", choices=["news", "topic"],
                    help="news: today's hottest story on the topic; topic: research the topic itself")
    ap.add_argument("--mode", default="standard", choices=["fast", "standard", "deep"])
    ap.add_argument("--pages", type=int, default=0, help="target report length in pages (overrides --mode)")
    ap.add_argument("--level", default="intermediate", choices=list(LEVELS))
    ap.add_argument("--niche", default="general", choices=list(NICHES))
    ap.add_argument("--lang", default="en", choices=list(LANGS))
    ap.add_argument("--days", type=int, default=1, help="how many days back to look for news")
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--no-email", action="store_true", help="save the files but do not send the email")
    ap.add_argument("--no-publish", action="store_true", help="private order: no Gumroad listing, no blog posts")
    ap.add_argument("--email-to", default="", help="send the result to these addresses instead of MAIL_TO")
    ap.add_argument("--style", default="", choices=["", "auto", "news", "story", "education", "concept"],
                    help="video style (default: news for --source news, auto for --source topic)")
    ap.add_argument("--video", action="store_true",
                    help="also make a long video, audio tracks per language and Shorts, emailed for review")
    ap.add_argument("--lesson", default="", help="SLUG:LESSON_ID of a planned course (blogwriter/course.py): the "
                                                  "video is that lesson, taught in its place in the course")
    args = ap.parse_args()
    lesson = None
    if args.lesson:
        from blogwriter import course
        slug, _, lesson_id = args.lesson.partition(":")
        lesson = course.context(course.load(slug), lesson_id)
    topic = " ".join(args.topic).strip() or (f"{lesson['title']} ({lesson['course']})" if lesson else "") or         input("Topic: ").strip()
    if not topic:
        print("No topic given.")
        return 2
    settings = Settings.from_env()
    if args.email_to.strip():
        settings = replace(settings, mail_to=_split(args.email_to))
    try:
        BlogPipeline(settings).run(topic, args.mode, args.days, make_pdf=not args.no_pdf, email=not args.no_email,
                                   source=args.source, pages=max(0, args.pages), level=args.level,
                                   niche=args.niche, lang=args.lang, publish=not args.no_publish,
                                   video=args.video or bool(lesson), style=args.style or ("education" if lesson else ""),
                                   lesson=lesson)
    except PipelineError as exc:
        print(f"\nFAILED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
