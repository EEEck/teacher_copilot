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
from app.schemas.api import ChatAttachment, ChatMessage, CompletenessChecklist, LessonPlan
from app.teacher_agent.agent import (
    build_memory_sweep_alignment_agent,
    build_memory_compact_agent,
    build_compile_agent,
    build_ingest_agent,
    build_lint_agent,
    build_memory_sweep_card_agent,
    build_plan_chat_agent,
    build_plan_lesson_agent,
    build_plan_opening_agent,
    build_profile_proposal_agent,
)
from app.teacher_agent.models import (
    CompileOutput,
    IngestTurnOutput,
    MemoryCompactOutput,
    MemorySweepAlignmentOutput,
    MemorySweepProposalOutput,
    PlanOutput,
    PlanTurnOutput,
    ProfileProposalOutput,
)
from app.context_limits import apply_char_limit, get_context_limits
from app.teacher_agent.prompt_assembly import (
    build_ingest_user_input_assembly,
    build_plan_user_input_assembly,
    trim_to_last_user_turns,
)
from app.teacher_agent.memory_update_state import (
    MemoryRuntime,
    memory_api_payload,
    merge_memory_turn,
)
from app.teacher_agent.planning_state import (
    PlanRuntime,
    merge_turn_into_runtime,
    planning_api_payload,
)
from app.teacher_agent.tools import WikiToolContext
from app.teacher_agent.stream_events import SseError, SseEvent, SseFinal, translate_sdk_event
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


def _trim_to_last_user_turns(
    messages: list[ChatMessage], n: int
) -> list[ChatMessage]:
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
        self.model = settings.openai_model
        self.chat_model = settings.openai_chat_model
        self.fast_model = settings.openai_fast_model
        self.reasoning_effort = settings.openai_reasoning_effort
        self.timeout = settings.agent_timeout_seconds
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
        planning: PlanRuntime | None = None,
        memory: MemoryRuntime | None = None,
    ) -> WikiToolContext:
        return WikiToolContext(
            wiki=self.wiki, class_id=class_id, planning=planning, memory=memory
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
        self, reply: str, plan_md: str, ready: bool, runtime: PlanRuntime
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
            memory_candidates=payload["memory_candidates"],
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
        )

    def _prepare_ingest_turn(
        self,
        class_id: str,
        messages: list[ChatMessage],
        partial_diary: str = "",
        attachments: list[ChatAttachment] | None = None,
        memory: MemoryRuntime | None = None,
    ) -> _PreparedAgentTurn:
        runtime = memory or MemoryRuntime()
        agent = build_ingest_agent(
            self._wiki_ctx(class_id, memory=runtime),
            self.chat_model,
            memory=runtime,
            reasoning_effort=self.reasoning_effort,
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
        ready = diary_complete and runtime.session_state.phase == "review_draft"
        return reply, diary_md, checklist, ready

    def _prepare_plan_turn(
        self,
        class_id: str,
        messages: list[ChatMessage],
        partial_plan: str = "",
        attachments: list[ChatAttachment] | None = None,
        planning: PlanRuntime | None = None,
    ) -> _PreparedAgentTurn:
        runtime = planning or PlanRuntime()
        current_draft = partial_plan.strip() or self.wiki.empty_plan_template()
        agent = build_plan_chat_agent(
            self._wiki_ctx(class_id, runtime),
            current_draft,
            self.chat_model,
            planning=runtime,
            reasoning_effort=self.reasoning_effort,
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
    ) -> tuple[str, str, bool] | None:
        if not isinstance(parsed, PlanTurnOutput):
            return None
        reply = parsed.reply
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
        return reply, plan_md, ready

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
        memory: MemoryRuntime | None = None,
    ) -> AsyncIterator[SseEvent]:
        turn = self._prepare_ingest_turn(
            class_id, messages, partial_diary, attachments, memory
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
        )
        if finalized is None:
            yield SseError(
                message="I had trouble processing that — could you try again?",
                code="parse_error",
            )
            return
        reply, diary_md, checklist, ready = finalized
        yield self._memory_final_event(reply, diary_md, ready, checklist, turn.runtime)

    async def plan_chat_stream(
        self,
        class_id: str,
        messages: list[ChatMessage],
        partial_plan: str = "",
        attachments: list[ChatAttachment] | None = None,
        planning: PlanRuntime | None = None,
    ) -> AsyncIterator[SseEvent]:
        turn = self._prepare_plan_turn(
            class_id, messages, partial_plan, attachments, planning
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
        finalized = self._finalize_plan_turn(
            out.final_output,
            turn.current_draft,
            turn.runtime,
            teacher_message=messages[-1].content if messages else "",
        )
        if finalized is None:
            yield SseError(
                message="I had trouble processing that — could you try again?",
                code="parse_error",
            )
            return
        reply, plan_md, ready = finalized
        yield self._plan_final_event(reply, plan_md, ready, turn.runtime)

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
            agent = build_plan_opening_agent(context, self.model)
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
        planning: PlanRuntime | None = None,
    ) -> tuple[str, str, bool]:
        turn = self._prepare_plan_turn(
            class_id, messages, partial_plan, attachments, planning
        )
        current_draft = turn.current_draft
        runtime = turn.runtime
        try:
            parsed = await self._run_structured(turn.agent, turn.user_input)
        except AgentTurnLimitError as exc:
            return str(exc), turn.current_draft, False
        if not isinstance(parsed, PlanTurnOutput):
            return "I had trouble processing that — could you try again?", current_draft, False
        finalized = self._finalize_plan_turn(
            parsed,
            current_draft,
            runtime,
            teacher_message=messages[-1].content if messages else "",
        )
        if finalized is None:
            return "I had trouble processing that â€” could you try again?", current_draft, False
        return finalized

    async def ingest_chat(
        self,
        class_id: str,
        messages: list[ChatMessage],
        partial_diary: str = "",
        attachments: list[ChatAttachment] | None = None,
        memory: MemoryRuntime | None = None,
    ) -> tuple[str, str, CompletenessChecklist, bool]:
        turn = self._prepare_ingest_turn(
            class_id, messages, partial_diary, attachments, memory
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
        lim = get_context_limits()
        user = (
            f"Create a {duration_minutes}-minute lesson plan for class {class_id}.\n"
            f"Anchor date: {anchor_date or 'next lesson after last logged entry'}.\n\n"
            f"Start from index.md via tools, then open relevant pages.\n"
            f"Context excerpt:\n{apply_char_limit(context, lim.plan_lesson_context_chars)}"
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
            "Propose user.md and copilot.md updates now."
        )
        agent = build_profile_proposal_agent(self.fast_model)
        parsed = await self._run_structured(agent, prompt)
        if not isinstance(parsed, ProfileProposalOutput):
            raise RuntimeError("Failed to propose profile updates")
        return parsed

    async def propose_memory_sweep_cards(
        self,
        class_id: str,
        subject: str,
        grouped_candidates: dict[str, list[dict]],
        target_excerpts: dict[str, str],
        alignment_groups: list[dict] | None = None,
        validation_error: str = "",
    ) -> MemorySweepProposalOutput:
        import json

        field_cap = get_context_limits().profile_propose_field_chars
        retry_block = (
            f"\nPrevious validation error:\n{validation_error}\n\n"
            if validation_error
            else ""
        )
        prompt = (
            f"Class: {class_id}\n"
            f"Subject: {subject}\n\n"
            f"{retry_block}"
            "Validated alignment groups:\n"
            f"{apply_char_limit(json.dumps(alignment_groups or [], indent=2), field_cap * 3)}\n\n"
            "Grouped candidate ledger rows:\n"
            f"{apply_char_limit(json.dumps(grouped_candidates, indent=2), field_cap * 4)}\n\n"
            "Current target memory excerpts:\n"
            f"{apply_char_limit(json.dumps(target_excerpts, indent=2), field_cap * 3)}\n\n"
            "Return review cards for the teacher. Do not write memory."
        )
        agent = build_memory_sweep_card_agent(self.fast_model)
        parsed = await self._run_structured(agent, prompt)
        if not isinstance(parsed, MemorySweepProposalOutput):
            raise RuntimeError("Failed to propose Memory Sweep cards")
        return parsed

    async def align_memory_sweep_candidates(
        self,
        class_id: str,
        subject: str,
        grouped_candidates: dict[str, list[dict]],
        target_excerpts: dict[str, str],
        validation_error: str = "",
    ) -> MemorySweepAlignmentOutput:
        import json

        field_cap = get_context_limits().profile_propose_field_chars
        retry_block = (
            f"\nPrevious validation error:\n{validation_error}\n\n"
            if validation_error
            else ""
        )
        prompt = (
            f"Class: {class_id}\n"
            f"Subject: {subject}\n\n"
            f"{retry_block}"
            "Grouped candidate ledger rows:\n"
            f"{apply_char_limit(json.dumps(grouped_candidates, indent=2), field_cap * 4)}\n\n"
            "Current target memory excerpts:\n"
            f"{apply_char_limit(json.dumps(target_excerpts, indent=2), field_cap * 3)}\n\n"
            "Return validated-ready alignment groups. Do not generate review cards."
        )
        agent = build_memory_sweep_alignment_agent(self.fast_model)
        parsed = await self._run_structured(agent, prompt)
        if not isinstance(parsed, MemorySweepAlignmentOutput):
            raise RuntimeError("Failed to align Memory Sweep candidates")
        return parsed
