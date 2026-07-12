"""Ingest (update-memory) flow — thin adapter over ArtifactSessionService.

Session lifecycle + chat turn loop live in the shared core; this adapter only
maps the generic session/draft into the ingest API schemas and owns the
ingest-specific propose/commit steps (the propose_review_commit strategy).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
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
from app.services.artifact_session_service import (
    ArtifactSession,
    ArtifactSessionService,
)
from app.services.memory_candidate_ledger import MemoryCandidateLedger
from app.services.workflow_drafts import (
    WorkflowDraftConflict,
    WorkflowDraftIdentity,
    WorkflowDraftStore,
)
from app.teacher_agent.agents import AgentRunner
from app.teacher_agent.memory_update_state import (
    LessonResultPatch,
    MemoryRuntime,
    MemorySessionPatch,
    MemoryStatePatch,
    MemoryTargetPatch,
    apply_memory_state_patch,
    memory_api_payload,
    render_lesson_result_state,
    render_memory_briefs,
    render_memory_session_state,
    render_memory_target_state,
    render_memory_runtime,
)
from app.teacher_agent.executive_verification import (
    WriteVerificationBlocked,
    enforce_applied_write_verification,
)
from app.teacher_agent.prompt_trace import build_ingest_chat_prompt_trace
from app.teacher_agent.wiki import parsing as wiki_parsing
from app.teacher_agent.wiki_store import WikiStore

MODE = "ingest"


@dataclass(frozen=True)
class IngestStartHintResolution:
    lesson_date: str
    lesson_title: str
    intent: str
    target_kind: str
    source: str
    found: bool
    has_plan: bool
    has_results: bool
    draft_markdown: str
    confidence: str
    target_confirmed: bool
    needs_confirmation: bool

    @property
    def phase(self) -> str:
        return "collect_results" if self.target_confirmed else "identify_target"


class IngestService:
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
        self.core = ArtifactSessionService(
            wiki,
            agents,
            memory_candidate_ledger=memory_candidate_ledger,
            workflow_drafts=workflow_drafts,
            workspace_id=workspace_id,
        )

    def _to_model(self, s: ArtifactSession) -> IngestSession:
        memory_state = (
            memory_api_payload(s.runtime)
            if isinstance(s.runtime, MemoryRuntime)
            else None
        )
        return IngestSession(
            session_id=s.session_id,
            draft_id=s.draft_id,
            artifact_revision=s.artifact_revision,
            artifact_hash=s.artifact_hash,
            turn_in_progress=s.turn_in_progress,
            latest_turn_complete=s.latest_turn_complete,
            class_id=s.class_id,
            status=IngestSessionStatus(s.status),
            messages=s.messages,
            completeness=s.completeness or CompletenessChecklist(items=[]),
            memory_state=memory_state,
            memory_candidates=(memory_state or {}).get("memory_candidates", []),
        )

    def _title_template(self, lesson_date: str, title: str) -> str:
        md = self.wiki.empty_diary_template(lesson_date)
        # Hinted titles arrive from the plan artifact ("Lesson Plan — …");
        # strip that prefix so the diary heading and raw slug stay results-shaped.
        clean_title = wiki_parsing.clean_results_title(title)
        if clean_title:
            md = md.replace(
                f"# Lesson Results — {lesson_date} — ",
                f"# Lesson Results — {lesson_date} — {clean_title}",
                1,
            )
        return md

    def _resolve_start_hint(
        self, class_id: str, hint: IngestSessionStartRequest
    ) -> IngestStartHintResolution | None:
        lesson_date = (hint.lesson_date or "").strip()
        if not lesson_date:
            return None

        title = " ".join(hint.lesson_title.split())
        has_plan = False
        has_results = False
        found = False
        draft_markdown = ""
        try:
            detail = self.wiki.get_lesson_detail(class_id, lesson_date)
            found = True
            title = title or detail.title
            has_plan = bool(detail.lesson_plan_markdown)
            has_results = bool(detail.diary_markdown.strip())
            if has_results and hint.intent == "correct_existing_results":
                draft_markdown = detail.diary_markdown
            else:
                draft_markdown = self._title_template(lesson_date, title)
        except KeyError:
            draft_markdown = self._title_template(lesson_date, title)

        target_kind = hint.target_kind or ""
        if not target_kind:
            if has_results:
                target_kind = "taught_lesson"
            elif has_plan:
                target_kind = "planned_lesson"
            else:
                target_kind = "new_lesson"
        intent = hint.intent or ""
        if not intent:
            intent = (
                "correct_existing_results"
                if target_kind == "taught_lesson"
                else "update_missing_results"
                if target_kind == "planned_lesson"
                else "log_new_results"
            )

        confirmed = found and (has_plan or has_results)
        confidence = (
            "high"
            if confirmed
            else "medium"
            if hint.source == "teacher_explicit"
            else "low"
        )
        return IngestStartHintResolution(
            lesson_date=lesson_date,
            lesson_title=title,
            intent=intent,
            target_kind=target_kind,
            source=hint.source,
            found=found,
            has_plan=has_plan,
            has_results=has_results,
            draft_markdown=draft_markdown,
            confidence=confidence,
            target_confirmed=confirmed,
            needs_confirmation=not confirmed,
        )

    def _apply_start_hint(
        self, session: ArtifactSession, hint: IngestSessionStartRequest
    ) -> None:
        if not isinstance(session.runtime, MemoryRuntime):
            return
        resolved = self._resolve_start_hint(session.class_id, hint)
        if resolved is None:
            return
        self._apply_start_hint_resolution(session, resolved)

    def _apply_start_hint_resolution(
        self, session: ArtifactSession, resolved: IngestStartHintResolution
    ) -> None:
        if not isinstance(session.runtime, MemoryRuntime):
            return
        session.partial_markdown = resolved.draft_markdown
        decisions = []
        open_questions = []
        if resolved.target_confirmed:
            decisions.append(f"Use {resolved.lesson_date} as the update-memory target.")
        else:
            open_questions.append(
                f"Confirm whether {resolved.lesson_date} is the lesson to update."
            )
        apply_memory_state_patch(
            session.runtime,
            MemoryStatePatch(
                target=MemoryTargetPatch(
                    intent=resolved.intent,
                    lesson_date=resolved.lesson_date,
                    lesson_title=resolved.lesson_title,
                    target_kind=resolved.target_kind,
                    target_confirmed=resolved.target_confirmed,
                    source=resolved.source,
                    confidence=resolved.confidence,
                    plan_loaded=resolved.has_plan,
                    existing_results_loaded=resolved.has_results,
                    needs_confirmation=resolved.needs_confirmation,
                ),
                session_state=MemorySessionPatch(
                    phase=resolved.phase,
                    teacher_goal=(
                        f"Update lesson results for {resolved.lesson_date}"
                        + (
                            f" ({resolved.lesson_title})"
                            if resolved.lesson_title
                            else ""
                        )
                    ),
                    decisions=decisions,
                    open_questions=open_questions,
                ),
                lesson_result_state=LessonResultPatch(
                    missing_categories=[
                        item.label
                        for item in self.wiki.checklist_from_diary(
                            session.partial_markdown
                        ).items
                        if item.required and not item.complete
                    ],
                    draft_confidence="medium" if resolved.has_results else "low",
                ),
            ),
        )
        session.completeness = self.wiki.checklist_from_diary(session.partial_markdown)

    async def start_session(
        self, class_id: str, hint: IngestSessionStartRequest | None = None
    ) -> IngestSession:
        if isinstance(hint, dict):
            hint = IngestSessionStartRequest(**hint)
        resolved = self._resolve_start_hint(class_id, hint) if hint is not None else None
        runtime = MemoryRuntime()
        initial_markdown = self.wiki.empty_diary_template()
        identity = WorkflowDraftIdentity(
            workspace_id=self.workspace_id,
            class_id=class_id,
            mode=MODE,
            intent=resolved.intent if resolved else "free_entry",
            target_kind=resolved.target_kind if resolved else "",
            lesson_date=resolved.lesson_date if resolved else "",
            lesson_title=resolved.lesson_title if resolved else "",
        )
        session = ArtifactSession(
            session_id="",
            class_id=class_id,
            mode=MODE,
            status="chatting",
            partial_markdown=initial_markdown,
            runtime=runtime,
        )
        if resolved is not None:
            self._apply_start_hint_resolution(session, resolved)
            initial_markdown = session.partial_markdown
            runtime = session.runtime
        session = await self.core.start_session(
            MODE,
            class_id,
            draft_identity=identity if self.workflow_drafts is not None else None,
            initial_markdown=initial_markdown,
            initial_runtime=runtime,
        )
        if self.workflow_drafts is None and resolved is not None:
            self._apply_start_hint_resolution(session, resolved)
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
        session = self.core.get_session(session_id)
        completeness = result.completeness or self.wiki.checklist_from_diary(
            result.markdown
        )
        return ChatResponse(
            reply=result.reply,
            diary_markdown=result.markdown,
            draft_id=session.draft_id,
            artifact_revision=session.artifact_revision,
            artifact_hash=session.artifact_hash,
            completeness=completeness,
            ready_to_propose=result.ready,
            last_change_summary=(result.memory or {}).get("last_change_summary", ""),
            memory_state=result.memory,
            memory_candidates=(result.memory or {}).get("memory_candidates", []),
            executive_state=result.executive,
        )

    async def chat_stream(
        self,
        session_id: str,
        message: str,
        diary_markdown: str | None = None,
        attachments: list[ChatAttachment] | None = None,
    ) -> AsyncIterator[str]:
        stream = self.core.chat_stream(session_id, message, diary_markdown, attachments)
        try:
            async for line in stream:
                yield line
        finally:
            await stream.aclose()

    def update_draft(self, session_id: str, diary_markdown: str) -> IngestDraft:
        self.core.require_latest_turn_complete(session_id, "update the draft")
        draft = self.core.update_draft(session_id, diary_markdown)
        assert isinstance(draft, IngestDraft)
        session = self.core.get_session(session_id)
        if isinstance(session.runtime, MemoryRuntime):
            draft.memory_state = memory_api_payload(session.runtime)
            draft.memory_candidates = draft.memory_state.get("memory_candidates", [])
        return draft

    async def propose(self, session_id: str) -> IngestDraft:
        session = self.core.get_session(session_id)
        self.core.require_latest_turn_complete(session_id, "prepare wiki updates")
        diary_md = session.partial_markdown
        if not diary_md.strip():
            diary_md = await self.agents.compile_diary(
                session.class_id, session.messages
            )
        verification = await self.agents.verify_artifact_for_write(
            session.class_id, "lesson results", diary_md, session.executive
        )
        try:
            enforce_applied_write_verification(
                session.executive,
                artifact=diary_md,
                verification=verification,
                action="ingest_propose",
                structurally_ready=self.wiki.is_diary_complete(diary_md),
            )
        except WriteVerificationBlocked:
            self.core._persist_session(session)
            raise
        draft = self.core.update_draft(session_id, diary_md)
        session = self.core.get_session(session_id)
        if self.workflow_drafts is not None and session.draft_id:
            self.workflow_drafts.mark_review_snapshot(
                session.draft_id,
                revision=session.artifact_revision,
                artifact_hash_value=session.artifact_hash,
            )
        self.core.set_status(session_id, IngestSessionStatus.reviewing.value)
        assert isinstance(draft, IngestDraft)
        if isinstance(session.runtime, MemoryRuntime):
            draft.memory_state = memory_api_payload(session.runtime)
            draft.memory_candidates = draft.memory_state.get("memory_candidates", [])
        return draft

    def get_draft(self, session_id: str) -> IngestDraft:
        draft = self.core.get_draft(session_id)
        assert isinstance(draft, IngestDraft)
        session = self.core.get_session(session_id)
        if isinstance(session.runtime, MemoryRuntime):
            draft.memory_state = memory_api_payload(session.runtime)
            draft.memory_candidates = draft.memory_state.get("memory_candidates", [])
        return draft

    def trace(self, class_id: str, session_id: str) -> MemoryTraceResponse:
        session = self.core.get_session(session_id)
        if session.class_id != class_id:
            raise KeyError("Session class mismatch")
        runtime = (
            session.runtime if isinstance(session.runtime, MemoryRuntime) else None
        )
        runtime_payload = memory_api_payload(runtime) if runtime else {}
        prompt_stack = {
            "teacher_context": self.wiki.build_teacher_context_trace()["text"],
            "active_class_core": self.wiki.build_active_class_core_context_trace(
                class_id
            )["text"],
            "ingest_context": self.wiki.build_ingest_context_slim(class_id),
            "memory_target_state": render_memory_target_state(runtime.target)
            if runtime
            else "",
            "memory_session_state": render_memory_session_state(runtime.session_state)
            if runtime
            else "",
            "lesson_result_state": render_lesson_result_state(
                runtime.lesson_result_state
            )
            if runtime
            else "",
            "memory_evidence_briefs": render_memory_briefs(runtime.evidence_briefs)
            if runtime
            else "",
            "memory_runtime": render_memory_runtime(runtime) if runtime else "",
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
                executive=session.executive,
            ),
            runtime=runtime_payload,
            messages=session.messages,
            artifact_markdown=session.partial_markdown,
            event_trace=session.debug_events,
            raw_evidence=dict(runtime.raw_store) if runtime else {},
        )

    async def commit(self, req: CommitIngestRequest) -> CommitIngestResponse:
        session = self.core.get_session(req.session_id)
        self.core.require_latest_turn_complete(req.session_id, "save memory")
        diary_markdown = req.diary_markdown
        if req.draft_id:
            if req.draft_id != session.draft_id:
                raise KeyError("Draft/session mismatch")
            expected_revision = (
                req.source_artifact_revision
                if req.source_artifact_revision is not None
                else req.expected_artifact_revision
            )
            expected_hash = (
                req.source_artifact_hash
                if req.source_artifact_hash is not None
                else req.expected_artifact_hash
            )
            if expected_revision is None or expected_hash is None:
                raise ValueError("draft revision/hash required")
            if self.workflow_drafts is None:
                if (
                    session.artifact_revision != expected_revision
                    or session.artifact_hash != expected_hash
                ):
                    raise ValueError("draft_changed_since_review_created")
            else:
                try:
                    row = self.workflow_drafts.validate_review_snapshot(
                        req.draft_id,
                        expected_revision=expected_revision,
                        expected_hash=expected_hash,
                    )
                except WorkflowDraftConflict as exc:
                    raise ValueError(str(exc)) from exc
                diary_markdown = row.artifact_markdown
        verification = await self.agents.verify_artifact_for_write(
            session.class_id, "lesson results", diary_markdown, session.executive
        )
        try:
            enforce_applied_write_verification(
                session.executive,
                artifact=diary_markdown,
                verification=verification,
                action="ingest_commit",
                structurally_ready=self.wiki.is_diary_complete(diary_markdown),
            )
        except WriteVerificationBlocked:
            self.core._persist_session(session)
            raise
        lesson_date = (
            self.wiki.extract_date_from_diary(diary_markdown)
            or date.today().isoformat()
        )
        title = self.wiki.extract_title(diary_markdown) or "Lesson"
        raw_path, applied, log_id = self.wiki.commit_ingest(
            session.class_id,
            diary_markdown,
            req.approved_updates,
            req.session_id,
        )
        self.core.set_status(req.session_id, IngestSessionStatus.committed.value)
        if self.workflow_drafts is not None and session.draft_id:
            self.workflow_drafts.mark_committed(session.draft_id)
        return CommitIngestResponse(
            raw_diary_path=raw_path,
            applied_wiki_paths=applied,
            log_entry_id=log_id,
            lesson_date=lesson_date,
            title=title,
        )

    def discard_draft(self, draft_id: str) -> None:
        if self.workflow_drafts is None:
            raise KeyError(f"Unknown workflow draft: {draft_id}")
        row = self.workflow_drafts.discard(draft_id)
        if row.backend_session_id in self.core.sessions:
            del self.core.sessions[row.backend_session_id]
