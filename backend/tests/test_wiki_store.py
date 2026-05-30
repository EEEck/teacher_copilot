"""Tests for wiki_store compile, timeline, students, index, and log."""

import re
import shutil
from pathlib import Path

from app.schemas.api import ApprovedWikiUpdate
from app.teacher_agent.wiki_store import WikiStore

CLASS_ID = "chemie_9b_2026_27"
_SEED_WIKI = Path(__file__).resolve().parent.parent / "teacher_wiki"

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


def test_compile_from_diary_proposals_have_unique_wiki_paths():
    root = Path(__file__).resolve().parent.parent / "teacher_wiki"
    wiki = WikiStore(root=root)
    _, proposals = wiki.compile_from_diary("chemie_9b_2026_27", DIARY)
    paths = [p.wiki_path for p in proposals]
    assert len(paths) == len(set(paths))


def test_snapshot_last_committed_date_is_iso_date():
    root = Path(__file__).resolve().parent.parent / "teacher_wiki"
    wiki = WikiStore(root=root)
    snap = wiki.get_snapshot("chemie_9b_2026_27")
    if snap.last_committed_date:
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", snap.last_committed_date)
        assert "[" not in snap.last_committed_date


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


def test_compile_from_diary_includes_raw_proposal():
    root = Path(__file__).resolve().parent.parent / "teacher_wiki"
    wiki = WikiStore(root=root)
    _, proposals = wiki.compile_from_diary(CLASS_ID, DIARY)
    assert any(p.wiki_path.startswith("raw/classes/") for p in proposals)


def test_commit_skips_unapproved_wiki_paths(tmp_path: Path):
    root = tmp_path / "wiki"
    shutil.copytree(_SEED_WIKI, root)
    wiki = WikiStore(root=root)
    _, proposals = wiki.compile_from_diary(CLASS_ID, DIARY)
    lesson_prop = next(p for p in proposals if "lesson_results.md" in p.wiki_path)
    student_prop = next(p for p in proposals if "students/S-014.md" in p.wiki_path)
    student_path = wiki.student_path(CLASS_ID, "S-014")
    before = wiki.read_text(student_path)

    wiki.commit_ingest(
        CLASS_ID,
        DIARY,
        [
            ApprovedWikiUpdate(
                wiki_path=lesson_prop.wiki_path,
                content=lesson_prop.proposed_content,
                approved=True,
            ),
            ApprovedWikiUpdate(
                wiki_path=student_prop.wiki_path,
                content=student_prop.proposed_content,
                approved=False,
            ),
        ],
        "test-session",
    )

    after = wiki.read_text(student_path)
    assert after == before
    assert "## 2026-10-01" not in after


def test_commit_requires_lesson_results_approved(tmp_path: Path):
    root = tmp_path / "wiki"
    shutil.copytree(_SEED_WIKI, root)
    wiki = WikiStore(root=root)
    _, proposals = wiki.compile_from_diary(CLASS_ID, DIARY)
    timeline_prop = next(p for p in proposals if p.wiki_path.endswith("timeline.md"))

    try:
        wiki.commit_ingest(
            CLASS_ID,
            DIARY,
            [
                ApprovedWikiUpdate(
                    wiki_path=timeline_prop.wiki_path,
                    content=timeline_prop.proposed_content,
                    approved=True,
                ),
            ],
            "test-session",
        )
    except ValueError as e:
        assert "lesson_results" in str(e)
    else:
        raise AssertionError("expected ValueError when lesson_results not approved")


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
