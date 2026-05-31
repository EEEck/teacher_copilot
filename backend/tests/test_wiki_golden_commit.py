"""Golden-style commit roundtrip: approved compile output is what lands on disk."""

import shutil
from pathlib import Path

from app.schemas.api import ApprovedWikiUpdate
from app.teacher_agent.wiki_store import WikiStore
from tests.wiki_fixtures import CLASS_ID, DIARY, SEED_WIKI

TEACHER_EDIT_MARKER = "TEACHER_EDIT_MARKER_IN_LESSON_RESULTS"


def test_full_approved_commit_writes_lesson_results_and_timeline(tmp_path: Path):
    root = tmp_path / "wiki"
    shutil.copytree(SEED_WIKI, root)
    wiki = WikiStore(root=root)
    lesson_date, proposals = wiki.compile_from_diary(CLASS_ID, DIARY)
    assert lesson_date == "2026-10-01"

    approved = [
        ApprovedWikiUpdate(
            wiki_path=p.wiki_path,
            content=p.proposed_content,
            approved=True,
        )
        for p in proposals
    ]
    lesson_prop = next(p for p in proposals if "lesson_results.md" in p.wiki_path)
    for u in approved:
        if u.wiki_path == lesson_prop.wiki_path:
            u.content = lesson_prop.proposed_content.replace(
                "Topic A", f"Topic A ({TEACHER_EDIT_MARKER})"
            )

    _, applied, log_id = wiki.commit_ingest(CLASS_ID, DIARY, approved, "golden-session")
    assert log_id
    assert lesson_prop.wiki_path in applied

    lesson_path = wiki.resolve_path(lesson_prop.wiki_path)
    written = wiki.read_text(lesson_path)
    assert TEACHER_EDIT_MARKER in written
    assert "Topic A" in written

    timeline_path = wiki.resolve_path(f"wiki/classes/{CLASS_ID}/timeline.md")
    timeline = wiki.read_text(timeline_path)
    assert "2026-10-01" in timeline

    raw_props = [p for p in proposals if p.wiki_path.startswith("raw/")]
    assert raw_props
    assert any(p.wiki_path in applied for p in raw_props)


def test_compile_proposal_paths_stable_on_seed():
    """Guards refactor: compile must still emit the full HITL surface."""
    wiki = WikiStore(root=SEED_WIKI)
    _, proposals = wiki.compile_from_diary(CLASS_ID, DIARY)
    paths = {p.wiki_path for p in proposals}
    suffixes = {p.rsplit("/", 1)[-1] for p in paths}
    assert "lesson_results.md" in suffixes
    assert "timeline.md" in suffixes
    assert "student_notes.md" in suffixes
    assert "course_state.md" in suffixes
    assert any(s.startswith("S-") and s.endswith(".md") for s in suffixes)
    assert any(p.startswith("raw/classes/") for p in paths)
