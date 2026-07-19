"""Agent runners using OpenAI Agents SDK."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Optional

from agents import Runner
from agents.exceptions import AgentsException, MaxTurnsExceeded
from openai import OpenAI

from app.config import Settings
from app.schemas.api import (
    ChatAttachment,
    ChatMessage,
    CompletenessChecklist,
    LessonPlan,
)
from app.teacher_agent.agent import (
    build_class_brief_agent,
    build_class_discussion_agent,
    build_memory_compact_agent,
    build_compile_agent,
    build_ingest_agent,
    build_lint_agent,
    build_plan_chat_agent,
    build_plan_lesson_agent,
    build_plan_opening_agent,
    build_profile_proposal_agent,
    build_write_verification_agent,
)
from app.teacher_agent.models import (
    ClassBriefOutput,
    ClassDiscussionTurnOutput,
    CompileOutput,
    IngestTurnOutput,
    MemoryConsolidationOutput,
    MemoryCompactOutput,
    PlanOutput,
    PlanTurnOutput,
    ProfileProposalOutput,
    WriteVerificationOutput,
)
from app.context_limits import apply_char_limit, get_context_limits
from app.teacher_agent.prompt_assembly import (
    build_class_discussion_user_input_assembly,
    build_ingest_user_input_assembly,
    build_plan_user_input_assembly,
    trim_to_last_user_turns,
)
from app.teacher_agent.class_discussion_state import (
    ClassDiscussionRuntime,
    ClassDiscussionStatePatch,
    discussion_api_payload,
    merge_class_discussion_turn,
)
from app.teacher_agent.citation_presentation import (
    render_reviewed_source_footer,
    strip_model_source_presentation,
    validate_discussion_source_presentation,
)
from app.teacher_agent.memory_update_state import (
    MemoryRuntime,
    memory_api_payload,
    merge_memory_turn,
)
from app.teacher_agent.executive_verification import (
    ExecutiveRuntime,
    WriteVerificationResult,
    artifact_fingerprint,
    apply_executive_patch,
    executive_api_payload,
)
from app.teacher_agent.planning_state import (
    PlanRuntime,
    merge_turn_into_runtime,
    planning_api_payload,
)
from app.teacher_agent.lesson_package import validate_lesson_artifact
from app.teacher_agent.package_renderer import render_markdown_artifact
from app.teacher_agent.tools import WikiToolContext
from app.teacher_agent.stream_events import (
    SseError,
    SseEvent,
    SseFinal,
    translate_sdk_event,
)
from app.teacher_agent.wiki_store import WikiStore

logger = logging.getLogger("klassenpilot.agents")


class AgentTurnLimitError(RuntimeError):
    """Agent used too many tool/reasoning steps in one turn."""


@dataclass
class _PreparedAgentTurn:
    runtime: Any
    current_draft: str
    agent: Any
    user_input: str


_TURN_LIMIT_REPLY = (
    "I needed more steps than allowed to finish this turn. "
    "Your draft is unchanged — try a shorter message or one topic at a time."
)

_DEBUG_PLAN_SECTION_RE = re.compile(
    r"\n## Evidence briefs\b.*?(?=\n## |\Z)",
    flags=re.IGNORECASE | re.DOTALL,
)
_STUDENT_ROSTER_ROW_RE = re.compile(
    r"^\|\s*(S-\d{3})\s*\|\s*([^|]+?)\s*\|",
    flags=re.MULTILINE,
)


def _strip_plan_debug_sections(plan_md: str) -> str:
    """Remove runtime/debug sections if the model copies them into plan_markdown."""
    return _DEBUG_PLAN_SECTION_RE.sub("", plan_md or "").rstrip() + "\n"


def _student_name_replacements(roster_md: str) -> list[tuple[str, str]]:
    """Return known roster name variants mapped to pseudonymous student IDs."""
    replacements: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for match in _STUDENT_ROSTER_ROW_RE.finditer(roster_md or ""):
        sid = match.group(1).strip()
        full_name = " ".join(match.group(2).split())
        variants = [full_name]
        first_name = full_name.split()[0] if full_name else ""
        if first_name and first_name != full_name:
            variants.append(first_name)
        for variant in variants:
            key = (variant.lower(), sid)
            if variant and key not in seen:
                seen.add(key)
                replacements.append((variant, sid))
    return sorted(replacements, key=lambda item: len(item[0]), reverse=True)


def _pseudonymize_known_students(text: str, roster_md: str) -> str:
    """Replace known roster names with S-### IDs in model-produced diary text."""
    out = text or ""
    for name, sid in _student_name_replacements(roster_md):
        pattern = re.compile(
            rf"(?<![\w-]){re.escape(name)}(?:\s*\({re.escape(sid)}\))?(?![\w-])"
        )
        out = pattern.sub(sid, out)
    return out


def _trim_to_last_user_turns(messages: list[ChatMessage], n: int) -> list[ChatMessage]:
    """Keep only the last ``n`` user turns (and everything after the earliest).

    Durable context lives in injected state, so trimming the verbatim window is
    safe; this preserves recent conversational nuance without re-sending the
    whole transcript each turn.
    """
    return trim_to_last_user_turns(messages, n)


def _is_turn_limit_error(exc: BaseException) -> bool:
    if isinstance(exc, MaxTurnsExceeded):
        return True
    return "max turns" in str(exc).lower()


def _summarize_run_items(items) -> list[str]:
    """Human-readable trace of what the agent did (tool calls, messages)."""
    summary: list[str] = []
    for item in items or []:
        raw = getattr(item, "raw_item", None)
        item_type = type(item).__name__
        name = getattr(raw, "name", None)
        if name is None and isinstance(raw, dict):
            name = raw.get("name") or raw.get("type")
        args = getattr(raw, "arguments", None)
        if args is None and isinstance(raw, dict):
            args = raw.get("arguments")
        if args and len(str(args)) > 120:
            args = str(args)[:120] + "…"
        if name or args:
            summary.append(f"{item_type}({name}) {args or ''}".strip())
        else:
            summary.append(item_type)
    return summary


def _log_turn_limit(label: str, exc: BaseException) -> None:
    run_data = getattr(exc, "run_data", None)
    if run_data is None:
        logger.warning("[%s] turn limit hit; no run_data on exception", label)
        return
    raw_responses = getattr(run_data, "raw_responses", []) or []
    new_items = getattr(run_data, "new_items", []) or []
    trace = _summarize_run_items(new_items)
    logger.warning(
        "[%s] turn limit hit: %d model responses, %d items\n  %s",
        label,
        len(raw_responses),
        len(new_items),
        "\n  ".join(trace) if trace else "(no items)",
    )


class AgentRunner:
    def __init__(self, settings: Settings, wiki: WikiStore) -> None:
        key = settings.openai_api_key.get_secret_value()
        if not key:
            self.client = None
        else:
            self.client = OpenAI(api_key=key)
        # Call classes resolved by profile (config.py): CHAT (plan+ingest),
        # IMPORTANT (Memory Sweep only, strong + max reasoning), UTILITY
        # (one-shots on the chat model, minimal reasoning).
        self.chat_model = settings.resolved_chat_model()
        self.chat_effort = settings.resolved_chat_effort()
        self.sweep_model = settings.resolved_important_model()
        self.sweep_effort = settings.resolved_important_effort()
        self.utility_model = settings.resolved_utility_model()
        self.utility_effort = settings.resolved_utility_effort()
        self.timeout = settings.agent_timeout_seconds
        self.plan_timeout = settings.plan_agent_timeout_seconds
        self.max_turns = settings.agent_max_turns
        self.wiki = wiki
        self.plan_history_turns = settings.plan_history_turns
        self.tool_output_limit: int | None = 500
        self.tool_args_limit: int | None = 500

    def _require_client(self) -> OpenAI:
        if self.client is None:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        return self.client

    def _wiki_ctx(
        self,
        class_id: str,
        planning: Any = None,
        memory: MemoryRuntime | None = None,
        teacher_message: str = "",
        executive: ExecutiveRuntime | None = None,
    ) -> WikiToolContext:
        return WikiToolContext(
            wiki=self.wiki,
            class_id=class_id,
            planning=planning,
            memory=memory,
            teacher_message=teacher_message,
            executive=executive or ExecutiveRuntime(),
        )

    def _format_attachments(self, attachments: list[ChatAttachment]) -> str:
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

    def _build_user_input(
        self,
        messages: list[ChatMessage],
        draft_label: str,
        draft_content: str,
        attachments: list[ChatAttachment] | None = None,
    ) -> str:
        lim = get_context_limits()
        parts = [
            f"{draft_label}:\n{apply_char_limit(draft_content, lim.ingest_draft_chars)}\n"
        ]
        if attachments:
            parts.append(
                f"Uploaded materials this turn:\n{self._format_attachments(attachments)}\n"
            )
        for m in messages:
            parts.append(f"{m.role}: {m.content}")
        return "\n".join(parts)

    def _build_plan_user_input(
        self,
        messages: list[ChatMessage],
        attachments: list[ChatAttachment] | None = None,
    ) -> str:
        """Plan-path user input: only the verbatim window + this turn's uploads.

        The current draft and durable context live in the agent instructions
        (built from persisted state), so they are not duplicated here.
        """
        return build_plan_user_input_assembly(
            messages, attachments, history_turns=self.plan_history_turns
        )["text"]

    def _merge_plan_turn(
        self,
        runtime: PlanRuntime,
        parsed: PlanTurnOutput,
        *,
        plan_changed: bool,
        teacher_message: str = "",
        plan_ready: bool = False,
    ) -> None:
        merge_turn_into_runtime(
            runtime,
            state_patch=parsed.state_patch,
            session_state=parsed.session_state,
            lesson_planning_state=parsed.lesson_planning_state,
            new_evidence_briefs=parsed.new_evidence_briefs,
            memory_candidates=parsed.memory_candidates,
            last_change_summary=parsed.last_change_summary,
            plan_changed=plan_changed,
            teacher_message=teacher_message,
            plan_ready=plan_ready,
        )

    def _plan_final_event(
        self,
        reply: str,
        plan_md: str,
        ready: bool,
        runtime: PlanRuntime,
        executive: ExecutiveRuntime,
    ) -> SseFinal:
        payload = planning_api_payload(runtime)
        return SseFinal(
            reply=reply,
            artifact_markdown=plan_md,
            ready=ready,
            completeness=None,
            phase=payload["phase"],
            last_change_summary=payload["last_change_summary"],
            session_state=payload["session_state"],
            lesson_planning_state=payload["lesson_planning_state"],
            lesson_artifact=payload["lesson_artifact"],
            memory_candidates=payload["memory_candidates"],
            executive_state=executive_api_payload(executive),
        )

    def _merge_memory_turn(
        self,
        runtime: MemoryRuntime,
        parsed: IngestTurnOutput,
        *,
        diary_changed: bool,
        teacher_message: str = "",
        diary_complete: bool = False,
    ) -> None:
        merge_memory_turn(
            runtime,
            state_patch=parsed.state_patch,
            new_evidence_briefs=parsed.new_evidence_briefs,
            memory_candidates=parsed.memory_candidates,
            last_change_summary=parsed.last_change_summary,
            unsupported_intent_reason=parsed.unsupported_intent_reason,
            diary_changed=diary_changed,
            teacher_message=teacher_message,
            diary_complete=diary_complete,
        )

    def _memory_final_event(
        self,
        reply: str,
        diary_md: str,
        ready: bool,
        checklist: CompletenessChecklist,
        runtime: MemoryRuntime,
        executive: ExecutiveRuntime,
    ) -> SseFinal:
        payload = memory_api_payload(runtime)
        return SseFinal(
            reply=reply,
            artifact_markdown=diary_md,
            ready=ready,
            completeness=checklist,
            last_change_summary=payload["last_change_summary"],
            memory_candidates=payload["memory_candidates"],
            memory_state=payload,
            executive_state=executive_api_payload(executive),
        )

    def _prepare_ingest_turn(
        self,
        class_id: str,
        messages: list[ChatMessage],
        partial_diary: str = "",
        attachments: list[ChatAttachment] | None = None,
        memory: MemoryRuntime | None = None,
        executive: ExecutiveRuntime | None = None,
    ) -> _PreparedAgentTurn:
        runtime = memory or MemoryRuntime()
        latest_teacher_message = messages[-1].content if messages else ""
        agent = build_ingest_agent(
            self._wiki_ctx(
                class_id,
                memory=runtime,
                teacher_message=latest_teacher_message,
                executive=executive,
            ),
            self.chat_model,
            memory=runtime,
            reasoning_effort=self.chat_effort,
        )
        current_draft = partial_diary.strip() or self.wiki.empty_diary_template()
        user_input = build_ingest_user_input_assembly(
            messages, current_draft, attachments
        )["text"]
        return _PreparedAgentTurn(runtime, current_draft, agent, user_input)

    def _finalize_ingest_turn(
        self,
        parsed: Any,
        current_draft: str,
        runtime: MemoryRuntime,
        *,
        class_id: str,
        teacher_message: str = "",
        executive: ExecutiveRuntime | None = None,
    ) -> tuple[str, str, CompletenessChecklist, bool] | None:
        if not isinstance(parsed, IngestTurnOutput):
            return None
        reply = parsed.reply
        diary_md = parsed.diary_markdown.strip() or current_draft
        roster_md = self.wiki.read_text(self.wiki.roll_up_paths(class_id)["students"])
        diary_md = _pseudonymize_known_students(diary_md, roster_md)
        checklist = self.wiki.checklist_from_diary(diary_md)
        diary_complete = self.wiki.is_diary_complete(diary_md)
        self._merge_memory_turn(
            runtime,
            parsed,
            diary_changed=diary_md.strip() != current_draft.strip(),
            teacher_message=teacher_message,
            diary_complete=diary_complete,
        )
        executive_runtime = executive or ExecutiveRuntime()
        apply_executive_patch(executive_runtime, parsed.executive_patch)
        ready = (
            diary_complete
            and runtime.session_state.phase == "review_draft"
            and not executive_runtime.open_blocking_findings()
        )
        return reply, diary_md, checklist, ready

    def _prepare_plan_turn(
        self,
        class_id: str,
        messages: list[ChatMessage],
        partial_plan: str = "",
        attachments: list[ChatAttachment] | None = None,
        planning: PlanRuntime | None = None,
        executive: ExecutiveRuntime | None = None,
    ) -> _PreparedAgentTurn:
        runtime = planning or PlanRuntime()
        current_draft = partial_plan.strip() or self.wiki.empty_plan_template()
        latest_teacher_message = messages[-1].content if messages else ""
        agent = build_plan_chat_agent(
            self._wiki_ctx(
                class_id,
                planning=runtime,
                teacher_message=latest_teacher_message,
                executive=executive,
            ),
            current_draft,
            self.chat_model,
            planning=runtime,
            reasoning_effort=self.chat_effort,
        )
        user_input = self._build_plan_user_input(messages, attachments)
        return _PreparedAgentTurn(runtime, current_draft, agent, user_input)

    def _finalize_plan_turn(
        self,
        parsed: Any,
        current_draft: str,
        runtime: PlanRuntime,
        *,
        teacher_message: str = "",
        executive: ExecutiveRuntime | None = None,
    ) -> tuple[str, str, bool] | None:
        if not isinstance(parsed, PlanTurnOutput):
            return None
        reply = parsed.reply
        artifact = parsed.lesson_artifact
        if artifact is not None:
            allowed_source_ids = {
                source.source_id for source in self.wiki.load_trusted_sources().values()
            }
            errors = validate_lesson_artifact(
                artifact, allowed_source_ids=allowed_source_ids
            )
            if not errors:
                runtime.lesson_artifact = artifact
                plan_md = render_markdown_artifact(artifact)
            else:
                plan_md = _strip_plan_debug_sections(
                    parsed.plan_markdown.strip() or current_draft
                )
        else:
            plan_md = _strip_plan_debug_sections(
                parsed.plan_markdown.strip() or current_draft
            )
        ready = self.wiki.is_plan_ready(plan_md)
        self._merge_plan_turn(
            runtime,
            parsed,
            plan_changed=plan_md.strip() != current_draft.strip(),
            teacher_message=teacher_message,
            plan_ready=ready,
        )
        executive_runtime = executive or ExecutiveRuntime()
        apply_executive_patch(executive_runtime, parsed.executive_patch)
        ready = ready and not executive_runtime.open_blocking_findings()
        return reply, plan_md, ready

    async def _run_structured(
        self, agent, user_input: str, *, timeout: float | None = None
    ):
        """Run an agent to completion, async + bounded by a wall-clock timeout.

        Never use Runner.run_sync here: the FastAPI request handlers are async,
        and a blocking run would stall the event loop for the whole turn.
        """
        self._require_client()
        try:
            result = await asyncio.wait_for(
                Runner.run(agent, user_input, max_turns=self.max_turns),
                timeout=timeout or self.timeout,
            )
        except AgentsException as exc:
            if _is_turn_limit_error(exc):
                _log_turn_limit(getattr(agent, "name", "agent"), exc)
                raise AgentTurnLimitError(_TURN_LIMIT_REPLY) from exc
            raise
        except Exception as exc:
            if _is_turn_limit_error(exc):
                _log_turn_limit(getattr(agent, "name", "agent"), exc)
                raise AgentTurnLimitError(_TURN_LIMIT_REPLY) from exc
            raise
        return result.final_output

    async def _yield_stream_events(
        self,
        agent: Any,
        user_input: str,
        result_holder: dict[str, Any],
        *,
        timeout: float | None = None,
    ) -> AsyncIterator[SseEvent]:
        """Drain one streamed run and store its result in a caller-owned holder."""
        self._require_client()
        result_holder["result"] = None
        result = Runner.run_streamed(agent, user_input, max_turns=self.max_turns)
        started = time.monotonic()
        wall_clock_limit = timeout or self.timeout
        try:
            async for event in result.stream_events():
                if time.monotonic() - started > wall_clock_limit:
                    yield SseError(message="The request timed out.", code="timeout")
                    return
                for translated in translate_sdk_event(
                    event,
                    tool_output_limit=self.tool_output_limit,
                    tool_args_limit=self.tool_args_limit,
                ):
                    yield translated
        except AgentsException as exc:
            if _is_turn_limit_error(exc):
                _log_turn_limit(getattr(agent, "name", "agent"), exc)
                yield SseError(message=_TURN_LIMIT_REPLY, code="turn_limit")
                return
            yield SseError(message=str(exc), code="agent_error")
            return
        except Exception as exc:
            if _is_turn_limit_error(exc):
                _log_turn_limit(getattr(agent, "name", "agent"), exc)
                yield SseError(message=_TURN_LIMIT_REPLY, code="turn_limit")
                return
            yield SseError(message=str(exc), code="error")
            return

        result_holder["result"] = result

    async def ingest_chat_stream(
        self,
        class_id: str,
        messages: list[ChatMessage],
        partial_diary: str = "",
        attachments: list[ChatAttachment] | None = None,
        memory: MemoryRuntime | None = None,
        executive: ExecutiveRuntime | None = None,
    ) -> AsyncIterator[SseEvent]:
        turn = self._prepare_ingest_turn(
            class_id, messages, partial_diary, attachments, memory, executive
        )
        result_holder: dict[str, Any] = {}
        async for event in self._yield_stream_events(
            turn.agent, turn.user_input, result_holder
        ):
            if isinstance(event, SseError):
                yield event
                return
            yield event

        out = result_holder.get("result")
        if out is None:
            return
        finalized = self._finalize_ingest_turn(
            out.final_output,
            turn.current_draft,
            turn.runtime,
            class_id=class_id,
            teacher_message=messages[-1].content if messages else "",
            executive=executive,
        )
        if finalized is None:
            yield SseError(
                message="I had trouble processing that — could you try again?",
                code="parse_error",
            )
            return
        reply, diary_md, checklist, ready = finalized
        yield self._memory_final_event(
            reply,
            diary_md,
            ready,
            checklist,
            turn.runtime,
            executive or ExecutiveRuntime(),
        )

    async def plan_chat_stream(
        self,
        class_id: str,
        messages: list[ChatMessage],
        partial_plan: str = "",
        attachments: list[ChatAttachment] | None = None,
        planning: PlanRuntime | None = None,
        executive: ExecutiveRuntime | None = None,
    ) -> AsyncIterator[SseEvent]:
        turn = self._prepare_plan_turn(
            class_id, messages, partial_plan, attachments, planning, executive
        )
        result_holder: dict[str, Any] = {}
        async for event in self._yield_stream_events(
            turn.agent, turn.user_input, result_holder, timeout=self.plan_timeout
        ):
            if isinstance(event, SseError):
                yield event
                return
            yield event

        out = result_holder.get("result")
        if out is None:
            return
        finalized = self._finalize_plan_turn(
            out.final_output,
            turn.current_draft,
            turn.runtime,
            teacher_message=messages[-1].content if messages else "",
            executive=executive,
        )
        if finalized is None:
            yield SseError(
                message="I had trouble processing that — could you try again?",
                code="parse_error",
            )
            return
        reply, plan_md, ready = finalized
        yield self._plan_final_event(
            reply,
            plan_md,
            ready,
            turn.runtime,
            executive or ExecutiveRuntime(),
        )

    def _plan_opening_fallback(self, class_id: str) -> str:
        snap = self.wiki.get_snapshot(class_id)
        lines = [
            f"I've loaded class memory for **{snap.label}**.",
            f"Current unit: {snap.current_unit}.",
        ]
        if snap.last_committed_date:
            lines.append(f"Last logged lesson: {snap.last_committed_date}.")
        if snap.open_loop_count:
            lines.append(f"Open loops tracked: {snap.open_loop_count}.")
        if snap.top_misconceptions:
            lines.append(f"Misconception to watch: {snap.top_misconceptions[0]}")
        lines.append(
            "What do you want to cover in the next lesson? "
            "Use the + button to attach a worksheet or draft plan (.md or .txt)."
        )
        return "\n\n".join(lines)

    async def plan_opening(self, class_id: str) -> str:
        if self.client is None:
            return self._plan_opening_fallback(class_id)
        try:
            context = self.wiki.build_plan_context_slim(class_id)
            agent = build_plan_opening_agent(
                context, self.utility_model, reasoning_effort=self.utility_effort
            )
            out = await self._run_structured(
                agent, "Open the planning session for this class."
            )
            text = out if isinstance(out, str) else str(out)
            return text.strip() or self._plan_opening_fallback(class_id)
        except Exception:
            return self._plan_opening_fallback(class_id)

    async def plan_chat(
        self,
        class_id: str,
        messages: list[ChatMessage],
        partial_plan: str = "",
        attachments: list[ChatAttachment] | None = None,
        planning: PlanRuntime | None = None,
        executive: ExecutiveRuntime | None = None,
    ) -> tuple[str, str, bool]:
        turn = self._prepare_plan_turn(
            class_id, messages, partial_plan, attachments, planning, executive
        )
        current_draft = turn.current_draft
        runtime = turn.runtime
        try:
            parsed = await self._run_structured(
                turn.agent, turn.user_input, timeout=self.plan_timeout
            )
        except AgentTurnLimitError as exc:
            return str(exc), turn.current_draft, False
        if not isinstance(parsed, PlanTurnOutput):
            return (
                "I had trouble processing that — could you try again?",
                current_draft,
                False,
            )
        finalized = self._finalize_plan_turn(
            parsed,
            current_draft,
            runtime,
            teacher_message=messages[-1].content if messages else "",
            executive=executive,
        )
        if finalized is None:
            return (
                "I had trouble processing that — could you try again?",
                current_draft,
                False,
            )
        return finalized

    def _is_high_stakes_student_request(self, messages: list[ChatMessage]) -> bool:
        latest = messages[-1].content.lower() if messages else ""
        return any(
            term in latest
            for term in (
                "grade",
                "diagnose",
                "placement",
                "lower track",
                "admission",
                "discipline",
                "disciplinary",
            )
        )

    def _class_brief_fallback(self, class_id: str) -> ClassBriefOutput:
        snap = self.wiki.get_snapshot(class_id)
        unit = snap.current_unit or "the current unit"
        reasons: list[str] = []
        watch: list[str] = []
        sources = [
            f"wiki/classes/{class_id}/course_state.md",
            f"wiki/classes/{class_id}/memory/planning_brief.md",
        ]
        if snap.open_loop_count:
            reasons.append(f"{snap.open_loop_count} open loops are still tracked.")
        if snap.top_misconceptions:
            watch.append(snap.top_misconceptions[0])
            reasons.append("Recent misconceptions still need attention.")
        if snap.last_committed_date:
            reasons.append(f"Last logged lesson: {snap.last_committed_date}.")
        if not reasons:
            reasons.append("Class memory is available for the next planning step.")
        return ClassBriefOutput(
            summary=(
                f"{snap.label} is in {unit}. "
                "Use Create lesson plan when you want the next teaching move, "
                "or Update memory after the next lesson."
            ),
            recommended_action_label="Create lesson plan",
            recommended_action_href=f"/classes/{class_id}/plan",
            recommended_action_rationale="A grounded next-lesson draft is the usual next action from class home.",
            reasons=reasons[:3],
            watch_items=watch[:3],
            source_paths=sources,
        )

    async def class_brief(self, class_id: str) -> ClassBriefOutput:
        if self.client is None:
            return self._class_brief_fallback(class_id)
        try:
            agent = build_class_brief_agent(
                self.wiki, class_id, self.utility_model
            )
            out = await self._run_structured(
                agent, "Prepare the current class-home executive briefing."
            )
            if isinstance(out, ClassBriefOutput):
                return out
        except Exception:
            logger.exception("Class brief generation failed; using fallback.")
        return self._class_brief_fallback(class_id)

    def _class_discussion_fallback(
        self, class_id: str, messages: list[ChatMessage]
    ) -> ClassDiscussionTurnOutput:
        if self._is_high_stakes_student_request(messages):
            return ClassDiscussionTurnOutput(
                reply=(
                    "I cannot make high-stakes student decisions. I can help review "
                    "evidence and draft neutral observations for teacher review."
                ),
                suggested_actions=["Update memory"],
            )
        snap = self.wiki.get_snapshot(class_id)
        lines = [
            f"From class memory for **{snap.label}**:",
            f"- Current unit: {snap.current_unit or 'unknown'}",
        ]
        if snap.open_loop_count:
            lines.append(f"- Open loops tracked: {snap.open_loop_count}")
        if snap.top_misconceptions:
            lines.append(f"- Misconception to watch: {snap.top_misconceptions[0]}")
        if snap.last_committed_date:
            lines.append(f"- Last logged lesson: {snap.last_committed_date}")
        lines.append(
            "Ask about open loops, misconceptions, recent lessons, or what to do next."
        )
        return ClassDiscussionTurnOutput(
            reply="\n".join(lines),
            source_paths=[
                f"wiki/classes/{class_id}/course_state.md",
                f"wiki/classes/{class_id}/memory/planning_brief.md",
            ],
            suggested_actions=["Create lesson plan", "Update memory"],
            state_patch=ClassDiscussionStatePatch(
                current_focus="class overview",
                key_observations=[f"Current unit: {snap.current_unit or 'unknown'}"],
                next_best_actions=["Create lesson plan", "Update memory"],
            ),
        )

    def _prepare_discuss_turn(
        self,
        class_id: str,
        messages: list[ChatMessage],
        attachments: list[ChatAttachment] | None = None,
        runtime: ClassDiscussionRuntime | None = None,
        executive: ExecutiveRuntime | None = None,
    ) -> _PreparedAgentTurn:
        rt = runtime or ClassDiscussionRuntime()
        latest_teacher_message = messages[-1].content if messages else ""
        agent = build_class_discussion_agent(
            self._wiki_ctx(
                class_id,
                planning=rt,
                teacher_message=latest_teacher_message,
                executive=executive,
            ),
            self.chat_model,
            runtime=rt,
            reasoning_effort=self.chat_effort,
        )
        user_input = build_class_discussion_user_input_assembly(
            messages, history_turns=self.plan_history_turns
        )["text"]
        if attachments:
            user_input = (
                f"{user_input}\n\nUploaded materials this turn:\n"
                f"{self._format_attachments(attachments)}"
            )
        return _PreparedAgentTurn(rt, "", agent, user_input)

    def _finalize_discuss_turn(
        self,
        class_id: str,
        parsed: Any,
        runtime: ClassDiscussionRuntime,
        *,
        executive: ExecutiveRuntime | None = None,
    ) -> str | None:
        if not isinstance(parsed, ClassDiscussionTurnOutput):
            return None
        merge_class_discussion_turn(
            runtime,
            state_patch=parsed.state_patch,
            new_evidence_briefs=parsed.new_evidence_briefs,
            memory_candidates=parsed.memory_candidates,
            source_paths=parsed.source_paths,
            suggested_actions=parsed.suggested_actions,
        )
        executive_runtime = executive or ExecutiveRuntime()
        apply_executive_patch(executive_runtime, parsed.executive_patch)
        footer = render_reviewed_source_footer(
            self.wiki, class_id, runtime.consulted_sources
        )
        return f"{parsed.reply.rstrip()}{footer}"

    @staticmethod
    def _discussion_citation_correction_input(
        original_user_input: str, draft: str, errors: list[str]
    ) -> str:
        """Tell the model exactly how to repair a rejected source presentation."""
        rendered_errors = "\n".join(f"- {error}" for error in errors)
        return (
            f"{original_user_input}\n\n"
            "Citation presentation correction:\n"
            "Return a complete corrected answer to the teacher. English content from "
            "the wiki is a KlassenPilot reviewed English summary, not a verbatim "
            "official German quotation. Do not include `Source:`/`Quelle:` lines or "
            "source URLs; the backend will add the official German source link.\n\n"
            f"Rejected draft:\n{draft}\n\nValidation errors:\n{rendered_errors}"
        )

    async def _correct_discussion_source_presentation(
        self,
        agent: Any,
        original_user_input: str,
        parsed: Any,
        runtime: ClassDiscussionRuntime,
    ) -> Any:
        """Run at most one correction turn, then fall back to backend provenance."""
        if not isinstance(parsed, ClassDiscussionTurnOutput):
            return parsed
        errors = validate_discussion_source_presentation(
            parsed.reply, runtime.consulted_sources
        )
        if not errors:
            return parsed
        try:
            corrected = await self._run_structured(
                agent,
                self._discussion_citation_correction_input(
                    original_user_input, parsed.reply, errors
                ),
            )
        except Exception:
            logger.warning("Discussion citation correction failed; using backend footer.")
            corrected = parsed
        if isinstance(corrected, ClassDiscussionTurnOutput):
            parsed = corrected
        if validate_discussion_source_presentation(
            parsed.reply, runtime.consulted_sources
        ):
            return parsed.model_copy(
                update={"reply": strip_model_source_presentation(parsed.reply)}
            )
        return parsed

    def _discuss_final_event(
        self,
        reply: str,
        runtime: ClassDiscussionRuntime,
        executive: ExecutiveRuntime,
    ) -> SseFinal:
        return SseFinal(
            reply=reply,
            artifact_markdown="",
            ready=False,
            completeness=None,
            memory_candidates=discussion_api_payload(runtime).get(
                "memory_candidates", []
            ),
            discussion_state=discussion_api_payload(runtime),
            executive_state=executive_api_payload(executive),
        )

    async def discuss_chat(
        self,
        class_id: str,
        messages: list[ChatMessage],
        attachments: list[ChatAttachment] | None = None,
        runtime: ClassDiscussionRuntime | None = None,
        executive: ExecutiveRuntime | None = None,
    ) -> str:
        runtime = runtime or ClassDiscussionRuntime()
        if self._is_high_stakes_student_request(messages) or self.client is None:
            out = self._class_discussion_fallback(class_id, messages)
            merge_class_discussion_turn(
                runtime,
                state_patch=out.state_patch,
                new_evidence_briefs=out.new_evidence_briefs,
                memory_candidates=out.memory_candidates,
                source_paths=out.source_paths,
                suggested_actions=out.suggested_actions,
            )
            return out.reply
        turn = self._prepare_discuss_turn(
            class_id, messages, attachments, runtime, executive
        )
        try:
            parsed = await self._run_structured(turn.agent, turn.user_input)
        except AgentTurnLimitError as exc:
            return str(exc)
        except Exception:
            logger.exception("Class discussion turn failed; using fallback.")
            out = self._class_discussion_fallback(class_id, messages)
            merge_class_discussion_turn(
                runtime,
                state_patch=out.state_patch,
                new_evidence_briefs=out.new_evidence_briefs,
                memory_candidates=out.memory_candidates,
                source_paths=out.source_paths,
                suggested_actions=out.suggested_actions,
            )
            return out.reply
        parsed = await self._correct_discussion_source_presentation(
            turn.agent, turn.user_input, parsed, turn.runtime
        )
        finalized = self._finalize_discuss_turn(
            class_id, parsed, turn.runtime, executive=executive
        )
        if finalized is None:
            return "I had trouble processing that — could you try again?"
        return finalized

    async def discuss_chat_stream(
        self,
        class_id: str,
        messages: list[ChatMessage],
        attachments: list[ChatAttachment] | None = None,
        runtime: ClassDiscussionRuntime | None = None,
        executive: ExecutiveRuntime | None = None,
    ) -> AsyncIterator[SseEvent]:
        runtime = runtime or ClassDiscussionRuntime()
        if self._is_high_stakes_student_request(messages) or self.client is None:
            out = self._class_discussion_fallback(class_id, messages)
            merge_class_discussion_turn(
                runtime,
                state_patch=out.state_patch,
                new_evidence_briefs=out.new_evidence_briefs,
                memory_candidates=out.memory_candidates,
                source_paths=out.source_paths,
                suggested_actions=out.suggested_actions,
            )
            yield self._discuss_final_event(
                out.reply, runtime, executive or ExecutiveRuntime()
            )
            return
        turn = self._prepare_discuss_turn(
            class_id, messages, attachments, runtime, executive
        )
        result_holder: dict[str, Any] = {}
        async for event in self._yield_stream_events(
            turn.agent, turn.user_input, result_holder
        ):
            if isinstance(event, SseError):
                yield event
                return
            yield event
        out = result_holder.get("result")
        if out is None:
            return
        parsed = await self._correct_discussion_source_presentation(
            turn.agent, turn.user_input, out.final_output, turn.runtime
        )
        finalized = self._finalize_discuss_turn(
            class_id, parsed, turn.runtime, executive=executive
        )
        if finalized is None:
            yield SseError(
                message="I had trouble processing that — could you try again?",
                code="parse_error",
            )
            return
        yield self._discuss_final_event(
            finalized, turn.runtime, executive or ExecutiveRuntime()
        )

    async def ingest_chat(
        self,
        class_id: str,
        messages: list[ChatMessage],
        partial_diary: str = "",
        attachments: list[ChatAttachment] | None = None,
        memory: MemoryRuntime | None = None,
        executive: ExecutiveRuntime | None = None,
    ) -> tuple[str, str, CompletenessChecklist, bool]:
        turn = self._prepare_ingest_turn(
            class_id, messages, partial_diary, attachments, memory, executive
        )
        current_draft = turn.current_draft
        runtime = turn.runtime
        try:
            parsed = await self._run_structured(turn.agent, turn.user_input)
        except AgentTurnLimitError as exc:
            return (
                str(exc),
                current_draft,
                self.wiki.checklist_from_diary(current_draft),
                False,
            )
        if not isinstance(parsed, IngestTurnOutput):
            return (
                "I had trouble processing that — could you try again?",
                current_draft,
                self.wiki.checklist_from_diary(current_draft),
                False,
            )
        finalized = self._finalize_ingest_turn(
            parsed,
            current_draft,
            runtime,
            class_id=class_id,
            teacher_message=messages[-1].content if messages else "",
            executive=executive,
        )
        if finalized is None:
            return (
                "I had trouble processing that — could you try again?",
                current_draft,
                self.wiki.checklist_from_diary(current_draft),
                False,
            )
        return finalized

    async def compile_diary(self, class_id: str, messages: list[ChatMessage]) -> str:
        context = self.wiki.load_index_context(class_id)
        transcript = "\n".join(f"{m.role}: {m.content}" for m in messages)
        lim = get_context_limits()
        prompt = (
            f"Class context:\n{apply_char_limit(context, lim.compile_context_chars)}\n\n"
            f"Conversation transcript:\n{transcript}\n\n"
            "Compile the lesson results markdown now."
        )
        agent = build_compile_agent(
            self.utility_model, reasoning_effort=self.utility_effort
        )
        parsed = await self._run_structured(agent, prompt)
        if not isinstance(parsed, CompileOutput):
            return self.wiki.empty_diary_template()
        return parsed.diary_markdown

    async def plan_lesson(
        self,
        class_id: str,
        duration_minutes: int = 45,
        anchor_date: Optional[str] = None,
    ) -> LessonPlan:
        context = self.wiki.load_index_context(class_id)
        lim = get_context_limits()
        user = (
            f"Create a {duration_minutes}-minute lesson plan for class {class_id}.\n"
            f"Anchor date: {anchor_date or 'next lesson after last logged entry'}.\n\n"
            f"Start from index.md via tools, then open relevant pages.\n"
            f"Context excerpt:\n{apply_char_limit(context, lim.plan_lesson_context_chars)}"
        )
        agent = build_plan_lesson_agent(
            self._wiki_ctx(class_id),
            self.utility_model,
            reasoning_effort=self.utility_effort,
        )
        parsed = await self._run_structured(agent, user)
        if not isinstance(parsed, PlanOutput):
            raise RuntimeError("Failed to generate lesson plan")
        return LessonPlan(**parsed.model_dump())

    async def verify_artifact_for_write(
        self,
        class_id: str,
        artifact_kind: str,
        markdown: str,
        executive: ExecutiveRuntime,
    ) -> WriteVerificationResult:
        """Run the isolated read-only verifier for one exact durable draft."""
        context = self.wiki.build_active_class_core_context_trace(class_id)["text"]
        agent = build_write_verification_agent(
            self._wiki_ctx(class_id, executive=executive),
            artifact_kind,
            context,
            self.chat_model,
            reasoning_effort=self.chat_effort,
        )
        prompt = (
            f"Artifact kind: {artifact_kind}\n\n"
            "Exact submitted artifact (inspect this text, do not rewrite it):\n"
            f"{markdown}\n"
        )
        parsed = await self._run_structured(agent, prompt)
        if not isinstance(parsed, WriteVerificationOutput):
            raise RuntimeError("Failed to verify artifact for write")
        return WriteVerificationResult(
            artifact_fingerprint=artifact_fingerprint(markdown),
            patch=parsed.executive_patch,
            message=parsed.message.strip() or "Verification complete.",
        )

    async def lint_wiki(self, class_id: str) -> str:
        context = self.wiki.read_wiki_index(class_id)
        agent = build_lint_agent(
            self._wiki_ctx(class_id),
            context,
            self.utility_model,
            reasoning_effort=self.utility_effort,
        )
        out = await self._run_structured(
            agent,
            f"Lint the wiki for class {class_id}. Read index.md and scan lessons, students, roll-ups.",
        )
        return out if isinstance(out, str) else str(out)

    async def compact_memory(
        self,
        class_id: str,
        start_date=None,
        end_date=None,
    ) -> tuple[MemoryCompactOutput, list[str], list[str]]:
        source = self.wiki.build_memory_compaction_source_packet(
            class_id, start_date=start_date, end_date=end_date
        )
        agent = build_memory_compact_agent(
            self.utility_model, reasoning_effort=self.utility_effort
        )
        prompt = (
            "Compact the approved class wiki memory into durable class memory pages.\n\n"
            f"{apply_char_limit(source['packet'], get_context_limits().memory_compact_source_chars)}"
        )
        parsed = await self._run_structured(agent, prompt)
        if not isinstance(parsed, MemoryCompactOutput):
            raise RuntimeError("Failed to compact class memory")
        warnings = list(source.get("warnings", [])) + list(parsed.warnings)
        return parsed, source.get("source_paths", []), warnings

    async def propose_profile_updates(
        self,
        class_id: str,
        final_lesson_markdown: str = "",
        session_state: dict | None = None,
        lesson_planning_state: dict | None = None,
        memory_candidates: list[dict] | None = None,
    ) -> ProfileProposalOutput:
        existing_user = self.wiki.read_user_profile()
        existing_copilot = self.wiki.read_copilot_profile(class_id)
        import json

        field_cap = get_context_limits().profile_propose_field_chars
        prompt = (
            f"Class: {class_id}\n\n"
            f"Existing user.md (global teacher profile):\n"
            f"{apply_char_limit(existing_user, field_cap) or '(empty)'}\n\n"
            f"Existing copilot.md (class working agreement):\n"
            f"{apply_char_limit(existing_copilot, field_cap) or '(empty)'}\n\n"
            f"Final lesson plan:\n"
            f"{apply_char_limit(final_lesson_markdown, field_cap) or '(none)'}\n\n"
            f"Session state:\n"
            f"{apply_char_limit(json.dumps(session_state or {}, indent=2), field_cap)}\n\n"
            f"Lesson planning state:\n"
            f"{apply_char_limit(json.dumps(lesson_planning_state or {}, indent=2), field_cap)}\n\n"
            f"Memory candidates from the session:\n"
            f"{apply_char_limit(json.dumps(memory_candidates or [], indent=2), field_cap)}\n\n"
            "Propose teacher_profile.md and copilot_profile.md updates now."
        )
        agent = build_profile_proposal_agent(
            self.utility_model, reasoning_effort=self.utility_effort
        )
        parsed = await self._run_structured(agent, prompt)
        if not isinstance(parsed, ProfileProposalOutput):
            raise RuntimeError("Failed to propose profile updates")
        return parsed


    async def consolidate_memory_sweep(
        self,
        class_id: str,
        subject: str,
        claims: list[dict],
        memory_indexes: dict[str, dict[str, str]],
        *,
        applied_history: dict[str, list[str]] | None = None,
        rejected_history: dict[str, list[str]] | None = None,
        budget_usage: dict[str, str] | None = None,
        today: str = "",
        validation_error: str = "",
    ) -> "MemoryConsolidationOutput":
        """Mem V4 second-judge sweep: claims + memory -> review operations."""
        import json

        from app.teacher_agent.agent import build_memory_sweep_consolidation_agent
        from app.teacher_agent.models import MemoryConsolidationOutput

        field_cap = get_context_limits().profile_propose_field_chars
        retry_block = (
            "\nPrevious validation error (fix the structural issue; reference "
            f"input ids only):\n{validation_error}\n\n"
            if validation_error
            else ""
        )
        prompt = (
            f"Class: {class_id}\n"
            f"Subject: {subject}\n"
            f"Today: {today}\n\n"
            f"{retry_block}"
            "Claims (reinforced and held durable-memory candidates, with priority metadata):\n"
            f"{apply_char_limit(json.dumps(claims, indent=2), field_cap * 4)}\n\n"
            "Current memory, bullets enumerated with ids:\n"
            f"{apply_char_limit(json.dumps(memory_indexes, indent=2), field_cap * 4)}\n\n"
            "Recently applied memory texts per target:\n"
            f"{apply_char_limit(json.dumps(applied_history or {}, indent=2), field_cap * 2)}\n\n"
            "Recently rejected memory texts per target:\n"
            f"{apply_char_limit(json.dumps(rejected_history or {}, indent=2), field_cap * 2)}\n\n"
            "Memory budget usage per target:\n"
            f"{apply_char_limit(json.dumps(budget_usage or {}, indent=2), field_cap)}\n\n"
            "Return one operation set accounting for every claim_id exactly once."
        )
        agent = build_memory_sweep_consolidation_agent(
            self.sweep_model, reasoning_effort=self.sweep_effort
        )
        parsed = await self._run_structured(agent, prompt)
        if not isinstance(parsed, MemoryConsolidationOutput):
            raise RuntimeError("Failed to consolidate Memory Sweep claims")
        return parsed

