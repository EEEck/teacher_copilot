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
