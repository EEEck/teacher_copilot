"""Generic artifact-session orchestration shared by every mode (ingest/plan/…).

Owns the session lifecycle that used to be copy-pasted across IngestService and
PlanService: in-memory store, opening message, the chat turn loop, draft build,
and readiness/status transitions. Mode-specific policy lives in ArtifactSpec;
mode-specific *commit* (wiki propose/commit vs single-file save) stays in the
thin adapters that wrap this core, since those touch different schemas/routes.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field, replace

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
from app.services.memory_candidate_ledger import insert_with_folding
from app.services.memory_skills import (
    read_curated_target_bullets,
    write_skill_for_target,
)
from app.teacher_agent.memory_capture import (
    discipline_memory_candidates,
    occasion_key_for,
    runtime_candidates_to_ledger_rows,
)
from app.services.output_safety import (
    SAFE_INTERNAL_DATA_REPLY,
    OutputSafetyFinding,
    check_teacher_visible_output,
)
from app.services.stream_safety import (
    StreamSafetyState,
    sanitize_teacher_visible_stream_event,
)
from app.services.workflow_drafts import WorkflowDraftIdentity, WorkflowDraftStore
from app.teacher_agent.agents import AgentRunner
from app.teacher_agent.executive_verification import ExecutiveRuntime
from app.teacher_agent.executive_verification import (
    executive_api_payload,
    executive_runtime_dump,
    executive_runtime_load,
)
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
    turn_in_progress: bool = False
    latest_turn_complete: bool = True
    pending_turn: dict = field(default_factory=dict)
    # Optional mode-specific runtime state. Plan mode uses this for structured
    # planning state, evidence briefs, raw refs, and memory candidates.
    runtime: object | None = None
    executive: ExecutiveRuntime = field(default_factory=ExecutiveRuntime)
    debug_events: list[dict] = field(default_factory=list)
    draft_id: str = ""
    artifact_revision: int = 0
    artifact_hash: str = ""


class ArtifactSessionService:
    def __init__(
        self,
        wiki: WikiStore,
        agents: AgentRunner,
        specs: dict[str, ArtifactSpec] | None = None,
        memory_candidate_ledger: MemoryCandidateLedger | None = None,
        workflow_drafts: WorkflowDraftStore | None = None,
        workspace_id: str = "local",
    ) -> None:
        self.wiki = wiki
        self.agents = agents
        self.specs = specs or default_specs()
        self.memory_candidate_ledger = memory_candidate_ledger
        self.workflow_drafts = workflow_drafts
        self.workspace_id = workspace_id
        self.sessions: dict[str, ArtifactSession] = {}
        self.drafts: dict[str, object] = {}
        self._stream_tasks: dict[str, asyncio.Task[None]] = {}
        self._stream_subscribers: dict[str, set[asyncio.Queue[str | None]]] = {}

    def spec_for(self, mode: str) -> ArtifactSpec:
        return self.specs[mode]

    async def start_session(
        self,
        mode: str,
        class_id: str,
        *,
        draft_identity: WorkflowDraftIdentity | None = None,
        initial_markdown: str | None = None,
        initial_runtime: object | None = None,
        initial_messages: list[ChatMessage] | None = None,
    ) -> ArtifactSession:
        spec = self.specs[mode]
        opening = ""
        if initial_messages is not None:
            messages = list(initial_messages)
        else:
            opening = await spec.opening(self.agents, class_id) if spec.opening else ""
            messages = [ChatMessage(role="assistant", content=opening)] if opening else []
        markdown = (
            initial_markdown
            if initial_markdown is not None
            else spec.empty_template(self.wiki)
        )
        runtime = (
            initial_runtime
            if initial_runtime is not None
            else spec.runtime_factory()
            if spec.runtime_factory
            else None
        )
        if self.workflow_drafts is not None and draft_identity is not None:
            opened = self.workflow_drafts.open_draft(
                draft_identity,
                default_status=spec.chatting_status,
                artifact_markdown=markdown,
                runtime_json=self._dump_runtime(mode, runtime),
                messages_json=[message.model_dump() for message in messages],
            )
            if opened.row.backend_session_id in self.sessions:
                session = self.sessions[opened.row.backend_session_id]
                await self._resume_pending_turn_if_needed(session)
                return session
            session = self._session_from_draft_row(opened.row)
            self.sessions[session.session_id] = session
            await self._resume_pending_turn_if_needed(session)
            return session

        session_id = str(uuid.uuid4())
        session = ArtifactSession(
            session_id=session_id,
            class_id=class_id,
            mode=mode,
            status=spec.chatting_status,
            messages=messages,
            partial_markdown=markdown,
            completeness=spec.completeness_of(self.wiki, markdown),
            opening_message=opening,
            runtime=runtime,
        )
        self.sessions[session_id] = session
        return session

    def _session_from_draft_row(self, row) -> ArtifactSession:
        spec = self.specs[row.mode]
        messages = [ChatMessage(**item) for item in row.messages_json]
        if spec.runtime_load:
            runtime = spec.runtime_load(row.runtime_json)
        elif spec.runtime_factory:
            runtime = spec.runtime_factory()
        else:
            runtime = None
        opening = messages[0].content if messages and messages[0].role == "assistant" else ""
        return ArtifactSession(
            session_id=row.backend_session_id,
            class_id=row.class_id,
            mode=row.mode,
            status=row.status,
            messages=messages,
            partial_markdown=row.artifact_markdown,
            completeness=spec.completeness_of(self.wiki, row.artifact_markdown),
            opening_message=opening,
            runtime=runtime,
            executive=executive_runtime_load(row.executive_json),
            turn_in_progress=row.turn_in_progress,
            latest_turn_complete=row.latest_turn_complete,
            pending_turn=row.pending_turn_json,
            draft_id=row.draft_id,
            artifact_revision=row.artifact_revision,
            artifact_hash=row.artifact_hash,
        )

    def _dump_runtime(self, mode: str, runtime: object | None) -> dict:
        spec = self.specs[mode]
        if runtime is None or spec.runtime_dump is None:
            return {}
        return spec.runtime_dump(runtime)

    def _persist_session(self, session: ArtifactSession) -> None:
        if self.workflow_drafts is None or not session.draft_id:
            return
        row = self.workflow_drafts.save_from_session(
            draft_id=session.draft_id,
            status=session.status,
            artifact_markdown=session.partial_markdown,
            runtime_json=self._dump_runtime(session.mode, session.runtime),
            executive_json=executive_runtime_dump(session.executive),
            messages_json=[message.model_dump() for message in session.messages],
            backend_session_id=session.session_id,
            pending_turn_json=session.pending_turn,
            turn_in_progress=session.turn_in_progress,
            latest_turn_complete=session.latest_turn_complete,
        )
        session.artifact_revision = row.artifact_revision
        session.artifact_hash = row.artifact_hash

    def _with_draft_metadata(self, draft: object, session: ArtifactSession) -> object:
        for field_name, value in (
            ("draft_id", session.draft_id),
            ("artifact_revision", session.artifact_revision),
            ("artifact_hash", session.artifact_hash),
            ("turn_in_progress", session.turn_in_progress),
            ("latest_turn_complete", session.latest_turn_complete),
            ("messages", session.messages),
        ):
            if hasattr(draft, field_name):
                setattr(draft, field_name, value)
        return draft

    def get_session(self, session_id: str) -> ArtifactSession:
        if session_id not in self.sessions:
            raise KeyError(f"Unknown session: {session_id}")
        return self.sessions[session_id]

    def require_latest_turn_complete(self, session_id: str, action: str) -> None:
        session = self.get_session(session_id)
        if session.latest_turn_complete:
            return
        raise ValueError(
            f"Cannot {action}: the latest chat turn has not been incorporated "
            "into the draft yet. Wait for the assistant response, or send the "
            "forgotten note again."
        )

    def _begin_turn(self, session: ArtifactSession) -> None:
        if session.turn_in_progress:
            raise ValueError(
                "Cannot start a new chat turn: another chat turn is still running."
            )
        session.turn_in_progress = True
        session.latest_turn_complete = False

    def _complete_turn(self, session: ArtifactSession) -> None:
        session.latest_turn_complete = True

    def _end_turn(self, session: ArtifactSession) -> None:
        session.turn_in_progress = False

    async def _resume_pending_turn_if_needed(self, session: ArtifactSession) -> None:
        if not session.turn_in_progress or session.session_id in self._stream_tasks:
            return
        if not session.pending_turn:
            # Older durable rows did not preserve enough input to continue. Do
            # not leave a permanent spinner after a backend restart.
            self._end_turn(session)
            self._persist_session(session)
            return
        attachments = [
            ChatAttachment(**payload)
            for payload in session.pending_turn.get("attachments", [])
            if isinstance(payload, dict)
        ]
        self._stream_tasks[session.session_id] = asyncio.create_task(
            self._run_stream_turn(
                session.session_id,
                "",
                None,
                attachments,
                resume=True,
            )
        )

    async def _ensure_lazy_opening(self, session: ArtifactSession) -> None:
        spec = self.specs[session.mode]
        if not spec.lazy_opening or session.messages:
            return
        if spec.prompt_trace:
            self._record_prompt_assembly(session, "plan_opening")
        opening = await spec.lazy_opening(self.agents, session.class_id)
        session.opening_message = opening
        session.messages.append(ChatMessage(role="assistant", content=opening))
        self._persist_session(session)

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
            session.executive,
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
            discussion=result.discussion,
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
        # Mem V3 capture discipline: source=teacher_explicit is only a model
        # hint until speech act, target policy, and quote provenance verify it.
        last_teacher_message = next(
            (msg.content for msg in reversed(session.messages) if msg.role == "user"),
            "",
        )
        candidates = discipline_memory_candidates(
            candidates, teacher_message=last_teacher_message
        )
        subject = self.wiki.get_class(session.class_id).subject
        turn_index = sum(1 for msg in session.messages if msg.role == "user")
        # Occasion anchor: reinforcement counts distinct occasions (one
        # lesson = one occasion, however many sessions/retries touch it).
        # Ingest resolves a lesson target; plan sessions anchor on the session.
        target = getattr(session.runtime, "target", None)
        lesson_date = (getattr(target, "lesson_date", "") or "").strip()
        occasion_key = occasion_key_for(
            session.mode, session.session_id, lesson_date
        )
        rows = runtime_candidates_to_ledger_rows(
            candidates,
            class_id=session.class_id,
            subject=subject,
            workflow=session.mode,
            session_id=session.session_id,
            turn_index=turn_index,
            occasion_key=occasion_key,
        )
        # Insert-time folding: exact/near duplicates join their cluster or are
        # neutralized against applied/rejected history (docs/mem_v3 lane 1). For
        # curated targets whose write skill declares dedup_scope=ledger+canonical
        # (B2), also fold against what is already written to the target file so a
        # re-capture of an already-present fact does not get re-proposed.
        bullets_by_target: dict[str, list[str]] = {}
        for row in rows:
            skill = write_skill_for_target(row.target)
            canonical_bullets: list[str] = []
            if skill is not None and skill.dedup_scope == "ledger+canonical":
                if row.target not in bullets_by_target:
                    bullets_by_target[row.target] = read_curated_target_bullets(
                        self.wiki, session.class_id, row.target
                    )
                canonical_bullets = bullets_by_target[row.target]
            insert_with_folding(
                self.memory_candidate_ledger, row, canonical_bullets=canonical_bullets
            )

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
        self._begin_turn(session)
        session.messages.append(ChatMessage(role="user", content=message))
        self._persist_session(session)
        try:
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
                session.executive,
            )
            result = replace(
                result,
                ready=result.ready
                and not session.executive.open_blocking_findings(),
                executive=executive_api_payload(session.executive),
            )
            result = self._guard_turn_result(session, result, previous_markdown)
            session.messages.append(ChatMessage(role="assistant", content=result.reply))
            session.partial_markdown = result.markdown
            if result.completeness is not None:
                session.completeness = result.completeness
            if result.ready:
                session.status = spec.ready_status
            self._persist_memory_candidates(session)
            self._complete_turn(session)
            self._persist_session(session)
            self.drafts[session_id] = self._with_draft_metadata(
                spec.build_draft(self.wiki, session.class_id, result.markdown),
                session,
            )
            return result
        finally:
            self._end_turn(session)
            self._persist_session(session)

    def _apply_turn_result(self, session: ArtifactSession, result: TurnResult) -> None:
        spec = self.specs[session.mode]
        session.messages.append(ChatMessage(role="assistant", content=result.reply))
        session.partial_markdown = result.markdown
        if result.completeness is not None:
            session.completeness = result.completeness
        if result.ready:
            session.status = spec.ready_status
        self._persist_memory_candidates(session)
        self._persist_session(session)
        self.drafts[session.session_id] = self._with_draft_metadata(
            spec.build_draft(self.wiki, session.class_id, result.markdown), session
        )

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

    def _subscribe_stream(self, session_id: str) -> asyncio.Queue[str | None]:
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._stream_subscribers.setdefault(session_id, set()).add(queue)
        return queue

    def _unsubscribe_stream(
        self, session_id: str, queue: asyncio.Queue[str | None]
    ) -> None:
        subscribers = self._stream_subscribers.get(session_id)
        if subscribers is None:
            return
        subscribers.discard(queue)
        if not subscribers:
            self._stream_subscribers.pop(session_id, None)

    def _publish_stream_line(self, session_id: str, line: str) -> None:
        for queue in list(self._stream_subscribers.get(session_id, ())):
            queue.put_nowait(line)

    def _finish_stream_subscribers(self, session_id: str) -> None:
        for queue in list(self._stream_subscribers.get(session_id, ())):
            queue.put_nowait(None)

    async def _run_stream_turn(
        self,
        session_id: str,
        message: str,
        markdown: str | None,
        attachments: list[ChatAttachment] | None,
        *,
        resume: bool = False,
    ) -> None:
        try:
            async for line in self._execute_chat_stream_turn(
                session_id, message, markdown, attachments, resume=resume
            ):
                self._publish_stream_line(session_id, line)
        except Exception:  # noqa: BLE001 - keep background failures visible to subscribers
            self._publish_stream_line(
                session_id,
                sse_encode(
                    SseError(
                        message="Something went wrong while generating the reply. Please send your message again.",
                        code="stream_error",
                    )
                ),
            )
        finally:
            self._stream_tasks.pop(session_id, None)
            self._finish_stream_subscribers(session_id)

    async def chat_stream(
        self,
        session_id: str,
        message: str,
        markdown: str | None = None,
        attachments: list[ChatAttachment] | None = None,
    ) -> AsyncIterator[str]:
        """SSE wire lines for one chat turn (ingest or plan).

        The model turn runs in a service-owned task. The HTTP stream is only a
        subscriber, so route changes/browser aborts do not cancel the draft
        update that is already underway.
        """
        queue = self._subscribe_stream(session_id)
        if session_id not in self._stream_tasks:
            session = self.get_session(session_id)
            if session.turn_in_progress:
                self._publish_stream_line(
                    session_id,
                    sse_encode(
                        SseError(
                            message=(
                                "A previous chat turn is still marked as running. "
                                "Return in a moment, or discard the draft if it does not finish."
                            ),
                            code="turn_in_progress",
                        )
                    ),
                )
                self._finish_stream_subscribers(session_id)
            else:
                self._stream_tasks[session_id] = asyncio.create_task(
                    self._run_stream_turn(session_id, message, markdown, attachments)
                )
        try:
            while True:
                line = await queue.get()
                if line is None:
                    return
                yield line
        finally:
            self._unsubscribe_stream(session_id, queue)

    async def _execute_chat_stream_turn(
        self,
        session_id: str,
        message: str,
        markdown: str | None = None,
        attachments: list[ChatAttachment] | None = None,
        *,
        resume: bool = False,
    ) -> AsyncIterator[str]:
        """Run one chat turn and produce SSE lines for active subscribers."""
        session = self.get_session(session_id)
        if not resume:
            if markdown is not None:
                session.partial_markdown = markdown
            await self._ensure_lazy_opening(session)
            self._begin_turn(session)
            session.messages.append(ChatMessage(role="user", content=message))
            session.pending_turn = {
                "attachments": [attachment.model_dump() for attachment in attachments or []]
            }
            self._persist_session(session)
        stage = "plan_chat" if session.mode == "plan" else f"{session.mode}_chat"
        self._record_prompt_assembly(session, stage, attachments or [])

        spec = self.specs[session.mode]
        if not spec.stream_turn or not spec.final_event_to_turn_result:
            try:
                yield sse_encode(
                    SseError(
                        message="Workflow streaming is not configured.", code="config_error"
                    )
                )
            finally:
                self._end_turn(session)
                session.pending_turn = {}
                self._persist_session(session)
            return
        stream = spec.stream_turn(
            self.agents,
            session.class_id,
            session.messages,
            session.partial_markdown,
            attachments or [],
            session.runtime,
            session.executive,
        )
        previous_markdown = session.partial_markdown
        sanitize_stream = get_settings().app_env == "production"
        stream_safety_state = StreamSafetyState()
        try:
            async for event in stream:
                if isinstance(event, SseFinal):
                    event.ready = (
                        event.ready
                        and not session.executive.open_blocking_findings()
                    )
                    event.executive_state = executive_api_payload(
                        session.executive
                    )
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
                    self._apply_turn_result(
                        session, spec.final_event_to_turn_result(event)
                    )
                    self._complete_turn(session)
                    event = event.model_copy(
                        update={
                            "draft_id": session.draft_id or None,
                            "artifact_revision": session.artifact_revision,
                            "artifact_hash": session.artifact_hash or None,
                        }
                    )
                yield sse_encode(event)
        finally:
            self._end_turn(session)
            session.pending_turn = {}
            self._persist_session(session)

    def update_draft(self, session_id: str, markdown: str) -> object:
        session = self.get_session(session_id)
        spec = self.specs[session.mode]
        session.partial_markdown = markdown
        completeness = spec.completeness_of(self.wiki, markdown)
        if completeness is not None:
            session.completeness = completeness
        if spec.readiness(self.wiki, markdown):
            session.status = spec.ready_status
        self._persist_session(session)
        draft = self._with_draft_metadata(
            spec.build_draft(self.wiki, session.class_id, markdown), session
        )
        self.drafts[session_id] = draft
        return draft

    def get_draft(self, session_id: str) -> object:
        if session_id in self.drafts:
            return self._with_draft_metadata(self.drafts[session_id], self.get_session(session_id))
        session = self.get_session(session_id)
        spec = self.specs[session.mode]
        return self._with_draft_metadata(
            spec.build_draft(self.wiki, session.class_id, session.partial_markdown),
            session,
        )

    def set_markdown(self, session_id: str, markdown: str) -> None:
        session = self.get_session(session_id)
        session.partial_markdown = markdown
        self._persist_session(session)

    def set_status(self, session_id: str, status: str) -> None:
        session = self.get_session(session_id)
        session.status = status
        self._persist_session(session)
