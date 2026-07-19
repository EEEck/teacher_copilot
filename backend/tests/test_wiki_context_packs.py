"""LogPack vs PlanPack isolation and anchor behavior."""

import shutil

from app.teacher_agent.wiki_store import WikiStore
from tests.wiki_fixtures import CLASS_ID, SEED_WIKI


def test_ingest_context_emphasizes_logging_and_student_notes():
    wiki = WikiStore(root=SEED_WIKI)
    ctx = wiki.build_ingest_context_slim(CLASS_ID)
    assert "Active class core context" in ctx
    assert "Update Memory task context" in ctx
    assert "Student roster excerpt" in ctx
    assert "S-001" in ctx or "pseudonymous" in ctx
    assert "AGENTS.md" not in ctx
    assert "Wiki logging conventions" not in ctx
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
    assert "Subject guide: chemie" in names
    assert "Curriculum profile" in names
    assert "Trusted source index" in names
    assert "Class memory: planning_brief.md" in names
    assert "Class memory: teaching_patterns.md" in names
    assert "Class memory: copilot_profile.md" in names
    assert "Class memory: session_summaries.md" in names
    assert "Common lesson patterns" in trace["text"]
    assert "by-lehrplanplus-chemie-9-ntg" in trace["text"]
    assert "Atombau und Periodensystem" not in trace["text"]
    assert all("function" in section for section in trace["sections"])
    assert all("source" in section for section in trace["sections"])


def test_active_class_core_includes_class_memory_but_not_the_subject_layer(tmp_path):
    shutil.copytree(SEED_WIKI, tmp_path, dirs_exist_ok=True)
    wiki = WikiStore(root=tmp_path)
    other_subject = tmp_path / "wiki" / "subjects" / "mathe.md"
    other_subject.write_text(
        "# Mathe\n\nThis subject guide must not be loaded for Chemie.",
        encoding="utf-8",
    )
    extra_memory = (
        tmp_path / "wiki" / "classes" / CLASS_ID / "memory" / "extra_note.md"
    )
    extra_memory.write_text("# Extra Note\n\nActive class extra memory.", encoding="utf-8")

    trace = wiki.build_active_class_core_context_trace(CLASS_ID)
    included_sources = {
        section["source"] for section in trace["sections"] if section["included"]
    }
    expected_memory_sources = {
        wiki.rel_wiki(path)
        for path in (tmp_path / "wiki" / "classes" / CLASS_ID / "memory").glob("*.md")
        if path.name != "teaching_framework_profile.md"
    }

    assert expected_memory_sources <= included_sources
    assert "Subject guide: chemie" not in [section["name"] for section in trace["sections"]]
    assert "This subject guide must not be loaded for Chemie." not in trace["text"]


def test_ingest_context_slim_does_not_embed_query_pack():
    wiki = WikiStore(root=SEED_WIKI)
    ctx = wiki.build_ingest_context_slim(CLASS_ID)
    assert "Ingest Query Pack" not in ctx
    assert "Previous lesson" in ctx
    assert ctx.count("## Student roster excerpt") == 1
    assert "## Open loops" not in ctx
    assert "## Course state" not in ctx
    assert "wiki/classes/chemie_9b_2026_27/open_loops.md" not in ctx


def test_context_package_ingest_uses_slim_pack():
    wiki = WikiStore(root=SEED_WIKI)
    ctx = wiki.build_context_package(CLASS_ID, "ingest")
    assert "Active class core context" in ctx
    assert "Update Memory task context" in ctx
    assert "Wiki index" not in ctx
    assert "Base class context" not in ctx
    assert "Ingest Query Pack" not in ctx


def test_teacher_and_active_class_core_are_separate_layers():
    wiki = WikiStore(root=SEED_WIKI)
    teacher = wiki.build_teacher_context_trace()
    core = wiki.build_active_class_core_context_trace(CLASS_ID)

    assert "Teacher Profile" in teacher["text"]
    assert "Teacher Profile" not in core["text"]
    assert "Subject guide: chemie" not in core["text"]
    assert "Class Copilot Profile" in core["text"]
    assert "Session Summaries" in core["text"]


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
