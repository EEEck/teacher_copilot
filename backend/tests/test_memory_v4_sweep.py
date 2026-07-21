"""Memory V4 PR3 contracts for second-judge Sweep behavior."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services.memory_candidate_ledger import MemoryCandidateLedger, MemoryCandidateRow
from app.services.memory_gate import gate_clusters
from app.services.memory_sweep import (
    cards_from_consolidation_ops,
    claims_from_clusters,
    propose_memory_sweep_review,
    validate_consolidation_ops,
)
from app.teacher_agent.models import (
    MemoryConsolidationOpOutput,
    MemoryConsolidationOutput,
)
from tests.conftest import CLASS_ID


NOW = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)


def _row(candidate_id: str = "singleton") -> MemoryCandidateRow:
    timestamp = "2026-07-17T10:00:00Z"
    return MemoryCandidateRow(
        id=candidate_id,
        created_at=timestamp,
        updated_at=timestamp,
        class_id=None,
        subject=None,
        workflow="plan",
        session_id="plan-1",
        turn_index=1,
        channel="teacher_behavior",
        target="teacher_profile.md",
        section="Communication",
        candidate_update="Prefer concise structured planning summaries.",
        evidence_summary="A possible teacher preference from one planning turn.",
        source="inferred_from_session",
        basis="inferred",
        confidence="low",
        cluster_key="teacher.communication.concise",
    )


def _claim(candidate_id: str = "candidate-1") -> dict:
    return {
        "claim_id": "C1",
        "cluster_key": "teacher.communication.concise",
        "target": "teacher_profile.md",
        "section": "Communication",
        "text": "Prefer concise structured planning summaries.",
        "evidence_summary": "Teacher may prefer concise planning summaries.",
        "signal_count": 1,
        "occasion_count": 1,
        "explicit": False,
        "candidate_ids": [candidate_id],
    }


def test_singleton_reaches_sweep_with_low_priority_metadata():
    singleton = _row()
    gate = gate_clusters([[singleton]], NOW)

    claims = claims_from_clusters(
        gate.eligible + gate.held,
        NOW,
        eligible_cluster_keys={row.cluster_key for cluster in gate.eligible for row in cluster},
    )

    assert len(claims) == 1
    assert claims[0]["sweep_gate"] == "held"
    assert claims[0]["occasion_count"] == 1
    assert claims[0]["priority"] == "singleton"


def test_sweep_can_downgrade_a_candidate_without_making_it_applicable():
    ops = validate_consolidation_ops(
        [
            {
                "claim_ids": ["C1"],
                "operation": "none",
                "target": "teacher_profile.md",
                "section": "Communication",
                "sweep_action": "downgrade",
                "rationale": "One weak signal is not enough for a durable preference.",
            }
        ],
        {},
        {"C1"},
    )

    cards = cards_from_consolidation_ops(
        ops,
        [{**_claim(), "explicit": True}],
        {},
        {"teacher_profile.md": ""},
    )

    assert len(cards) == 1
    assert cards[0].operation == "reject_low_signal"
    assert cards[0].status_recommendation == "downgrade"
    assert cards[0].can_apply is False


def test_sweep_merge_is_a_reviewable_update_for_related_claims():
    claims = [_claim("candidate-1"), {**_claim("candidate-2"), "claim_id": "C2"}]
    ops = validate_consolidation_ops(
        [
            {
                "claim_ids": ["C1", "C2"],
                "operation": "update",
                "target": "teacher_profile.md",
                "section": "Communication",
                "memory_id": "M1",
                "new_text": "Teacher prefers concise structured planning summaries.",
                "sweep_action": "merge",
                "rationale": "Both signals describe one communication preference.",
            }
        ],
        {"M1": "Teacher prefers brief planning summaries."},
        {"C1", "C2"},
    )

    cards = cards_from_consolidation_ops(
        ops,
        claims,
        {"M1": "Teacher prefers brief planning summaries."},
        {"teacher_profile.md": "- Teacher prefers brief planning summaries."},
    )

    assert len(cards) == 1
    assert cards[0].operation == "adjust"
    assert cards[0].status_recommendation == "merge"
    assert cards[0].can_apply is True
    assert set(cards[0].candidate_ids) == {"candidate-1", "candidate-2"}


def test_sweep_rejects_model_operation_that_crosses_claim_target():
    with pytest.raises(ValueError, match="target"):
        validate_consolidation_ops(
            [
                {
                    "claim_ids": ["C1"],
                    "operation": "add",
                    "target": "teaching_patterns.md",
                    "section": "What Worked Well",
                    "new_text": "A class learning pattern.",
                    "sweep_action": "promote",
                }
            ],
            {},
            {"C1"},
            claim_targets={"C1": "teacher_profile.md"},
        )


@pytest.mark.anyio
async def test_proposal_sends_singletons_to_the_second_judge(tmp_path, wiki):
    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    ledger.add(_row())

    class CapturingSweepAgent:
        def __init__(self):
            self.claims = []

        async def consolidate_memory_sweep(
            self, class_id, subject, claims, memory_indexes, **kwargs
        ):
            self.claims = claims
            return MemoryConsolidationOutput(
                operations=[
                    MemoryConsolidationOpOutput(
                        claim_ids=[claim["claim_id"]],
                        operation="none",
                        target=claim["target"],
                        section=claim["section"],
                        sweep_action="needs_review",
                        rationale="Singleton is visible to the second judge.",
                    )
                    for claim in claims
                ],
                warnings=[],
            )

    agents = CapturingSweepAgent()
    result = await propose_memory_sweep_review(
        wiki=wiki,
        ledger=ledger,
        agents=agents,
        class_id=CLASS_ID,
    )

    assert agents.claims
    assert agents.claims[0]["sweep_gate"] == "held"
    card = next(iter(next(iter(result.cards_by_queue.values()))))
    assert card.status_recommendation == "needs_review"
