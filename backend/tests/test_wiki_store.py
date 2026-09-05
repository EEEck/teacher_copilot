"""Integration tests for WikiStore compile and read APIs."""

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
    assert any("students.md" in p for p in paths)
    assert any("timeline.md" in p for p in paths)
    assert any("students/S-014.md" in p for p in paths)


def test_compile_from_diary_proposals_have_unique_wiki_paths():
    root = Path(__file__).resolve().parent.parent / "teacher_wiki"
    wiki = WikiStore(root=root)
    _, proposals = wiki.compile_from_diary("chemie_9b_2026_27", DIARY)
    paths = [p.wiki_path for p in proposals]
    assert len(paths) == len(set(paths))


def test_seeded_snapshot_retains_last_lesson_commit_not_later_compaction():
    root = Path(__file__).resolve().parent.parent / "teacher_wiki"
    wiki = WikiStore(root=root)
    snap = wiki.get_snapshot("chemie_9b_2026_27")
    assert snap.last_committed_date == "2026-05-29"
    assert snap.last_committed_at == "2026-05-29T15:30:00"
    assert snap.last_committed_title == "Anions and Oxidation State Review"


def test_timeline_has_seed_lessons():
    root = Path(__file__).resolve().parent.parent / "teacher_wiki"
    wiki = WikiStore(root=root)
    timeline = wiki.get_timeline("chemie_9b_2026_27")
    assert len(timeline.entries) >= 2
