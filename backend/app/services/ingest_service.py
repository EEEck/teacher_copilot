"""In-memory ingest session store and orchestration."""

from __future__ import annotations

import uuid
from datetime import date
from dataclasses import dataclass, field

from app.schemas.api import (
    ChatAttachment,
    ChatMessage,
    ChatResponse,
    CommitIngestRequest,
    CommitIngestResponse,
    IngestDraft,
    IngestSession,
    IngestSessionStatus,
)
from app.teacher_agent.agents import AgentRunner
from app.teacher_agent.wiki_store import WikiStore


@dataclass
class SessionStore:
    sessions: dict[str, IngestSession] = field(default_factory=dict)
    partial_diaries: dict[str, str] = field(default_factory=dict)
    drafts: dict[str, IngestDraft] = field(default_factory=dict)


class IngestService:
    def __init__(self, wiki: WikiStore, agents: AgentRunner) -> None:
        self.wiki = wiki
        self.agents = agents
        self.store = SessionStore()

    def start_session(self, class_id: str) -> IngestSession:
        session_id = str(uuid.uuid4())
        session = IngestSession(
            session_id=session_id,
            class_id=class_id,
            status=IngestSessionStatus.chatting,
            messages=[],
            completeness=self.wiki.checklist_from_diary(self.wiki.empty_diary_template()),
        )
        self.store.sessions[session_id] = session
        self.store.partial_diaries[session_id] = self.wiki.empty_diary_template()
        return session

    def get_session(self, session_id: str) -> IngestSession:
        if session_id not in self.store.sessions:
            raise KeyError(f"Unknown session: {session_id}")
        return self.store.sessions[session_id]

    def _build_draft(self, class_id: str, diary_md: str) -> IngestDraft:
        _, proposals = self.wiki.compile_from_diary(class_id, diary_md)
        return IngestDraft(
            diary_markdown=diary_md,
            wiki_proposals=proposals,
            completeness=self.wiki.checklist_from_diary(diary_md),
        )

    def chat(
        self,
        session_id: str,
        message: str,
        diary_markdown: str | None = None,
        attachments: list[ChatAttachment] | None = None,
    ) -> ChatResponse:
        session = self.get_session(session_id)
        if diary_markdown is not None:
            self.store.partial_diaries[session_id] = diary_markdown

        session.messages.append(ChatMessage(role="user", content=message))
        partial = self.store.partial_diaries.get(session_id, "")

        reply, diary_md, checklist, ready = self.agents.ingest_chat(
            session.class_id,
            session.messages,
            partial,
            attachments=attachments or [],
        )
        session.messages.append(ChatMessage(role="assistant", content=reply))
        session.completeness = checklist
        self.store.partial_diaries[session_id] = diary_md
        self.store.drafts[session_id] = self._build_draft(session.class_id, diary_md)
        if ready:
            session.status = IngestSessionStatus.ready_to_propose

        return ChatResponse(
            reply=reply,
            diary_markdown=diary_md,
            completeness=checklist,
            ready_to_propose=ready,
        )

    def update_draft(self, session_id: str, diary_markdown: str) -> IngestDraft:
        session = self.get_session(session_id)
        self.store.partial_diaries[session_id] = diary_markdown
        draft = self._build_draft(session.class_id, diary_markdown)
        self.store.drafts[session_id] = draft
        session.completeness = draft.completeness
        if self.wiki.is_diary_complete(diary_markdown):
            session.status = IngestSessionStatus.ready_to_propose
        return draft

    def propose(self, session_id: str) -> IngestDraft:
        session = self.get_session(session_id)
        diary_md = self.store.partial_diaries.get(session_id, "")
        if not diary_md.strip():
            diary_md = self.agents.compile_diary(session.class_id, session.messages)
        self.store.partial_diaries[session_id] = diary_md
        draft = self._build_draft(session.class_id, diary_md)
        self.store.drafts[session_id] = draft
        session.completeness = draft.completeness
        session.status = IngestSessionStatus.reviewing
        return draft

    def get_draft(self, session_id: str) -> IngestDraft:
        if session_id in self.store.drafts:
            return self.store.drafts[session_id]
        session = self.get_session(session_id)
        diary = self.store.partial_diaries.get(session_id, self.wiki.empty_diary_template())
        _, proposals = self.wiki.compile_from_diary(session.class_id, diary)
        return IngestDraft(
            diary_markdown=diary,
            wiki_proposals=proposals,
            completeness=self.wiki.checklist_from_diary(diary),
        )

    def commit(self, req: CommitIngestRequest) -> CommitIngestResponse:
        session = self.get_session(req.session_id)
        lesson_date = self.wiki._extract_date_from_diary(req.diary_markdown) or date.today().isoformat()
        title = self.wiki._extract_title(req.diary_markdown) or "Lesson"
        raw_path, applied, log_id = self.wiki.commit_ingest(
            session.class_id,
            req.diary_markdown,
            req.approved_updates,
            req.session_id,
        )
        session.status = IngestSessionStatus.committed
        return CommitIngestResponse(
            raw_diary_path=raw_path,
            applied_wiki_paths=applied,
            log_entry_id=log_id,
            lesson_date=lesson_date,
            title=title,
        )
