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
    is_subject_guide_target,
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
    speech_act: str = Field(
        default="",
        description=(
            "How the teacher's message relates to this candidate: "
            "conduct_request (teacher directs the agent's behavior or states a "
            "standing preference, not bounded to the current document), "
            "store_request (teacher explicitly asks to remember/add/remove "
            "something in memory), observation (teacher reports what happened). "
            "Leave empty when unsure."
        ),
    )
    fast_lane: bool = Field(
        default=False,
        description=(
            "Backend-computed after verification; never set this yourself."
        ),
    )


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


# Mem V3 fallback markers. The primary fast-lane policy is speech_act +
# target + quote provenance; these markers only corroborate legacy/empty
# speech_act conduct requests for profile targets.
_DURABLE_PREFERENCE_MARKERS = (
    "from now on",
    "always",
    "going forward",
    "in the future",
    "for future",
    "all future",
    "for the next block",
    "for all lesson",
    "for all brief",
    "for all classes",
    "not just this",
    "general preference",
    "general communication",
    "as a general",
)
DIRECT_TEACHER_QUOTE_PREFIX = "Direct teacher quote:"

# Fast-lane policy per target (dictation vs observation, docs/mem_v3):
# - conduct files hold the agent's standing instructions -> any direct
#   request or correction qualifies;
# - content files are teachable -> only an explicit store/remove request
#   ("remember/add/remove ...") qualifies;
# - compiled files are built from lessons, never dictated -> never fast lane.
FAST_LANE_ALWAYS_TARGETS = {"teacher_profile.md", "copilot_profile.md"}
FAST_LANE_STORE_REQUEST_TARGETS = {"teaching_patterns.md", "planning_brief.md"}
_MIN_VERIFIED_QUOTE_CHARS = 10


def occasion_key_for(mode: str, session_id: str, lesson_date: str = "") -> str:
    """Occasion anchor for reinforcement counting (docs/mem_v3 lane 2).

    An occasion is the artifact the capture was about, so re-pasting the same
    report into several sessions counts once:
    - ingest anchors on the lesson being logged (``lesson:<date>``); if the
      target is unresolved, the key is empty and the gate falls back to a
      6-hour time bucket (still collapses retries);
    - plan sessions have no resolved lesson at capture time and are NOT a
      re-paste failure mode, so each plan session is its own occasion
      (``plansession:<id>``) — this also avoids wrongly collapsing two
      distinct evening planning sessions into one time bucket.
    """
    date = (lesson_date or "").strip()
    if date:
        return f"lesson:{date}"
    if mode == "plan":
        return f"plansession:{session_id}"
    return ""


def has_durable_preference_scope(text: str) -> bool:
    normalized = clean_text(text).lower()
    return bool(normalized) and any(
        marker in normalized for marker in _DURABLE_PREFERENCE_MARKERS
    )


def has_fast_lane_explicit_proof(text: str) -> bool:
    """Ledger-side fast-lane token: the verified-quote prefix.

    Only ``discipline_memory_candidates`` writes this prefix, and only after
    verifying the quote against the actual teacher message (fabricated quotes
    are stripped and the candidate downgraded), so its presence in a ledger
    row's evidence is the trust token for the explicit fast lane.
    """
    return DIRECT_TEACHER_QUOTE_PREFIX.lower() in clean_text(text).lower()


def fast_lane_policy(target: str) -> str:
    """Return 'always' | 'store_request' | 'never' for a memory target."""
    canonical = canonical_memory_target(target)
    if canonical in FAST_LANE_ALWAYS_TARGETS:
        return "always"
    if canonical in FAST_LANE_STORE_REQUEST_TARGETS or is_subject_guide_target(
        canonical
    ):
        return "store_request"
    return "never"


def is_fast_lane_explicit_target(target: str) -> bool:
    """Targets that can EVER use the explicit fast lane."""
    return fast_lane_policy(target) != "never"


def has_fast_lane_explicit_signal(target: str, evidence: str) -> bool:
    return is_fast_lane_explicit_target(target) and has_fast_lane_explicit_proof(
        evidence
    )


def is_fast_lane_row(
    target: str,
    source: str,
    evidence: str,
    fast_lane_flag: bool,
) -> bool:
    """Ledger-side fast-lane check with defense in depth.

    The persisted ``fast_lane`` verdict (written only by
    ``discipline_memory_candidates`` after full verification) is the primary
    signal. For conduct files ("always" tier) the verified-quote token in
    evidence is accepted as a fallback for rows written before the flag
    existed. Compiled targets ("never" tier) are held regardless of any
    token — a forged or legacy prefix cannot fast-lane class memory. Content
    files ("store_request" tier) require the persisted verdict, because the
    speech-act judgment is not reconstructible from a ledger row.
    """
    policy = fast_lane_policy(target)
    if policy == "never":
        return False
    if fast_lane_flag:
        return True
    return (
        policy == "always"
        and source == "teacher_explicit"
        and has_fast_lane_explicit_proof(evidence)
    )


def _strip_quote_prefix(evidence: str) -> str:
    """Remove any quote-prefix segments so downgrades cannot leak the token."""
    parts = [
        part.strip()
        for part in clean_text(evidence).split("|")
        if DIRECT_TEACHER_QUOTE_PREFIX.lower() not in part.lower()
    ]
    return " | ".join(part for part in parts if part)


def _verified_quote(evidence: str, teacher_message: str) -> str | None:
    """Verify the model's claimed teacher quote against the real message.

    Returns the verified quote, "" when the model quoted nothing (caller may
    fall back to the whole message), or None when the model FABRICATED a
    quote that does not appear in what the teacher typed.
    """
    evidence_clean = clean_text(evidence)
    lower = evidence_clean.lower()
    prefix = DIRECT_TEACHER_QUOTE_PREFIX.lower()
    if prefix not in lower:
        return ""
    start = lower.index(prefix) + len(prefix)
    quoted = evidence_clean[start:].split("|", 1)[0].strip().strip('"“”')
    message_normalized = clean_text(teacher_message).lower()
    if (
        len(quoted) >= _MIN_VERIFIED_QUOTE_CHARS
        and quoted.lower() in message_normalized
    ):
        return quoted
    return None


def discipline_memory_candidates(
    candidates: Iterable[MemoryCandidate],
    *,
    teacher_message: str,
) -> list[MemoryCandidate]:
    """Keep only defensible explicit claims; downgrade the rest to signals.

    The workflow model judges the speech act (conduct_request /
    store_request / observation) — that is the primary classification, per
    the direct-agent-instruction pattern (ChatGPT memory, LangMem procedural
    memory). Deterministic code enforces exactly three things:
    1. the lane policy of the target (dictation vs observation boundary);
    2. quote provenance — a quoted sentence must actually appear in the
       teacher's message; a fabricated quote downgrades the candidate;
    3. the future-scope markers as fallback corroboration when the model
       did not classify the speech act (legacy/typed-state paths).
    Kept candidates get the canonical verified-quote prefix stamped into
    evidence and ``fast_lane=True``; downgraded candidates have any quote
    prefix stripped so the token cannot leak into the ledger.
    """
    marker_scoped = has_durable_preference_scope(teacher_message)
    out: list[MemoryCandidate] = []
    for candidate in candidates:
        if candidate.source != "teacher_explicit":
            if candidate.fast_lane:
                candidate = candidate.model_copy(update={"fast_lane": False})
            out.append(candidate)
            continue

        policy = fast_lane_policy(candidate.target)
        speech_act = (candidate.speech_act or "").strip().lower()
        act_ok = (
            speech_act == "store_request"
            if policy == "store_request"
            else speech_act in ("conduct_request", "store_request") or marker_scoped
        )
        quote = _verified_quote(candidate.evidence, teacher_message)

        if policy == "never" or not act_ok or quote is None:
            evidence = _strip_quote_prefix(candidate.evidence)
            candidate = candidate.model_copy(
                update={
                    "source": "inferred_from_session",
                    "basis": "inferred",
                    "confidence": "low",
                    "fast_lane": False,
                    "evidence": evidence[:1600],
                }
            )
            out.append(candidate)
            continue

        # Kept: stamp the canonical verified quote (model's verified quote,
        # or the whole teacher message when the model quoted nothing).
        verified = quote or clean_text(teacher_message)
        rest = _strip_quote_prefix(candidate.evidence)
        evidence = f"{DIRECT_TEACHER_QUOTE_PREFIX} {verified}"
        if rest:
            evidence = f"{evidence} | {rest}"
        candidate = candidate.model_copy(
            update={"evidence": evidence[:1600], "fast_lane": True}
        )
        out.append(candidate)
    return out


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
    occasion_key: str = "",
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
        occasion_key=occasion_key,
    )
