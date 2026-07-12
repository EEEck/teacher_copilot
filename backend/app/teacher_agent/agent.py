"""OpenAI Agents SDK agent definitions."""

from __future__ import annotations

from agents import Agent
from agents.model_settings import ModelSettings
from openai.types.shared import Reasoning

from app.teacher_agent.models import (
    CompileOutput,
    IngestTurnOutput,
    MemoryConsolidationOutput,
    MemoryCompactOutput,
    PlanOutput,
    PlanTurnOutput,
    ProfileProposalOutput,
    WriteVerificationOutput,
)
from app.teacher_agent.memory_update_state import MemoryRuntime
from app.teacher_agent.planning_state import PlanRuntime
from app.teacher_agent.executive_verification import render_executive_runtime
from app.teacher_agent.prompt_assembly import (
    build_ingest_chat_prompt_assembly,
    build_plan_chat_prompt_assembly,
)
from app.teacher_agent.prompts import (
    COMPILE_SYSTEM,
    LINT_SYSTEM,
    MEMORY_COMPACT_SYSTEM,
    MEMORY_SWEEP_CONSOLIDATION_SYSTEM,
    PROFILE_PROPOSAL_SYSTEM,
    PLAN_OPENING_SYSTEM,
    PLAN_SYSTEM,
    WRITE_VERIFICATION_SYSTEM,
    apply_prompt,
    TEACHER_AGENT_SECURITY_POLICY,
)
from app.context_limits import apply_char_limit, get_context_limits
from app.teacher_agent.tools import (
    WikiToolContext,
    create_chat_wiki_tools,
    create_memory_update_tools,
    create_wiki_tools,
)


def chat_model_settings(
    reasoning_effort: str, *, model: str | None = None
) -> ModelSettings | None:
    """Reasoning settings for any agent (chat, sweep, or utility one-shot).

    Set effort to ``none`` to match the API default and skip hidden reasoning
    tokens. Non-reasoning models ignore this when unsupported. Call classes pass
    their profile-resolved effort (chat/important/utility — see config.py).
    """
    normalized_effort = reasoning_effort
    if reasoning_effort == "minimal" and model and model.startswith("gpt-5.4"):
        normalized_effort = "none"
    if normalized_effort == "none":
        return None
    return ModelSettings(reasoning=Reasoning(effort=normalized_effort, summary="auto"))


def build_ingest_agent(
    ctx: WikiToolContext,
    model: str,
    *,
    memory: MemoryRuntime | None = None,
    reasoning_effort: str = "medium",
) -> Agent:
    rt = memory or MemoryRuntime()
    assembly = build_ingest_chat_prompt_assembly(
        ctx.wiki,
        ctx.class_id,
        messages=[],
        current_diary="",
        runtime=rt,
        executive=ctx.executive,
        attachments=[],
    )
    instructions = assembly["instructions"]
    settings = chat_model_settings(reasoning_effort, model=model)
    return Agent(
        name="KlassenPilot Ingest",
        instructions=instructions,
        model=model,
        **({"model_settings": settings} if settings else {}),
        tools=create_memory_update_tools(ctx),
        output_type=IngestTurnOutput,
    )


def build_plan_chat_agent(
    ctx: WikiToolContext,
    current_plan: str,
    model: str,
    *,
    planning: PlanRuntime | None = None,
    reasoning_effort: str = "medium",
) -> Agent:
    wiki = ctx.wiki
    class_id = ctx.class_id
    rt = planning or PlanRuntime()
    assembly = build_plan_chat_prompt_assembly(
        wiki,
        class_id,
        messages=[],
        current_plan=current_plan,
        runtime=rt,
        executive=ctx.executive,
        attachments=[],
    )
    instructions = assembly["instructions"]
    settings = chat_model_settings(reasoning_effort, model=model)
    return Agent(
        name="KlassenPilot Plan Chat",
        instructions=instructions,
        model=model,
        **({"model_settings": settings} if settings else {}),
        tools=create_chat_wiki_tools(ctx),
        output_type=PlanTurnOutput,
    )


def build_write_verification_agent(
    ctx: WikiToolContext,
    artifact_kind: str,
    active_class_core: str,
    model: str,
    *,
    reasoning_effort: str = "medium",
) -> Agent:
    return Agent(
        name="KlassenPilot Write Verifier",
        instructions=apply_prompt(
            WRITE_VERIFICATION_SYSTEM,
            artifact_kind=artifact_kind,
            active_class_core=active_class_core,
            executive_state=render_executive_runtime(ctx.executive),
            security_policy=TEACHER_AGENT_SECURITY_POLICY,
        ),
        model=model,
        **_reasoning(reasoning_effort, model),
        tools=create_chat_wiki_tools(ctx),
        output_type=WriteVerificationOutput,
    )


def _reasoning(reasoning_effort: str, model: str) -> dict:
    settings = chat_model_settings(reasoning_effort, model=model)
    return {"model_settings": settings} if settings else {}


def build_plan_opening_agent(
    context: str, model: str, *, reasoning_effort: str = "minimal"
) -> Agent:
    return Agent(
        name="KlassenPilot Plan Opening",
        instructions=apply_prompt(
            PLAN_OPENING_SYSTEM,
            context=apply_char_limit(
                context, get_context_limits().plan_opening_context_chars
            ),
        ),
        model=model,
        **_reasoning(reasoning_effort, model),
    )


def build_compile_agent(model: str, *, reasoning_effort: str = "minimal") -> Agent:
    return Agent(
        name="KlassenPilot Compile",
        instructions=COMPILE_SYSTEM,
        model=model,
        output_type=CompileOutput,
        **_reasoning(reasoning_effort, model),
    )


def build_plan_lesson_agent(
    ctx: WikiToolContext, model: str, *, reasoning_effort: str = "minimal"
) -> Agent:
    return Agent(
        name="KlassenPilot Plan Lesson",
        instructions=PLAN_SYSTEM,
        model=model,
        tools=create_wiki_tools(ctx),
        output_type=PlanOutput,
        **_reasoning(reasoning_effort, model),
    )


def build_lint_agent(
    ctx: WikiToolContext, context: str, model: str, *, reasoning_effort: str = "minimal"
) -> Agent:
    return Agent(
        name="KlassenPilot Wiki Lint",
        instructions=LINT_SYSTEM
        + f"\n\nClass: {ctx.class_id}\n\n"
        + apply_char_limit(context, get_context_limits().lint_context_chars),
        model=model,
        tools=create_wiki_tools(ctx),
        **_reasoning(reasoning_effort, model),
    )


def build_memory_compact_agent(
    model: str, *, reasoning_effort: str = "minimal"
) -> Agent:
    return Agent(
        name="KlassenPilot Memory Compact",
        instructions=apply_prompt(
            MEMORY_COMPACT_SYSTEM,
            security_policy=TEACHER_AGENT_SECURITY_POLICY,
        ),
        model=model,
        output_type=MemoryCompactOutput,
        **_reasoning(reasoning_effort, model),
    )


def build_profile_proposal_agent(
    model: str, *, reasoning_effort: str = "minimal"
) -> Agent:
    return Agent(
        name="KlassenPilot Profile Proposal",
        instructions=apply_prompt(
            PROFILE_PROPOSAL_SYSTEM,
            security_policy=TEACHER_AGENT_SECURITY_POLICY,
        ),
        model=model,
        output_type=ProfileProposalOutput,
        **_reasoning(reasoning_effort, model),
    )


def build_memory_sweep_consolidation_agent(
    model: str, *, reasoning_effort: str = "high"
) -> Agent:
    return Agent(
        name="KlassenPilot Memory Consolidation",
        instructions=apply_prompt(
            MEMORY_SWEEP_CONSOLIDATION_SYSTEM,
            security_policy=TEACHER_AGENT_SECURITY_POLICY,
        ),
        model=model,
        output_type=MemoryConsolidationOutput,
        **_reasoning(reasoning_effort, model),
    )
