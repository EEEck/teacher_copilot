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

from app.schemas.api import ChatAttachment, ChatMessage, CompletenessChecklist
from app.teacher_agent.stream_events import SseError, SseEvent, SseFinal, sse_encode
from app.services.artifact_spec import ArtifactSpec, TurnResult, default_specs
from app.teacher_agent.agents import AgentRunner
from app.teacher_agent.wiki_store import WikiStore


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


class ArtifactSessionService:
    def __init__(
        self,
        wiki: WikiStore,
        agents: AgentRunner,
        specs: dict[str, ArtifactSpec] | None = None,
    ) -> None:
        self.wiki = wiki
        self.agents = agents
        self.specs = specs or default_specs()
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
            completeness=spec.completeness_of(self.wiki, spec.empty_template(self.wiki)),
            opening_message=opening,
        )
        self.sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> ArtifactSession:
        if session_id not in self.sessions:
            raise KeyError(f"Unknown session: {session_id}")
        return self.sessions[session_id]

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

        session.messages.append(ChatMessage(role="user", content=message))
        result = await spec.run_turn(
            self.agents,
            session.class_id,
            session.messages,
            session.partial_markdown,
            attachments or [],
        )
        session.messages.append(ChatMessage(role="assistant", content=result.reply))
        session.partial_markdown = result.markdown
        if result.completeness is not None:
            session.completeness = result.completeness
        self.drafts[session_id] = spec.build_draft(
            self.wiki, session.class_id, result.markdown
        )
        if result.ready:
            session.status = spec.ready_status
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
        session.messages.append(ChatMessage(role="user", content=message))

        stream_fn = (
            self.agents.ingest_chat_stream
            if session.mode == "ingest"
            else self.agents.plan_chat_stream
        )
        async for event in stream_fn(
            session.class_id,
            session.messages,
            session.partial_markdown,
            attachments=attachments or [],
        ):
            if isinstance(event, SseFinal):
                self._apply_turn_result(
                    session,
                    TurnResult(
                        reply=event.reply,
                        markdown=event.artifact_markdown,
                        ready=event.ready,
                        completeness=event.completeness,
                    ),
                )
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
