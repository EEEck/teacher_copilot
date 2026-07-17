"""PR 1 goldens for semantic memory Admission and Priority boundaries."""

from __future__ import annotations

from app.teacher_agent.memory_capture import (
    MemoryCandidate,
    admit_memory_candidate,
    discipline_memory_candidates,
    runtime_candidates_to_ledger_rows,
)


def _candidate(**updates) -> MemoryCandidate:
    values = {
        "target": "teacher_profile.md",
        "section": "Communication",
        "candidate_update": "Prefer concise planning summaries.",
        "evidence": "Direct teacher quote: Please keep planning summaries concise.",
        "source": "teacher_explicit",
        "basis": "explicit",
        "confidence": "high",
        "speech_act": "conduct_request",
        "scope": "global",
    }
    values.update(updates)
    return MemoryCandidate(**values)


def test_direct_request_without_marker_is_admitted_and_fast_lane_eligible():
    message = "Please keep planning summaries concise."
    result = admit_memory_candidate(
        _candidate(), teacher_message=message, origin_message_id="turn-1"
    )

    assert result.admission == "stage"
    assert result.fast_lane is True
    assert result.reason_codes == ["explicit_request"]


def test_observation_with_always_never_overrides_speech_act():
    message = "This class always needs a worked example before the equation."
    candidate = _candidate(
        target="teaching_patterns.md",
        candidate_update="This class benefits from a worked example before equations.",
        evidence=f"Direct teacher quote: {message}",
        speech_act="observation",
        scope="class",
    )
    result = admit_memory_candidate(
        candidate, teacher_message=message, origin_message_id="turn-2"
    )

    assert result.admission == "stage"
    assert result.fast_lane is False
    assert "observation_signal" in result.reason_codes


def test_unknown_speech_act_or_scope_abstains_into_needs_review():
    message = "Use molecule models for organic chemistry."
    result = admit_memory_candidate(
        _candidate(
            target="teaching_patterns.md",
            evidence=f"Direct teacher quote: {message}",
            speech_act="unknown",
            scope="unknown",
        ),
        teacher_message=message,
        origin_message_id="turn-3",
    )

    assert result.admission == "needs_review"
    assert result.fast_lane is False
    assert "unknown_speech_act" in result.reason_codes
    assert "unknown_scope" in result.reason_codes


def test_missing_or_fabricated_quote_is_needs_review():
    message = "Can you keep the next plan concise?"
    missing = admit_memory_candidate(
        _candidate(evidence="Teacher asked for concise plans."),
        teacher_message=message,
        origin_message_id="turn-4",
    )
    fabricated = admit_memory_candidate(
        _candidate(
            evidence="Direct teacher quote: Always use a completely different format."
        ),
        teacher_message=message,
        origin_message_id="turn-4",
    )

    assert missing.admission == "needs_review"
    assert "missing_quote" in missing.reason_codes
    assert fabricated.admission == "needs_review"
    assert "quote_not_in_origin_message" in fabricated.reason_codes


def test_block_scope_is_valid_but_never_global_fast_lane():
    message = "For the organic chemistry block, start with molecule models."
    candidate = _candidate(
        target="teaching_patterns.md",
        candidate_update="Use molecule models first during the organic chemistry block.",
        evidence=f"Direct teacher quote: {message}",
        scope="block",
        scope_label="organic chemistry",
    )
    result = admit_memory_candidate(
        candidate, teacher_message=message, origin_message_id="turn-5"
    )

    assert result.admission == "stage"
    assert result.fast_lane is False
    assert result.candidate.scope_label == "organic chemistry"


def test_turn_scope_is_not_converted_to_a_durable_ledger_row():
    candidate = _candidate(
        scope="turn",
        evidence="Direct teacher quote: Please keep this answer concise.",
    )
    disciplined = discipline_memory_candidates(
        [candidate],
        teacher_message="Please keep this answer concise.",
        origin_turn_index=6,
    )

    assert disciplined[0].admission == "needs_review"
    assert runtime_candidates_to_ledger_rows(
        disciplined,
        class_id="chemie_9b_2026_27",
        subject="chemie",
        workflow="plan",
        session_id="turn-scope",
        turn_index=6,
    ) == []


def test_unsupported_target_is_downgraded_and_cannot_fast_lane():
    candidate = _candidate(
        target="session_summaries.md",
        evidence="Direct teacher quote: Please keep planning summaries concise.",
    )
    disciplined = discipline_memory_candidates(
        [candidate], teacher_message="Please keep planning summaries concise."
    )[0]

    assert disciplined.source == "inferred_from_session"
    assert disciplined.fast_lane is False


def test_discipline_does_not_recheck_an_older_bound_candidate_against_latest_message():
    first_message = "Please keep planning summaries concise."
    older = _candidate()
    first = discipline_memory_candidates(
        [older], teacher_message=first_message, origin_turn_index=1
    )[0]
    latest = "The redox demonstration worked well today."
    second = discipline_memory_candidates([first], teacher_message=latest)[0]

    assert first.fast_lane is True
    assert second.fast_lane is True
    assert second.origin_turn_index == 1
    assert second.origin_message_hash == first.origin_message_hash
