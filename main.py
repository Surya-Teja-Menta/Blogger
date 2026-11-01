"""CLI:  python main.py "topic" [--mode fast|standard|deep] [--days N] [--no-pdf] [--no-email]"""
import argparse
import sys

from blogwriter import BlogPipeline, PipelineError


def main() -> int:
    ap = argparse.ArgumentParser(description="Automatic news-driven blog / report generator")
    ap.add_argument("topic", nargs="*", help="topic, e.g. 'geopolitics'")
    ap.add_argument("--mode", default="standard", choices=["fast", "standard", "deep"])
    ap.add_argument("--days", type=int, default=1, help="how many days back to look for news")
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--no-email", action="store_true", help="save the files but do not send the email")
    args = ap.parse_args()
    topic = " ".join(args.topic).strip() or input("Topic: ").strip()
    if not topic:
        print("No topic given.")
        return 2
    try:
        BlogPipeline().run(topic, args.mode, args.days, make_pdf=not args.no_pdf, email=not args.no_email)
    except PipelineError as exc:
        print(f"\nFAILED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
