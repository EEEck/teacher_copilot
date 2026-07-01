"""Shared durable-memory candidate capture helpers.

Workflow runtimes keep their own task state, but candidate handling is shared:
validation, dedupe, caps, rendering, and lifecycle hook shapes all live here.
The ledger remains review evidence only; this module never writes wiki files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from pydantic import BaseModel, Field

from app.context_limits import get_context_limits
from app.teacher_agent.memory_targets import (
    canonical_memory_target,
    is_supported_runtime_target,
)

MEMORY_TARGETS = (
    "class_state.md",
    "planning_brief.md",
    "taught_so_far.md",
    "teaching_patterns.md",
    "copilot_profile.md",
    "teacher_profile.md",
    "copilot.md",
    "user.md",
    "canonical_wiki",
)
MEMORY_SOURCES = (
    "teacher_explicit",
    "inferred_from_session",
    "final_lesson",
    "tool_result",
    "approved_wiki",
    "memory_compaction",
)
CONFIDENCE = ("low", "medium", "high")
BASIS = ("explicit", "inferred")


class MemoryCandidate(BaseModel):
    """A possible durable-memory update, tracked but never written during chat."""

    target: str = "copilot_profile.md"
    section: str = "General"
    candidate_update: str = ""
    evidence: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    source: str = "inferred_from_session"
    basis: str = "inferred"
    confidence: str = "low"
    requires_teacher_approval: bool = True


@dataclass(frozen=True)
class MemoryCaptureContext:
    """Bounded lifecycle context for future candidate consolidation hooks."""

    workflow: str
    session_id: str
    class_id: str
    subject: str | None = None
    turn_index: int = 0
    teacher_message: str = ""
    assistant_response: str = ""
    artifact_markdown: str = ""
    runtime: Any | None = None
    existing_candidates: tuple[MemoryCandidate, ...] = field(default_factory=tuple)


class MemoryCaptureLifecycle:
    """No-op lifecycle surface modeled after Hermes/OpenClaw memory hooks.

    Later implementations may add bounded LLM consolidation at these hook
    points. The contract is intentionally narrow: return review-only
    candidates, never mutate wiki memory.
    """

    def on_turn_complete(self, context: MemoryCaptureContext) -> list[MemoryCandidate]:
        return []

    def on_artifact_approved(
        self, context: MemoryCaptureContext
    ) -> list[MemoryCandidate]:
        return []

    def on_session_end(self, context: MemoryCaptureContext) -> list[MemoryCandidate]:
        return []

    def on_pre_compact(self, context: MemoryCaptureContext) -> list[MemoryCandidate]:
        return []


def clean_text(value: str | None) -> str:
    return " ".join((value or "").split())


def candidate_key(candidate: MemoryCandidate) -> tuple[str, str]:
    return (
        canonical_memory_target(candidate.target),
        " ".join(candidate.candidate_update.lower().split()),
    )


def candidate_is_allowed(candidate: MemoryCandidate) -> bool:
    return (
        is_supported_runtime_target(candidate.target)
        and candidate.source in MEMORY_SOURCES
        and candidate.basis in BASIS
        and candidate.confidence in CONFIDENCE
    )


def _review_only(candidate: MemoryCandidate) -> MemoryCandidate:
    if candidate.requires_teacher_approval:
        return candidate
    return candidate.model_copy(update={"requires_teacher_approval": True})


def merge_memory_candidates(
    existing: list[MemoryCandidate],
    incoming: Iterable[MemoryCandidate] | None,
    *,
    cap: int | None = None,
) -> list[MemoryCandidate]:
    """Return existing + validated incoming candidates, deduped and capped."""
    out = [_review_only(candidate) for candidate in existing]
    seen = {candidate_key(candidate) for candidate in out}
    for candidate in incoming or []:
        if not candidate_is_allowed(candidate):
            continue
        if not candidate.candidate_update.strip():
            continue
        candidate = _review_only(candidate)
        key = candidate_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        out.append(candidate)
    limit = cap if cap is not None else get_context_limits().candidates_cap
    if len(out) > limit:
        out = out[-limit:]
    return out


_DURABLE_PREFERENCE_MARKERS = (
    "from now on",
    "future",
    "always",
    "going forward",
    "general preference",
    "general communication",
    "not just this lesson",
    "all lesson",
    "all future",
    "for future",
)


def has_durable_preference_scope(text: str) -> bool:
    normalized = clean_text(text).lower()
    return bool(normalized) and any(
        marker in normalized for marker in _DURABLE_PREFERENCE_MARKERS
    )


def teacher_preference_candidate(
    *,
    preference: str,
    teacher_message: str,
) -> MemoryCandidate:
    evidence = clean_text(teacher_message)
    if evidence:
        evidence = f"Teacher explicitly framed this as a durable preference: {evidence}"
    else:
        evidence = "Teacher preference was captured in typed workflow runtime state."
    return MemoryCandidate(
        target="teacher_profile.md",
        section="Communication",
        candidate_update=clean_text(preference),
        evidence=evidence[:1000],
        evidence_refs=[],
        source="teacher_explicit",
        basis="explicit",
        confidence="high",
        requires_teacher_approval=True,
    )


def durable_preference_candidates_from_state_values(
    preferences: list[str] | None,
    *,
    teacher_message: str,
) -> list[MemoryCandidate]:
    """Repair missed durable preference candidates from model-emitted state.

    This intentionally does not mine raw teacher text broadly. The workflow
    model must have already placed the preference in a typed state field.
    """
    if not preferences:
        return []
    if not has_durable_preference_scope(teacher_message):
        return []

    candidates: list[MemoryCandidate] = []
    for preference in preferences:
        text = clean_text(preference)
        if not text:
            continue
        candidates.append(
            teacher_preference_candidate(
                preference=text,
                teacher_message=teacher_message,
            )
        )
    return candidates


def has_teacher_preference_candidate(candidates: Iterable[MemoryCandidate]) -> bool:
    for candidate in candidates:
        target = candidate.target.strip().lower()
        if (
            target in {"user.md", "teacher_profile.md"}
            and candidate.source == "teacher_explicit"
        ):
            return True
    return False


def render_memory_candidates(
    candidates: list[MemoryCandidate],
    *,
    title: str | None = None,
    max_chars: int = 220,
) -> str:
    parts: list[str] = []
    if title:
        parts.append(title)
    if not candidates:
        empty = "- None proposed yet."
        if title:
            parts.append(empty)
            return "\n".join(parts)
        return empty
    for candidate in candidates:
        parts.append(
            "- "
            f"({candidate.target}, {candidate.section}, {candidate.basis}, "
            f"{candidate.confidence}) {candidate.candidate_update[:max_chars]}"
        )
    return "\n".join(parts)


def runtime_candidates_to_ledger_rows(
    candidates: Iterable[Any],
    *,
    class_id: str,
    subject: str | None,
    workflow: str,
    session_id: str,
    turn_index: int,
):
    """Adapter around the SQLite ledger row conversion.

    Import lazily to keep the teacher-agent layer independent from services at
    module import time.
    """
    from app.services.memory_candidate_ledger import rows_from_runtime_candidates

    return rows_from_runtime_candidates(
        candidates,
        class_id=class_id,
        subject=subject,
        workflow=workflow,
        session_id=session_id,
        turn_index=turn_index,
    )
