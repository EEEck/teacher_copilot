"""Tests for tiered class memory packages and manual compaction."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.teacher_agent.wiki_store import WikiStore
from tests.conftest import CLASS_ID


def test_context_packages_include_compact_memory_when_present(wiki: WikiStore):
    wiki.commit_memory_compaction(
        CLASS_ID,
        {
            "taught_so_far": "# Taught So Far\n\n- Compact sequence marker.\n",
            "planning_brief": "# Planning Brief\n\n- Planning marker.\n",
            "teaching_patterns": "# Teaching Patterns\n\n- Pattern marker.\n",
            "copilot_profile": "# Class Copilot Profile\n\n- Profile marker.\n",
        },
    )

    plan = wiki.build_context_package(CLASS_ID, "plan")
    ingest = wiki.build_context_package(CLASS_ID, "ingest")

    assert "Base class context" in plan
    assert "Last 2 taught lessons" in plan
    assert "Compact sequence marker" in plan
    assert "Profile marker" in plan
    assert "Recent saved plans" in ingest
    assert "Compact sequence marker" in ingest


def test_memory_compaction_normalizes_duplicate_class_header(wiki: WikiStore):
    wiki.commit_memory_compaction(
        CLASS_ID,
        {
            "taught_so_far": (
                f"# Taught So Far\n\n> Class: {CLASS_ID}\n\n"
                f"> Class: {CLASS_ID}\n\n- Compact sequence marker.\n"
            ),
        },
    )

    written = wiki.read_wiki_page(f"wiki/classes/{CLASS_ID}/memory/taught_so_far.md")
    assert written.count(f"> Class: {CLASS_ID}") == 1
    assert "Compact sequence marker" in written


def test_memory_compaction_adds_title_when_model_starts_at_h2(wiki: WikiStore):
    wiki.commit_memory_compaction(
        CLASS_ID,
        {
            "copilot_profile": (
                f"## Teacher Preferences\n\n> Class: {CLASS_ID}\n"
                "- Prefers compact plans.\n"
            ),
        },
    )

    written = wiki.read_wiki_page(f"wiki/classes/{CLASS_ID}/memory/copilot_profile.md")
    assert written.startswith("# Class Copilot Profile")
    assert written.count(f"> Class: {CLASS_ID}") == 1
    assert "## Teacher Preferences" in written


def test_profile_conclusion_is_bounded_and_class_scoped(wiki: WikiStore):
    rel = wiki.add_profile_conclusion(
        CLASS_ID,
        "Planning Patterns That Worked",
        "Peer checking helps reduce balancing errors.",
        source_path=f"wiki/classes/{CLASS_ID}/lessons/2026-05-07/lesson_results.md",
    )
    assert rel == f"wiki/classes/{CLASS_ID}/memory/copilot_profile.md"
    profile = wiki.read_copilot_profile(CLASS_ID)
    assert "Planning Patterns That Worked" in profile
    assert "Peer checking helps reduce balancing errors." in profile

    hits = wiki.search_personal_memory(CLASS_ID, "peer checking")
    assert hits
    assert hits[0]["path"].endswith("copilot_profile.md")


def test_profile_conclusion_rejects_non_class_source(wiki: WikiStore):
    try:
        wiki.add_profile_conclusion(
            CLASS_ID,
            "Teacher Preferences",
            "Prefers concise plans.",
            source_path="wiki/classes/other/lessons/2026-01-01/lesson_results.md",
        )
    except ValueError as exc:
        assert "source_path must be under" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_memory_compact_api_writes_only_class_memory(client: TestClient):
    res = client.post(f"/api/classes/{CLASS_ID}/memory/compact", json={})
    assert res.status_code == 200, res.text
    body = res.json()
    applied = body["applied_wiki_paths"]

    assert body["log_entry_id"]
    assert applied
    assert all(p.startswith(f"wiki/classes/{CLASS_ID}/memory/") for p in applied)
    assert f"wiki/classes/{CLASS_ID}/memory/copilot_profile.md" in applied
    assert body["source_paths"]

    file_res = client.get(
        f"/api/classes/{CLASS_ID}/wiki/file",
        params={"path": f"wiki/classes/{CLASS_ID}/memory/copilot_profile.md"},
    )
    assert file_res.status_code == 200
    assert "Teacher Preferences" in file_res.json()["markdown"]
