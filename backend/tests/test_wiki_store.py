"""Tests for wiki_store compile, timeline, students, index, and log."""

import re
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
    assert any("timeline.md" in p for p in paths)
    assert any("students/S-014.md" in p for p in paths)


def test_timeline_has_seed_lessons():
    root = Path(__file__).resolve().parent.parent / "teacher_wiki"
    wiki = WikiStore(root=root)
    timeline = wiki.get_timeline("chemie_9b_2026_27")
    assert len(timeline.entries) >= 2


def test_parse_student_observations():
    root = Path(__file__).resolve().parent.parent / "teacher_wiki"
    wiki = WikiStore(root=root)
    block = wiki._extract_section_body(DIARY, "Student observations")
    by_student = wiki._parse_student_observations(block)
    assert "S-014" in by_student
    assert "S-021" in by_student


def test_rebuild_index_includes_sections():
    root = Path(__file__).resolve().parent.parent / "teacher_wiki"
    wiki = WikiStore(root=root)
    wiki.rebuild_index()
    index = wiki.read_text(wiki.index_path)
    assert "## Classes" in index
    assert "### Lessons" in index
    assert "### Students" in index
    assert "chemie_9b_2026_27" in index


def test_append_log_iso_timestamp(tmp_path: Path):
    wiki = WikiStore(root=tmp_path)
    wiki.write_text(wiki.log_path, "# Wiki Log\n")
    wiki._append_log(
        "test_class",
        "2099-01-01",
        "Test Log Entry",
        ["wiki/test.md"],
        kind="test",
    )
    log_after = wiki.read_text(wiki.log_path)
    assert re.search(r"##\s*\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\]", log_after)
    assert "> Lesson date: 2099-01-01" in log_after
