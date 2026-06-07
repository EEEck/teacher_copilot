"""OpenAI Agents SDK agent definitions."""

from __future__ import annotations

from agents import Agent
from agents.model_settings import ModelSettings
from openai.types.shared import Reasoning

from app.teacher_agent.models import (
    CompileOutput,
    IngestTurnOutput,
    MemoryCompactOutput,
    PlanOutput,
    PlanTurnOutput,
    ProfileProposalOutput,
)
from app.teacher_agent.planning_state import (
    PlanRuntime,
    render_briefs,
    render_lesson_planning_state,
    render_session_state,
)
from app.teacher_agent.prompts import (
    COMPILE_SYSTEM,
    INGEST_WIKI_TOOLS_POLICY,
    INGEST_SYSTEM,
    LINT_SYSTEM,
    MEMORY_COMPACT_SYSTEM,
    PLAN_CHAT_SYSTEM,
    PLAN_MEMORY_POLICY,
    PROFILE_PROPOSAL_SYSTEM,
    PLAN_SKILL,
    PLAN_WIKI_TOOLS_POLICY,
    PLAN_OPENING_SYSTEM,
    PLAN_SYSTEM,
    apply_prompt,
)
from app.context_limits import apply_char_limit, get_context_limits
from app.teacher_agent.tools import WikiToolContext, create_chat_wiki_tools, create_wiki_tools
from app.teacher_agent.wiki import memory as wiki_memory


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
    lim = get_context_limits()
    instructions = apply_prompt(
        INGEST_SYSTEM,
        sections=sections,
        context=apply_char_limit(context, lim.ingest_context_backstop),
        wiki_tools_policy=INGEST_WIKI_TOOLS_POLICY,
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


def _profiles_slice(wiki, class_id: str) -> str:
    user_md = wiki.read_user_profile().strip()
    copilot_md = wiki.read_copilot_profile(class_id).strip()
    user_block = (
        wiki_memory.clamp_memory_page("user", user_md).rstrip()
        if user_md
        else "- No teacher profile yet."
    )
    copilot_block = (
        wiki_memory.clamp_memory_page("copilot_profile", copilot_md).rstrip()
        if copilot_md
        else "- No copilot profile yet."
    )
    return (
        f"### Teacher (user.md)\n{user_block}\n\n"
        f"### Copilot working agreement (copilot.md)\n{copilot_block}"
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
    instructions = apply_prompt(
        PLAN_CHAT_SYSTEM,
        skill=PLAN_SKILL,
        memory_policy=PLAN_MEMORY_POLICY,
        class_slice=wiki.build_plan_context_slim(class_id),
        profiles=_profiles_slice(wiki, class_id),
        session_state=render_session_state(rt.session_state),
        lesson_state=render_lesson_planning_state(rt.lesson_planning_state),
        current_plan=apply_char_limit(
            (current_plan or "").strip(), get_context_limits().plan_current_chars
        )
        or "- (empty draft)",
        evidence=render_briefs(rt.evidence_briefs),
        wiki_tools_policy=PLAN_WIKI_TOOLS_POLICY,
    )
    instructions = apply_char_limit(
        instructions, get_context_limits().plan_instructions_backstop
    )
    settings = chat_model_settings(reasoning_effort)
    return Agent(
        name="KlassenPilot Plan Chat",
        instructions=instructions,
        model=model,
        **({"model_settings": settings} if settings else {}),
        tools=create_chat_wiki_tools(ctx),
        output_type=PlanTurnOutput,
    )


def build_plan_opening_agent(context: str, model: str) -> Agent:
    return Agent(
        name="KlassenPilot Plan Opening",
        instructions=apply_prompt(
            PLAN_OPENING_SYSTEM,
            context=apply_char_limit(context, get_context_limits().plan_opening_context_chars),
        ),
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
        instructions=LINT_SYSTEM
        + f"\n\nClass: {ctx.class_id}\n\n"
        + apply_char_limit(context, get_context_limits().lint_context_chars),
        model=model,
        tools=create_wiki_tools(ctx),
    )


def build_memory_compact_agent(model: str) -> Agent:
    return Agent(
        name="KlassenPilot Memory Compact",
        instructions=MEMORY_COMPACT_SYSTEM,
        model=model,
        output_type=MemoryCompactOutput,
    )


def build_profile_proposal_agent(model: str) -> Agent:
    return Agent(
        name="KlassenPilot Profile Proposal",
        instructions=PROFILE_PROPOSAL_SYSTEM,
        model=model,
        output_type=ProfileProposalOutput,
    )
