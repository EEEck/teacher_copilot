"""PR1 (mem_v3 B1): post-save ``/memory/apply`` closes the originating ledger
rows so the Memory Sweep never re-proposes an already-applied fast-lane
candidate. See docs/mem_v3/next_implementation.md.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.memory_candidate_ledger import (
    MemoryCandidateLedger,
    MemoryCandidateRow,
)
from app.teacher_agent.wiki_store import WikiStore
from tests.conftest import CLASS_ID


def _fast_lane_teacher_profile_row(candidate_id: str, content: str) -> MemoryCandidateRow:
    """A backend-verified fast-lane teacher-preference row (the post-save shape)."""
    now = "2026-07-06T09:00:00Z"
    return MemoryCandidateRow(
        id=candidate_id,
        created_at=now,
        updated_at=now,
        class_id=CLASS_ID,
        subject="chemie",
        workflow="plan",
        session_id="sess-1",
        turn_index=1,
        channel="teacher_behavior",
        target="teacher_profile.md",
        section="Communication",
        candidate_update=content,
        evidence_summary="Direct teacher quote.",
        source="teacher_explicit",
        basis="explicit",
        confidence="high",
        status="captured",
        fast_lane=True,
    )


def test_apply_closes_ledger_row_and_sweep_skips_it(
    client: TestClient,
    wiki: WikiStore,
    memory_candidate_ledger: MemoryCandidateLedger,
):
    content = "Always keep future lesson plans in English."
    memory_candidate_ledger.add(_fast_lane_teacher_profile_row("cand-tp-1", content))

    # Precondition: the open fast-lane row is sweep-eligible before apply.
    review_before = memory_candidate_ledger.list_review_candidates(
        class_id=CLASS_ID, subject="chemie"
    )
    assert any(r.id == "cand-tp-1" for r in review_before)

    resp = client.post(
        f"/api/classes/{CLASS_ID}/memory/apply",
        json={
            "items": [
                {
                    "target": "teacher_profile.md",
                    "section": "Communication",
                    "content": content,
                    "candidate_ids": ["cand-tp-1"],
                }
            ]
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["updated_candidate_ids"] == ["cand-tp-1"]
    assert body["applied_wiki_paths"], body
    assert content in wiki.read_user_profile()

    # The originating row is closed to ``applied`` and no longer reviewable.
    applied = memory_candidate_ledger.list_candidates(statuses=["applied"])
    assert any(r.id == "cand-tp-1" for r in applied)
    review_after = memory_candidate_ledger.list_review_candidates(
        class_id=CLASS_ID, subject="chemie"
    )
    assert all(r.id != "cand-tp-1" for r in review_after)

    # And the HTTP sweep does not re-propose it.
    sweep = client.post(f"/api/classes/{CLASS_ID}/memory/sweep/propose")
    assert sweep.status_code == 200, sweep.text
    proposed_ids = {
        cid
        for cards in sweep.json()["queues"].values()
        for card in cards
        for cid in [card["candidate_id"], *card["candidate_ids"]]
    }
    assert "cand-tp-1" not in proposed_ids


def test_apply_leaves_row_open_when_write_does_not_land(
    client: TestClient,
    memory_candidate_ledger: MemoryCandidateLedger,
):
    # An unsupported target is skipped, never written — so its ledger row must
    # stay reviewable rather than being wrongly marked applied.
    memory_candidate_ledger.add(
        _fast_lane_teacher_profile_row("cand-skip-1", "Never written.")
    )

    resp = client.post(
        f"/api/classes/{CLASS_ID}/memory/apply",
        json={
            "items": [
                {
                    "target": "canonical_wiki",
                    "section": "General",
                    "content": "Never written.",
                    "candidate_ids": ["cand-skip-1"],
                }
            ]
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["updated_candidate_ids"] == []
    assert body["skipped"]

    still_open = memory_candidate_ledger.list_candidates(statuses=["captured"])
    assert any(r.id == "cand-skip-1" for r in still_open)


def test_approved_framework_adjustment_regenerates_only_the_class_profile(
    client: TestClient,
    wiki: WikiStore,
):
    base_path = (
        wiki.root / "wiki" / "subjects" / "chemie" / "teaching_frameworks" / "09" / "key_summary.md"
    )
    base = wiki.read_text(base_path)
    adjustment = "Use particle-model drawings before formal ion notation."

    resp = client.post(
        f"/api/classes/{CLASS_ID}/memory/apply",
        json={"items": [{"target": "teaching_framework_profile.md", "section": "Teacher-approved adjustments", "content": adjustment}]},
    )

    assert resp.status_code == 200, resp.text
    profile = wiki.read_text(wiki.memory_dir(CLASS_ID) / "teaching_framework_profile.md")
    assert adjustment in profile
    assert wiki.read_text(base_path) == base
