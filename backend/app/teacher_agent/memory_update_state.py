"""Runtime state for the update-memory chat.

The update-memory agent has two jobs that should stay separate:
identify the lesson/memory target, then help the teacher produce a reviewed
lesson-results artifact. This runtime state keeps that target/task context out
of the durable wiki until the teacher approves the normal commit flow.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from app.context_limits import get_context_limits
from app.teacher_agent.runtime_render import (
    append_bullet_section,
    render_evidence_briefs,
    render_scalar,
)

MEMORY_PHASES = ("identify_target", "collect_results", "review_draft", "unsupported")
MEMORY_INTENTS = (
    "unknown",
    "log_new_results",
    "update_missing_results",
    "correct_existing_results",
    "improve_memory",
    "unsupported",
)
TARGET_KINDS = ("unknown", "planned_lesson", "taught_lesson", "new_lesson", "class_memory")
TARGET_SOURCES = ("", "teacher_explicit", "timeline_hint", "agent_inferred")
CONFIDENCE = ("low", "medium", "high")


class MemoryTargetState(BaseModel):
    intent: str = "unknown"
    lesson_date: str = ""
    lesson_title: str = ""
    target_kind: str = "unknown"
    target_confirmed: bool = False
    source: str = ""
    confidence: str = "low"
    plan_loaded: bool = False
    existing_results_loaded: bool = False
    needs_confirmation: bool = True


class MemorySessionState(BaseModel):
    active_task: str = "update_memory"
    phase: str = "identify_target"
    teacher_goal: str = ""
    decisions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    superseded: list[str] = Field(default_factory=list)
    agent_next_step: str = ""


class LessonResultState(BaseModel):
    covered: list[str] = Field(default_factory=list)
    participation: list[str] = Field(default_factory=list)
    went_well: list[str] = Field(default_factory=list)
    did_not_go_well: list[str] = Field(default_factory=list)
    student_observations: list[str] = Field(default_factory=list)
    homework_followups: list[str] = Field(default_factory=list)
    missing_categories: list[str] = Field(default_factory=list)
    draft_confidence: str = "low"


class MemoryEvidenceBrief(BaseModel):
    type: str = "tool_call"
    purpose: str = ""
    brief: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    raw_ref: str = ""
    confidence: str = "medium"


class MemoryTargetPatch(BaseModel):
    intent: str | None = None
    lesson_date: str | None = None
    lesson_title: str | None = None
    target_kind: str | None = None
    target_confirmed: bool | None = None
    source: str | None = None
    confidence: str | None = None
    plan_loaded: bool | None = None
    existing_results_loaded: bool | None = None
    needs_confirmation: bool | None = None


class MemorySessionPatch(BaseModel):
    phase: str | None = None
    teacher_goal: str | None = None
    decisions: list[str] | None = None
    open_questions: list[str] | None = None
    superseded: list[str] | None = None
    agent_next_step: str | None = None


class LessonResultPatch(BaseModel):
    covered: list[str] | None = None
    participation: list[str] | None = None
    went_well: list[str] | None = None
    did_not_go_well: list[str] | None = None
    student_observations: list[str] | None = None
    homework_followups: list[str] | None = None
    missing_categories: list[str] | None = None
    draft_confidence: str | None = None


class MemoryStatePatch(BaseModel):
    target: MemoryTargetPatch = Field(default_factory=MemoryTargetPatch)
    session_state: MemorySessionPatch = Field(default_factory=MemorySessionPatch)
    lesson_result_state: LessonResultPatch = Field(default_factory=LessonResultPatch)


@dataclass
class MemoryRuntime:
    target: MemoryTargetState = field(default_factory=MemoryTargetState)
    session_state: MemorySessionState = field(default_factory=MemorySessionState)
    lesson_result_state: LessonResultState = field(default_factory=LessonResultState)
    evidence_briefs: list[MemoryEvidenceBrief] = field(default_factory=list)
    raw_store: dict[str, str] = field(default_factory=dict)
    diary_version: int = 0
    last_change_summary: str = ""
    unsupported_intent_reason: str = ""
    _raw_counter: int = 0

    def next_raw_ref(self, kind: str) -> str:
        self._raw_counter += 1
        return f"{kind}_{self._raw_counter:03d}"

    def add_raw(self, kind: str, payload: str) -> str:
        ref = self.next_raw_ref(kind)
        self.raw_store[ref] = payload
        cap = get_context_limits().raw_store_cap
        if len(self.raw_store) > cap:
            for stale in list(self.raw_store)[:-cap]:
                del self.raw_store[stale]
        return ref


def _clean_text(value: str | None) -> str:
    return " ".join((value or "").split())


def _append_unique(existing: list[str], updates: list[str] | None) -> list[str]:
    if not updates:
        return existing
    out = list(existing)
    seen = {" ".join(x.lower().split()) for x in out}
    for item in updates:
        text = _clean_text(item)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _patch_has_values(patch: MemoryStatePatch | None) -> bool:
    if patch is None:
        return False
    data = patch.model_dump(exclude_none=True)
    return any(bool(value) for value in data.values())


def _apply_target_patch(state: MemoryTargetState, patch: MemoryTargetPatch) -> MemoryTargetState:
    data = state.model_dump()
    if patch.intent in MEMORY_INTENTS:
        data["intent"] = patch.intent
    if patch.target_kind in TARGET_KINDS:
        data["target_kind"] = patch.target_kind
    if patch.source in TARGET_SOURCES:
        data["source"] = patch.source
    if patch.confidence in CONFIDENCE:
        data["confidence"] = patch.confidence
    for field_name in ("lesson_date", "lesson_title"):
        value = getattr(patch, field_name)
        if value is not None:
            text = _clean_text(value)
            if text:
                data[field_name] = text
    for field_name in (
        "target_confirmed",
        "plan_loaded",
        "existing_results_loaded",
        "needs_confirmation",
    ):
        value = getattr(patch, field_name)
        if value is not None:
            data[field_name] = value
    if data["target_confirmed"] and data["target_kind"] == "unknown":
        if data["existing_results_loaded"] or data["intent"] == "correct_existing_results":
            data["target_kind"] = "taught_lesson"
        elif data["plan_loaded"] or data["intent"] == "update_missing_results":
            data["target_kind"] = "planned_lesson"
        elif data["intent"] == "log_new_results":
            data["target_kind"] = "new_lesson"
    if data["target_confirmed"]:
        data["needs_confirmation"] = False
    return MemoryTargetState(**data)


def _apply_session_patch(state: MemorySessionState, patch: MemorySessionPatch) -> MemorySessionState:
    data = state.model_dump()
    if patch.phase in MEMORY_PHASES:
        data["phase"] = patch.phase
    if patch.teacher_goal is not None:
        goal = _clean_text(patch.teacher_goal)
        if goal:
            data["teacher_goal"] = goal
    if patch.agent_next_step is not None:
        step = _clean_text(patch.agent_next_step)
        if step:
            data["agent_next_step"] = step
    for field_name in ("decisions", "open_questions", "superseded"):
        data[field_name] = _append_unique(data[field_name], getattr(patch, field_name))
    return MemorySessionState(**data)


def _apply_lesson_result_patch(
    state: LessonResultState, patch: LessonResultPatch
) -> LessonResultState:
    data = state.model_dump()
    if patch.draft_confidence in CONFIDENCE:
        data["draft_confidence"] = patch.draft_confidence
    for field_name in (
        "covered",
        "participation",
        "went_well",
        "did_not_go_well",
        "student_observations",
        "homework_followups",
        "missing_categories",
    ):
        data[field_name] = _append_unique(data[field_name], getattr(patch, field_name))
    return LessonResultState(**data)


def apply_memory_state_patch(runtime: MemoryRuntime, patch: MemoryStatePatch) -> None:
    runtime.target = _apply_target_patch(runtime.target, patch.target)
    runtime.session_state = _apply_session_patch(runtime.session_state, patch.session_state)
    runtime.lesson_result_state = _apply_lesson_result_patch(
        runtime.lesson_result_state, patch.lesson_result_state
    )


def teacher_signals_finalize(message: str) -> bool:
    """True when the teacher's latest message clearly accepts the draft for save."""
    text = (message or "").lower()
    if not text.strip():
        return False
    markers = (
        "ready to save",
        "enough detail",
        "that's enough",
        "that is enough",
        "looks good to save",
        "good to save",
        "please finalize",
        "make the lesson results ready",
    )
    return any(marker in text for marker in markers)


def apply_memory_phase_auto_advance(
    runtime: MemoryRuntime,
    *,
    teacher_message: str = "",
    diary_complete: bool = False,
) -> None:
    """Apply deterministic phase transitions the backend owns after model patches."""
    if runtime.session_state.phase == "unsupported":
        return

    phase = runtime.session_state.phase
    target = runtime.target

    if (
        phase == "identify_target"
        and target.target_confirmed
        and target.lesson_date.strip()
    ):
        runtime.session_state.phase = "collect_results"
        phase = "collect_results"

    if (
        phase == "collect_results"
        and diary_complete
        and teacher_signals_finalize(teacher_message)
    ):
        runtime.session_state.phase = "review_draft"


def merge_memory_turn(
    runtime: MemoryRuntime,
    *,
    state_patch: MemoryStatePatch | None,
    new_evidence_briefs: list[MemoryEvidenceBrief],
    last_change_summary: str,
    unsupported_intent_reason: str,
    diary_changed: bool,
    teacher_message: str = "",
    diary_complete: bool = False,
) -> None:
    if _patch_has_values(state_patch):
        apply_memory_state_patch(runtime, state_patch)
    if last_change_summary:
        runtime.last_change_summary = last_change_summary
    if unsupported_intent_reason:
        runtime.unsupported_intent_reason = unsupported_intent_reason
        runtime.session_state.phase = "unsupported"
        runtime.target.intent = "unsupported"
    for brief in new_evidence_briefs:
        if brief.raw_ref:
            runtime.evidence_briefs = [
                b for b in runtime.evidence_briefs if b.raw_ref != brief.raw_ref
            ]
        runtime.evidence_briefs.append(brief)
    cap = get_context_limits().briefs_store_cap
    if len(runtime.evidence_briefs) > cap:
        runtime.evidence_briefs = runtime.evidence_briefs[-cap:]
    if diary_changed:
        runtime.diary_version += 1
    apply_memory_phase_auto_advance(
        runtime,
        teacher_message=teacher_message,
        diary_complete=diary_complete,
    )


def memory_api_payload(runtime: MemoryRuntime) -> dict:
    return {
        "phase": runtime.session_state.phase,
        "intent": runtime.target.intent,
        "target": runtime.target.model_dump(),
        "session_state": runtime.session_state.model_dump(),
        "lesson_result_state": runtime.lesson_result_state.model_dump(),
        "evidence_briefs": [b.model_dump() for b in runtime.evidence_briefs],
        "diary_version": runtime.diary_version,
        "last_change_summary": runtime.last_change_summary,
        "unsupported_intent_reason": runtime.unsupported_intent_reason,
    }


def render_memory_target_state(target: MemoryTargetState) -> str:
    parts = [
        "## Memory target state",
        f"- intent: {target.intent}",
        f"- target kind: {target.target_kind}",
        f"- target confirmed: {target.target_confirmed}",
        f"- needs confirmation: {target.needs_confirmation}",
        f"- confidence: {target.confidence}",
    ]
    if target.lesson_date:
        parts.append(render_scalar("lesson date", target.lesson_date))
    if target.lesson_title:
        parts.append(render_scalar("lesson title", target.lesson_title))
    if target.source:
        parts.append(render_scalar("source", target.source))
    parts.append(f"- saved plan loaded: {target.plan_loaded}")
    parts.append(f"- existing results loaded: {target.existing_results_loaded}")
    return "\n".join(parts)


def render_memory_session_state(session: MemorySessionState) -> str:
    parts = [
        "## Memory session state",
        f"- phase: {session.phase}",
    ]
    if session.teacher_goal:
        parts.append(render_scalar("teacher goal", session.teacher_goal))
    if session.agent_next_step:
        parts.append(render_scalar("next step", session.agent_next_step))
    append_bullet_section(parts, "Decisions", session.decisions)
    append_bullet_section(parts, "Open questions", session.open_questions)
    append_bullet_section(parts, "Superseded / rejected", session.superseded)
    return "\n".join(parts)


def render_lesson_result_state(result: LessonResultState) -> str:
    parts = [
        "## Lesson result state",
        f"- draft confidence: {result.draft_confidence}",
    ]
    sections = [
        ("What was covered", result.covered),
        ("Student participation", result.participation),
        ("What went well", result.went_well),
        ("What did not go well", result.did_not_go_well),
        ("Student observations", result.student_observations),
        ("Homework and follow-ups", result.homework_followups),
        ("Missing lesson-result categories", result.missing_categories),
    ]
    for label, items in sections:
        append_bullet_section(parts, label, items)
    return "\n".join(parts)


def render_memory_briefs(briefs: list[MemoryEvidenceBrief]) -> str:
    return render_evidence_briefs(
        briefs,
        title="## Memory evidence briefs (compact; request raw via get_raw_evidence)",
        empty="## Memory evidence briefs\n- None yet.",
    )


def render_memory_runtime(runtime: MemoryRuntime) -> str:
    """Legacy combined renderer; prefer split renderers for prompt assembly."""
    return "\n\n".join(
        [
            render_memory_target_state(runtime.target),
            render_memory_session_state(runtime.session_state),
            render_lesson_result_state(runtime.lesson_result_state),
            render_memory_briefs(runtime.evidence_briefs),
        ]
    )
