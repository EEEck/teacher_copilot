"""Ingest (update-memory) flow — thin adapter over ArtifactSessionService.

Session lifecycle + chat turn loop live in the shared core; this adapter only
maps the generic session/draft into the ingest API schemas and owns the
ingest-specific propose/commit steps (the propose_review_commit strategy).
"""

from __future__ import annotations

from datetime import date

from app.schemas.api import (
    ChatAttachment,
    ChatResponse,
    CommitIngestRequest,
    CommitIngestResponse,
    CompletenessChecklist,
    IngestDraft,
    IngestSession,
    IngestSessionStatus,
)
from app.services.artifact_session_service import ArtifactSession, ArtifactSessionService
from app.teacher_agent.agents import AgentRunner
from app.teacher_agent.wiki_store import WikiStore

MODE = "ingest"


class IngestService:
    def __init__(self, wiki: WikiStore, agents: AgentRunner) -> None:
        self.wiki = wiki
        self.agents = agents
        self.core = ArtifactSessionService(wiki, agents)

    def _to_model(self, s: ArtifactSession) -> IngestSession:
        return IngestSession(
            session_id=s.session_id,
            class_id=s.class_id,
            status=IngestSessionStatus(s.status),
            messages=s.messages,
            completeness=s.completeness or CompletenessChecklist(items=[]),
        )

    async def start_session(self, class_id: str) -> IngestSession:
        session = await self.core.start_session(MODE, class_id)
        return self._to_model(session)

    def get_session(self, session_id: str) -> ArtifactSession:
        return self.core.get_session(session_id)

    async def chat(
        self,
        session_id: str,
        message: str,
        diary_markdown: str | None = None,
        attachments: list[ChatAttachment] | None = None,
    ) -> ChatResponse:
        result = await self.core.chat(session_id, message, diary_markdown, attachments)
        completeness = result.completeness or self.wiki.checklist_from_diary(result.markdown)
        return ChatResponse(
            reply=result.reply,
            diary_markdown=result.markdown,
            completeness=completeness,
            ready_to_propose=result.ready,
        )

    def update_draft(self, session_id: str, diary_markdown: str) -> IngestDraft:
        draft = self.core.update_draft(session_id, diary_markdown)
        assert isinstance(draft, IngestDraft)
        return draft

    async def propose(self, session_id: str) -> IngestDraft:
        session = self.core.get_session(session_id)
        diary_md = session.partial_markdown
        if not diary_md.strip():
            diary_md = await self.agents.compile_diary(session.class_id, session.messages)
        draft = self.core.update_draft(session_id, diary_md)
        self.core.set_status(session_id, IngestSessionStatus.reviewing.value)
        assert isinstance(draft, IngestDraft)
        return draft

    def get_draft(self, session_id: str) -> IngestDraft:
        draft = self.core.get_draft(session_id)
        assert isinstance(draft, IngestDraft)
        return draft

    def commit(self, req: CommitIngestRequest) -> CommitIngestResponse:
        session = self.core.get_session(req.session_id)
        lesson_date = (
            self.wiki._extract_date_from_diary(req.diary_markdown) or date.today().isoformat()
        )
        title = self.wiki._extract_title(req.diary_markdown) or "Lesson"
        raw_path, applied, log_id = self.wiki.commit_ingest(
            session.class_id,
            req.diary_markdown,
            req.approved_updates,
            req.session_id,
        )
        self.core.set_status(req.session_id, IngestSessionStatus.committed.value)
        return CommitIngestResponse(
            raw_diary_path=raw_path,
            applied_wiki_paths=applied,
            log_entry_id=log_id,
            lesson_date=lesson_date,
            title=title,
        )
