"""Unit tests for update-memory runtime phase auto-advance."""

from __future__ import annotations

from app.teacher_agent.memory_update_state import (
    MemoryRuntime,
    MemorySessionPatch,
    MemoryStatePatch,
    MemoryTargetPatch,
    apply_memory_phase_auto_advance,
    merge_memory_turn,
    teacher_signals_finalize,
)


def test_teacher_signals_finalize_accepts_save_intent():
    assert teacher_signals_finalize("That is enough detail. Please make the lesson results ready to save memory.")
    assert not teacher_signals_finalize("Add more about student participation.")


def test_auto_advance_moves_confirmed_target_to_collect_results():
    runtime = MemoryRuntime()
    runtime.target.lesson_date = "2026-05-29"
    runtime.target.target_confirmed = True

    apply_memory_phase_auto_advance(runtime)

    assert runtime.session_state.phase == "collect_results"


def test_auto_advance_moves_finalize_message_to_review_draft():
    runtime = MemoryRuntime()
    runtime.session_state.phase = "collect_results"
    runtime.target.lesson_date = "2026-05-29"
    runtime.target.target_confirmed = True

    apply_memory_phase_auto_advance(
        runtime,
        teacher_message="That is enough detail. Please make the lesson results ready to save memory.",
        diary_complete=True,
    )

    assert runtime.session_state.phase == "review_draft"


def test_merge_memory_turn_applies_auto_advance_after_model_patch():
    runtime = MemoryRuntime()
    merge_memory_turn(
        runtime,
        state_patch=MemoryStatePatch(
            target=MemoryTargetPatch(
                intent="correct_existing_results",
                lesson_date="2026-05-29",
                target_kind="taught_lesson",
                target_confirmed=True,
            ),
            session_state=MemorySessionPatch(phase="identify_target"),
        ),
        new_evidence_briefs=[],
        last_change_summary="Updated lesson results.",
        unsupported_intent_reason="",
        diary_changed=True,
        teacher_message="Lesson Results — 2026-05-29 — ...",
        diary_complete=False,
    )

    assert runtime.session_state.phase == "collect_results"
    assert runtime.target.intent == "correct_existing_results"
