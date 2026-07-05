"""Tests for wiki commit / ingest trust."""

import shutil
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.schemas.api import ApprovedWikiUpdate
from app.teacher_agent.wiki_store import WikiStore
from tests.wiki_fixtures import CLASS_ID, DIARY, SEED_WIKI


def test_compile_from_diary_includes_raw_proposal():
    wiki = WikiStore(root=SEED_WIKI)
    _, proposals = wiki.compile_from_diary(CLASS_ID, DIARY)
    assert any(p.wiki_path.startswith("raw/classes/") for p in proposals)


def test_compile_from_diary_allows_future_lesson_date_for_draft_preview():
    # Drafts are also compiled for planned future lessons; only committing
    # results for a beyond-school-year date is blocked.
    wiki = WikiStore(root=SEED_WIKI)
    future = (date.today() + timedelta(days=400)).isoformat()
    diary = DIARY.replace("2026-10-01", future)
    lesson_date, _ = wiki.compile_from_diary(CLASS_ID, diary)
    assert lesson_date == future


def test_commit_rejects_beyond_school_year_lesson_date(tmp_path: Path):
    root = tmp_path / "wiki"
    shutil.copytree(SEED_WIKI, root)
    wiki = WikiStore(root=root)
    _, proposals = wiki.compile_from_diary(CLASS_ID, DIARY)
    future = (date.today() + timedelta(days=400)).isoformat()
    diary = DIARY.replace("2026-10-01", future)
    with pytest.raises(ValueError, match="school year"):
        wiki.commit_ingest(
            CLASS_ID,
            diary,
            [
                ApprovedWikiUpdate(
                    wiki_path=p.wiki_path,
                    content=p.proposed_content,
                    approved=True,
                )
                for p in proposals
            ],
            "future-date-session",
        )


def test_commit_allows_lesson_date_six_months_ahead(tmp_path: Path):
    # Teachers plan a full school year ahead — six months out must commit fine.
    root = tmp_path / "wiki"
    shutil.copytree(SEED_WIKI, root)
    wiki = WikiStore(root=root)
    soon = (date.today() + timedelta(days=180)).isoformat()
    diary = DIARY.replace("2026-10-01", soon)
    _, proposals = wiki.compile_from_diary(CLASS_ID, diary)
    _, applied, _ = wiki.commit_ingest(
        CLASS_ID,
        diary,
        [
            ApprovedWikiUpdate(
                wiki_path=p.wiki_path,
                content=p.proposed_content,
                approved=True,
            )
            for p in proposals
        ],
        "planned-ahead-session",
    )
    assert any("lesson_results.md" in path for path in applied)


def test_commit_skips_unapproved_wiki_paths(tmp_path: Path):
    root = tmp_path / "wiki"
    shutil.copytree(SEED_WIKI, root)
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


def test_commit_derives_student_pages_from_approved_lesson_results_when_draft_is_stale(
    tmp_path: Path,
):
    root = tmp_path / "wiki"
    shutil.copytree(SEED_WIKI, root)
    wiki = WikiStore(root=root)
    _, proposals = wiki.compile_from_diary(CLASS_ID, DIARY)
    lesson_prop = next(p for p in proposals if "lesson_results.md" in p.wiki_path)
    students_index_prop = next(p for p in proposals if p.wiki_path.endswith("students.md"))
    stale_diary = """# Lesson Results — 2026-10-01 — Test Lesson

## What was covered

## Student participation

## What went well

## What didn't go well

## Student observations

## Homework & follow-ups
"""

    _, applied, _ = wiki.commit_ingest(
        CLASS_ID,
        stale_diary,
        [
            ApprovedWikiUpdate(
                wiki_path=lesson_prop.wiki_path,
                content=lesson_prop.proposed_content,
                approved=True,
            ),
            ApprovedWikiUpdate(
                wiki_path=students_index_prop.wiki_path,
                content=students_index_prop.proposed_content,
                approved=True,
            ),
        ],
        "stale-draft-session",
    )

    assert f"wiki/classes/{CLASS_ID}/students/S-014.md" in applied
    assert f"wiki/classes/{CLASS_ID}/students/S-021.md" in applied
    assert "## 2026-10-01" in wiki.read_text(wiki.student_path(CLASS_ID, "S-014"))
    assert "Excellent" in wiki.read_text(wiki.student_path(CLASS_ID, "S-014"))


def test_commit_requires_lesson_results_approved(tmp_path: Path):
    root = tmp_path / "wiki"
    shutil.copytree(SEED_WIKI, root)
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


def test_repeated_commit_replaces_date_keyed_rollup_sections(tmp_path: Path):
    root = tmp_path / "wiki"
    shutil.copytree(SEED_WIKI, root)
    wiki = WikiStore(root=root)

    _, first_proposals = wiki.compile_from_diary(CLASS_ID, DIARY)
    wiki.commit_ingest(
        CLASS_ID,
        DIARY,
        [
            ApprovedWikiUpdate(
                wiki_path=p.wiki_path,
                content=p.proposed_content,
                approved=True,
            )
            for p in first_proposals
        ],
        "first-session",
    )

    _, second_proposals = wiki.compile_from_diary(CLASS_ID, DIARY)
    wiki.commit_ingest(
        CLASS_ID,
        DIARY,
        [
            ApprovedWikiUpdate(
                wiki_path=p.wiki_path,
                content=p.proposed_content,
                approved=True,
            )
            for p in second_proposals
        ],
        "second-session",
    )

    misconceptions = wiki.read_text(wiki.roll_up_paths(CLASS_ID)["misconceptions"])
    open_loops = wiki.read_text(wiki.roll_up_paths(CLASS_ID)["open_loops"])

    assert misconceptions.count("## 2026-10-01") == 1
    assert open_loops.count("## 2026-10-01") == 1
