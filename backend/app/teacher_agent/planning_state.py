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
MEMORY_TARGETS = ("class_state.md", "copilot.md", "user.md", "canonical_wiki")
MEMORY_SOURCES = (
    "teacher_explicit",
    "inferred_from_session",
    "final_lesson",
    "tool_result",
)
CONFIDENCE = ("low", "medium", "high")


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


class MemoryCandidate(BaseModel):
    """A possible durable-memory update, tracked but never written during chat."""

    target: str = "copilot.md"
    candidate_update: str = ""
    evidence: str = ""
    source: str = "inferred_from_session"
    confidence: str = "low"
    requires_teacher_approval: bool = True


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
    lesson_planning_state: LessonPlanningState = field(default_factory=LessonPlanningState)
    evidence_briefs: list[EvidenceBrief] = field(default_factory=list)
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


# --- merge: fold one model turn into the persisted runtime ------------------


def _candidate_key(c: MemoryCandidate) -> tuple[str, str]:
    return (c.target.strip().lower(), " ".join(c.candidate_update.lower().split()))


def _patch_has_values(patch: StatePatch | None) -> bool:
    if patch is None:
        return False
    data = patch.model_dump(exclude_none=True)
    return any(bool(value) for value in data.values())


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
    for field in ("milestones", "decisions", "open_questions", "superseded"):
        data[field] = _append_unique(data[field], getattr(patch, field))
    return SessionState(**data)


def _apply_lesson_patch(
    state: LessonPlanningState, patch: LessonPlanningStatePatch
) -> LessonPlanningState:
    data = state.model_dump()
    for field in ("lesson_topic", "lesson_goal", "target_class"):
        value = getattr(patch, field)
        if value is not None:
            text = _clean_text(value)
            if text:
                data[field] = text
    if patch.duration_minutes and patch.duration_minutes > 0:
        data["duration_minutes"] = patch.duration_minutes
    for field in (
        "success_criteria",
        "teacher_preferences_for_this_lesson",
        "constraints",
        "materials_used",
        "class_context_used",
        "accepted_plan_elements",
        "needs_revision",
    ):
        data[field] = _append_unique(data[field], getattr(patch, field))
    return LessonPlanningState(**data)


def apply_state_patch(runtime: PlanRuntime, patch: StatePatch) -> None:
    """Apply a model-proposed patch to backend-owned runtime state."""
    runtime.session_state = _apply_session_patch(runtime.session_state, patch.session_state)
    runtime.lesson_planning_state = _apply_lesson_patch(
        runtime.lesson_planning_state, patch.lesson_planning_state
    )


def _candidate_is_allowed(c: MemoryCandidate) -> bool:
    return (
        c.target in MEMORY_TARGETS
        and c.source in MEMORY_SOURCES
        and c.confidence in CONFIDENCE
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
    seen = {_candidate_key(c) for c in runtime.memory_candidates}
    for cand in memory_candidates:
        if not _candidate_is_allowed(cand):
            continue
        if not cand.candidate_update.strip():
            continue
        key = _candidate_key(cand)
        if key in seen:
            continue
        seen.add(key)
        runtime.memory_candidates.append(cand)
    candidates_cap = get_context_limits().candidates_cap
    if len(runtime.memory_candidates) > candidates_cap:
        runtime.memory_candidates = runtime.memory_candidates[-candidates_cap:]

    if plan_changed:
        runtime.plan_version += 1


# --- compact renderers (injected into the per-turn system prompt) -----------


def _bullets(
    items: list[str],
    *,
    limit: int | None = None,
    max_chars: int | None = None,
) -> list[str]:
    lim = get_context_limits()
    limit = lim.state_list_limit if limit is None else limit
    max_chars = lim.state_bullet_max_chars if max_chars is None else max_chars
    out = []
    for item in items[:limit]:
        text = " ".join(str(item).split())
        if text:
            out.append(f"- {text[:max_chars]}")
    return out


def render_session_state(s: SessionState) -> str:
    parts = [
        "## Session state",
        f"- phase: {s.phase}",
    ]
    if s.teacher_goal:
        parts.append(f"- teacher goal: {s.teacher_goal[:200]}")
    if s.agent_next_step:
        parts.append(f"- next step: {s.agent_next_step[:200]}")
    if s.decisions:
        parts.append("### Decisions")
        parts.extend(_bullets(s.decisions))
    if s.open_questions:
        parts.append("### Open questions")
        parts.extend(_bullets(s.open_questions))
    if s.superseded:
        parts.append("### Superseded / rejected")
        parts.extend(_bullets(s.superseded))
    return "\n".join(parts)


def render_lesson_planning_state(s: LessonPlanningState) -> str:
    parts = ["## Lesson planning state"]
    fields = [
        ("topic", s.lesson_topic),
        ("goal", s.lesson_goal),
        ("target class", s.target_class),
        ("duration (min)", str(s.duration_minutes) if s.duration_minutes else ""),
    ]
    parts.extend(f"- {label}: {value[:200]}" for label, value in fields if value)
    sections = [
        ("Success criteria", s.success_criteria),
        ("Teacher preferences (this lesson)", s.teacher_preferences_for_this_lesson),
        ("Constraints", s.constraints),
        ("Materials used", s.materials_used),
        ("Class context used", s.class_context_used),
        ("Accepted plan elements", s.accepted_plan_elements),
        ("Needs revision", s.needs_revision),
    ]
    for label, items in sections:
        if items:
            parts.append(f"### {label}")
            parts.extend(_bullets(items))
    return "\n".join(parts)


def render_briefs(briefs: list[EvidenceBrief], *, max_briefs: int | None = None) -> str:
    lim = get_context_limits()
    max_briefs = lim.briefs_inject_limit if max_briefs is None else max_briefs
    if not briefs:
        return "## Evidence briefs\n- None yet."
    parts = ["## Evidence briefs (compact; request raw via get_raw_evidence)"]
    for b in briefs[-max_briefs:]:
        head = f"- [{b.raw_ref or 'no-ref'}] {b.type}: {b.purpose[:160]}".rstrip()
        parts.append(head)
        for line in b.brief[: lim.brief_lines_per_item]:
            parts.append(f"  - {' '.join(str(line).split())[:200]}")
        if b.impact_on_plan:
            parts.append(f"  - impact: {b.impact_on_plan[:200]}")
    return "\n".join(parts)


def planning_api_payload(rt: PlanRuntime) -> dict:
    """Compact, JSON-safe view of the runtime for API responses / SSE finals."""
    return {
        "phase": rt.session_state.phase,
        "last_change_summary": rt.last_change_summary,
        "plan_version": rt.plan_version,
        "session_state": rt.session_state.model_dump(),
        "lesson_planning_state": rt.lesson_planning_state.model_dump(),
        "memory_candidates": [c.model_dump() for c in rt.memory_candidates],
    }


def render_memory_candidates(cands: list[MemoryCandidate]) -> str:
    if not cands:
        return "- None proposed yet."
    parts = []
    for c in cands:
        parts.append(
            f"- ({c.target}, {c.source}, {c.confidence}) {c.candidate_update[:200]}"
        )
    return "\n".join(parts)
