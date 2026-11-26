"""The monthly channel report, emailed on the 1st: last month's views, watch time and new subscribers, every video's
numbers, and where viewers leave the most watched ones. Reads only (YouTube Analytics and Data APIs); needs a sign-in
that includes the yt-analytics.readonly permission (tools/yt_auth.py).

    python -m blogwriter.monthly [YYYY-MM]"""
import datetime as dt
import sys

import requests

from . import youtube

ANALYTICS = "https://youtubeanalytics.googleapis.com/v2/reports"
COLUMNS = "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained"
LEAVERS = 5          # how many of the most watched videos get the "where viewers leave" line


def month_of(text: str = "", today: dt.date = None) -> tuple:
    """(first day, last day) of "YYYY-MM", or of the month before today."""
    if text:
        first = dt.date.fromisoformat(f"{text}-01")
    else:
        first = ((today or dt.date.today()).replace(day=1) - dt.timedelta(days=1)).replace(day=1)
    return first, (first + dt.timedelta(days=32)).replace(day=1) - dt.timedelta(days=1)


def query(token: str, first, last, **extra) -> list:
    r = requests.get(ANALYTICS, params={"ids": "channel==MINE", "startDate": str(first), "endDate": str(last), **extra},
                     headers={"Authorization": f"Bearer {token}"}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"YouTube Analytics refused ({r.status_code}): {r.text[:300]}")
    return r.json().get("rows") or []


def titles(token: str, ids: list) -> dict:
    r = requests.get(f"{youtube.API_URL}/videos", params={"part": "snippet", "id": ",".join(ids[:50])},
                     headers={"Authorization": f"Bearer {token}"}, timeout=60)
    return {i["id"]: i["snippet"]["title"] for i in (r.json().get("items") or [])} if r.status_code == 200 else {}


def leave_point(rows: list) -> str:
    """rows: (share of the video, share of viewers still watching). The loss in the first tenth and the steepest tenth."""
    if len(rows) < 20:
        return ""
    step = len(rows) // 10
    drop, at = max((rows[k][1] - rows[k + step][1], rows[k][0]) for k in range(step, len(rows) - step))
    early = rows[0][1] - rows[step][1]
    return f"the first tenth loses {early:.0%}; the biggest fall after it is {drop:.0%}, from {at:.0%} into the video"


def build(token: str, first, last) -> str:
    total = query(token, first, last, metrics=COLUMNS)
    rows = query(token, first, last, metrics=COLUMNS, dimensions="video", sort="-views", maxResults=50)
    lines = [f"Adyora on YouTube, {first:%B %Y}", ""]
    if not total or not rows:
        return "\n".join(lines + ["No views recorded for this month."]) + "\n"
    views, minutes, _, percent, subs = total[0]
    lines += [f"Views: {views:,}   Watch time: {minutes / 60:,.1f} hours   Average watched: {percent:.0f}%   "
              f"New subscribers: {subs}", "", "Videos, most viewed first (views | average watched | new subscribers):"]
    names = titles(token, [r[0] for r in rows])
    for vid, v, _, seconds, pct, s in rows:
        lines.append(f"  {v:>6,} | {int(seconds) // 60}:{int(seconds) % 60:02d} ({pct:.0f}%) | {s} | {names.get(vid, vid)}")
    lines += ["", "Where viewers leave:"]
    for vid in [r[0] for r in rows[:LEAVERS]]:
        try:
            where = leave_point(query(token, first, last, metrics="audienceWatchRatio",
                                      dimensions="elapsedVideoTimeRatio", filters=f"video=={vid}"))
        except RuntimeError:
            where = ""
        lines.append(f"  {names.get(vid, vid)}: {where or 'not enough views yet'}")
    lines += ["", "Impressions and click-through rate: see YouTube Studio (Analytics > Reach)."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    from .config import Settings
    from .mailer import send_email
    first, last = month_of(argv[0] if argv else "")
    try:
        text, ok = build(youtube.access_token(), first, last), True
    except (RuntimeError, requests.RequestException, ValueError) as exc:
        text, ok = f"The monthly report could not be made: {exc}\n", False
    print(text)
    send_email(Settings.from_env(), f"[Monthly report] {first:%B %Y}", text, [], print)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
