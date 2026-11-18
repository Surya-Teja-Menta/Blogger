"""The owner's notes (blogwriter/notes.py): typed once, put in front of the research, the plan, the script and the look."""
import os

from blogwriter import design, notes, video


def test_notes_are_one_short_line_and_empty_without_them(monkeypatch):
    monkeypatch.delenv("VIDEO_NOTES", raising=False)
    assert notes.owner_notes() == "" and notes.block() == ""
    monkeypatch.setenv("VIDEO_NOTES", "  make it retro,\n also cover caching  ")
    assert notes.owner_notes() == "make it retro, also cover caching"
    assert "make it retro, also cover caching" in notes.block("the look") and "THE LOOK" in notes.block("the look")
    monkeypatch.setenv("VIDEO_NOTES", "x" * 2000)
    assert len(notes.owner_notes()) == 600


def test_the_script_rules_the_plan_and_the_art_director_all_carry_the_notes(monkeypatch):
    monkeypatch.setenv("VIDEO_NOTES", "retro 80s arcade style; also cover rate limiting")
    brief = video.check_brief({"minutes": 8, "acts": [{"title": "A"}]}, "education")
    rules, _ = video.shape_prompt(brief, "education", "Caching", "(none)")
    assert "retro 80s arcade style" in rules and "rate limiting" in rules
    assert "retro 80s arcade style" in design.prompt("Caching", "education", "calm")
    monkeypatch.delenv("VIDEO_NOTES")
    clean, _ = video.shape_prompt(brief, "education", "Caching", "(none)")
    assert "NOTES FROM THE OWNER" not in clean


def test_a_video_with_notes_always_asks_the_model_for_a_look(monkeypatch):
    monkeypatch.delenv("FILM_LOOK", raising=False)
    asked = []
    monkeypatch.setattr("blogwriter.looks.choose", lambda *a, **k: asked.append(a[3]) or None)
    monkeypatch.setenv("VIDEO_NOTES", "retro")
    design.design(lambda *a, **k: {}, "Some title", "education", "calm retro", lambda m: None, {})
    assert asked and "retro" in asked[0]                     # the look chooser sees the notes in the mood
