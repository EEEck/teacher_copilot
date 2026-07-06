"""DeepEval Memory Sweep goldens with deterministic ledger + apply helpers."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from deepeval import assert_test
from deepeval.dataset import Golden
from deepeval.test_case import LLMTestCase

from app.services.memory_apply import apply_memory_items
from app.services.memory_candidate_ledger import (
    MemoryCandidateLedger,
    MemoryCandidateRow,
)
from tests.evals.goldens.memory_sweep import MEMORY_SWEEP_GOLDENS, MemorySweepSeed
from tests.evals.metrics.memory_sweep_metrics import MemorySweepMetric


@dataclass(frozen=True)
class _ApplyItem:
    target: str
    section: str
    content: str


def _row_from_seed(seed: MemorySweepSeed) -> MemoryCandidateRow:
    return MemoryCandidateRow(
        id=seed.candidate_id,
        created_at="2026-06-22T09:00:00Z",
        updated_at="2026-06-22T09:00:00Z",
        class_id=seed.class_id,
        subject=seed.subject,
        workflow=seed.workflow,
        session_id=seed.session_id,
        turn_index=1,
        channel=seed.channel,
        target=seed.target,
        section=seed.section,
        candidate_update=seed.content,
        evidence_summary="Golden Memory Sweep evidence.",
        evidence_refs=["golden:memory_sweep"],
        source=seed.source,
        basis=seed.basis,
        confidence=seed.confidence,
        cluster_key=seed.candidate_id,
    )


def _proposal_lookup(grouped):
    return {
        proposal.candidate_id: proposal
        for proposals in grouped.values()
        for proposal in proposals
    }


@pytest.mark.parametrize(
    "golden",
    MEMORY_SWEEP_GOLDENS,
    ids=[g.golden_id for g in MEMORY_SWEEP_GOLDENS],
)
def test_memory_sweep_golden_stub(tmp_path, eval_wiki, golden):
    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    ledger.add_many(_row_from_seed(seed) for seed in golden.seeds)

    grouped = ledger.propose_for_sweep(class_id=golden.class_id, subject=golden.subject)
    proposals_by_id = _proposal_lookup(grouped)
    grouped_targets = {
        queue: [proposal.target for proposal in proposals]
        for queue, proposals in grouped.items()
    }

    paths_to_track = set(golden.changed_markers) | set(golden.unchanged_paths)
    before_texts = {
        path: eval_wiki.read_wiki_page(path)
        for path in paths_to_track
    }

    apply_items = [
        _ApplyItem(
            proposals_by_id[candidate_id].target,
            proposals_by_id[candidate_id].section,
            proposals_by_id[candidate_id].content,
        )
        for candidate_id in golden.apply_candidate_ids
    ]
    applied_paths, skipped, warnings, _ = apply_memory_items(eval_wiki, golden.class_id, apply_items)
    assert warnings == []

    for candidate_id in golden.apply_candidate_ids:
        ledger.update_status(
            candidate_id,
            "applied",
            updated_at="2026-06-22T10:00:00Z",
            review_batch_id=golden.golden_id,
            promoted_at="2026-06-22T10:00:00Z",
        )
    for candidate_id in golden.reject_candidate_ids:
        ledger.update_status(
            candidate_id,
            "rejected",
            updated_at="2026-06-22T10:00:00Z",
            review_batch_id=golden.golden_id,
            rejection_reason="Golden rejection.",
        )

    after_texts = {
        path: eval_wiki.read_wiki_page(path)
        for path in paths_to_track
    }
    next_grouped = ledger.propose_for_sweep(class_id=golden.class_id, subject=golden.subject)
    remaining_candidate_ids = [
        proposal.candidate_id
        for proposals in next_grouped.values()
        for proposal in proposals
    ]

    test_case = LLMTestCase(
        input=golden.golden_id,
        actual_output="",
        metadata={
            "grouped_targets": grouped_targets,
            "applied_paths": applied_paths,
            "skipped": skipped,
            "before_texts": before_texts,
            "after_texts": after_texts,
            "remaining_candidate_ids": remaining_candidate_ids,
        },
    )
    deepeval_golden = Golden(
        input=test_case.input,
        metadata={
            "golden_id": golden.golden_id,
            "class_id": golden.class_id,
        },
    )
    assert_test(
        test_case=test_case,
        metrics=[MemorySweepMetric(golden=golden)],
        golden=deepeval_golden,
        run_async=False,
    )
