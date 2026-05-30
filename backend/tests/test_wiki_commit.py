"""Tests for wiki commit / ingest trust."""

import shutil
from pathlib import Path

from app.schemas.api import ApprovedWikiUpdate
from app.teacher_agent.wiki_store import WikiStore
from tests.wiki_fixtures import CLASS_ID, DIARY, SEED_WIKI


def test_compile_from_diary_includes_raw_proposal():
    wiki = WikiStore(root=SEED_WIKI)
    _, proposals = wiki.compile_from_diary(CLASS_ID, DIARY)
    assert any(p.wiki_path.startswith("raw/classes/") for p in proposals)


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
