"""Tests for wiki.parsing pure helpers."""

from app.teacher_agent.wiki import parsing
from tests.wiki_fixtures import DIARY


def test_extract_title_from_diary():
    assert parsing.extract_title(DIARY) == "Test Lesson"


def test_extract_date_from_diary():
    assert parsing.extract_date_from_diary(DIARY) == "2026-10-01"


def test_extract_section_body_student_observations():
    block = parsing.extract_section_body(DIARY, "Student observations")
    assert "S-014" in block
    assert "S-021" in block


def test_parse_student_observations():
    block = parsing.extract_section_body(DIARY, "Student observations")
    by_student = parsing.parse_student_observations(block)
    assert "S-014" in by_student
    assert "S-021" in by_student
    assert any("Excellent" in b for b in by_student["S-014"])


def test_lines_to_bullets_skips_empty_markers():
    bullets = parsing.lines_to_bullets("- Real item\n- none\n- N/A")
    assert bullets == ["Real item"]


def test_parse_log_entry_iso_header():
    header = "## [2026-05-01T12:00:00] ingest | 2026-10-01 — Demo (id:abc12345)"
    block = header + "\n> Lesson date: 2026-10-01\n- Updated: wiki/classes/x/lessons/2026-10-01/lesson_results.md"
    meta = parsing.parse_log_entry(header, block)
    assert meta is not None
    assert meta["lesson_date"] == "2026-10-01"
    assert meta["title"] == "Demo"
    assert "lesson_results.md" in meta["wiki_paths"][0]
