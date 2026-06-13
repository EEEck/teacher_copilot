"""LogPack vs PlanPack isolation and anchor behavior."""

from pathlib import Path

from app.teacher_agent.wiki_store import WikiStore
from tests.wiki_fixtures import CLASS_ID, SEED_WIKI


def test_ingest_context_emphasizes_logging_and_student_notes():
    wiki = WikiStore(root=SEED_WIKI)
    ctx = wiki.build_ingest_context_slim(CLASS_ID)
    assert "Ingest context (compact)" in ctx
    assert "Student roster excerpt" in ctx
    assert "S-001" in ctx or "pseudonymous" in ctx
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


def test_plan_context_slim_trace_names_context_contributors():
    wiki = WikiStore(root=SEED_WIKI)
    trace = wiki.build_plan_context_slim_trace(CLASS_ID)
    assert trace["text"] == wiki.build_plan_context_slim(CLASS_ID)
    names = [section["name"] for section in trace["sections"]]
    assert "Class identity snapshot" in names
    assert "Top misconceptions" in names
    assert "Recent lessons" in names
    assert "Subject guide" in names
    assert "Planning brief" in names
    assert "Teaching patterns" in names
    assert "Common lesson patterns" in trace["text"]
    assert all("function" in section for section in trace["sections"])
    assert all("source" in section for section in trace["sections"])


def test_ingest_context_slim_does_not_embed_query_pack():
    wiki = WikiStore(root=SEED_WIKI)
    ctx = wiki.build_ingest_context_slim(CLASS_ID)
    assert "Ingest Query Pack" not in ctx
    assert "Previous lesson" in ctx
    assert ctx.count("## Student roster excerpt") == 1
    assert ctx.count("## Open loops") == 1
    assert ctx.count("## Course state") == 1


def test_context_package_ingest_uses_slim_pack():
    wiki = WikiStore(root=SEED_WIKI)
    ctx = wiki.build_context_package(CLASS_ID, "ingest")
    assert "Ingest context (compact)" in ctx
    assert "Wiki index" not in ctx
    assert "Base class context" not in ctx
    assert "Ingest Query Pack" not in ctx


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
