"""The owner's notes for one video: "make it retro", "also cover how caching helps", "keep it under 8 minutes", "mention
the 2021 outage". Typed into the "Notes" box of the Make a video workflow (VIDEO_NOTES in the environment) and put in front
of every model that shapes the video: the research (extra topics are searched too), the plan, the script (every part)
and the art director (colours, look, backdrop). The notes come first when they conflict with the defaults, and they never
license an invented fact: anything stated as fact still has to come from the researched facts."""
import os


def owner_notes() -> str:
    """The notes for this run, one line, at most 600 characters ("" when there are none)."""
    return " ".join(os.environ.get("VIDEO_NOTES", "").split())[:600]


def block(what: str = "this video") -> str:
    """The notes as a paragraph for a prompt ("" when there are none)."""
    n = owner_notes()
    return (f"\n\nNOTES FROM THE OWNER FOR {what.upper()} (follow them; they come before the defaults above when the two "
            f"disagree; a style or look note changes the look and the voice, a topic note adds that topic to the video; "
            f"never invent a fact for a note, state only what the facts support): {n}\n") if n else ""
