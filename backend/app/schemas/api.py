from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    agent_max_turns: int = 16
    openai_configured: bool = False


class ClassSummary(BaseModel):
    id: str
    label: str
    subject: str


class ClassesResponse(BaseModel):
    classes: list[ClassSummary]


class WikiLintResponse(BaseModel):
    class_id: str
    report_markdown: str


class MemoryCompactRequest(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class MemoryCompactApplyRequest(BaseModel):
    pages: dict[str, str] = Field(default_factory=dict)
    source_paths: list[str] = Field(default_factory=list)


class MemoryCompactResponse(BaseModel):
    class_id: str
    applied_wiki_paths: list[str]
    log_entry_id: str
    source_paths: list[str] = Field(default_factory=list)
    stale_report: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class MemoryProposalResponse(BaseModel):
    """Proposed (uncommitted) derived memory pages — teacher reviews before apply."""

    class_id: str
    pages: dict = Field(default_factory=dict)
    source_paths: list[str] = Field(default_factory=list)
    stale_report: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ProfileProposalRequest(BaseModel):
    """Inputs from a finished planning session used to propose profile updates."""

    final_lesson_markdown: str = ""
    session_state: Optional[dict] = None
    lesson_planning_state: Optional[dict] = None
    memory_candidates: list[dict] = Field(default_factory=list)


class ProfileCandidate(BaseModel):
    target: str  # user.md | copilot.md
    section: str = "General"
    content: str
    basis: str = "inferred"  # explicit | inferred
    confidence: str = "low"
    evidence: str = ""


class ProfileProposalResponse(BaseModel):
    class_id: str
    candidates: list[ProfileCandidate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class MemoryApplyItem(BaseModel):
    target: str  # user.md | copilot.md | class_state.md | wiki/subjects/{subject}.md
    section: str = "General"
    content: str


class MemoryApplyRequest(BaseModel):
    items: list[MemoryApplyItem] = Field(default_factory=list)


class MemoryApplyResponse(BaseModel):
    class_id: str
    applied_wiki_paths: list[str] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class MemorySweepCandidate(BaseModel):
    card_id: str = ""
    source_group_id: str = ""
    candidate_id: str
    candidate_ids: list[str] = Field(default_factory=list)
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
    operation: Literal[
        "add",
        "adjust",
        "already_covered",
        "reject_low_signal",
        "needs_decision",
    ] = "add"
    replaces_content: str = ""
    status_recommendation: Literal[
        "promote",
        "already_covered",
        "needs_decision",
        "reject_low_signal",
    ] = "promote"
    why_now: str = ""
    current_memory_excerpt: str = ""
    signal_count: int = 1
    can_apply: bool = False
    review_only_reason: str = ""


class MemorySweepProposalResponse(BaseModel):
    class_id: str
    subject: str = ""
    queues: dict[str, list[MemorySweepCandidate]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class MemoryCandidateStatusRequest(BaseModel):
    status: Literal["proposed", "approved", "applied", "rejected", "snoozed", "deleted", "expired"]
    rejection_reason: str | None = None
    review_batch_id: str | None = None


class MemoryCandidateStatusResponse(BaseModel):
    candidate_id: str
    status: str


class MemorySweepDecision(BaseModel):
    card_id: str = ""
    action: Literal["apply", "reject", "snooze", "delete", "already_covered"]
    target: str
    section: str = "General"
    content: str = ""
    operation: Literal[
        "add",
        "adjust",
        "already_covered",
        "reject_low_signal",
        "needs_decision",
    ] = "add"
    replaces_content: str = ""
    candidate_ids: list[str] = Field(default_factory=list)
    rejection_reason: str | None = None


class MemorySweepApplyRequest(BaseModel):
    decisions: list[MemorySweepDecision] = Field(default_factory=list)
    review_batch_id: str | None = None


class MemorySweepApplyResponse(BaseModel):
    class_id: str
    applied_wiki_paths: list[str] = Field(default_factory=list)
    updated_candidate_ids: list[str] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TimelineEntry(BaseModel):
    date: str
    title: str
    month_key: str = ""
    summary: str = ""
    highlights: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)
    covered: list[str] = Field(default_factory=list)
    homework: Optional[str] = None
    raw_path: Optional[str] = None
    has_plan: bool = False
    # "taught" = lesson_results.md exists; "planned" = only a saved lesson_plan.md
    status: str = "taught"
    committed_at: Optional[str] = None
    wiki_paths: list[str] = Field(default_factory=list)


class ClassTimeline(BaseModel):
    class_id: str
    entries: list[TimelineEntry]
    months: list[str] = Field(default_factory=list)


class ClassMemorySnapshot(BaseModel):
    class_id: str
    label: str
    current_unit: str
    last_lesson_date: Optional[str] = None
    last_committed_date: Optional[str] = None
    last_committed_at: Optional[str] = None
    last_committed_title: Optional[str] = None
    open_loop_count: int = 0
    top_misconceptions: list[str] = Field(default_factory=list)
    recent_lessons: list[str] = Field(default_factory=list)


class RollupExcerpt(BaseModel):
    wiki_path: str
    label: str
    markdown: str


class LessonDetail(BaseModel):
    class_id: str
    date: str
    title: str
    primary_markdown: str
    diary_markdown: str
    raw_markdown: str = ""
    lesson_plan_markdown: Optional[str] = None
    rollup_excerpts: list[RollupExcerpt] = Field(default_factory=list)


class ReviseLessonRequest(BaseModel):
    diary_markdown: str


class ReviseLessonResponse(BaseModel):
    entry: TimelineEntry
    applied_wiki_paths: list[str]


class ChatMessage(BaseModel):
    role: str
    content: str


class IngestSessionStatus(str, Enum):
    chatting = "chatting"
    ready_to_propose = "ready_to_propose"
    reviewing = "reviewing"
    committed = "committed"


IngestStartIntent = Literal[
    "log_new_results",
    "update_missing_results",
    "correct_existing_results",
]
IngestStartTargetKind = Literal["new_lesson", "planned_lesson", "taught_lesson"]
IngestStartSource = Literal["teacher_explicit", "timeline_hint", "agent_inferred"]


class IngestSessionStartRequest(BaseModel):
    lesson_date: Optional[str] = None
    lesson_title: str = ""
    intent: Optional[IngestStartIntent] = None
    target_kind: Optional[IngestStartTargetKind] = None
    source: IngestStartSource = "teacher_explicit"


class CompletenessItem(BaseModel):
    field: str
    label: str
    complete: bool
    required: bool = True


class CompletenessChecklist(BaseModel):
    items: list[CompletenessItem]


class IngestSession(BaseModel):
    session_id: str
    class_id: str
    status: IngestSessionStatus
    messages: list[ChatMessage] = Field(default_factory=list)
    completeness: CompletenessChecklist = Field(default_factory=lambda: CompletenessChecklist(items=[]))
    memory_state: Optional[dict] = None
    memory_candidates: list[dict] = Field(default_factory=list)


class WikiUpdateProposal(BaseModel):
    wiki_path: str
    current_content: str
    proposed_content: str
    rationale: str


class IngestDraft(BaseModel):
    diary_markdown: str
    wiki_proposals: list[WikiUpdateProposal]
    completeness: CompletenessChecklist
    memory_state: Optional[dict] = None
    memory_candidates: list[dict] = Field(default_factory=list)


class ApprovedWikiUpdate(BaseModel):
    wiki_path: str
    content: str
    approved: bool = True


class CommitIngestRequest(BaseModel):
    session_id: str
    diary_markdown: str
    approved_updates: list[ApprovedWikiUpdate]


class CommitIngestResponse(BaseModel):
    raw_diary_path: str
    applied_wiki_paths: list[str]
    log_entry_id: str
    lesson_date: str = ""
    title: str = ""
    class_memory_proposal: Optional[MemoryProposalResponse] = None


class WikiFileResponse(BaseModel):
    wiki_path: str
    markdown: str


class ChatAttachment(BaseModel):
    filename: str
    content: str


class ChatRequest(BaseModel):
    message: str
    diary_markdown: Optional[str] = None
    attachments: list[ChatAttachment] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    diary_markdown: str
    completeness: CompletenessChecklist
    ready_to_propose: bool = False
    last_change_summary: str = ""
    memory_state: Optional[dict] = None
    memory_candidates: list[dict] = Field(default_factory=list)


class UpdateDraftRequest(BaseModel):
    diary_markdown: str


class PlanSessionStatus(str, Enum):
    chatting = "chatting"
    ready_to_save = "ready_to_save"
    saved = "saved"


class PlanSession(BaseModel):
    session_id: str
    class_id: str
    status: PlanSessionStatus
    messages: list[ChatMessage] = Field(default_factory=list)
    opening_message: str = ""


class PlanDraft(BaseModel):
    plan_markdown: str


class PlanChatRequest(BaseModel):
    message: str
    plan_markdown: Optional[str] = None
    attachments: list[ChatAttachment] = Field(default_factory=list)


class PlanChatResponse(BaseModel):
    reply: str
    plan_markdown: str
    ready_to_save: bool = False
    # Runtime context-manager state (lesson-planning chat).
    phase: Optional[str] = None
    last_change_summary: str = ""
    session_state: Optional[dict] = None
    lesson_planning_state: Optional[dict] = None
    memory_candidates: list[dict] = Field(default_factory=list)


class UpdatePlanDraftRequest(BaseModel):
    plan_markdown: str


class SavePlanRequest(BaseModel):
    session_id: str
    lesson_date: str
    plan_markdown: str


class SavePlanResponse(BaseModel):
    lesson_date: str
    title: str
    plan_path: str
    session_state: Optional[dict] = None
    lesson_planning_state: Optional[dict] = None
    # Proposed durable-memory updates from the session (proposed only; never
    # written here — durable writes are a separate teacher-approved action).
    memory_candidates: list[dict] = Field(default_factory=list)


class AgentTraceResponse(BaseModel):
    """Debug/review bundle for one artifact-agent session."""

    class_id: str
    session_id: str
    status: str
    prompt_stack: dict = Field(default_factory=dict)
    prompt_assembly: dict = Field(default_factory=dict)
    runtime: dict = Field(default_factory=dict)
    messages: list[ChatMessage] = Field(default_factory=list)
    artifact_markdown: str = ""
    event_trace: list[dict] = Field(default_factory=list)
    raw_evidence: dict = Field(default_factory=dict)


class PlanTraceResponse(AgentTraceResponse):
    """Debug/review bundle for one lesson-planning session."""


class MemoryTraceResponse(AgentTraceResponse):
    """Debug/review bundle for one update-memory session."""


class PlanLessonRequest(BaseModel):
    anchor_lesson_date: Optional[date] = None
    duration_minutes: int = 45


class LessonFlowPhase(BaseModel):
    phase: str
    minutes: int
    description: str


class LessonPlan(BaseModel):
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

    def to_markdown(self) -> str:
        lines = [
            f"# Lesson Plan — {self.title}",
            "",
            f"> Duration: {self.duration_minutes} min",
            "",
            "## Learning goals",
            *[f"- {g}" for g in self.learning_goals],
            "",
            "## Lesson flow",
        ]
        for phase in self.lesson_flow:
            lines.append(f"- **{phase.phase}** ({phase.minutes} min): {phase.description}")
        lines.extend(
            [
                "",
                "## Warmup",
                self.warmup,
                "",
                "## Practice",
                *[f"- {t}" for t in self.practice_tasks],
                "",
                "## Homework",
                self.homework,
                "",
                "## Teacher notes",
                self.teacher_notes,
            ]
        )
        if self.addresses_open_loops:
            lines.extend(["", "## Addresses open loops", *[f"- {x}" for x in self.addresses_open_loops]])
        if self.addresses_misconceptions:
            lines.extend(["", "## Addresses misconceptions", *[f"- {x}" for x in self.addresses_misconceptions]])
        return "\n".join(lines) + "\n"
