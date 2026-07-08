"""Deterministic Memory Capture speech-act goldens."""

from __future__ import annotations

import pytest

from app.teacher_agent.memory_capture import (
    DIRECT_TEACHER_QUOTE_PREFIX,
    MemoryCandidate,
    discipline_memory_candidates,
)
from tests.evals.goldens.memory_capture import MEMORY_CAPTURE_GOLDENS


@pytest.mark.parametrize(
    "golden",
    MEMORY_CAPTURE_GOLDENS,
    ids=[golden.golden_id for golden in MEMORY_CAPTURE_GOLDENS],
)
def test_memory_capture_speech_act_golden(golden):
    targets = golden.expected_targets or (golden.target,)
    candidates = [
        MemoryCandidate(
            target=target,
            section="General",
            candidate_update="Golden durable memory candidate.",
            evidence=golden.evidence,
            source="teacher_explicit",
            basis="explicit",
            confidence="high",
            speech_act=golden.speech_act,
        )
        for target in targets
    ]

    out = discipline_memory_candidates(candidates, teacher_message=golden.teacher_message)

    assert len(out) == len(targets)
    for candidate in out:
        assert candidate.fast_lane is golden.expected_fast_lane
        assert candidate.source == golden.expected_source
        if golden.expected_fast_lane:
            assert candidate.evidence.startswith(DIRECT_TEACHER_QUOTE_PREFIX)
        else:
            assert DIRECT_TEACHER_QUOTE_PREFIX not in candidate.evidence
