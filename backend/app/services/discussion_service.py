"""Class discussion flow — thin adapter over ArtifactSessionService.

Read-only wiki chat with optional MemoryCandidate capture. No artifact commit.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.schemas.api import (
    ChatAttachment,
    ClassBriefAction,
    DiscussChatResponse,
    DiscussDraft,
    DiscussSession,
    DiscussSessionStatus,
    DiscussTraceResponse,
)
from app.services.artifact_session_service import (
    ArtifactSession,
    ArtifactSessionService,
)
from app.services.memory_candidate_ledger import MemoryCandidateLedger, OPEN_STATUSES
from app.services.workflow_drafts import WorkflowDraftIdentity, WorkflowDraftStore
from app.teacher_agent.agents import AgentRunner
from app.teacher_agent.class_discussion_state import (
    discussion_api_payload,
    render_class_discussion_state,
)
from app.teacher_agent.prompt_assembly import build_class_discussion_prompt_assembly
from app.teacher_agent.wiki_store import WikiStore

MODE = "discuss"


def _suggested_action_models(labels: list[str], class_id: str) -> list[ClassBriefAction]:
    href_by_label = {
        "update memory": f"/classes/{class_id}/memory",
        "create lesson plan": f"/classes/{class_id}/plan",
        "memory sweep": f"/classes/{class_id}/memory-sweep",
        "discuss class state": f"/classes/{class_id}",
        "inspect wiki": f"/classes/{class_id}/wiki/view",
    }
    actions: list[ClassBriefAction] = []
    for label in labels:
        key = " ".join(label.lower().split())
        actions.append(
            ClassBriefAction(
                label=label,
                href=href_by_label.get(key, ""),
            )
        )
    return actions


def _enrich_candidates_with_ledger(
    candidates: list[dict],
    *,
    ledger: MemoryCandidateLedger | None,
    class_id: str,
    session_id: str,
) -> list[dict]:
    if ledger is None or not candidates:
        return candidates
    rows = ledger.list_candidates(class_id=class_id, statuses=OPEN_STATUSES)
    session_rows = [row for row in rows if row.session_id == session_id]
    enriched: list[dict] = []
    for candidate in candidates:
        payload = dict(candidate)
        match = next(
            (
                row
                for row in session_rows
                if row.candidate_update == candidate.get("candidate_update")
                and row.target == candidate.get("target")
            ),
            None,
        )
        if match is not None:
            payload["candidate_id"] = match.id
            payload["occasion_key"] = match.occasion_key
            payload["requires_teacher_approval"] = True
        enriched.append(payload)
    return enriched


class DiscussionService:
    def __init__(
        self,
        wiki: WikiStore,
        agents: AgentRunner,
        memory_candidate_ledger: MemoryCandidateLedger | None = None,
        workflow_drafts: WorkflowDraftStore | None = None,
        workspace_id: str = "local",
    ) -> None:
        self.wiki = wiki
        self.agents = agents
        self.workflow_drafts = workflow_drafts
        self.workspace_id = workspace_id
        self.memory_candidate_ledger = memory_candidate_ledger
        self.core = ArtifactSessionService(
            wiki,
            agents,
            memory_candidate_ledger=memory_candidate_ledger,
            workflow_drafts=workflow_drafts,
            workspace_id=workspace_id,
        )

    def _to_model(self, s: ArtifactSession) -> DiscussSession:
        return DiscussSession(
            session_id=s.session_id,
            draft_id=s.draft_id,
            artifact_revision=s.artifact_revision,
            artifact_hash=s.artifact_hash,
            turn_in_progress=s.turn_in_progress,
            latest_turn_complete=s.latest_turn_complete,
            class_id=s.class_id,
            status=DiscussSessionStatus.chatting,
            messages=s.messages,
            opening_message=s.opening_message,
        )

    async def start_session(self, class_id: str) -> DiscussSession:
        session = await self.core.start_session(
            MODE,
            class_id,
            draft_identity=WorkflowDraftIdentity(
                workspace_id=self.workspace_id,
                class_id=class_id,
                mode=MODE,
                intent="discuss_class_state",
            )
            if self.workflow_drafts is not None
            else None,
        )
        return self._to_model(session)

    def get_session(self, session_id: str) -> ArtifactSession:
        return self.core.get_session(session_id)

    def get_draft(self, session_id: str) -> DiscussDraft:
        draft = self.core.get_draft(session_id)
        assert isinstance(draft, DiscussDraft)
        return draft

    async def chat(
        self,
        session_id: str,
        message: str,
        attachments: list[ChatAttachment] | None = None,
    ) -> DiscussChatResponse:
        result = await self.core.chat(session_id, message, None, attachments)
        session = self.core.get_session(session_id)
        discussion = result.discussion or {}
        return DiscussChatResponse(
            reply=result.reply,
            draft_id=session.draft_id,
            artifact_revision=session.artifact_revision,
            artifact_hash=session.artifact_hash,
            discussion_state=discussion.get("discussion_state", {}),
            evidence_briefs=discussion.get("evidence_briefs", []),
            memory_candidates=_enrich_candidates_with_ledger(
                discussion.get("memory_candidates", []),
                ledger=self.memory_candidate_ledger,
                class_id=session.class_id,
                session_id=session_id,
            ),
            source_paths=discussion.get("source_paths", []),
            suggested_actions=_suggested_action_models(
                discussion.get("suggested_actions", []), session.class_id
            ),
            executive_state=result.executive,
        )

    async def chat_stream(
        self,
        session_id: str,
        message: str,
        attachments: list[ChatAttachment] | None = None,
    ) -> AsyncIterator[str]:
        async for line in self.core.chat_stream(session_id, message, None, attachments):
            yield line

    def trace(self, class_id: str, session_id: str) -> DiscussTraceResponse:
        session = self.core.get_session(session_id)
        if session.class_id != class_id:
            raise KeyError("Session class mismatch")
        runtime = session.runtime
        runtime_payload = discussion_api_payload(runtime) if runtime else {}
        teacher_context = self.wiki.build_teacher_context_trace()["text"]
        active_class_core = self.wiki.build_active_class_core_context_trace(class_id)[
            "text"
        ]
        prompt_stack = {
            "teacher_context": teacher_context,
            "active_class_core": active_class_core,
            "discussion_state": render_class_discussion_state(runtime.discussion_state)
            if runtime
            else "",
        }
        return DiscussTraceResponse(
            class_id=class_id,
            session_id=session_id,
            status=session.status,
            prompt_stack=prompt_stack,
            prompt_assembly=build_class_discussion_prompt_assembly(
                self.wiki,
                class_id,
                messages=session.messages,
                runtime=runtime,
                executive=session.executive,
            ),
            runtime=runtime_payload,
            messages=session.messages,
            artifact_markdown="",
            event_trace=session.debug_events,
            raw_evidence=dict(runtime.raw_store) if runtime else {},
        )

    def discard_draft(self, draft_id: str) -> None:
        if self.workflow_drafts is None:
            raise KeyError(f"Unknown workflow draft: {draft_id}")
        row = self.workflow_drafts.discard(draft_id)
        if row.backend_session_id in self.core.sessions:
            del self.core.sessions[row.backend_session_id]
