"""Structured outputs for teacher agents."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.api import LessonFlowPhase
from app.teacher_agent.memory_capture import MemoryCandidate
from app.teacher_agent.memory_update_state import (
    MemoryEvidenceBrief,
    MemoryStatePatch,
)
from app.teacher_agent.planning_state import (
    EvidenceBrief,
    LessonPlanningState,
    SessionState,
    StatePatch,
)


class CompileOutput(BaseModel):
    diary_markdown: str = Field(
        description="Full lesson results markdown with all sections"
    )


class IngestTurnOutput(BaseModel):
    reply: str = Field(description="Conversational reply to the teacher")
    diary_markdown: str = Field(
        description="Updated full lesson results markdown with all sections"
    )
    last_change_summary: str = Field(
        default="",
        description="One-line summary of what changed in the lesson-results draft",
    )
    state_patch: MemoryStatePatch = Field(
        default_factory=MemoryStatePatch,
        description=(
            "Preferred runtime-state update contract for Update Memory. "
            "Backend validates and applies this patch; missing fields mean no change."
        ),
    )
    new_evidence_briefs: list[MemoryEvidenceBrief] = Field(
        default_factory=list,
        description="Compact briefs for lesson/memory evidence used to identify or update the target",
    )
    memory_candidates: list[MemoryCandidate] = Field(
        default_factory=list,
        description=(
            "Durable-memory update candidates from the update-memory chat. "
            "These are review-only, never direct writes, and explicit durable "
            "teacher/class/copilot signals should be emitted here in the same turn."
        ),
    )
    unsupported_intent_reason: str = Field(
        default="",
        description="Set only when the teacher asks for an update-memory task outside the MVP scope.",
    )


class PlanTurnOutput(BaseModel):
    reply: str = Field(description="Conversational reply to the teacher")
    plan_markdown: str = Field(description="Updated full lesson plan markdown")
    last_change_summary: str = Field(
        default="", description="One-line summary of what changed in the plan this turn"
    )
    state_patch: StatePatch = Field(
        default_factory=StatePatch,
        description=(
            "Preferred runtime-state update contract. Backend validates and applies "
            "this patch to PlanRuntime; missing fields mean no change."
        ),
    )
    # Compatibility fallback while older stubs/outputs are migrated. New prompts
    # ask for state_patch, not full authoritative snapshots.
    session_state: SessionState = Field(default_factory=SessionState)
    lesson_planning_state: LessonPlanningState = Field(
        default_factory=LessonPlanningState
    )
    new_evidence_briefs: list[EvidenceBrief] = Field(
        default_factory=list,
        description="Compact briefs for tool/search/material results used this turn",
    )
    memory_candidates: list[MemoryCandidate] = Field(
        default_factory=list,
        description=(
            "Durable-memory update candidates. These are review-only, never direct "
            "writes, and explicit durable teacher/class/copilot signals should be "
            "emitted here in the same turn."
        ),
    )


class PlanOutput(BaseModel):
    title: str
    lesson_date: Optional[str] = None
    duration_minutes: int = 45
    learning_goals: list[str]
    lesson_flow: list[LessonFlowPhase]
    warmup: str
    practice_tasks: list[str]
    homework: str
    teacher_notes: str
    addresses_open_loops: list[str] = Field(default_factory=list)
    addresses_misconceptions: list[str] = Field(default_factory=list)


class MemoryCompactOutput(BaseModel):
    taught_so_far_markdown: str = Field(
        description="Compact year-to-date content sequence for the class"
    )
    planning_brief_markdown: str = Field(
        description="Planning-oriented summary of readiness, open loops, and misconception priorities"
    )
    teaching_patterns_markdown: str = Field(
        description=(
            "Durable class+subject teaching style: how THIS class learns and which "
            "teaching approaches work or fail for it (absorbs the class learning profile)"
        )
    )
    copilot_profile_markdown: str = Field(
        description=(
            "Copilot working agreement for this class only: planning patterns to apply, "
            "avoid-rules, repeated teacher corrections, agent-behavior preferences"
        )
    )
    class_state_markdown: str = Field(
        default="",
        description="Derived current-state snapshot for the class (compact)",
    )
    session_summaries_markdown: str = Field(
        default="",
        description="Optional compact summaries of prior workflow sessions",
    )
    stale_report: list[str] = Field(
        default_factory=list,
        description="Notes on stale or conflicting facts found while compacting",
    )
    warnings: list[str] = Field(default_factory=list)


class ProfileCandidateOut(BaseModel):
    target: str = "copilot_profile.md"  # teacher_profile.md | copilot_profile.md
    section: str = "General"
    content: str = ""
    basis: str = "inferred"  # explicit | inferred
    confidence: str = "low"
    evidence: str = ""


class ProfileProposalOutput(BaseModel):
    user_candidates: list[ProfileCandidateOut] = Field(default_factory=list)
    copilot_candidates: list[ProfileCandidateOut] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class MemorySweepAlignmentGroupOutput(BaseModel):
    group_id: str = Field(description="Stable id for this normalized claim group")
    target: str
    section: str = "General"
    ledger_candidate_ids: list[str] = Field(
        default_factory=list,
        description="All ledger candidate IDs assigned to this group, each input ID exactly once.",
    )
    matched_memory_item_ids: list[str] = Field(default_factory=list)
    relationship: str = Field(
        default="new_semantic_claim",
        description=(
            "new_semantic_claim | broadens_existing_memory | already_covered | "
            "possible_conflict | one_off_or_low_signal | scoped_exception"
        ),
    )
    decision: str = Field(
        default="merge",
        description=(
            "merge | adjust_existing | already_covered | needs_decision | reject_low_signal"
        ),
    )
    group_label: str = Field(
        default="", description="Short semantic label for the claim"
    )
    surface_labels: list[str] = Field(
        default_factory=list,
        description="Surface phrasings or labels used by the raw ledger rows in this group.",
    )
    shared_attributes: list[str] = Field(
        default_factory=list,
        description="Attributes that make the grouped rows one coherent durable claim.",
    )
    distinguishing_attributes: list[str] = Field(
        default_factory=list,
        description="Meaningful differences that remain after grouping; empty when none matter.",
    )
    merge_test: str = Field(
        default="",
        description="Short public test explaining why the rows can or cannot be one memory claim.",
    )
    public_rationale: str = Field(
        default="",
        description="Short teacher/operator-reviewable rationale; no hidden reasoning.",
    )


class MemorySweepAlignmentOutput(BaseModel):
    alignment_groups: list[MemorySweepAlignmentGroupOutput] = Field(
        default_factory=list
    )
    warnings: list[str] = Field(default_factory=list)


class MemorySweepCardOutput(BaseModel):
    candidate_id: str
    card_id: str = Field(
        default="",
        description="Stable review-card id. If omitted, the backend derives one from represented candidate IDs and target.",
    )
    source_group_id: str = Field(
        default="",
        description="Alignment group id this review card was generated from.",
    )
    candidate_ids: list[str] = Field(
        default_factory=list,
        description=(
            "All ledger candidate IDs represented by this review card; include candidate_id. "
            "When multiple rows support the same durable claim, return one card with all IDs."
        ),
    )
    review_queue: str
    channel: str
    target: str
    section: str = "General"
    content: str
    evidence_summary: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: str = "low"
    basis: str = "inferred"
    status: str = "captured"
    relationship: str = ""
    group_label: str = ""
    surface_labels: list[str] = Field(default_factory=list)
    shared_attributes: list[str] = Field(default_factory=list)
    distinguishing_attributes: list[str] = Field(default_factory=list)
    merge_test: str = ""
    public_rationale: str = ""
    operation: str = Field(
        default="add",
        description=(
            "Claim-level sweep operation. add creates a new memory bullet; adjust "
            "refines an exact existing bullet using replaces_content; already_covered, "
            "reject_low_signal, and needs_decision do not write memory."
        ),
    )
    replaces_content: str = Field(
        default="",
        description=(
            "For operation='adjust', copy the exact existing memory bullet text from "
            "the current memory excerpt that should be replaced. Leave empty otherwise."
        ),
    )
    status_recommendation: str = Field(
        default="promote",
        description=(
            "promote | already_covered | needs_decision | reject_low_signal. "
            "Compatibility field: add and adjust map to promote. "
            "use already_covered only when the current memory already captures the generalized claim."
        ),
    )
    why_now: str = Field(
        default="",
        description=(
            "Concise evidence-grounded reason, including whether this is repeated evidence, "
            "a refinement of current memory, already covered, ambiguous, or low-signal."
        ),
    )
    signal_count: int = Field(
        default=1,
        description="Number of represented ledger rows, not the number of output cards.",
    )


class MemorySweepProposalOutput(BaseModel):
    cards: list[MemorySweepCardOutput] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
