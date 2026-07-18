"""Shared durable-memory candidate capture helpers.

Workflow runtimes keep their own task state, but candidate handling is shared:
validation, dedupe, caps, rendering, and lifecycle hook shapes all live here.
The ledger remains review evidence only; this module never writes wiki files.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal

from pydantic import BaseModel, Field

from app.context_limits import get_context_limits
from app.teacher_agent.memory_targets import (
    canonical_memory_target,
    is_subject_guide_target,
    is_supported_runtime_target,
)

MEMORY_TARGETS = (
    "planning_brief.md",
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
SPEECH_ACTS = ("conduct_request", "store_request", "observation", "unknown")
MEMORY_SCOPES = ("turn", "lesson", "block", "class", "global", "unknown")
ADMISSION_DECISIONS = ("ignore", "stage", "needs_review")
FAST_LANE_ACTS = {"conduct_request", "store_request"}
KNOWN_SPEECH_ACTS = FAST_LANE_ACTS | {"observation"}
KNOWN_MEMORY_SCOPES = {"turn", "lesson", "block", "class", "global"}


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
    routing_reason: str = Field(
        default="",
        description=(
            "Internal one-sentence reason for choosing this memory target. "
            "Used for traces/evals/debugging; not teacher-facing."
        ),
    )
    requires_teacher_approval: bool = True
    speech_act: str = Field(
        default="unknown",
        description=(
            "How the teacher's message relates to this candidate: "
            "conduct_request (teacher directs the agent's behavior or states a "
            "standing preference, not bounded to the current document), "
            "store_request (teacher explicitly asks to remember/add/remove "
            "something in memory), observation (teacher reports what happened). "
            "Use unknown when unsure."
        ),
    )
    scope: str = Field(
        default="unknown",
        description=(
            "How broadly the claim remains valid: turn, lesson, block, class, "
            "global, or unknown."
        ),
    )
    scope_label: str = Field(
        default="",
        description="Compact bounded label such as 'organic chemistry' for block scope.",
    )
    # Backend-owned provenance/admission fields. The model may leave these at
    # their defaults; discipline_memory_candidates computes them from the
    # current teacher message before anything reaches the ledger.
    origin_kind: str = Field(default="", description="Backend provenance kind.")
    origin_turn_index: int = Field(default=0, ge=0)
    origin_message_hash: str = Field(default="", description="Hash of the source teacher message.")
    quote_fingerprint: str = Field(default="", description="Hash of the verified teacher quote.")
    capture_batch_id: str = Field(default="", description="Backend batch identity for one teacher turn.")
    admission: str = Field(
        default="",
        description="Backend-owned Admission decision: ignore, stage, or needs_review.",
    )
    admission_reason_codes: list[str] = Field(default_factory=list)
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


@dataclass(frozen=True)
class MemoryAdmissionResult:
    """Backend-owned Admission and Priority verdict for one candidate."""

    candidate: MemoryCandidate
    admission: Literal["ignore", "stage", "needs_review"]
    fast_lane: bool = False
    reason_codes: list[str] = field(default_factory=list)


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
        "|".join(
            (
                canonical_memory_target(candidate.target),
                clean_text(candidate.section).casefold(),
                clean_text(candidate.scope).casefold() or "unknown",
                clean_text(candidate.scope_label).casefold(),
                " ".join(candidate.candidate_update.lower().split()),
            )
        ),
        clean_text(candidate.candidate_update).casefold(),
    )


def group_memory_candidates(
    candidates: Iterable[MemoryCandidate],
) -> list[MemoryCandidate]:
    """Group exact same-purpose claims within one capture batch.

    Scope and section are part of identity. A claim reused for a bounded block
    must not erase an otherwise identical class-wide claim before ledger
    folding has a chance to review both.
    """

    out: list[MemoryCandidate] = []
    seen: set[tuple[str, str]] = set()
    for candidate in candidates:
        if not candidate.candidate_update.strip():
            continue
        key = candidate_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        out.append(candidate)
    return out


def bound_memory_capture_batch(
    candidates: Iterable[MemoryCandidate],
    *,
    max_candidates: int | None = None,
) -> list[MemoryCandidate]:
    """Apply the operational per-turn guard without silently dropping claims.

    The guard is deliberately applied after exact grouping. When the batch is
    too large, reserve one ledger item for a compact ``needs_review`` bundle
    containing the overflow evidence. It cannot fast-lane and uses the
    canonical review target rather than pretending the overflow is a normal
    class or teacher preference.
    """

    limit = (
        max_candidates
        if max_candidates is not None
        else get_context_limits().memory_capture_batch_max_candidates
    )
    if limit < 1:
        raise ValueError("max_candidates must be at least 1")
    grouped = group_memory_candidates(candidates)
    if len(grouped) <= limit:
        return grouped

    keep_count = limit - 1
    kept = grouped[:keep_count]
    overflow = grouped[keep_count:]
    claims = [
        (
            f"- {candidate.target}/{candidate.section}/"
            f"{candidate.scope}: {clean_text(candidate.candidate_update)}"
        )
        for candidate in overflow
    ]
    first = overflow[0]
    bundle = first.model_copy(
        update={
            "target": "canonical_wiki",
            "section": "Memory capture overflow",
            "candidate_update": (
                f"{len(overflow)} additional memory capture claims require review."
            ),
            "evidence": (
                "Operational batch guard preserved these unbounded claims for review:\n"
                + "\n".join(claims)
            )[:1600],
            "source": "inferred_from_session",
            "basis": "inferred",
            "confidence": "low",
            "speech_act": "unknown",
            "scope": "unknown",
            "scope_label": "",
            "admission": "needs_review",
            "admission_reason_codes": ["batch_overflow"],
            "fast_lane": False,
            "requires_teacher_approval": True,
        }
    )
    return [*kept, bundle]


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

    Returns the verified quote, or None when the candidate omitted or
    fabricated a quote. A missing quote is not authorization to use the whole
    message: that was the old shortcut that allowed weak candidates through.
    """
    evidence_clean = clean_text(evidence)
    lower = evidence_clean.lower()
    prefix = DIRECT_TEACHER_QUOTE_PREFIX.lower()
    if prefix not in lower:
        return None
    start = lower.index(prefix) + len(prefix)
    quoted = evidence_clean[start:].split("|", 1)[0].strip().strip('"“”')
    message_normalized = clean_text(teacher_message).lower()
    if (
        len(quoted) >= _MIN_VERIFIED_QUOTE_CHARS
        and quoted.lower() in message_normalized
    ):
        return quoted
    return None


def _message_fingerprint(value: str) -> str:
    normalized = clean_text(value).casefold().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest() if normalized else ""


def _quote_fingerprint(value: str) -> str:
    normalized = clean_text(value).casefold().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest() if normalized else ""


def admit_memory_candidate(
    candidate: MemoryCandidate,
    *,
    teacher_message: str,
    origin_message_id: str,
    origin_turn_index: int = 0,
) -> MemoryAdmissionResult:
    """Compute the V4 Admission/Priority verdict for one model candidate.

    The model supplies semantic hints; this function owns the trust boundary.
    In particular, unknown speech act/scope, missing provenance, and missing or
    fabricated quotes can only move a candidate to review, never to fast lane.
    """

    speech_act = clean_text(candidate.speech_act).casefold() or "unknown"
    scope = clean_text(candidate.scope).casefold() or "unknown"
    reasons: list[str] = []
    quote = _verified_quote(candidate.evidence, teacher_message)

    if not candidate.candidate_update.strip():
        reasons.append("empty_claim")
    if not candidate_is_allowed(candidate):
        reasons.append("unsupported_target_or_source")

    # Non-explicit evidence can be useful review material, but it is never a
    # fast-lane candidate and does not need to masquerade as a teacher request.
    if candidate.source != "teacher_explicit":
        if reasons:
            decision: Literal["ignore", "stage", "needs_review"] = "ignore"
        else:
            decision = "stage"
            reasons.append("non_explicit_signal")
        bound = candidate.model_copy(
            update={
                "speech_act": speech_act,
                "scope": scope,
                "origin_kind": "teacher_message" if teacher_message else "",
                "origin_turn_index": max(0, origin_turn_index),
                "origin_message_hash": origin_message_id or _message_fingerprint(teacher_message),
                "quote_fingerprint": _quote_fingerprint(quote or ""),
                "capture_batch_id": origin_message_id or _message_fingerprint(teacher_message),
                "admission": decision,
                "admission_reason_codes": reasons,
                "fast_lane": False,
            }
        )
        return MemoryAdmissionResult(bound, decision, False, reasons)

    if speech_act not in KNOWN_SPEECH_ACTS:
        reasons.append("unknown_speech_act")
    if scope not in KNOWN_MEMORY_SCOPES:
        reasons.append("unknown_scope")
    if scope == "turn":
        reasons.append("turn_scope_not_durable")
    if not origin_message_id:
        reasons.append("missing_origin")
    if not clean_text(candidate.evidence):
        reasons.append("missing_quote")
    elif quote is None:
        reasons.append(
            "missing_quote"
            if DIRECT_TEACHER_QUOTE_PREFIX.lower() not in clean_text(candidate.evidence).casefold()
            else "quote_not_in_origin_message"
        )

    if reasons:
        decision = "ignore" if "unsupported_target_or_source" in reasons else "needs_review"
        bound = candidate.model_copy(
            update={
                "speech_act": speech_act,
                "scope": scope,
                "origin_kind": "teacher_message",
                "origin_turn_index": max(0, origin_turn_index),
                "origin_message_hash": origin_message_id,
                "quote_fingerprint": _quote_fingerprint(quote or ""),
                "capture_batch_id": origin_message_id,
                "admission": decision,
                "admission_reason_codes": reasons,
                "fast_lane": False,
            }
        )
        return MemoryAdmissionResult(bound, decision, False, reasons)

    if speech_act == "observation":
        reasons.append("observation_signal")
        decision = "stage"
        fast_lane = False
    else:
        fast_lane = (
            speech_act in FAST_LANE_ACTS
            and scope in {"class", "global"}
            and candidate.confidence == "high"
            and is_fast_lane_explicit_target(candidate.target)
            and (
                fast_lane_policy(candidate.target) == "always"
                or speech_act == "store_request"
            )
        )
        decision = "stage"
        reasons.append("explicit_request" if fast_lane else "regular_signal")

    bound = candidate.model_copy(
        update={
            "speech_act": speech_act,
            "scope": scope,
            "origin_kind": "teacher_message",
            "origin_turn_index": max(0, origin_turn_index),
            "origin_message_hash": origin_message_id,
            "quote_fingerprint": _quote_fingerprint(quote or ""),
            "capture_batch_id": origin_message_id,
            "admission": decision,
            "admission_reason_codes": reasons,
            "fast_lane": fast_lane,
        }
    )
    return MemoryAdmissionResult(bound, decision, fast_lane, reasons)


def discipline_memory_candidates(
    candidates: Iterable[MemoryCandidate],
    *,
    teacher_message: str,
    origin_turn_index: int = 0,
) -> list[MemoryCandidate]:
    """Keep only defensible explicit claims; downgrade the rest to signals.

    The workflow model proposes speech act and scope. Backend Admission then
    verifies origin and quote provenance, and Priority grants fast lane only
    for a narrow explicit-request policy. Marker words such as ``always`` are
    evidence the model may consider, never authorization. Candidates bound to
    an earlier teacher message are not rechecked against the latest message;
    full transcript storage is intentionally out of scope.
    """
    out: list[MemoryCandidate] = []
    for candidate in candidates:
        if candidate.source != "teacher_explicit":
            # Inferred/tool evidence is already a regular review signal. Do
            # not mutate its provenance merely because this turn is being
            # persisted, but never allow a model-provided fast-lane bit to
            # survive.
            out.append(
                candidate
                if not candidate.fast_lane
                else candidate.model_copy(update={"fast_lane": False})
            )
            continue
        if candidate.origin_message_hash and candidate.admission in ADMISSION_DECISIONS:
            # This candidate was already admitted against its source message.
            # Do not compare its quote with a later turn's text.
            out.append(candidate.model_copy(update={"fast_lane": bool(candidate.fast_lane and candidate.admission == "stage")}))
            continue

        result = admit_memory_candidate(
            candidate,
            teacher_message=teacher_message,
            origin_message_id=_message_fingerprint(teacher_message),
            origin_turn_index=origin_turn_index,
        )
        candidate = result.candidate
        quote = _verified_quote(candidate.evidence, teacher_message)
        if result.fast_lane and quote is not None:
            rest = _strip_quote_prefix(candidate.evidence)
            evidence = f"{DIRECT_TEACHER_QUOTE_PREFIX} {quote}"
            if rest:
                evidence = f"{evidence} | {rest}"
            candidate = candidate.model_copy(update={"evidence": evidence[:1600]})
        else:
            # Keep regular/uncertain signals review-only and prevent the quote
            # token from acting as a legacy fast-lane capability.
            candidate = candidate.model_copy(
                update={
                    "source": "inferred_from_session"
                    if candidate.source == "teacher_explicit"
                    else candidate.source,
                    "basis": "inferred"
                    if candidate.source == "teacher_explicit"
                    else candidate.basis,
                    "confidence": "low"
                    if candidate.source == "teacher_explicit"
                    else candidate.confidence,
                    "fast_lane": False,
                    "evidence": _strip_quote_prefix(candidate.evidence)[:1600],
                }
            )
        out.append(candidate)
    return out


# Human-readable target list for the remember(...) tool's retry feedback.
REMEMBER_TARGET_HINT = (
    "teacher_profile.md (how to communicate with the teacher), "
    "copilot_profile.md (how to plan for this class), "
    "teaching_patterns.md (how this class learns), "
    "planning_brief.md (current planning priorities), or "
    "wiki/subjects/<subject>.md (subject-wide teaching guidance)"
)


def validate_remember_call(
    *,
    target: str,
    content: str,
    quote: str,
    speech_act: str = "",
    scope: str = "unknown",
    routing_reason: str = "",
    teacher_message: str,
) -> tuple[MemoryCandidate | None, str]:
    """Validate one ``remember(...)`` tool call against the teacher's words.

    Returns ``(candidate, "")`` when the call is well-formed, or
    ``(None, error)`` with a structured, model-facing message so the agent can
    correct and retry within the turn. The three checks all ground in ground
    truth (a supported preference target; the teacher actually said the quote),
    never in a guess about intent — persist-time ``discipline_memory_candidates``
    still makes the authoritative fast-lane decision.
    """
    clean_content = clean_text(content)
    if not clean_content:
        return None, "Nothing to remember: pass the durable fact as `content`."

    canonical = canonical_memory_target(target)
    if not is_fast_lane_explicit_target(canonical):
        return None, (
            f"'{target}' is not a memory target you can write to. Use one of: "
            f"{REMEMBER_TARGET_HINT}. Class state and the lesson record are not "
            "memory targets — they come from the saved lessons."
        )

    clean_quote = clean_text(quote)
    if len(clean_quote) < _MIN_VERIFIED_QUOTE_CHARS:
        return None, (
            "Pass `quote`: the teacher's exact sentence that asked for this "
            "(copy their words verbatim)."
        )
    if clean_quote.lower() not in clean_text(teacher_message).lower():
        return None, (
            "That quote is not in the teacher's message. Copy their exact "
            "words — do not paraphrase or invent a sentence."
        )

    candidate = MemoryCandidate(
        target=canonical,
        section="General",
        candidate_update=clean_content,
        evidence=f"{DIRECT_TEACHER_QUOTE_PREFIX} {clean_quote}",
        source="teacher_explicit",
        basis="explicit",
        confidence="high",
        routing_reason=clean_text(routing_reason)[:320],
        speech_act=clean_text(speech_act).lower(),
        scope=clean_text(scope).lower() or "unknown",
        requires_teacher_approval=True,
    )
    return candidate, ""


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
