"""Integration tests for WikiStore compile and read APIs."""

import re
from pathlib import Path

from app.teacher_agent.wiki_store import WikiStore
from tests.wiki_fixtures import DIARY


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
