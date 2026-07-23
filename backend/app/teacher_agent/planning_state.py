"""Runtime state objects for the lesson-planning chat context manager.

These objects keep a planning chat oriented without re-sending the whole
transcript each turn. The model proposes ``state_patch`` updates as part of
``PlanTurnOutput``; the backend owns/persists the merged state on the session
(``PlanRuntime``) and re-injects a compact rendering on the next turn. Because
durable context lives here, the verbatim conversation window can be trimmed
safely (trimmed turns are not "lost" - their decisions/constraints survive in
this state).

Design follows the OpenAI Agents SDK context-personalization pattern:
structured state + compact injection + progressive exposure of raw evidence.
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
from app.teacher_agent.memory_capture import (
    BASIS as BASIS,
    CONFIDENCE as CONFIDENCE,
    MEMORY_SOURCES as MEMORY_SOURCES,
    MEMORY_TARGETS as MEMORY_TARGETS,
    MemoryCandidate as MemoryCandidate,
    candidate_key,
    clean_text,
    durable_preference_candidates_from_state_values,
    has_teacher_preference_candidate,
    merge_memory_candidates,
    render_memory_candidates as render_shared_memory_candidates,
)

PLAN_PHASES = ("requirements_discussion", "lesson_refinement", "finalize")

# Evidence brief / candidate enums kept as plain strings for structured-output
# friendliness (mirrors how PlanOutput uses Optional/defaults).
EVIDENCE_TYPES = (
    "wiki_search",
    "material_parse",
    "tool_call",
    "textbook_lookup",
    "web_search",
)


class SessionState(BaseModel):
    """Keeps the chat oriented (phase, goals, decisions, open questions)."""

    active_task: str = "lesson_planning"
    phase: str = "requirements_discussion"
    session_goal: str = "Create a usable lesson plan with the teacher."
    teacher_goal: str = ""
    milestones: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    superseded: list[str] = Field(default_factory=list)
    agent_next_step: str = ""


class LessonPlanningState(BaseModel):
    """Keeps the lesson aligned with the teacher's goals and constraints."""

    lesson_topic: str = ""
    lesson_goal: str = ""
    workflow_kind: str = "lesson_planning"
    learning_targets: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    target_class: str = ""
    duration_minutes: int = 0
    teacher_preferences_for_this_lesson: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    materials_used: list[str] = Field(default_factory=list)
    class_context_used: list[str] = Field(default_factory=list)
    accepted_plan_elements: list[str] = Field(default_factory=list)
    needs_revision: list[str] = Field(default_factory=list)


class EvidenceBrief(BaseModel):
    """Compact summary of a tool/search/material result (raw kept behind raw_ref)."""

    type: str = "tool_call"
    purpose: str = ""
    brief: list[str] = Field(default_factory=list)
    impact_on_plan: str = ""
    source_refs: list[str] = Field(default_factory=list)
    raw_ref: str = ""
    confidence: str = "medium"


class SessionStatePatch(BaseModel):
    """Model-proposed semantic updates to SessionState.

    Missing fields mean "no change". Lists are appended/deduped by backend code;
    the model does not own the full state snapshot.
    """

    phase: str | None = None
    teacher_goal: str | None = None
    milestones: list[str] | None = None
    decisions: list[str] | None = None
    open_questions: list[str] | None = None
    superseded: list[str] | None = None
    agent_next_step: str | None = None


class LessonPlanningStatePatch(BaseModel):
    """Model-proposed semantic updates to LessonPlanningState."""

    lesson_topic: str | None = None
    lesson_goal: str | None = None
    workflow_kind: str | None = None
    learning_targets: list[str] | None = None
    success_criteria: list[str] | None = None
    target_class: str | None = None
    duration_minutes: int | None = None
    teacher_preferences_for_this_lesson: list[str] | None = None
    constraints: list[str] | None = None
    materials_used: list[str] | None = None
    class_context_used: list[str] | None = None
    accepted_plan_elements: list[str] | None = None
    needs_revision: list[str] | None = None


class StatePatch(BaseModel):
    """One turn's proposed runtime-state patch.

    The backend validates and applies this patch to PlanRuntime. This is the
    preferred contract; full state snapshots are kept only as a compatibility
    fallback while older tests/stubs are migrated.
    """

    session_state: SessionStatePatch = Field(default_factory=SessionStatePatch)
    lesson_planning_state: LessonPlanningStatePatch = Field(
        default_factory=LessonPlanningStatePatch
    )


@dataclass
class PlanRuntime:
    """Per-session persisted runtime memory (server RAM, like ArtifactSession)."""

    session_state: SessionState = field(default_factory=SessionState)
    lesson_planning_state: LessonPlanningState = field(
        default_factory=LessonPlanningState
    )
    evidence_briefs: list[EvidenceBrief] = field(default_factory=list)
    consulted_sources: list[dict[str, str]] = field(default_factory=list)
    raw_store: dict[str, str] = field(default_factory=dict)
    memory_candidates: list[MemoryCandidate] = field(default_factory=list)
    plan_version: int = 0
    last_change_summary: str = ""
    _raw_counter: int = 0

    def next_raw_ref(self, kind: str) -> str:
        self._raw_counter += 1
        return f"{kind}_{self._raw_counter:03d}"

    def add_raw(self, kind: str, payload: str) -> str:
        """Store a raw tool output under a fresh raw_ref, pruning oldest if needed."""
        ref = self.next_raw_ref(kind)
        self.raw_store[ref] = payload
        cap = get_context_limits().raw_store_cap
        if len(self.raw_store) > cap:
            for stale in list(self.raw_store)[:-cap]:
                del self.raw_store[stale]
        return ref

    def record_source_read(self, source_id: str, section_id: str) -> None:
        """Record provenance for a source section read during this session."""
        item = {
            "source_id": str(source_id).strip(),
            "section_id": str(section_id).strip() or "summary",
        }
        if not item["source_id"]:
            return
        if item not in self.consulted_sources:
            self.consulted_sources.append(item)
        if len(self.consulted_sources) > get_context_limits().briefs_store_cap:
            self.consulted_sources = self.consulted_sources[-get_context_limits().briefs_store_cap :]


# --- merge: fold one model turn into the persisted runtime ------------------


def _candidate_key(c: MemoryCandidate) -> tuple[str, str]:
    return candidate_key(c)


def _patch_has_values(patch: StatePatch | None) -> bool:
    if patch is None:
        return False
    data = patch.model_dump(exclude_none=True)
    return any(bool(value) for value in data.values())


def _clean_text(value: str | None) -> str:
    return clean_text(value)


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


def _apply_session_patch(state: SessionState, patch: SessionStatePatch) -> SessionState:
    data = state.model_dump()
    if patch.phase in PLAN_PHASES:
        data["phase"] = patch.phase
    if patch.teacher_goal is not None:
        goal = _clean_text(patch.teacher_goal)
        if goal:
            data["teacher_goal"] = goal
    if patch.agent_next_step is not None:
        step = _clean_text(patch.agent_next_step)
        if step:
            data["agent_next_step"] = step
    for field_name in ("milestones", "decisions", "open_questions", "superseded"):
        data[field_name] = _append_unique(data[field_name], getattr(patch, field_name))
    return SessionState(**data)


def _apply_lesson_patch(
    state: LessonPlanningState, patch: LessonPlanningStatePatch
) -> LessonPlanningState:
    data = state.model_dump()
    for field_name in ("lesson_topic", "lesson_goal", "target_class"):
        value = getattr(patch, field_name)
        if value is not None:
            text = _clean_text(value)
            if text:
                data[field_name] = text
    if patch.duration_minutes and patch.duration_minutes > 0:
        data["duration_minutes"] = patch.duration_minutes
    if patch.workflow_kind in {"lesson_planning", "lesson_differentiation"}:
        data["workflow_kind"] = patch.workflow_kind
    for field_name in (
        "learning_targets",
        "success_criteria",
        "teacher_preferences_for_this_lesson",
        "constraints",
        "materials_used",
        "class_context_used",
        "accepted_plan_elements",
        "needs_revision",
    ):
        data[field_name] = _append_unique(data[field_name], getattr(patch, field_name))
    return LessonPlanningState(**data)


def apply_state_patch(runtime: PlanRuntime, patch: StatePatch) -> None:
    """Apply a model-proposed patch to backend-owned runtime state."""
    runtime.session_state = _apply_session_patch(
        runtime.session_state, patch.session_state
    )
    runtime.lesson_planning_state = _apply_lesson_patch(
        runtime.lesson_planning_state, patch.lesson_planning_state
    )


def teacher_signals_plan_finalize(message: str) -> bool:
    """True when the teacher clearly accepts the plan after the requested turn."""
    text = (message or "").lower()
    if not text.strip():
        return False
    if any(
        marker in text
        for marker in (
            "not happy",
            "isn't good",
            "doesn't work",
            # German negatives
            "nicht gut",
            "gefällt mir nicht",
            "passt nicht",
            "funktioniert nicht",
        )
    ):
        return False
    direct = (
        "ready to save",
        "good to save",
        "please finalize",
        "finalize it",
        "that's it",
        "that is it",
        # German (users often type German)
        "kann gespeichert",
        "so speichern",
        "fertigstellen",
        "passt so",
    )
    if any(marker in text for marker in direct):
        return True
    acceptance = (
        "i am happy",
        "i'm happy",
        "happy with it",
        "looks good",
        "works for me",
        "i like it",
        # German
        "sieht gut aus",
        "gefällt mir",
        "so ist gut",
    )
    completion = (
        "last refinement",
        "final refinement",
        "last tweak",
        "final tweak",
        "done",
        "finished",
        # German
        "fertig",
        "letzte änderung",
        "letzter schliff",
    )
    return any(marker in text for marker in acceptance) and any(
        marker in text for marker in completion
    )


def apply_plan_phase_auto_advance(
    runtime: PlanRuntime,
    *,
    teacher_message: str = "",
    plan_ready: bool = False,
) -> None:
    """Apply deterministic phase transitions the backend owns after model patches."""
    if runtime.session_state.phase == "finalize":
        return
    if plan_ready and teacher_signals_plan_finalize(teacher_message):
        runtime.session_state.phase = "finalize"
        runtime.session_state.open_questions = []
        runtime.session_state.agent_next_step = (
            "Present the finalized lesson plan for teacher review."
        )
        runtime.lesson_planning_state.needs_revision = []


def _state_patch_preference_candidates(
    state_patch: StatePatch | None,
    *,
    teacher_message: str,
) -> list[MemoryCandidate]:
    """Promote durable preference signals already found by the planner.

    This is a contract repair, not raw-message memory extraction: the model must
    have put the preference into structured state first. The backend only
    ensures a cross-session preference does not disappear before review.
    """
    if state_patch is None:
        return []
    return durable_preference_candidates_from_state_values(
        state_patch.lesson_planning_state.teacher_preferences_for_this_lesson,
        teacher_message=teacher_message,
    )


def _merge_state(old, new):
    """Field-wise merge that never lets an empty model value wipe persisted state.

    For each field, take the model's new value when it is truthy (non-empty
    list / non-empty string / non-zero); otherwise keep the persisted value.
    This protects accumulated decisions/constraints when a turn returns partial
    or empty state, while still allowing real updates (and shrinking a list down
    to >=1 item). Clearing a field fully to empty is intentionally not possible;
    use the dedicated `superseded` channel to retire decisions.
    """
    data = {}
    for name in type(new).model_fields:
        new_val = getattr(new, name)
        data[name] = new_val if new_val else getattr(old, name)
    return type(new)(**data)


def merge_turn_into_runtime(
    runtime: PlanRuntime,
    *,
    session_state: SessionState,
    lesson_planning_state: LessonPlanningState,
    new_evidence_briefs: list[EvidenceBrief],
    memory_candidates: list[MemoryCandidate],
    last_change_summary: str,
    plan_changed: bool,
    state_patch: StatePatch | None = None,
    teacher_message: str = "",
    plan_ready: bool = False,
) -> None:
    """Persist a turn's emitted state (merge state, merge briefs/candidates)."""
    if _patch_has_values(state_patch):
        apply_state_patch(runtime, state_patch)
    else:
        runtime.session_state = _merge_state(runtime.session_state, session_state)
        runtime.lesson_planning_state = _merge_state(
            runtime.lesson_planning_state, lesson_planning_state
        )
    if last_change_summary:
        runtime.last_change_summary = last_change_summary

    # Evidence briefs: replace any prior brief with the same raw_ref, else append.
    for brief in new_evidence_briefs:
        if brief.raw_ref:
            runtime.evidence_briefs = [
                b for b in runtime.evidence_briefs if b.raw_ref != brief.raw_ref
            ]
        runtime.evidence_briefs.append(brief)
    briefs_cap = get_context_limits().briefs_store_cap
    if len(runtime.evidence_briefs) > briefs_cap:
        runtime.evidence_briefs = runtime.evidence_briefs[-briefs_cap:]

    # Memory candidates: accumulate with dedupe by (target, normalized update).
    all_memory_candidates = list(memory_candidates)
    if not has_teacher_preference_candidate(
        [*runtime.memory_candidates, *all_memory_candidates]
    ):
        all_memory_candidates.extend(
            _state_patch_preference_candidates(
                state_patch,
                teacher_message=teacher_message,
            )
        )
    runtime.memory_candidates = merge_memory_candidates(
        runtime.memory_candidates,
        all_memory_candidates,
        cap=get_context_limits().candidates_cap,
    )

    if plan_changed:
        runtime.plan_version += 1

    apply_plan_phase_auto_advance(
        runtime,
        teacher_message=teacher_message,
        plan_ready=plan_ready,
    )


# --- compact renderers (injected into the per-turn system prompt) -----------


def render_session_state(s: SessionState) -> str:
    parts = [
        "## Session state",
        f"- phase: {s.phase}",
    ]
    if s.teacher_goal:
        parts.append(render_scalar("teacher goal", s.teacher_goal))
    if s.agent_next_step:
        parts.append(render_scalar("next step", s.agent_next_step))
    append_bullet_section(parts, "Decisions", s.decisions)
    append_bullet_section(parts, "Open questions", s.open_questions)
    append_bullet_section(parts, "Superseded / rejected", s.superseded)
    return "\n".join(parts)


def render_lesson_planning_state(s: LessonPlanningState) -> str:
    parts = ["## Lesson planning state"]
    parts.append(f"- workflow: {s.workflow_kind}")
    fields = [
        ("topic", s.lesson_topic),
        ("goal", s.lesson_goal),
        ("target class", s.target_class),
        ("duration (min)", str(s.duration_minutes) if s.duration_minutes else ""),
    ]
    parts.extend(f"- {label}: {value[:200]}" for label, value in fields if value)
    sections = [
        ("Learning targets", s.learning_targets),
        ("Success criteria", s.success_criteria),
        ("Teacher preferences (this lesson)", s.teacher_preferences_for_this_lesson),
        ("Constraints", s.constraints),
        ("Materials used", s.materials_used),
        ("Class context used", s.class_context_used),
        ("Accepted plan elements", s.accepted_plan_elements),
        ("Needs revision", s.needs_revision),
    ]
    for label, items in sections:
        append_bullet_section(parts, label, items)
    return "\n".join(parts)


def render_briefs(briefs: list[EvidenceBrief], *, max_briefs: int | None = None) -> str:
    return render_evidence_briefs(
        briefs,
        impact_field="impact_on_plan",
        max_briefs=max_briefs,
    )


def planning_api_payload(rt: PlanRuntime) -> dict:
    """Compact, JSON-safe view of the runtime for API responses / SSE finals."""
    return {
        "phase": rt.session_state.phase,
        "last_change_summary": rt.last_change_summary,
        "plan_version": rt.plan_version,
        "session_state": rt.session_state.model_dump(),
        "lesson_planning_state": rt.lesson_planning_state.model_dump(),
        "consulted_sources": list(rt.consulted_sources),
        "memory_candidates": [c.model_dump() for c in rt.memory_candidates],
    }


def render_memory_candidates(cands: list[MemoryCandidate]) -> str:
    return render_shared_memory_candidates(cands, max_chars=200)
