from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"


class ClassSummary(BaseModel):
    id: str
    label: str
    subject: str


class ClassesResponse(BaseModel):
    classes: list[ClassSummary]


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


class WikiUpdateProposal(BaseModel):
    wiki_path: str
    current_content: str
    proposed_content: str
    rationale: str


class IngestDraft(BaseModel):
    diary_markdown: str
    wiki_proposals: list[WikiUpdateProposal]
    completeness: CompletenessChecklist


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


class ChatRequest(BaseModel):
    message: str
    diary_markdown: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    diary_markdown: str
    completeness: CompletenessChecklist
    ready_to_propose: bool = False


class UpdateDraftRequest(BaseModel):
    diary_markdown: str


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
