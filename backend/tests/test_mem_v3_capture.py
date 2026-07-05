"""Mem V3 Phase 3 goldens: capture discipline (docs/mem_v3/design.md lane 1).

Explicit/high durable-preference status must be corroborated by clearly
future-scoped teacher wording; otherwise candidates are weak inferred
signals routed through the sweep gate. This is the backend enforcement of
the owner rule from the beta round: a one-off "organize this in mbb style"
must never become a durable global preference.
"""

from __future__ import annotations

import pytest

from app.teacher_agent import memory_capture as capture
from app.teacher_agent.memory_capture import MemoryCandidate


# --- tightened future-scope markers ----------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        "From now on, use MBB-style communication for all lesson-planning summaries.",
        "Always start briefs with the recommendation.",
        "Going forward I want shorter homework blocks.",
        "Use this style in the future for all briefs.",
        "This is a general preference for me, not just this one class.",
        "Please keep answers concise for all future lessons.",
    ],
)
def test_future_scoped_statements_are_durable(message: str):
    assert capture.has_durable_preference_scope(message)


@pytest.mark.parametrize(
    "message",
    [
        # The beta failure case: a one-off formatting request.
        "can you organize the lesson results in a mbb style so it is easier to review",
        # Bare "future" as a topic word must not trigger.
        "The future of chemistry teaching is exciting.",
        "let's discuss future lesson ideas for this unit",
        # One-off scoping words.
        "just for this answer, keep it short",
        "",
    ],
)
def test_one_off_requests_are_not_durable(message: str):
    assert not capture.has_durable_preference_scope(message)


# --- discipline: downgrade unsupported explicit claims ----------------------


def _explicit_candidate(text: str = "Prefers MBB-style summaries.") -> MemoryCandidate:
    return MemoryCandidate(
        target="teacher_profile.md",
        section="Communication",
        candidate_update=text,
        source="teacher_explicit",
        basis="explicit",
        confidence="high",
    )


def _require_discipline():
    fn = getattr(capture, "discipline_memory_candidates", None)
    if fn is None:
        pytest.xfail("mem_v3 phase 3: discipline_memory_candidates not implemented")
    return fn


def test_explicit_claim_without_scope_is_downgraded():
    discipline = _require_discipline()
    out = discipline(
        [_explicit_candidate()],
        teacher_message="can you organize the lesson results in a mbb style",
    )
    assert len(out) == 1
    downgraded = out[0]
    assert downgraded.source == "inferred_from_session"
    assert downgraded.basis == "inferred"
    assert downgraded.confidence == "low"


def test_explicit_claim_with_scope_is_kept():
    discipline = _require_discipline()
    out = discipline(
        [_explicit_candidate()],
        teacher_message="From now on, use MBB-style summaries for all briefs.",
    )
    assert out[0].source == "teacher_explicit"
    assert out[0].confidence == "high"


def test_inferred_candidates_pass_through_unchanged():
    discipline = _require_discipline()
    inferred = MemoryCandidate(
        target="teaching_patterns.md",
        section="class_learning_profile",
        candidate_update="Class benefits from concrete examples first.",
        source="inferred_from_session",
        basis="inferred",
        confidence="low",
    )
    out = discipline([inferred], teacher_message="whatever was said")
    assert out[0] == inferred


def test_state_repair_still_requires_scope():
    # The typed-state repair path must obey the same rule.
    candidates = capture.durable_preference_candidates_from_state_values(
        ["Use MBB-style summaries."],
        teacher_message="can you organize this in mbb style",
    )
    assert candidates == []
    candidates = capture.durable_preference_candidates_from_state_values(
        ["Use MBB-style summaries."],
        teacher_message="From now on use MBB-style summaries for all briefs.",
    )
    assert len(candidates) == 1
    assert candidates[0].source == "teacher_explicit"
