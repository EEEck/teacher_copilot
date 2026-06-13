"""Ingest (update-memory) flow — thin adapter over ArtifactSessionService.

Session lifecycle + chat turn loop live in the shared core; this adapter only
maps the generic session/draft into the ingest API schemas and owns the
ingest-specific propose/commit steps (the propose_review_commit strategy).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date

from app.schemas.api import (
    ChatAttachment,
    ChatResponse,
    CommitIngestRequest,
    CommitIngestResponse,
    CompletenessChecklist,
    IngestDraft,
    IngestSession,
    IngestSessionStartRequest,
    IngestSessionStatus,
    MemoryTraceResponse,
)
from app.services.artifact_session_service import ArtifactSession, ArtifactSessionService
from app.teacher_agent.agents import AgentRunner
from app.teacher_agent.memory_update_state import (
    LessonResultPatch,
    MemoryRuntime,
    MemorySessionPatch,
    MemoryStatePatch,
    MemoryTargetPatch,
    apply_memory_state_patch,
    memory_api_payload,
    render_memory_runtime,
)
from app.teacher_agent.prompt_trace import build_ingest_chat_prompt_trace
from app.teacher_agent.wiki_store import WikiStore

MODE = "ingest"


class IngestService:
    def __init__(self, wiki: WikiStore, agents: AgentRunner) -> None:
        self.wiki = wiki
        self.agents = agents
        self.core = ArtifactSessionService(wiki, agents)

    def _to_model(self, s: ArtifactSession) -> IngestSession:
        memory_state = (
            memory_api_payload(s.runtime)
            if isinstance(s.runtime, MemoryRuntime)
            else None
        )
        return IngestSession(
            session_id=s.session_id,
            class_id=s.class_id,
            status=IngestSessionStatus(s.status),
            messages=s.messages,
            completeness=s.completeness or CompletenessChecklist(items=[]),
            memory_state=memory_state,
        )

    def _title_template(self, lesson_date: str, title: str) -> str:
        md = self.wiki.empty_diary_template(lesson_date)
        clean_title = " ".join((title or "").split())
        if clean_title:
            md = md.replace(
                f"# Lesson Results — {lesson_date} — ",
                f"# Lesson Results — {lesson_date} — {clean_title}",
                1,
            )
        return md

    def _apply_start_hint(
        self, session: ArtifactSession, hint: IngestSessionStartRequest
    ) -> None:
        if not isinstance(session.runtime, MemoryRuntime):
            return
        lesson_date = (hint.lesson_date or "").strip()
        if not lesson_date:
            return

        title = hint.lesson_title.strip()
        has_plan = False
        has_results = False
        try:
            detail = self.wiki.get_lesson_detail(session.class_id, lesson_date)
            title = title or detail.title
            has_plan = bool(detail.lesson_plan_markdown)
            has_results = bool(detail.diary_markdown.strip())
            if has_results and hint.intent == "correct_existing_results":
                session.partial_markdown = detail.diary_markdown
            else:
                session.partial_markdown = self._title_template(lesson_date, title)
        except KeyError:
            session.partial_markdown = self._title_template(lesson_date, title)

        target_kind = hint.target_kind.strip()
        if not target_kind:
            if has_results:
                target_kind = "taught_lesson"
            elif has_plan:
                target_kind = "planned_lesson"
            else:
                target_kind = "new_lesson"
        intent = hint.intent.strip()
        if not intent:
            intent = (
                "correct_existing_results"
                if target_kind == "taught_lesson"
                else "update_missing_results"
                if target_kind == "planned_lesson"
                else "log_new_results"
            )
        apply_memory_state_patch(
            session.runtime,
            MemoryStatePatch(
                target=MemoryTargetPatch(
                    intent=intent,
                    lesson_date=lesson_date,
                    lesson_title=title,
                    target_kind=target_kind,
                    target_confirmed=True,
                    source=hint.source or "teacher_explicit",
                    confidence="high",
                    plan_loaded=has_plan,
                    existing_results_loaded=has_results,
                    needs_confirmation=False,
                ),
                session_state=MemorySessionPatch(
                    phase="collect_results",
                    teacher_goal=(
                        f"Update lesson results for {lesson_date}"
                        + (f" ({title})" if title else "")
                    ),
                    decisions=[f"Use {lesson_date} as the update-memory target."],
                ),
                lesson_result_state=LessonResultPatch(
                    missing_categories=[
                        item.label
                        for item in self.wiki.checklist_from_diary(
                            session.partial_markdown
                        ).items
                        if item.required and not item.complete
                    ],
                    draft_confidence="medium" if has_results else "low",
                ),
            ),
        )
        session.completeness = self.wiki.checklist_from_diary(session.partial_markdown)

    async def start_session(
        self, class_id: str, hint: IngestSessionStartRequest | None = None
    ) -> IngestSession:
        session = await self.core.start_session(MODE, class_id)
        if hint is not None:
            self._apply_start_hint(session, hint)
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
            last_change_summary=(result.memory or {}).get("last_change_summary", ""),
            memory_state=result.memory,
        )

    async def chat_stream(
        self,
        session_id: str,
        message: str,
        diary_markdown: str | None = None,
        attachments: list[ChatAttachment] | None = None,
    ) -> AsyncIterator[str]:
        async for line in self.core.chat_stream(
            session_id, message, diary_markdown, attachments
        ):
            yield line

    def update_draft(self, session_id: str, diary_markdown: str) -> IngestDraft:
        draft = self.core.update_draft(session_id, diary_markdown)
        assert isinstance(draft, IngestDraft)
        session = self.core.get_session(session_id)
        if isinstance(session.runtime, MemoryRuntime):
            draft.memory_state = memory_api_payload(session.runtime)
        return draft

    async def propose(self, session_id: str) -> IngestDraft:
        session = self.core.get_session(session_id)
        diary_md = session.partial_markdown
        if not diary_md.strip():
            diary_md = await self.agents.compile_diary(session.class_id, session.messages)
        draft = self.core.update_draft(session_id, diary_md)
        self.core.set_status(session_id, IngestSessionStatus.reviewing.value)
        assert isinstance(draft, IngestDraft)
        if isinstance(session.runtime, MemoryRuntime):
            draft.memory_state = memory_api_payload(session.runtime)
        return draft

    def get_draft(self, session_id: str) -> IngestDraft:
        draft = self.core.get_draft(session_id)
        assert isinstance(draft, IngestDraft)
        session = self.core.get_session(session_id)
        if isinstance(session.runtime, MemoryRuntime):
            draft.memory_state = memory_api_payload(session.runtime)
        return draft

    def trace(self, class_id: str, session_id: str) -> MemoryTraceResponse:
        session = self.core.get_session(session_id)
        if session.class_id != class_id:
            raise KeyError("Session class mismatch")
        runtime = session.runtime if isinstance(session.runtime, MemoryRuntime) else None
        runtime_payload = memory_api_payload(runtime) if runtime else {}
        prompt_stack = {
            "ingest_context": self.wiki.build_ingest_context_slim(class_id),
            "memory_runtime": render_memory_runtime(runtime)
            if runtime
            else "",
            "current_diary_markdown": session.partial_markdown,
        }
        return MemoryTraceResponse(
            class_id=class_id,
            session_id=session_id,
            status=session.status,
            prompt_stack=prompt_stack,
            prompt_assembly=build_ingest_chat_prompt_trace(
                self.wiki,
                class_id,
                messages=session.messages,
                current_diary=session.partial_markdown,
                runtime=runtime,
            ),
            runtime=runtime_payload,
            messages=session.messages,
            artifact_markdown=session.partial_markdown,
            event_trace=session.debug_events,
            raw_evidence=dict(runtime.raw_store) if runtime else {},
        )

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
