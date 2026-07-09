from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services.memory_candidate_ledger import (
    MemoryCandidateLedger,
    MemoryCandidateRow,
)
from app.services.memory_sweep_reviews import (
    MemorySweepReviewStore,
    build_memory_sweep_source_snapshot,
    memory_sweep_source_fingerprint,
)
from app.teacher_agent.wiki_store import WikiStore
from tests.conftest import CLASS_ID, StubAgentRunner


def _seed_review_candidate(ledger: MemoryCandidateLedger) -> None:
    ledger.add(
        MemoryCandidateRow(
            id="cand_review_persistence_1",
            created_at="2026-07-09T08:00:00Z",
            updated_at="2026-07-09T08:00:00Z",
            class_id=CLASS_ID,
            subject="chemie",
            workflow="ingest",
            session_id="sess_review_persistence",
            turn_index=1,
            channel="class_learning_pattern",
            target="teaching_patterns.md",
            section="What Worked Well",
            candidate_update="Short retrieval warmups helped the class start faster.",
            evidence_summary="Teacher mentioned a faster start after retrieval.",
            evidence_refs=["wiki/classes/chemie_9b_2026_27/lessons/2026-07-08/lesson_results.md"],
            source="inferred_from_session",
            basis="repeated_behavior",
            confidence="medium",
            cluster_key="class.retrieval.faster_start",
        )
    )


def test_memory_sweep_review_store_persists_ready_review(tmp_path: Path) -> None:
    store = MemorySweepReviewStore(tmp_path / "memory_sweep_reviews.sqlite")
    store.initialize()

    review = store.create_generating(
        workspace_id="local",
        class_id=CLASS_ID,
        source_fingerprint="fp_1",
        source={"candidate_ids": ["cand_review_persistence_1"]},
    )
    ready = store.mark_ready(
        review.review_id,
        proposals={
            "class_id": CLASS_ID,
            "subject": "chemie",
            "queues": {"Class Evolution": [{"candidate_id": "cand_review_persistence_1"}]},
            "warnings": [],
        },
    )
    saved = store.save_decisions(
        ready.review_id,
        decisions=[
            {
                "card_id": "card_1",
                "action": "apply",
                "candidate_ids": ["cand_review_persistence_1"],
                "content": "Short retrieval warmups helped the class start faster.",
            }
        ],
    )

    reloaded = MemorySweepReviewStore(tmp_path / "memory_sweep_reviews.sqlite")
    reloaded.initialize()
    active = reloaded.get_active(CLASS_ID)

    assert active is not None
    assert active.review_id == saved.review_id
    assert active.status == "ready"
    assert active.has_teacher_edits is True
    assert active.proposals["queues"]["Class Evolution"][0]["candidate_id"] == "cand_review_persistence_1"
    assert active.decisions[0]["action"] == "apply"


def test_memory_sweep_source_fingerprint_changes_when_ledger_changes(
    wiki: WikiStore,
    tmp_path: Path,
) -> None:
    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    _seed_review_candidate(ledger)

    before = build_memory_sweep_source_snapshot(
        wiki=wiki,
        ledger=ledger,
        class_id=CLASS_ID,
    )
    before_fingerprint = memory_sweep_source_fingerprint(before)

    ledger.update_status(
        "cand_review_persistence_1",
        "snoozed",
        updated_at="2026-07-09T09:00:00Z",
        review_batch_id="review_1",
    )
    after = build_memory_sweep_source_snapshot(
        wiki=wiki,
        ledger=ledger,
        class_id=CLASS_ID,
    )

    assert memory_sweep_source_fingerprint(after) != before_fingerprint


def test_memory_sweep_review_api_opens_once_and_resumes(
    client: TestClient,
    memory_candidate_ledger: MemoryCandidateLedger,
    agents: StubAgentRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_review_candidate(memory_candidate_ledger)
    call_count = 0
    original = agents.consolidate_memory_sweep

    async def counted_consolidate(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return await original(*args, **kwargs)

    monkeypatch.setattr(agents, "consolidate_memory_sweep", counted_consolidate)

    first = client.post(f"/api/classes/{CLASS_ID}/memory/sweep/review")
    second = client.post(f"/api/classes/{CLASS_ID}/memory/sweep/review")

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["review_id"] == second.json()["review_id"]
    assert first.json()["status"] == "ready"
    assert call_count == 1


def test_memory_sweep_review_api_patches_decisions_and_discards(
    client: TestClient,
    memory_candidate_ledger: MemoryCandidateLedger,
) -> None:
    _seed_review_candidate(memory_candidate_ledger)
    opened = client.post(f"/api/classes/{CLASS_ID}/memory/sweep/review")
    assert opened.status_code == 200, opened.text
    review_id = opened.json()["review_id"]

    patched = client.patch(
        f"/api/classes/{CLASS_ID}/memory/sweep/review/{review_id}",
        json={
            "decisions": [
                {
                    "card_id": "card_1",
                    "action": "apply",
                    "target": "teaching_patterns.md",
                    "section": "What Worked Well",
                    "content": "Short retrieval warmups helped the class start faster.",
                    "candidate_ids": ["cand_review_persistence_1"],
                }
            ]
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["has_teacher_edits"] is True
    assert patched.json()["decisions"][0]["action"] == "apply"

    discarded = client.post(
        f"/api/classes/{CLASS_ID}/memory/sweep/review/{review_id}/discard"
    )
    assert discarded.status_code == 200, discarded.text
    assert discarded.json()["status"] == "discarded"

    reopened = client.post(f"/api/classes/{CLASS_ID}/memory/sweep/review")
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["review_id"] != review_id


def test_memory_sweep_review_apply_rejects_stale_fingerprint(
    client: TestClient,
    memory_candidate_ledger: MemoryCandidateLedger,
) -> None:
    _seed_review_candidate(memory_candidate_ledger)
    opened = client.post(f"/api/classes/{CLASS_ID}/memory/sweep/review")
    assert opened.status_code == 200, opened.text
    review_id = opened.json()["review_id"]
    card = next(
        card
        for cards in opened.json()["queues"].values()
        for card in cards
        if card["candidate_ids"]
    )
    patched = client.patch(
        f"/api/classes/{CLASS_ID}/memory/sweep/review/{review_id}",
        json={
            "decisions": [
                {
                    "card_id": card["card_id"],
                    "action": "apply",
                    "target": card["target"],
                    "section": card["section"],
                    "content": card["content"],
                    "operation": card["operation"],
                    "replaces_content": card["replaces_content"],
                    "candidate_ids": card["candidate_ids"],
                }
            ]
        },
    )
    assert patched.status_code == 200, patched.text
    memory_candidate_ledger.update_status(
        "cand_review_persistence_1",
        "snoozed",
        updated_at="2026-07-09T09:00:00Z",
        review_batch_id="review_stale",
    )

    applied = client.post(
        f"/api/classes/{CLASS_ID}/memory/sweep/review/{review_id}/apply"
    )

    assert applied.status_code == 409
    assert "stale_review" in applied.text
