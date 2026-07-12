from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import routes
from app.services.memory_candidate_ledger import (
    MemoryCandidateLedger,
    MemoryCandidateRow,
)
from app.services.memory_sweep_reviews import (
    MemorySweepReviewStore,
    build_memory_sweep_source_snapshot,
    memory_sweep_source_fingerprint,
    memory_sweep_stale_reasons,
)
from app.teacher_agent.wiki_store import WikiStore
from tests.conftest import CLASS_ID, StubAgentRunner


def _seed_review_candidate(
    ledger: MemoryCandidateLedger,
    *,
    candidate_id: str = "cand_review_persistence_1",
    created_at: str = "2026-07-09T08:00:00Z",
) -> None:
    ledger.add(
        MemoryCandidateRow(
            id=candidate_id,
            created_at=created_at,
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


def _wait_for_ready_review(client: TestClient):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        response = client.get(f"/api/classes/{CLASS_ID}/memory/sweep/review")
        if response.json()["status"] != "generating":
            assert response.json()["status"] == "ready", response.text
            return response
        time.sleep(0.01)
    pytest.fail("Memory Sweep review did not finish")


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


def test_discarded_memory_sweep_review_is_not_revived_by_generation(
    tmp_path: Path,
) -> None:
    store = MemorySweepReviewStore(tmp_path / "memory_sweep_reviews.sqlite")
    store.initialize()
    review = store.create_generating(
        class_id=CLASS_ID,
        source_fingerprint="fp_1",
        source={},
    )
    store.discard(review.review_id)

    finished = store.mark_ready(
        review.review_id,
        proposals={"class_id": CLASS_ID, "subject": "chemie", "queues": {}},
    )

    assert finished.status == "discarded"


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
    assert first.json()["status"] == "generating"
    _wait_for_ready_review(client)
    assert call_count == 1


def test_memory_sweep_review_api_returns_generating_before_work_completes(
    client: TestClient,
    memory_candidate_ledger: MemoryCandidateLedger,
) -> None:
    _seed_review_candidate(memory_candidate_ledger)

    opened = client.post(f"/api/classes/{CLASS_ID}/memory/sweep/review")

    assert opened.status_code == 200, opened.text
    assert opened.json()["status"] == "generating"
    review_id = opened.json()["review_id"]

    resumed = _wait_for_ready_review(client)

    assert resumed.json()["review_id"] == review_id


def test_memory_sweep_review_status_does_not_rebuild_source_while_generating(
    client: TestClient,
    memory_sweep_reviews: MemorySweepReviewStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    memory_sweep_reviews.create_generating(
        class_id=CLASS_ID,
        source_fingerprint="fp_1",
        source={},
    )

    def source_must_not_run(**kwargs):
        raise AssertionError("generating review should not rebuild its source")

    monkeypatch.setattr(routes, "_memory_sweep_source", source_must_not_run)

    response = client.get(f"/api/classes/{CLASS_ID}/memory/sweep/review")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "generating"


def test_memory_sweep_housekeeping_does_not_stale_its_new_review(
    client: TestClient,
    memory_candidate_ledger: MemoryCandidateLedger,
) -> None:
    _seed_review_candidate(
        memory_candidate_ledger,
        created_at="2020-01-01T08:00:00Z",
    )

    opened = client.post(f"/api/classes/{CLASS_ID}/memory/sweep/review")
    assert opened.status_code == 200, opened.text

    resumed = _wait_for_ready_review(client)

    assert resumed.json()["status"] == "ready"
    assert resumed.json()["is_stale"] is False


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
    opened = _wait_for_ready_review(client)
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


def test_memory_sweep_review_api_explains_new_candidates_that_make_a_draft_stale(
    client: TestClient,
    memory_candidate_ledger: MemoryCandidateLedger,
) -> None:
    _seed_review_candidate(memory_candidate_ledger)
    opened = client.post(f"/api/classes/{CLASS_ID}/memory/sweep/review")
    assert opened.status_code == 200, opened.text

    _seed_review_candidate(
        memory_candidate_ledger,
        candidate_id="cand_review_persistence_2",
    )
    resumed = client.get(f"/api/classes/{CLASS_ID}/memory/sweep/review")

    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["is_stale"] is True
    assert resumed.json()["stale_reasons"] == [
        "1 new memory candidate arrived after this draft was generated."
    ]


def test_memory_sweep_stale_reasons_tolerates_asymmetric_wiki_targets() -> None:
    """Union-of-keys diffs must not KeyError when a target exists on only one side.

    HITL 2026-07-12: teaching_patterns.md present only in the live snapshot raised
    KeyError and the frontend showed "Cannot reach API".
    """
    previous = {
        "ledger_rows": [],
        "wiki_targets": [],
        "synthetic_student_summaries": [],
    }
    current = {
        "ledger_rows": [],
        "wiki_targets": [
            {"target": "teaching_patterns.md", "excerpt_hash": "hash_live"}
        ],
        "synthetic_student_summaries": [],
    }
    reasons = memory_sweep_stale_reasons(previous, current)
    assert reasons == [
        "1 memory page changed after this draft was generated."
    ]

    # Removed target (only in previous) must also be safe.
    reasons_removed = memory_sweep_stale_reasons(current, previous)
    assert reasons_removed == [
        "1 memory page changed after this draft was generated."
    ]


def test_memory_sweep_stale_reasons_tolerates_asymmetric_student_summaries() -> None:
    previous = {
        "ledger_rows": [],
        "wiki_targets": [],
        "synthetic_student_summaries": [
            {
                "candidate_id": "cand_only_previous",
                "target": "students/anna.md",
                "content_hash": "c1",
                "excerpt_hash": "e1",
            }
        ],
    }
    current = {
        "ledger_rows": [],
        "wiki_targets": [],
        "synthetic_student_summaries": [],
    }
    reasons = memory_sweep_stale_reasons(previous, current)
    assert reasons == [
        "1 student summary changed after this draft was generated."
    ]
