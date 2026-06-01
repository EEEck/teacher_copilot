"""Agent runners using OpenAI Agents SDK."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from typing import Any, Optional

from agents import Runner
from agents.exceptions import AgentsException, MaxTurnsExceeded
from openai import OpenAI

logger = logging.getLogger("klassenpilot.agents")

from app.config import Settings
from app.schemas.api import ChatAttachment, ChatMessage, CompletenessChecklist, LessonPlan
from app.teacher_agent.agent import (
    build_memory_compact_agent,
    build_compile_agent,
    build_ingest_agent,
    build_lint_agent,
    build_plan_chat_agent,
    build_plan_lesson_agent,
    build_plan_opening_agent,
)
from app.teacher_agent.models import (
    CompileOutput,
    IngestTurnOutput,
    MemoryCompactOutput,
    PlanOutput,
    PlanTurnOutput,
)
from app.teacher_agent.tools import WikiToolContext
from app.teacher_agent.stream_events import SseError, SseEvent, SseFinal, translate_sdk_event
from app.teacher_agent.wiki_store import DIARY_SECTION_HEADINGS, WikiStore

class AgentTurnLimitError(RuntimeError):
    """Agent used too many tool/reasoning steps in one turn."""

_TURN_LIMIT_REPLY = (
    "I needed more steps than allowed to finish this turn. "
    "Your draft is unchanged — try a shorter message or one topic at a time."
)


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
        self.model = settings.openai_model
        self.chat_model = settings.openai_chat_model
        self.fast_model = settings.openai_fast_model
        self.reasoning_effort = settings.openai_reasoning_effort
        self.timeout = settings.agent_timeout_seconds
        self.max_turns = settings.agent_max_turns
        self.wiki = wiki
        self.tool_output_limit: int | None = 500
        self.tool_args_limit: int | None = 500

    def _require_client(self) -> OpenAI:
        if self.client is None:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        return self.client

    def _wiki_ctx(self, class_id: str) -> WikiToolContext:
        return WikiToolContext(wiki=self.wiki, class_id=class_id)

    def _format_attachments(self, attachments: list[ChatAttachment]) -> str:
        if not attachments:
            return ""
        blocks = []
        for att in attachments:
            blocks.append(f"### Upload: {att.filename}\n{att.content[:8000]}")
        return "\n\n".join(blocks)

    def _build_user_input(
        self,
        messages: list[ChatMessage],
        draft_label: str,
        draft_content: str,
        attachments: list[ChatAttachment] | None = None,
    ) -> str:
        parts = [f"{draft_label}:\n{draft_content[:6000]}\n"]
        if attachments:
            parts.append(
                f"Uploaded materials this turn:\n{self._format_attachments(attachments)}\n"
            )
        for m in messages:
            parts.append(f"{m.role}: {m.content}")
        return "\n".join(parts)

    async def _run_structured(self, agent, user_input: str):
        """Run an agent to completion, async + bounded by a wall-clock timeout.

        Never use Runner.run_sync here: the FastAPI request handlers are async,
        and a blocking run would stall the event loop for the whole turn.
        """
        self._require_client()
        try:
            result = await asyncio.wait_for(
                Runner.run(agent, user_input, max_turns=self.max_turns),
                timeout=self.timeout,
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
        self, agent: Any, user_input: str, result_holder: dict[str, Any]
    ) -> AsyncIterator[SseEvent]:
        """Drain one streamed run and store its result in a caller-owned holder."""
        self._require_client()
        result_holder["result"] = None
        result = Runner.run_streamed(agent, user_input, max_turns=self.max_turns)
        started = time.monotonic()
        try:
            async for event in result.stream_events():
                if time.monotonic() - started > self.timeout:
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
    ) -> AsyncIterator[SseEvent]:
        context = self.wiki.build_context_package(class_id, "ingest")
        sections = "\n".join(f"- {s}" for s in DIARY_SECTION_HEADINGS)
        agent = build_ingest_agent(
            self._wiki_ctx(class_id),
            sections,
            context,
            self.chat_model,
            reasoning_effort=self.reasoning_effort,
        )
        current_draft = partial_diary.strip() or self.wiki.empty_diary_template()
        user_input = self._build_user_input(
            messages, "Current diary draft (update each turn)", current_draft, attachments
        )
        result_holder: dict[str, Any] = {}
        async for event in self._yield_stream_events(agent, user_input, result_holder):
            if isinstance(event, SseError):
                yield event
                return
            yield event

        out = result_holder.get("result")
        if out is None:
            return
        parsed = out.final_output
        if not isinstance(parsed, IngestTurnOutput):
            yield SseError(
                message="I had trouble processing that — could you try again?",
                code="parse_error",
            )
            return
        reply = parsed.reply
        diary_md = parsed.diary_markdown.strip() or current_draft
        checklist = self.wiki.checklist_from_diary(diary_md)
        ready = self.wiki.is_diary_complete(diary_md) or "ready to save" in reply.lower()
        yield SseFinal(
            reply=reply,
            artifact_markdown=diary_md,
            ready=ready,
            completeness=checklist,
        )

    async def plan_chat_stream(
        self,
        class_id: str,
        messages: list[ChatMessage],
        partial_plan: str = "",
        attachments: list[ChatAttachment] | None = None,
    ) -> AsyncIterator[SseEvent]:
        context = self.wiki.build_context_package(class_id, "plan")
        agent = build_plan_chat_agent(
            self._wiki_ctx(class_id),
            context,
            self.chat_model,
            reasoning_effort=self.reasoning_effort,
        )
        current_draft = partial_plan.strip() or self.wiki.empty_plan_template()
        user_input = self._build_user_input(
            messages, "Current plan draft (update each turn)", current_draft, attachments
        )
        result_holder: dict[str, Any] = {}
        async for event in self._yield_stream_events(agent, user_input, result_holder):
            if isinstance(event, SseError):
                yield event
                return
            yield event

        out = result_holder.get("result")
        if out is None:
            return
        parsed = out.final_output
        if not isinstance(parsed, PlanTurnOutput):
            yield SseError(
                message="I had trouble processing that — could you try again?",
                code="parse_error",
            )
            return
        reply = parsed.reply
        plan_md = parsed.plan_markdown.strip() or current_draft
        ready = self.wiki.is_plan_ready(plan_md) or "ready to save" in reply.lower()
        yield SseFinal(
            reply=reply,
            artifact_markdown=plan_md,
            ready=ready,
            completeness=None,
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
            context = self.wiki.build_context_package(class_id, "plan")
            agent = build_plan_opening_agent(context[:14000], self.model)
            out = await self._run_structured(agent, "Open the planning session for this class.")
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
    ) -> tuple[str, str, bool]:
        context = self.wiki.build_context_package(class_id, "plan")
        agent = build_plan_chat_agent(
            self._wiki_ctx(class_id),
            context,
            self.chat_model,
            reasoning_effort=self.reasoning_effort,
        )
        current_draft = partial_plan.strip() or self.wiki.empty_plan_template()
        user_input = self._build_user_input(
            messages, "Current plan draft (update each turn)", current_draft, attachments
        )
        try:
            parsed = await self._run_structured(agent, user_input)
        except AgentTurnLimitError as exc:
            return str(exc), current_draft, False
        if not isinstance(parsed, PlanTurnOutput):
            return "I had trouble processing that — could you try again?", current_draft, False
        reply = parsed.reply
        plan_md = parsed.plan_markdown.strip() or current_draft
        ready = self.wiki.is_plan_ready(plan_md) or "ready to save" in reply.lower()
        return reply, plan_md, ready

    async def ingest_chat(
        self,
        class_id: str,
        messages: list[ChatMessage],
        partial_diary: str = "",
        attachments: list[ChatAttachment] | None = None,
    ) -> tuple[str, str, CompletenessChecklist, bool]:
        context = self.wiki.build_context_package(class_id, "ingest")
        sections = "\n".join(f"- {s}" for s in DIARY_SECTION_HEADINGS)
        agent = build_ingest_agent(
            self._wiki_ctx(class_id),
            sections,
            context,
            self.chat_model,
            reasoning_effort=self.reasoning_effort,
        )
        current_draft = partial_diary.strip() or self.wiki.empty_diary_template()
        user_input = self._build_user_input(
            messages, "Current diary draft (update each turn)", current_draft, attachments
        )
        try:
            parsed = await self._run_structured(agent, user_input)
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
        reply = parsed.reply
        diary_md = parsed.diary_markdown.strip() or current_draft
        checklist = self.wiki.checklist_from_diary(diary_md)
        ready = self.wiki.is_diary_complete(diary_md) or "ready to save" in reply.lower()
        return reply, diary_md, checklist, ready

    async def compile_diary(self, class_id: str, messages: list[ChatMessage]) -> str:
        context = self.wiki.load_index_context(class_id)
        transcript = "\n".join(f"{m.role}: {m.content}" for m in messages)
        prompt = (
            f"Class context:\n{context[:8000]}\n\n"
            f"Conversation transcript:\n{transcript}\n\n"
            "Compile the lesson results markdown now."
        )
        agent = build_compile_agent(self.fast_model)
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
        user = (
            f"Create a {duration_minutes}-minute lesson plan for class {class_id}.\n"
            f"Anchor date: {anchor_date or 'next lesson after last logged entry'}.\n\n"
            f"Start from index.md via tools, then open relevant pages.\n"
            f"Context excerpt:\n{context[:4000]}"
        )
        agent = build_plan_lesson_agent(self._wiki_ctx(class_id), self.fast_model)
        parsed = await self._run_structured(agent, user)
        if not isinstance(parsed, PlanOutput):
            raise RuntimeError("Failed to generate lesson plan")
        return LessonPlan(**parsed.model_dump())

    async def lint_wiki(self, class_id: str) -> str:
        context = self.wiki.read_wiki_index(class_id)
        agent = build_lint_agent(self._wiki_ctx(class_id), context, self.fast_model)
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
        agent = build_memory_compact_agent(self.fast_model)
        prompt = (
            "Compact the approved class wiki memory into durable class memory pages.\n\n"
            f"{source['packet'][:30000]}"
        )
        parsed = await self._run_structured(agent, prompt)
        if not isinstance(parsed, MemoryCompactOutput):
            raise RuntimeError("Failed to compact class memory")
        warnings = list(source.get("warnings", [])) + list(parsed.warnings)
        return parsed, source.get("source_paths", []), warnings
