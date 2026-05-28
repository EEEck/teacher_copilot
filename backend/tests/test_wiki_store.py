"""Tests for wiki_store compile and timeline."""

from pathlib import Path

from app.teacher_agent.wiki_store import WikiStore

DIARY = """# Lesson Results — 2026-10-01 — Test Lesson

## What was covered
- Topic A
- Topic B

## Student participation
- Active class discussion

## What went well
- Good engagement

## What didn't go well
- Rushed ending

## Student observations
- S-014: Excellent
- S-021: Needed help

## Homework & follow-ups
- Homework: Sheet 3
- Next: Review Topic A
"""


def test_compile_from_diary_produces_lesson_results_and_rollups():
    root = Path(__file__).resolve().parent.parent / "teacher_wiki"
    wiki = WikiStore(root=root)
    _, proposals = wiki.compile_from_diary("chemie_9b_2026_27", DIARY)
    paths = {p.wiki_path for p in proposals}
    assert any("lesson_results.md" in p for p in paths)
    assert any("course_state.md" in p for p in paths)
    assert any("student_notes.md" in p for p in paths)


def test_timeline_has_seed_lessons():
    root = Path(__file__).resolve().parent.parent / "teacher_wiki"
    wiki = WikiStore(root=root)
    timeline = wiki.get_timeline("chemie_9b_2026_27")
    assert len(timeline.entries) >= 2
