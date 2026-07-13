"""Structured outputs for teacher agents."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.api import LessonFlowPhase
from app.teacher_agent.executive_verification import ExecutivePatch
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
    executive_patch: ExecutivePatch = Field(default_factory=ExecutivePatch)


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
    executive_patch: ExecutivePatch = Field(default_factory=ExecutivePatch)


class WriteVerificationOutput(BaseModel):
    """Read-only check of the exact artifact submitted for a durable action."""

    executive_patch: ExecutivePatch = Field(default_factory=ExecutivePatch)
    message: str = Field(
        default="Verification complete.",
        description=(
            "One concise teacher-visible outcome. If blocking, name the mismatch "
            "and ask the smallest decision needed; never claim a write occurred."
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
    # taught_so_far_markdown and class_state_markdown were retired (mem_v3 PR2):
    # those facts are derived from the canonical timeline / course_state rollups,
    # not curated as compact pages.
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


class MemoryConsolidationOpOutput(BaseModel):
    """One Mem V3 consolidation decision (mem0-style ID-referenced ops)."""

    claim_ids: list[str] = Field(
        description="Input claim ids this operation resolves. Every input claim id must appear in exactly one operation.",
    )
    operation: str = Field(
        description=(
            "add | update | delete | none. add appends new_text as a new memory "
            "bullet; update replaces the referenced memory bullet with new_text; "
            "delete removes the referenced obsolete bullet (prefer update when a "
            "claim supersedes it); none records that current memory already covers "
            "the claim or it is not worth writing."
        ),
    )
    target: str = Field(description="Memory file the operation applies to.")
    section: str = Field(default="", description="Section within the target file.")
    memory_id: str = Field(
        default="",
        description=(
            "For update/delete: the id of the referenced memory bullet, copied "
            "EXACTLY from the enumerated current-memory index. Never invent ids."
        ),
    )
    new_text: str = Field(
        default="",
        description=(
            "For add/update: the durable memory bullet to write. State the "
            "underlying claim, not whichever phrasing appeared most often."
        ),
    )
    rationale: str = Field(
        default="",
        description="One teacher-readable sentence explaining the decision.",
    )


class MemoryConsolidationOutput(BaseModel):
    operations: list[MemoryConsolidationOpOutput] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
