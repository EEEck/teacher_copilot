"""Generic artifact-session orchestration shared by every mode (ingest/plan/…).

Owns the session lifecycle that used to be copy-pasted across IngestService and
PlanService: in-memory store, opening message, the chat turn loop, draft build,
and readiness/status transitions. Mode-specific policy lives in ArtifactSpec;
mode-specific *commit* (wiki propose/commit vs single-file save) stays in the
thin adapters that wrap this core, since those touch different schemas/routes.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from app.config import get_settings
from app.schemas.api import ChatAttachment, ChatMessage, CompletenessChecklist
from app.teacher_agent.stream_events import (
    SseError,
    SseEvent,
    SseFinal,
    SseReasoningDelta,
    sse_encode,
)
from app.services.artifact_spec import ArtifactSpec, TurnResult, default_specs
from app.services.memory_candidate_ledger import MemoryCandidateLedger
from app.teacher_agent.memory_capture import runtime_candidates_to_ledger_rows
from app.services.output_safety import (
    SAFE_INTERNAL_DATA_REPLY,
    OutputSafetyFinding,
    check_teacher_visible_output,
)
from app.services.stream_safety import (
    StreamSafetyState,
    sanitize_teacher_visible_stream_event,
)
from app.teacher_agent.agents import AgentRunner
from app.teacher_agent.wiki_store import WikiStore

_TRACE_EVENT_CAP = 200


@dataclass
class ArtifactSession:
    session_id: str
    class_id: str
    mode: str
    status: str
    messages: list[ChatMessage] = field(default_factory=list)
    partial_markdown: str = ""
    completeness: CompletenessChecklist | None = None
    opening_message: str = ""
    # Optional mode-specific runtime state. Plan mode uses this for structured
    # planning state, evidence briefs, raw refs, and memory candidates.
    runtime: object | None = None
    debug_events: list[dict] = field(default_factory=list)


class ArtifactSessionService:
    def __init__(
        self,
        wiki: WikiStore,
        agents: AgentRunner,
        specs: dict[str, ArtifactSpec] | None = None,
        memory_candidate_ledger: MemoryCandidateLedger | None = None,
    ) -> None:
        self.wiki = wiki
        self.agents = agents
        self.specs = specs or default_specs()
        self.memory_candidate_ledger = memory_candidate_ledger
        self.sessions: dict[str, ArtifactSession] = {}
        self.drafts: dict[str, object] = {}

    def spec_for(self, mode: str) -> ArtifactSpec:
        return self.specs[mode]

    async def start_session(self, mode: str, class_id: str) -> ArtifactSession:
        spec = self.specs[mode]
        session_id = str(uuid.uuid4())
        opening = await spec.opening(self.agents, class_id) if spec.opening else ""
        messages = [ChatMessage(role="assistant", content=opening)] if opening else []
        session = ArtifactSession(
            session_id=session_id,
            class_id=class_id,
            mode=mode,
            status=spec.chatting_status,
            messages=messages,
            partial_markdown=spec.empty_template(self.wiki),
            completeness=spec.completeness_of(
                self.wiki, spec.empty_template(self.wiki)
            ),
            opening_message=opening,
            runtime=spec.runtime_factory() if spec.runtime_factory else None,
        )
        self.sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> ArtifactSession:
        if session_id not in self.sessions:
            raise KeyError(f"Unknown session: {session_id}")
        return self.sessions[session_id]

    async def _ensure_lazy_opening(self, session: ArtifactSession) -> None:
        spec = self.specs[session.mode]
        if not spec.lazy_opening or session.messages:
            return
        if spec.prompt_trace:
            self._record_prompt_assembly(session, "plan_opening")
        opening = await spec.lazy_opening(self.agents, session.class_id)
        session.opening_message = opening
        session.messages.append(ChatMessage(role="assistant", content=opening))

    def _record_prompt_assembly(
        self,
        session: ArtifactSession,
        stage: str,
        attachments: list[ChatAttachment] | None = None,
    ) -> None:
        spec = self.specs[session.mode]
        if not get_settings().is_agent_trace_enabled():
            return
        if not spec.prompt_trace:
            return
        payload = spec.prompt_trace(
            self.wiki,
            session.class_id,
            session.messages,
            session.partial_markdown,
            session.runtime,
            attachments or [],
            stage,
        )
        session.debug_events.append({"type": "prompt_assembly", **payload})
        if len(session.debug_events) > _TRACE_EVENT_CAP:
            session.debug_events = session.debug_events[-_TRACE_EVENT_CAP:]

    def _record_safety_output_blocked(
        self,
        session: ArtifactSession,
        findings: list[OutputSafetyFinding],
    ) -> None:
        session.debug_events.append(
            {
                "type": "safety_output_blocked",
                "rules": [
                    {"field": finding.field, "rule": finding.rule}
                    for finding in findings
                ],
            }
        )
        if len(session.debug_events) > _TRACE_EVENT_CAP:
            session.debug_events = session.debug_events[-_TRACE_EVENT_CAP:]

    def _safe_fallback_result(
        self,
        session: ArtifactSession,
        result: TurnResult,
        previous_markdown: str,
        findings: list[OutputSafetyFinding],
    ) -> TurnResult:
        spec = self.specs[session.mode]
        self._record_safety_output_blocked(session, findings)
        return TurnResult(
            reply=SAFE_INTERNAL_DATA_REPLY,
            markdown=previous_markdown,
            ready=spec.readiness(self.wiki, previous_markdown),
            completeness=spec.completeness_of(self.wiki, previous_markdown),
            planning=result.planning,
            memory=result.memory,
        )

    def _guard_turn_result(
        self,
        session: ArtifactSession,
        result: TurnResult,
        previous_markdown: str,
    ) -> TurnResult:
        findings = check_teacher_visible_output(
            reply=result.reply,
            markdown=result.markdown,
        )
        if not findings:
            return result
        return self._safe_fallback_result(session, result, previous_markdown, findings)

    def _safe_fallback_final_event(
        self,
        session: ArtifactSession,
        event: SseFinal,
        previous_markdown: str,
        findings: list[OutputSafetyFinding],
    ) -> SseFinal:
        spec = self.specs[session.mode]
        self._record_safety_output_blocked(session, findings)
        return event.model_copy(
            update={
                "reply": SAFE_INTERNAL_DATA_REPLY,
                "artifact_markdown": previous_markdown,
                "ready": spec.readiness(self.wiki, previous_markdown),
                "completeness": spec.completeness_of(self.wiki, previous_markdown),
            }
        )

    def _guard_final_event(
        self,
        session: ArtifactSession,
        event: SseFinal,
        previous_markdown: str,
    ) -> SseFinal:
        findings = check_teacher_visible_output(
            reply=event.reply,
            artifact_markdown=event.artifact_markdown,
        )
        if not findings:
            return event
        return self._safe_fallback_final_event(
            session, event, previous_markdown, findings
        )

    def _persist_memory_candidates(self, session: ArtifactSession) -> None:
        if self.memory_candidate_ledger is None or session.runtime is None:
            return
        candidates = getattr(session.runtime, "memory_candidates", [])
        if not candidates:
            return
        subject = self.wiki.get_class(session.class_id).subject
        turn_index = sum(1 for msg in session.messages if msg.role == "user")
        rows = runtime_candidates_to_ledger_rows(
            candidates,
            class_id=session.class_id,
            subject=subject,
            workflow=session.mode,
            session_id=session.session_id,
            turn_index=turn_index,
        )
        self.memory_candidate_ledger.add_many(rows)

    async def chat(
        self,
        session_id: str,
        message: str,
        markdown: str | None = None,
        attachments: list[ChatAttachment] | None = None,
    ) -> TurnResult:
        session = self.get_session(session_id)
        spec = self.specs[session.mode]
        if markdown is not None:
            session.partial_markdown = markdown

        await self._ensure_lazy_opening(session)
        session.messages.append(ChatMessage(role="user", content=message))
        stage = "plan_chat" if session.mode == "plan" else f"{session.mode}_chat"
        self._record_prompt_assembly(session, stage, attachments or [])
        previous_markdown = session.partial_markdown
        result = await spec.run_turn(
            self.agents,
            session.class_id,
            session.messages,
            session.partial_markdown,
            attachments or [],
            session.runtime,
        )
        result = self._guard_turn_result(session, result, previous_markdown)
        session.messages.append(ChatMessage(role="assistant", content=result.reply))
        session.partial_markdown = result.markdown
        if result.completeness is not None:
            session.completeness = result.completeness
        self.drafts[session_id] = spec.build_draft(
            self.wiki, session.class_id, result.markdown
        )
        if result.ready:
            session.status = spec.ready_status
        self._persist_memory_candidates(session)
        return result

    def _apply_turn_result(self, session: ArtifactSession, result: TurnResult) -> None:
        spec = self.specs[session.mode]
        session.messages.append(ChatMessage(role="assistant", content=result.reply))
        session.partial_markdown = result.markdown
        if result.completeness is not None:
            session.completeness = result.completeness
        self.drafts[session.session_id] = spec.build_draft(
            self.wiki, session.class_id, result.markdown
        )
        if result.ready:
            session.status = spec.ready_status
        self._persist_memory_candidates(session)

    def _record_debug_event(self, session: ArtifactSession, event: SseEvent) -> None:
        if isinstance(event, SseReasoningDelta):
            return
        if isinstance(event, SseError):
            payload = event.model_dump()
        elif isinstance(event, SseFinal):
            payload = {
                "type": event.type,
                "reply": event.reply,
                "ready": event.ready,
                "artifact_chars": len(event.artifact_markdown or ""),
                "phase": event.phase,
                "last_change_summary": event.last_change_summary,
                "memory_candidates": event.memory_candidates or [],
                "memory_state": event.memory_state or {},
            }
        else:
            payload = event.model_dump()
        session.debug_events.append(payload)
        if len(session.debug_events) > _TRACE_EVENT_CAP:
            session.debug_events = session.debug_events[-_TRACE_EVENT_CAP:]

    async def chat_stream(
        self,
        session_id: str,
        message: str,
        markdown: str | None = None,
        attachments: list[ChatAttachment] | None = None,
    ) -> AsyncIterator[str]:
        """SSE wire lines for one chat turn (ingest or plan)."""
        session = self.get_session(session_id)
        if markdown is not None:
            session.partial_markdown = markdown
        await self._ensure_lazy_opening(session)
        session.messages.append(ChatMessage(role="user", content=message))
        stage = "plan_chat" if session.mode == "plan" else f"{session.mode}_chat"
        self._record_prompt_assembly(session, stage, attachments or [])

        spec = self.specs[session.mode]
        if not spec.stream_turn or not spec.final_event_to_turn_result:
            yield sse_encode(
                SseError(
                    message="Workflow streaming is not configured.", code="config_error"
                )
            )
            return
        stream = spec.stream_turn(
            self.agents,
            session.class_id,
            session.messages,
            session.partial_markdown,
            attachments or [],
            session.runtime,
        )
        previous_markdown = session.partial_markdown
        sanitize_stream = get_settings().app_env == "production"
        stream_safety_state = StreamSafetyState()
        async for event in stream:
            if isinstance(event, SseFinal):
                event = self._guard_final_event(session, event, previous_markdown)
            elif sanitize_stream:
                safe_event = sanitize_teacher_visible_stream_event(
                    event, stream_safety_state
                )
                if safe_event is None:
                    continue
                event = safe_event
            self._record_debug_event(session, event)
            if isinstance(event, SseFinal):
                self._apply_turn_result(session, spec.final_event_to_turn_result(event))
            yield sse_encode(event)

    def update_draft(self, session_id: str, markdown: str) -> object:
        session = self.get_session(session_id)
        spec = self.specs[session.mode]
        session.partial_markdown = markdown
        draft = spec.build_draft(self.wiki, session.class_id, markdown)
        self.drafts[session_id] = draft
        completeness = spec.completeness_of(self.wiki, markdown)
        if completeness is not None:
            session.completeness = completeness
        if spec.readiness(self.wiki, markdown):
            session.status = spec.ready_status
        return draft

    def get_draft(self, session_id: str) -> object:
        if session_id in self.drafts:
            return self.drafts[session_id]
        session = self.get_session(session_id)
        spec = self.specs[session.mode]
        return spec.build_draft(self.wiki, session.class_id, session.partial_markdown)

    def set_markdown(self, session_id: str, markdown: str) -> None:
        self.get_session(session_id).partial_markdown = markdown

    def set_status(self, session_id: str, status: str) -> None:
        self.get_session(session_id).status = status
