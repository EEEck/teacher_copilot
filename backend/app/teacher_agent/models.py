"""Structured outputs for teacher agents."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.api import LessonFlowPhase


class CompileOutput(BaseModel):
    diary_markdown: str = Field(description="Full lesson results markdown with all sections")


class IngestTurnOutput(BaseModel):
    reply: str = Field(description="Conversational reply to the teacher")
    diary_markdown: str = Field(description="Updated full lesson results markdown with all sections")


class PlanTurnOutput(BaseModel):
    reply: str = Field(description="Conversational reply to the teacher")
    plan_markdown: str = Field(description="Updated full lesson plan markdown")


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
        description="Durable patterns about what worked or failed for this class"
    )
    copilot_profile_markdown: str = Field(
        description="Bounded Honcho-style teacher/class/copilot profile"
    )
    session_summaries_markdown: str = Field(
        default="",
        description="Optional compact summaries of prior workflow sessions",
    )
    warnings: list[str] = Field(default_factory=list)
