"""OpenAI Agents SDK agent definitions."""

from __future__ import annotations

from agents import Agent

from app.teacher_agent.models import CompileOutput, IngestTurnOutput, PlanOutput, PlanTurnOutput
from app.teacher_agent.prompts import (
    COMPILE_SYSTEM,
    INGEST_SYSTEM,
    LINT_SYSTEM,
    PLAN_CHAT_SYSTEM,
    PLAN_OPENING_SYSTEM,
    PLAN_SYSTEM,
)
from app.teacher_agent.tools import WikiToolContext, create_wiki_tools


def build_ingest_agent(ctx: WikiToolContext, sections: str, context: str, model: str) -> Agent:
    instructions = INGEST_SYSTEM.format(sections=sections, context=context[:8000])
    return Agent(
        name="KlassenPilot Ingest",
        instructions=instructions,
        model=model,
        tools=create_wiki_tools(ctx),
        output_type=IngestTurnOutput,
    )


def build_plan_chat_agent(ctx: WikiToolContext, context: str, model: str) -> Agent:
    return Agent(
        name="KlassenPilot Plan Chat",
        instructions=PLAN_CHAT_SYSTEM.format(context=context[:8000]),
        model=model,
        tools=create_wiki_tools(ctx),
        output_type=PlanTurnOutput,
    )


def build_plan_opening_agent(context: str, model: str) -> Agent:
    return Agent(
        name="KlassenPilot Plan Opening",
        instructions=PLAN_OPENING_SYSTEM.format(context=context[:12000]),
        model=model,
    )


def build_compile_agent(model: str) -> Agent:
    return Agent(
        name="KlassenPilot Compile",
        instructions=COMPILE_SYSTEM,
        model=model,
        output_type=CompileOutput,
    )


def build_plan_lesson_agent(ctx: WikiToolContext, model: str) -> Agent:
    return Agent(
        name="KlassenPilot Plan Lesson",
        instructions=PLAN_SYSTEM,
        model=model,
        tools=create_wiki_tools(ctx),
        output_type=PlanOutput,
    )


def build_lint_agent(ctx: WikiToolContext, context: str, model: str) -> Agent:
    return Agent(
        name="KlassenPilot Wiki Lint",
        instructions=LINT_SYSTEM + f"\n\nClass: {ctx.class_id}\n\n{context[:4000]}",
        model=model,
        tools=create_wiki_tools(ctx),
    )
