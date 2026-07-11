from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.config import get_settings
from app.schemas.api import (
    AgentTraceResponse,
    ChatMessage,
    ClassBriefAction,
    ClassDiscussionChatResponse,
    ClassDiscussionSession,
)
from app.services.output_safety import (
    SAFE_INTERNAL_DATA_REPLY,
    OutputSafetyFinding,
    check_teacher_visible_output,
)
from app.services.memory_candidate_ledger import MemoryCandidateLedger
from app.teacher_agent.agents import AgentRunner
from app.teacher_agent.class_discussion_state import (
    ClassDiscussionRuntime,
    discussion_api_payload,
)
from app.teacher_agent.memory_capture import runtime_candidates_to_ledger_rows
from app.teacher_agent.prompt_assembly import build_class_discussion_prompt_assembly
from app.teacher_agent.wiki_store import WikiStore


@dataclass
class ClassDiscussionSessionState:
    session_id: str
    class_id: str
    messages: list[ChatMessage] = field(default_factory=list)
    runtime: ClassDiscussionRuntime = field(default_factory=ClassDiscussionRuntime)
    debug_events: list[dict] = field(default_factory=list)
    turn_in_progress: bool = False
    latest_turn_complete: bool = True


class ClassDiscussionService:
    def __init__(
        self,
        wiki: WikiStore,
        agents: AgentRunner,
        memory_candidate_ledger: MemoryCandidateLedger | None = None,
    ) -> None:
        self.wiki = wiki
        self.agents = agents
        self.memory_candidate_ledger = memory_candidate_ledger
        self.sessions: dict[str, ClassDiscussionSessionState] = {}

    def start_session(self, class_id: str) -> ClassDiscussionSession:
        self.wiki.get_class(class_id)
        session_id = str(uuid.uuid4())
        session = ClassDiscussionSessionState(session_id=session_id, class_id=class_id)
        self.sessions[session_id] = session
        return ClassDiscussionSession(
            session_id=session_id,
            class_id=class_id,
            messages=[],
        )

    def get_session(self, session_id: str) -> ClassDiscussionSessionState:
        if session_id not in self.sessions:
            raise KeyError(f"Unknown discussion session: {session_id}")
        return self.sessions[session_id]

    def _trim_debug_events(self, session: ClassDiscussionSessionState) -> None:
        session.debug_events = session.debug_events[-100:]

    def _begin_turn(self, session: ClassDiscussionSessionState) -> None:
        if session.turn_in_progress:
            raise ValueError(
                "Cannot start a new discussion turn: another discussion turn is still running."
            )
        session.turn_in_progress = True
        session.latest_turn_complete = False

    def _complete_turn(self, session: ClassDiscussionSessionState) -> None:
        session.latest_turn_complete = True

    def _end_turn(self, session: ClassDiscussionSessionState) -> None:
        session.turn_in_progress = False

    def _record_prompt_assembly(self, session: ClassDiscussionSessionState) -> dict:
        if not get_settings().is_agent_trace_enabled():
            return {}
        assembly = build_class_discussion_prompt_assembly(
            self.wiki,
            session.class_id,
            messages=session.messages,
            runtime=session.runtime,
        )
        payload = {"type": "prompt_assembly", **assembly}
        session.debug_events.append(payload)
        self._trim_debug_events(session)
        return assembly

    def _record_safety_output_blocked(
        self,
        session: ClassDiscussionSessionState,
        findings: list[OutputSafetyFinding],
    ) -> None:
        if not get_settings().is_agent_trace_enabled():
            return
        session.debug_events.append(
            {
                "type": "safety_output_blocked",
                "rules": [
                    {"field": finding.field, "rule": finding.rule}
                    for finding in findings
                ],
            }
        )
        self._trim_debug_events(session)

    def _safe_reply(
        self,
        session: ClassDiscussionSessionState,
        reply: str,
    ) -> str:
        findings = check_teacher_visible_output(reply=reply)
        if not findings:
            return reply
        self._record_safety_output_blocked(session, findings)
        return SAFE_INTERNAL_DATA_REPLY

    def _action_for_label(self, class_id: str, label: str) -> ClassBriefAction:
        normalized = label.strip().lower()
        if "memory sweep" in normalized:
            return ClassBriefAction(
                label="Memory Sweep", href=f"/classes/{class_id}/memory-sweep"
            )
        if "update" in normalized or "memory" in normalized:
            return ClassBriefAction(
                label="Update memory", href=f"/classes/{class_id}/memory"
            )
        if "plan" in normalized:
            return ClassBriefAction(
                label="Create lesson plan", href=f"/classes/{class_id}/plan"
            )
        return ClassBriefAction(label=label.strip() or "Discuss class state")

    def _candidate_payloads(self, session: ClassDiscussionSessionState) -> list[dict]:
        candidates = session.runtime.memory_candidates
        if not candidates:
            return []
        subject = self.wiki.get_class(session.class_id).subject
        turn_index = sum(1 for msg in session.messages if msg.role == "user")
        rows = runtime_candidates_to_ledger_rows(
            candidates,
            class_id=session.class_id,
            subject=subject,
            workflow="discussion",
            session_id=session.session_id,
            turn_index=turn_index,
        )
        payloads: list[dict] = []
        for candidate, row in zip(candidates, rows):
            payload = candidate.model_dump()
            payload["candidate_id"] = row.id
            payloads.append(payload)
        return payloads

    def _persist_memory_candidates(self, session: ClassDiscussionSessionState) -> None:
        if self.memory_candidate_ledger is None:
            return
        candidates = session.runtime.memory_candidates
        if not candidates:
            return
        subject = self.wiki.get_class(session.class_id).subject
        turn_index = sum(1 for msg in session.messages if msg.role == "user")
        rows = runtime_candidates_to_ledger_rows(
            candidates,
            class_id=session.class_id,
            subject=subject,
            workflow="discussion",
            session_id=session.session_id,
            turn_index=turn_index,
        )
        self.memory_candidate_ledger.add_many(rows)

    async def chat(
        self, session_id: str, message: str
    ) -> ClassDiscussionChatResponse:
        session = self.get_session(session_id)
        self._begin_turn(session)
        try:
            session.messages.append(ChatMessage(role="user", content=message))
            self._record_prompt_assembly(session)
            output = await self.agents.class_discussion_chat(
                session.class_id,
                session.messages,
                runtime=session.runtime,
            )
            reply = self._safe_reply(session, output.reply)
            session.messages.append(ChatMessage(role="assistant", content=reply))
            self._persist_memory_candidates(session)
            payload = discussion_api_payload(session.runtime)
            self._complete_turn(session)
            return ClassDiscussionChatResponse(
                reply=reply,
                discussion_state=payload["discussion_state"],
                evidence_briefs=payload["evidence_briefs"],
                memory_candidates=self._candidate_payloads(session),
                source_paths=output.source_paths,
                suggested_actions=[
                    self._action_for_label(session.class_id, action)
                    for action in output.suggested_actions
                ],
            )
        finally:
            self._end_turn(session)

    def trace(self, session_id: str) -> AgentTraceResponse:
        session = self.get_session(session_id)
        prompt_assembly = {}
        for event in reversed(session.debug_events):
            if event.get("type") == "prompt_assembly":
                prompt_assembly = event
                break
        return AgentTraceResponse(
            class_id=session.class_id,
            session_id=session.session_id,
            status="chatting",
            prompt_stack={},
            prompt_assembly=prompt_assembly,
            runtime={
                "raw_refs": sorted(session.runtime.raw_store),
                "discussion_state": session.runtime.discussion_state.model_dump(),
                "evidence_brief_count": len(session.runtime.evidence_briefs),
                "memory_candidate_count": len(session.runtime.memory_candidates),
            },
            messages=session.messages,
            artifact_markdown="",
            event_trace=session.debug_events,
            raw_evidence=session.runtime.raw_store,
        )
