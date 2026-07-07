"""Phase 2 tests: memory refresh proposal, profile proposal, HITL apply.

All durable writes stay teacher-approved: /memory/refresh and
/memory/profile/propose never write; only /memory/apply does, via the bounded
helpers. Offline against the stub agent + a tmp copy of the seed wiki.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.teacher_agent.wiki import memory as wiki_memory
from app.teacher_agent.wiki_store import WikiStore
from tests.conftest import CLASS_ID


# --- memory refresh proposal (no writes) ------------------------------------


def test_memory_refresh_proposes_without_writing(client: TestClient, wiki: WikiStore):
    mem = wiki.memory_paths(CLASS_ID)
    before = wiki.read_text(mem["copilot_profile"])

    res = client.post(f"/api/classes/{CLASS_ID}/memory/refresh", json={})
    assert res.status_code == 200, res.text
    body = res.json()
    # class_state.md / taught_so_far.md were retired; refresh proposes the
    # surviving curated pages only.
    assert "class_state" not in body["pages"]
    assert "taught_so_far" not in body["pages"]
    assert "planning_brief" in body["pages"]
    assert body["pages"]["planning_brief"].strip()
    # Proposal must not write anything.
    assert wiki.read_text(mem["copilot_profile"]) == before


def test_memory_compact_writes_surviving_pages(client: TestClient, wiki: WikiStore):
    res = client.post(f"/api/classes/{CLASS_ID}/memory/compact", json={})
    assert res.status_code == 200, res.text
    applied = res.json()["applied_wiki_paths"]
    assert f"wiki/classes/{CLASS_ID}/memory/planning_brief.md" in applied
    assert f"wiki/classes/{CLASS_ID}/memory/class_state.md" not in applied
    brief = wiki.read_text(wiki.memory_paths(CLASS_ID)["planning_brief"])
    assert brief.strip()


# --- profile proposal (explicit vs inferred, no writes) ---------------------


def test_profile_proposal_labels_basis(client: TestClient, wiki: WikiStore):
    user_before = wiki.read_user_profile()
    res = client.post(
        f"/api/classes/{CLASS_ID}/memory/profile/propose",
        json={"final_lesson_markdown": "# Lesson\n- redox"},
    )
    assert res.status_code == 200, res.text
    candidates = res.json()["candidates"]
    assert candidates
    targets = {c["target"] for c in candidates}
    assert {"teacher_profile.md", "copilot_profile.md"} <= targets
    assert {c["basis"] for c in candidates} <= {"explicit", "inferred"}
    # Proposal does not write.
    assert wiki.read_user_profile() == user_before


# --- bounded global user.md writer ------------------------------------------


def test_add_user_profile_conclusion_is_bounded(wiki: WikiStore):
    rel = wiki.add_user_profile_conclusion(
        "Communication", "Prefers concise, practical plans."
    )
    assert rel == "wiki/teacher_profile.md"
    assert "Prefers concise, practical plans." in wiki.read_user_profile()

    too_long = "x" * (wiki_memory.USER_PROFILE_ENTRY_LIMIT + 50)
    try:
        wiki.add_user_profile_conclusion("Communication", too_long)
    except ValueError as exc:
        assert "<=" in str(exc)
    else:
        raise AssertionError("expected ValueError for oversized entry")


def test_user_profile_section_cap(wiki: WikiStore):
    for i in range(wiki_memory.USER_PROFILE_SECTION_LIMIT + 4):
        wiki.add_user_profile_conclusion("Goals", f"Goal number {i}.")
    text = wiki.read_user_profile()
    bullets = [
        ln
        for ln in text.splitlines()
        if ln.strip().startswith("- Goal number")
    ]
    assert len(bullets) <= wiki_memory.USER_PROFILE_SECTION_LIMIT


# --- HITL apply writes only approved paths ----------------------------------


def test_memory_apply_writes_only_approved(client: TestClient, wiki: WikiStore):
    res = client.post(
        f"/api/classes/{CLASS_ID}/memory/apply",
        json={
            "items": [
                {
                    "target": "user.md",
                    "section": "Communication",
                    "content": "Prefers concise, practical plans.",
                },
                {
                    "target": "copilot.md",
                    "section": "Planning Patterns",
                    "content": "Draft early, then refine the markdown directly.",
                },
                {
                    "target": "teaching_patterns.md",
                    "section": "What Worked",
                    "content": "Short diagnostic checks surfaced misconceptions early.",
                },
                {"target": "canonical_wiki", "content": "Should be skipped."},
            ]
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "wiki/teacher_profile.md" in body["applied_wiki_paths"]
    assert (
        f"wiki/classes/{CLASS_ID}/memory/copilot_profile.md"
        in body["applied_wiki_paths"]
    )
    assert any("canonical_wiki" in s for s in body["skipped"])

    assert "Prefers concise, practical plans." in wiki.read_user_profile()
    assert (
        "Draft early, then refine the markdown directly."
        in wiki.read_copilot_profile(CLASS_ID)
    )
    assert (
        "Short diagnostic checks surfaced misconceptions early."
        in wiki.read_text(wiki.memory_paths(CLASS_ID)["teaching_patterns"])
    )


def test_memory_apply_unknown_class_404(client: TestClient):
    res = client.post(
        "/api/classes/nope/memory/apply",
        json={"items": [{"target": "user.md", "content": "x"}]},
    )
    assert res.status_code == 404


def test_apply_memory_items_helper_dispatch(wiki: WikiStore):
    from dataclasses import dataclass

    from app.services.memory_apply import apply_memory_items

    @dataclass
    class Item:
        target: str
        section: str
        content: str

    applied, skipped, warnings, _ = apply_memory_items(
        wiki,
        CLASS_ID,
        [
            Item("user.md", "Lesson Style", "Prefers concise plans."),
            Item("teaching_patterns.md", "What Worked", "Class 9b responds to worked examples."),
            Item("canonical_wiki", "", "ignored"),
            Item("user.md", "Lesson Style", "   "),
        ],
    )
    assert "wiki/teacher_profile.md" in applied
    assert any("teaching_patterns.md" in p for p in applied)
    assert any("canonical_wiki" in s for s in skipped)
    assert "empty item" in skipped
    assert warnings == []
