"""Prompt assembly diagnostics for lesson-planning sessions.

These helpers intentionally mirror the plan-agent prompt construction without
calling the model. They make context assembly reviewable: each prompt section is
tagged with the function/source that contributed it and the exact rendered text.
"""

from __future__ import annotations

from app.schemas.api import ChatAttachment, ChatMessage
from app.context_limits import apply_char_limit, get_context_limits
from app.teacher_agent.planning_state import (
    PlanRuntime,
    render_briefs,
    render_lesson_planning_state,
    render_session_state,
)
from app.teacher_agent.prompts import (
    PLAN_CHAT_SYSTEM,
    PLAN_MEMORY_POLICY,
    PLAN_OPENING_SYSTEM,
    PLAN_SKILL,
    PLAN_WIKI_TOOLS_POLICY,
    apply_prompt,
)
from app.teacher_agent.wiki import memory as wiki_memory


def _section(
    *,
    name: str,
    function: str,
    source: str,
    text: str,
    included: bool = True,
) -> dict:
    return {
        "name": name,
        "function": function,
        "source": source,
        "included": included,
        "chars": len(text or ""),
        "text": text or "",
    }


def _trim_to_last_user_turns(messages: list[ChatMessage], n: int) -> list[ChatMessage]:
    if n <= 0 or not messages:
        return list(messages)
    seen_users = 0
    start = 0
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].role == "user":
            seen_users += 1
            if seen_users >= n:
                start = i
                break
    return messages[start:]


def _format_attachments(attachments: list[ChatAttachment] | None) -> str:
    if not attachments:
        return ""
    lim = get_context_limits()
    blocks = []
    for att in attachments:
        blocks.append(
            f"### Upload: {att.filename}\n"
            f"{apply_char_limit(att.content, lim.upload_attachment_chars)}"
        )
    return "\n\n".join(blocks)


def build_plan_user_input_trace(
    messages: list[ChatMessage],
    attachments: list[ChatAttachment] | None = None,
) -> dict:
    lim = get_context_limits()
    trimmed = _trim_to_last_user_turns(messages, lim.plan_history_turns)
    parts: list[str] = []
    sections: list[dict] = []
    if attachments:
        text = f"Uploaded materials this turn:\n{_format_attachments(attachments)}\n"
        parts.append(text)
        sections.append(
            _section(
                name="Uploaded materials",
                function="AgentRunner._build_plan_user_input",
                source="PlanChatRequest.attachments",
                text=text,
            )
        )
    convo_lines = ["Recent conversation (most recent last):"]
    for m in trimmed:
        convo_lines.append(f"{m.role}: {m.content}")
    convo = "\n".join(convo_lines)
    parts.append(convo)
    sections.append(
        _section(
            name="Recent conversation window",
            function="AgentRunner._build_plan_user_input",
            source=f"last {lim.plan_history_turns} user turns",
            text=convo,
        )
    )
    rendered = "\n".join(parts)
    return {
        "function": "AgentRunner._build_plan_user_input",
        "chars": len(rendered),
        "text": rendered,
        "sections": sections,
    }


def build_profiles_trace(wiki, class_id: str) -> dict:
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
    rendered = (
        f"### Teacher (user.md)\n{user_block}\n\n"
        f"### Copilot working agreement (copilot.md)\n{copilot_block}"
    )
    return {
        "function": "agent._profiles_slice",
        "chars": len(rendered),
        "text": rendered,
        "sections": [
            _section(
                name="Teacher profile",
                function="wiki.read_user_profile",
                source="wiki/teacher_profile.md",
                text=user_block,
                included=bool(user_md),
            ),
            _section(
                name="Class copilot profile",
                function="wiki.read_copilot_profile",
                source=f"wiki/classes/{class_id}/memory/copilot_profile.md",
                text=copilot_block,
                included=bool(copilot_md),
            ),
        ],
    }


def build_plan_chat_prompt_trace(
    wiki,
    class_id: str,
    *,
    messages: list[ChatMessage],
    current_plan: str,
    runtime: PlanRuntime | None,
    attachments: list[ChatAttachment] | None = None,
) -> dict:
    rt = runtime or PlanRuntime()
    lim = get_context_limits()
    class_trace = wiki.build_plan_context_slim_trace(class_id)
    profiles_trace = build_profiles_trace(wiki, class_id)
    session_state = render_session_state(rt.session_state)
    lesson_state = render_lesson_planning_state(rt.lesson_planning_state)
    current_plan_text = (
        apply_char_limit((current_plan or "").strip(), lim.plan_current_chars)
        or "- (empty draft)"
    )
    evidence = render_briefs(rt.evidence_briefs)
    user_input = build_plan_user_input_trace(messages, attachments)
    rendered_instructions = apply_prompt(
        PLAN_CHAT_SYSTEM,
        skill=PLAN_SKILL,
        memory_policy=PLAN_MEMORY_POLICY,
        class_slice=class_trace["text"],
        profiles=profiles_trace["text"],
        session_state=session_state,
        lesson_state=lesson_state,
        current_plan=current_plan_text,
        evidence=evidence,
        wiki_tools_policy=PLAN_WIKI_TOOLS_POLICY,
    )
    rendered_instructions = apply_char_limit(
        rendered_instructions, lim.plan_instructions_backstop
    )
    sections = [
        _section(
            name="Plan chat system template",
            function="build_plan_chat_agent",
            source="prompts.PLAN_CHAT_SYSTEM",
            text=PLAN_CHAT_SYSTEM,
        ),
        _section(
            name="Active skill",
            function="build_plan_chat_agent",
            source="prompts.PLAN_SKILL",
            text=PLAN_SKILL,
        ),
        _section(
            name="Memory policy",
            function="build_plan_chat_agent",
            source="prompts.PLAN_MEMORY_POLICY",
            text=PLAN_MEMORY_POLICY,
        ),
        _section(
            name="Class slice",
            function="wiki.build_plan_context_slim",
            source="compact class wiki memory",
            text=class_trace["text"],
        ),
        _section(
            name="Profiles",
            function="agent._profiles_slice",
            source="wiki/teacher_profile.md + class copilot_profile.md",
            text=profiles_trace["text"],
        ),
        _section(
            name="Session state",
            function="render_session_state",
            source="PlanRuntime.session_state",
            text=session_state,
        ),
        _section(
            name="Lesson planning state",
            function="render_lesson_planning_state",
            source="PlanRuntime.lesson_planning_state",
            text=lesson_state,
        ),
        _section(
            name="Current lesson artifact",
            function="build_plan_chat_agent",
            source="ArtifactSession.partial_markdown",
            text=current_plan_text,
        ),
        _section(
            name="Evidence briefs",
            function="render_briefs",
            source="PlanRuntime.evidence_briefs",
            text=evidence,
        ),
        _section(
            name="Wiki tools policy",
            function="build_plan_chat_agent",
            source="prompts.PLAN_WIKI_TOOLS_POLICY",
            text=PLAN_WIKI_TOOLS_POLICY,
        ),
        _section(
            name="User input",
            function="AgentRunner._build_plan_user_input",
            source="ArtifactSession.messages + attachments",
            text=user_input["text"],
        ),
    ]
    return {
        "stage": "plan_chat",
        "model_call": "KlassenPilot Plan Chat",
        "instruction_chars": len(rendered_instructions),
        "user_input_chars": len(user_input["text"]),
        "instructions": rendered_instructions,
        "user_input": user_input["text"],
        "sections": sections,
        "nested": {
            "class_slice": class_trace,
            "profiles": profiles_trace,
            "user_input": user_input,
        },
    }


def build_plan_opening_prompt_trace(wiki, class_id: str) -> dict:
    lim = get_context_limits()
    class_trace = wiki.build_plan_context_slim_trace(class_id)
    context = apply_char_limit(class_trace["text"], lim.plan_opening_context_chars)
    instructions = apply_prompt(PLAN_OPENING_SYSTEM, context=context)
    user_input = "Open the planning session for this class."
    return {
        "stage": "plan_opening",
        "model_call": "KlassenPilot Plan Opening",
        "instruction_chars": len(instructions),
        "user_input_chars": len(user_input),
        "instructions": instructions,
        "user_input": user_input,
        "sections": [
            _section(
                name="Plan opening system template",
                function="build_plan_opening_agent",
                source="prompts.PLAN_OPENING_SYSTEM",
                text=PLAN_OPENING_SYSTEM,
            ),
            _section(
                name="Opening class context",
                function="wiki.build_plan_context_slim",
                source="compact class wiki memory",
                text=context,
            ),
            _section(
                name="Opening user input",
                function="AgentRunner.plan_opening",
                source="constant",
                text=user_input,
            ),
        ],
        "nested": {"class_slice": class_trace},
    }
