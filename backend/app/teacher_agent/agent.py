"""OpenAI Agents SDK agent definitions."""

from __future__ import annotations

from agents import Agent
from agents.model_settings import ModelSettings
from openai.types.shared import Reasoning

from app.teacher_agent.models import CompileOutput, IngestTurnOutput, PlanOutput, PlanTurnOutput
from app.teacher_agent.prompts import (
    CHAT_WIKI_TOOLS_POLICY,
    COMPILE_SYSTEM,
    INGEST_SYSTEM,
    LINT_SYSTEM,
    PLAN_CHAT_SYSTEM,
    PLAN_OPENING_SYSTEM,
    PLAN_SYSTEM,
    apply_prompt,
)
from app.teacher_agent.tools import WikiToolContext, create_chat_wiki_tools, create_wiki_tools

_CHAT_CONTEXT_CHARS = 14_000


def chat_model_settings(reasoning_effort: str) -> ModelSettings | None:
    """Optional reasoning summaries for chat agents (ingest/plan).

    Set effort to ``none`` to match GPT-5.4's API default and skip hidden reasoning tokens.
    Non-reasoning models (e.g. gpt-4o-mini) ignore this when unsupported.
    """
    if reasoning_effort == "none":
        return None
    return ModelSettings(reasoning=Reasoning(effort=reasoning_effort, summary="auto"))


def build_ingest_agent(
    ctx: WikiToolContext,
    sections: str,
    context: str,
    model: str,
    *,
    reasoning_effort: str = "medium",
) -> Agent:
    instructions = apply_prompt(
        INGEST_SYSTEM,
        sections=sections,
        context=context[:_CHAT_CONTEXT_CHARS],
        wiki_tools_policy=CHAT_WIKI_TOOLS_POLICY,
    )
    settings = chat_model_settings(reasoning_effort)
    return Agent(
        name="KlassenPilot Ingest",
        instructions=instructions,
        model=model,
        **({"model_settings": settings} if settings else {}),
        tools=create_wiki_tools(ctx),
        output_type=IngestTurnOutput,
    )


def build_plan_chat_agent(
    ctx: WikiToolContext,
    context: str,
    model: str,
    *,
    reasoning_effort: str = "medium",
) -> Agent:
    settings = chat_model_settings(reasoning_effort)
    return Agent(
        name="KlassenPilot Plan Chat",
        instructions=apply_prompt(
            PLAN_CHAT_SYSTEM,
            context=context[:_CHAT_CONTEXT_CHARS],
            wiki_tools_policy=CHAT_WIKI_TOOLS_POLICY,
        ),
        model=model,
        **({"model_settings": settings} if settings else {}),
        tools=create_chat_wiki_tools(ctx),
        output_type=PlanTurnOutput,
    )


def build_plan_opening_agent(context: str, model: str) -> Agent:
    return Agent(
        name="KlassenPilot Plan Opening",
        instructions=apply_prompt(PLAN_OPENING_SYSTEM, context=context[:12000]),
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
