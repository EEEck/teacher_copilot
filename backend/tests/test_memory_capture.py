"""Tests for shared workflow memory-candidate capture helpers."""

from __future__ import annotations

from app.teacher_agent.memory_capture import (
    MemoryCandidate,
    MemoryCaptureContext,
    MemoryCaptureLifecycle,
    durable_preference_candidates_from_state_values,
    merge_memory_candidates,
    render_memory_candidates,
    runtime_candidates_to_ledger_rows,
)
from tests.conftest import CLASS_ID


def test_merge_memory_candidates_appends_valid_candidate_once():
    candidate = MemoryCandidate(
        target="user.md",
        section="Communication",
        candidate_update="Prefers concise planning summaries.",
        source="teacher_explicit",
        basis="explicit",
        confidence="high",
    )

    merged = merge_memory_candidates([], [candidate, candidate], cap=10)

    assert merged == [candidate]


def test_merge_memory_candidates_forces_review_only_flag():
    candidate = MemoryCandidate(
        target="user.md",
        section="Communication",
        candidate_update="Prefers concise planning summaries.",
        source="teacher_explicit",
        basis="explicit",
        confidence="high",
        requires_teacher_approval=False,
    )

    merged = merge_memory_candidates([], [candidate], cap=10)

    assert len(merged) == 1
    assert merged[0].requires_teacher_approval is True


def test_merge_memory_candidates_drops_invalid_candidates():
    valid = MemoryCandidate(
        target="teaching_patterns.md",
        candidate_update="This class benefits from worked examples.",
        source="teacher_explicit",
        basis="explicit",
        confidence="high",
    )
    invalid_target = MemoryCandidate(
        target="wiki/classes/chemie_9b_2026_27/timeline.md",
        candidate_update="Unsafe arbitrary wiki path.",
        source="teacher_explicit",
        basis="explicit",
        confidence="high",
    )
    invalid_source = MemoryCandidate(
        target="user.md",
        candidate_update="Invalid source.",
        source="chat_observation",
        basis="explicit",
        confidence="high",
    )
    empty_update = MemoryCandidate(
        target="user.md",
        candidate_update=" ",
        source="teacher_explicit",
        basis="explicit",
        confidence="high",
    )

    merged = merge_memory_candidates(
        [],
        [invalid_target, invalid_source, empty_update, valid],
        cap=10,
    )

    assert merged == [valid]


def test_merge_memory_candidates_enforces_cap():
    candidates = [
        MemoryCandidate(target="class_state.md", candidate_update=f"fact {i}")
        for i in range(6)
    ]

    merged = merge_memory_candidates([], candidates, cap=3)

    assert [candidate.candidate_update for candidate in merged] == [
        "fact 3",
        "fact 4",
        "fact 5",
    ]


def test_subject_guide_candidate_survives_shared_capture_and_ledger_adapter():
    candidate = MemoryCandidate(
        target="wiki/subjects/chemie.md",
        section="Common lesson patterns",
        candidate_update=(
            "For chemistry classes, introduce oxidation numbers after electron transfer."
        ),
        evidence="Explicit teacher subject-wide guidance.",
        source="teacher_explicit",
        basis="explicit",
        confidence="high",
    )

    merged = merge_memory_candidates([], [candidate], cap=10)
    rows = runtime_candidates_to_ledger_rows(
        merged,
        class_id=CLASS_ID,
        subject="chemie",
        workflow="plan",
        session_id="subject-capture",
        turn_index=1,
    )

    assert len(merged) == 1
    assert len(rows) == 1
    assert rows[0].target == "wiki/subjects/chemie.md"
    assert rows[0].channel == "subject_concept"


def test_durable_preference_repair_requires_typed_state_signal():
    candidates = durable_preference_candidates_from_state_values(
        ["Use MBB-style communication for future lesson-planning summaries."],
        teacher_message="This is my general communication preference.",
    )
    one_off = durable_preference_candidates_from_state_values(
        ["Use MBB-style communication for this answer only."],
        teacher_message="For this answer only, use MBB.",
    )

    assert len(candidates) == 1
    assert candidates[0].target == "user.md"
    assert candidates[0].section == "Communication"
    assert candidates[0].basis == "explicit"
    assert one_off == []


def test_durable_preference_repair_requires_durable_teacher_turn():
    candidates = durable_preference_candidates_from_state_values(
        ["Use MBB-style communication for future lesson-planning summaries."],
        teacher_message="Use MBB for this answer.",
    )

    assert candidates == []


def test_render_memory_candidates_supports_prompt_shapes():
    candidate = MemoryCandidate(
        target="user.md",
        section="Communication",
        candidate_update="Prefers concise planning summaries.",
    )

    assert render_memory_candidates([]) == "- None proposed yet."
    rendered = render_memory_candidates([candidate], title="## Memory candidates")
    assert rendered.startswith("## Memory candidates")
    assert "user.md" in rendered
    assert "Prefers concise" in rendered


def test_memory_capture_lifecycle_stub_is_noop():
    lifecycle = MemoryCaptureLifecycle()
    context = MemoryCaptureContext(
        workflow="plan",
        session_id="s1",
        class_id=CLASS_ID,
    )

    assert lifecycle.on_turn_complete(context) == []
    assert lifecycle.on_artifact_approved(context) == []
    assert lifecycle.on_session_end(context) == []
    assert lifecycle.on_pre_compact(context) == []
