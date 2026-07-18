"""PR 2 goldens for per-turn memory batching and ledger provenance."""

from __future__ import annotations

from app.services.memory_candidate_ledger import (
    MemoryCandidateLedger,
    insert_with_folding,
    rows_from_runtime_candidates,
)
from app.teacher_agent.memory_capture import (
    MemoryCandidate,
    bound_memory_capture_batch,
    candidate_key,
    group_memory_candidates,
)


def _candidate(index: int, **updates) -> MemoryCandidate:
    values = {
        "target": "teaching_patterns.md",
        "section": "class_learning_profile",
        "candidate_update": f"The class benefits from worked examples {index}.",
        "evidence": f"Direct teacher quote: The class benefits from worked examples {index}.",
        "source": "teacher_explicit",
        "basis": "explicit",
        "confidence": "high",
        "speech_act": "observation",
        "scope": "class",
        "origin_kind": "teacher_message",
        "origin_turn_index": 4,
        "origin_message_hash": "message-hash-4",
        "quote_fingerprint": f"quote-{index}",
        "capture_batch_id": "message-hash-4",
    }
    values.update(updates)
    return MemoryCandidate(**values)


def test_candidate_group_key_keeps_scope_and_section_distinct():
    first = _candidate(1)
    same_claim_other_scope = _candidate(1, scope="block", scope_label="organic chemistry")
    same_claim_other_section = _candidate(1, section="what_worked_well")

    assert len({candidate_key(first), candidate_key(same_claim_other_scope)}) == 2
    assert len({candidate_key(first), candidate_key(same_claim_other_section)}) == 2
    assert len(group_memory_candidates([first, same_claim_other_scope, same_claim_other_section])) == 3


def test_batch_guard_preserves_seven_claims_and_one_review_bundle():
    candidates = [_candidate(index) for index in range(10)]
    bounded = bound_memory_capture_batch(candidates, max_candidates=8)

    assert len(bounded) == 8
    assert [item.candidate_update for item in bounded[:7]] == [
        f"The class benefits from worked examples {index}." for index in range(7)
    ]
    overflow = bounded[-1]
    assert overflow.target == "canonical_wiki"
    assert overflow.admission == "needs_review"
    assert overflow.fast_lane is False
    assert "batch_overflow" in overflow.admission_reason_codes
    assert "worked examples 9" in overflow.evidence


def test_batch_guard_caps_fast_lane_rows_and_overflow_is_not_fast_lane():
    candidates = [
        _candidate(
            index,
            target="teacher_profile.md",
            section="communication",
            candidate_update=f"Keep preference {index}.",
            evidence=f"Direct teacher quote: Keep preference {index}.",
            speech_act="conduct_request",
            scope="global",
            fast_lane=True,
        )
        for index in range(12)
    ]
    bounded = bound_memory_capture_batch(candidates, max_candidates=8)

    assert len([item for item in bounded if item.fast_lane]) <= 7
    assert bounded[-1].fast_lane is False
    assert bounded[-1].admission == "needs_review"


def test_ledger_row_preserves_scope_origin_quote_and_batch_metadata(tmp_path):
    candidate = _candidate(1, scope_label="whole class")
    rows = rows_from_runtime_candidates(
        [candidate],
        class_id="chemie_9b_2026_27",
        subject="chemie",
        workflow="discuss",
        session_id="session-1",
        turn_index=4,
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.scope == "class"
    assert row.scope_label == "whole class"
    assert row.origin_kind == "teacher_message"
    assert row.origin_turn_index == 4
    assert row.origin_message_hash == "message-hash-4"
    assert row.quote_fingerprint == "quote-1"
    assert row.capture_batch_id == "message-hash-4"

    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    ledger.add(row)
    loaded = ledger.list_candidates()[0]
    assert loaded == row


def test_same_message_duplicate_is_idempotent_but_new_message_gets_new_row_id():
    first = _candidate(1)
    same_message = _candidate(1)
    later_message = _candidate(
        1,
        origin_turn_index=5,
        origin_message_hash="message-hash-5",
        quote_fingerprint="quote-5",
        capture_batch_id="message-hash-5",
    )
    first_row = rows_from_runtime_candidates(
        [first],
        class_id="chemie_9b_2026_27",
        subject="chemie",
        workflow="discuss",
        session_id="session-1",
        turn_index=4,
    )[0]
    retry_row = rows_from_runtime_candidates(
        [same_message],
        class_id="chemie_9b_2026_27",
        subject="chemie",
        workflow="discuss",
        session_id="session-1",
        turn_index=4,
    )[0]
    later_row = rows_from_runtime_candidates(
        [later_message],
        class_id="chemie_9b_2026_27",
        subject="chemie",
        workflow="discuss",
        session_id="session-1",
        turn_index=5,
    )[0]

    assert retry_row.id == first_row.id
    assert later_row.id != first_row.id


def test_separate_message_occurrences_share_a_cluster_for_reinforcement(tmp_path):
    first = _candidate(1)
    later = _candidate(
        1,
        origin_turn_index=5,
        origin_message_hash="message-hash-5",
        quote_fingerprint="quote-5",
        capture_batch_id="message-hash-5",
    )
    first_rows = rows_from_runtime_candidates(
        [first],
        class_id="chemie_9b_2026_27",
        subject="chemie",
        workflow="discuss",
        session_id="session-1",
        turn_index=5,
        occasion_key="lesson:2026-07-01",
    )
    later_rows = rows_from_runtime_candidates(
        [later],
        class_id="chemie_9b_2026_27",
        subject="chemie",
        workflow="discuss",
        session_id="session-1",
        turn_index=5,
        occasion_key="lesson:2026-07-08",
    )
    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    insert_with_folding(ledger, first_rows[0])
    insert_with_folding(ledger, later_rows[0])

    loaded = ledger.list_candidates()
    assert len(loaded) == 2
    assert loaded[0].cluster_key == loaded[1].cluster_key
