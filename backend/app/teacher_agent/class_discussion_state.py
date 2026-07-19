"""Backend-owned runtime state for read-only class discussion chat."""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from app.context_limits import get_context_limits
from app.teacher_agent.memory_capture import MemoryCandidate, merge_memory_candidates
from app.teacher_agent.planning_state import EvidenceBrief


class ClassDiscussionState(BaseModel):
    """Compact session interpretation — not durable wiki memory."""

    current_focus: str = ""
    answered_questions: list[str] = Field(default_factory=list)
    key_observations: list[str] = Field(default_factory=list)
    confusion_signals: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    next_best_actions: list[str] = Field(default_factory=list)


class ClassDiscussionStatePatch(BaseModel):
    """Model-proposed updates to discussion runtime state."""

    current_focus: str | None = None
    answered_questions: list[str] = Field(default_factory=list)
    key_observations: list[str] = Field(default_factory=list)
    confusion_signals: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    next_best_actions: list[str] = Field(default_factory=list)


@dataclass
class ClassDiscussionRuntime:
    """Session-local evidence store for read-only class discussion."""

    discussion_state: ClassDiscussionState = field(default_factory=ClassDiscussionState)
    evidence_briefs: list[EvidenceBrief] = field(default_factory=list)
    consulted_sources: list[dict[str, str]] = field(default_factory=list)
    memory_candidates: list[MemoryCandidate] = field(default_factory=list)
    raw_store: dict[str, str] = field(default_factory=dict)
    counters: dict[str, int] = field(default_factory=dict)
    last_source_paths: list[str] = field(default_factory=list)
    last_suggested_actions: list[str] = field(default_factory=list)

    def next_raw_ref(self, kind: str) -> str:
        key = (kind or "evidence").strip().lower().replace(" ", "_")
        self.counters[key] = self.counters.get(key, 0) + 1
        return f"{key}_{self.counters[key]}"

    def add_raw(self, kind: str, payload: str) -> str:
        raw_ref = self.next_raw_ref(kind)
        self.raw_store[raw_ref] = payload
        cap = get_context_limits().raw_store_cap
        if len(self.raw_store) > cap:
            for stale in list(self.raw_store)[:-cap]:
                del self.raw_store[stale]
        return raw_ref

    def record_source_read(self, source_id: str, section_id: str) -> None:
        """Record trusted-source provenance for a discussion answer."""
        item = {
            "source_id": str(source_id).strip(),
            "section_id": str(section_id).strip() or "summary",
        }
        if not item["source_id"] or item in self.consulted_sources:
            return
        self.consulted_sources.append(item)
        cap = get_context_limits().briefs_store_cap
        if len(self.consulted_sources) > cap:
            self.consulted_sources = self.consulted_sources[-cap:]


def _clean(value: str | None) -> str:
    return " ".join((value or "").split())


def _append_unique(existing: list[str], updates: list[str] | None) -> list[str]:
    if not updates:
        return existing
    out = list(existing)
    seen = {" ".join(item.lower().split()) for item in out}
    for item in updates:
        text = _clean(item)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def merge_class_discussion_turn(
    runtime: ClassDiscussionRuntime,
    *,
    state_patch: ClassDiscussionStatePatch,
    new_evidence_briefs: list[EvidenceBrief] | None = None,
    memory_candidates: list[MemoryCandidate] | None = None,
    source_paths: list[str] | None = None,
    suggested_actions: list[str] | None = None,
) -> None:
    """Fold one model turn into the backend-owned discussion runtime."""

    state = runtime.discussion_state.model_copy(deep=True)
    focus = _clean(state_patch.current_focus)
    if focus:
        state.current_focus = focus
    for field_name in (
        "answered_questions",
        "key_observations",
        "confusion_signals",
        "open_questions",
        "next_best_actions",
    ):
        setattr(
            state,
            field_name,
            _append_unique(getattr(state, field_name), getattr(state_patch, field_name)),
        )
    runtime.discussion_state = state

    if new_evidence_briefs:
        runtime.evidence_briefs.extend(new_evidence_briefs)
        cap = get_context_limits().candidates_cap
        if len(runtime.evidence_briefs) > cap:
            runtime.evidence_briefs = runtime.evidence_briefs[-cap:]

    runtime.memory_candidates = merge_memory_candidates(
        runtime.memory_candidates,
        memory_candidates,
        cap=get_context_limits().candidates_cap,
    )
    if source_paths is not None:
        runtime.last_source_paths = [_clean(path) for path in source_paths if _clean(path)]
    if suggested_actions is not None:
        runtime.last_suggested_actions = [
            _clean(action) for action in suggested_actions if _clean(action)
        ]


def discussion_api_payload(runtime: ClassDiscussionRuntime) -> dict:
    return {
        "discussion_state": runtime.discussion_state.model_dump(),
        "evidence_briefs": [brief.model_dump() for brief in runtime.evidence_briefs],
        "consulted_sources": list(runtime.consulted_sources),
        "memory_candidates": [
            candidate.model_dump() for candidate in runtime.memory_candidates
        ],
        "source_paths": list(runtime.last_source_paths),
        "suggested_actions": list(runtime.last_suggested_actions),
        "memory_candidate_count": len(runtime.memory_candidates),
    }


def render_class_discussion_state(state: ClassDiscussionState) -> str:
    parts = ["## Class discussion state"]
    if state.current_focus:
        parts.append(f"- Current focus: {state.current_focus}")
    fields = (
        ("Answered questions", state.answered_questions),
        ("Key observations", state.key_observations),
        ("Confusion signals", state.confusion_signals),
        ("Open questions", state.open_questions),
        ("Next best actions", state.next_best_actions),
    )
    for label, values in fields:
        if values:
            parts.append(f"- {label}:")
            parts.extend(f"  - {value}" for value in values)
    if len(parts) == 1:
        parts.append("- No discussion state captured yet.")
    return "\n".join(parts)
