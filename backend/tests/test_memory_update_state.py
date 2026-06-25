"""Unit tests for update-memory runtime phase auto-advance."""

from __future__ import annotations

from app.teacher_agent.agents import _pseudonymize_known_students
from app.teacher_agent.memory_capture import MemoryCandidate
from app.teacher_agent.memory_update_state import (
    LessonResultPatch,
    MemoryEvidenceBrief,
    MemoryRuntime,
    MemorySessionPatch,
    MemoryStatePatch,
    MemoryTargetPatch,
    apply_memory_phase_auto_advance,
    merge_memory_turn,
    render_lesson_result_state,
    render_memory_briefs,
    render_memory_runtime,
    render_memory_session_state,
    render_memory_target_state,
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


def test_confirmed_memory_target_derives_kind_when_model_omits_it():
    runtime = MemoryRuntime()
    merge_memory_turn(
        runtime,
        state_patch=MemoryStatePatch(
            target=MemoryTargetPatch(
                intent="correct_existing_results",
                lesson_date="2026-05-29",
                target_confirmed=True,
                existing_results_loaded=True,
            ),
        ),
        new_evidence_briefs=[],
        last_change_summary="Loaded existing lesson.",
        unsupported_intent_reason="",
        diary_changed=False,
    )

    assert runtime.target.target_kind == "taught_lesson"
    assert runtime.target.needs_confirmation is False


def test_split_memory_renderers_include_runtime_context():
    runtime = MemoryRuntime()
    merge_memory_turn(
        runtime,
        state_patch=MemoryStatePatch(
            target=MemoryTargetPatch(
                intent="log_new_results",
                lesson_date="2026-06-02",
                lesson_title="Ions review",
                target_kind="new_lesson",
                target_confirmed=True,
                confidence="high",
            ),
            session_state=MemorySessionPatch(
                phase="collect_results",
                teacher_goal="Log today's lesson.",
                decisions=["Use 2026-06-02 as the lesson date."],
                superseded=["Earlier date guess was 2026-06-01."],
                agent_next_step="Ask for homework follow-ups.",
            ),
            lesson_result_state=LessonResultPatch(
                covered=["Reviewed ion charge vs oxidation number."],
                missing_categories=["Homework & follow-ups"],
                draft_confidence="medium",
            ),
        ),
        new_evidence_briefs=[
            MemoryEvidenceBrief(
                type="tool_call",
                purpose="read target lesson",
                brief=["No existing lesson results found."],
                raw_ref="memory_target_001",
            )
        ],
        last_change_summary="Updated runtime.",
        unsupported_intent_reason="",
        diary_changed=False,
    )

    assert "lesson date: 2026-06-02" in render_memory_target_state(runtime.target)
    session = render_memory_session_state(runtime.session_state)
    assert "Use 2026-06-02 as the lesson date." in session
    assert "Earlier date guess" in session
    assert "Ask for homework follow-ups." in session
    result = render_lesson_result_state(runtime.lesson_result_state)
    assert "Reviewed ion charge" in result
    assert "Homework & follow-ups" in result
    evidence = render_memory_briefs(runtime.evidence_briefs)
    assert "memory_target_001" in evidence
    assert "No existing lesson results found." in evidence
    combined = render_memory_runtime(runtime)
    assert "## Memory target state" in combined
    assert "## Memory session state" in combined
    assert "## Lesson result state" in combined
    assert "## Memory evidence briefs" in combined


def test_pseudonymize_known_students_replaces_roster_names():
    roster = """# Students

| ID | Name | Note | Page |
|---|---|---|---|
| S-014 | Alex Weber | Strong with formula writing. | [students/S-014.md](students/S-014.md) |
| S-033 | Joonho Kim | Concrete tasks help. | [students/S-033.md](students/S-033.md) |
| S-042 | Matt Keller | Reliable on conservation checks. | [students/S-042.md](students/S-042.md) |
"""
    diary = (
        "- Matt (S-042) helped other students.\n"
        "- Joonho Kim understood the phosphate link.\n"
        "- Alex was interrupting."
    )

    out = _pseudonymize_known_students(diary, roster)

    assert "Matt" not in out
    assert "Joonho" not in out
    assert "Alex" not in out
    assert "S-042 helped other students" in out
    assert "S-033 understood the phosphate link" in out
    assert "S-014 was interrupting" in out


def test_merge_memory_turn_accumulates_memory_candidates_once():
    runtime = MemoryRuntime()
    candidate = MemoryCandidate(
        target="user.md",
        section="Communication",
        candidate_update="Prefers MBB-style concise communication.",
        evidence="Repeated teacher request in update-memory chat.",
        source="teacher_explicit",
        basis="explicit",
        confidence="high",
    )

    for _ in range(2):
        merge_memory_turn(
            runtime,
            state_patch=MemoryStatePatch(),
            new_evidence_briefs=[],
            memory_candidates=[candidate],
            last_change_summary="",
            unsupported_intent_reason="",
            diary_changed=False,
        )

    assert len(runtime.memory_candidates) == 1
    assert runtime.memory_candidates[0].target == "user.md"
    assert runtime.memory_candidates[0].basis == "explicit"
