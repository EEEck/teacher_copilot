"""LogPack vs PlanPack isolation and anchor behavior."""

from pathlib import Path

from app.teacher_agent.wiki_store import WikiStore
from tests.wiki_fixtures import CLASS_ID, SEED_WIKI


def test_ingest_context_emphasizes_logging_and_student_notes():
    wiki = WikiStore(root=SEED_WIKI)
    ctx = wiki.build_ingest_context(CLASS_ID)
    assert "Update lesson notes" in ctx
    assert "Student notes" in ctx
    assert "S-xxx" in ctx or "pseudonyms" in ctx
    assert "AGENTS.md" in ctx or "Wiki logging conventions" in ctx
    assert "Plan next lesson" not in ctx


def test_plan_context_emphasizes_forward_planning():
    wiki = WikiStore(root=SEED_WIKI)
    ctx = wiki.build_plan_context(CLASS_ID)
    assert "Plan next lesson" in ctx
    assert "Planning Query Pack" in ctx
    assert "Top misconceptions" in ctx
    assert "upcoming lesson" in ctx.lower()
    assert "Student notes (use S-xxx" not in ctx


def test_ingest_context_includes_ingest_query_pack():
    wiki = WikiStore(root=SEED_WIKI)
    ctx = wiki.build_ingest_context(CLASS_ID)
    assert "Ingest Query Pack" in ctx
    assert "Previous lesson" in ctx


def test_review_query_pack_is_available():
    wiki = WikiStore(root=SEED_WIKI)
    ctx = wiki.build_review_query_pack(CLASS_ID)
    assert "Review Query Pack" in ctx
    assert "Taught-so-far sequence" in ctx


def test_snapshot_last_committed_date_is_iso_not_bracketed():
    wiki = WikiStore(root=SEED_WIKI)
    snap = wiki.get_snapshot(CLASS_ID)
    if snap.last_committed_date:
        assert "[" not in snap.last_committed_date
        assert len(snap.last_committed_date) == 10
