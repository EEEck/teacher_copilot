"""Lesson-plan flow — thin adapter over ArtifactSessionService.

Session lifecycle + chat turn loop live in the shared core; this adapter only
maps the generic session/draft into the plan API schemas and owns the
plan-specific single_file_save step plus the standalone one-shot generator.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from pathlib import Path

from app.schemas.api import (
    ChatAttachment,
    LessonPlan,
    PlanChatResponse,
    PlanDraft,
    PlanLessonRequest,
    PlanMaterialSummary,
    PlanSession,
    PlanSessionStatus,
    PlanTraceResponse,
    SavePlanRequest,
    SavePlanResponse,
)
from app.services.materials_ocr_prompts import materials_ocr_context_from_wiki
from app.services.materials_scratch import (
    MaterialArmName,
    attach_prebuilt_package,
    ocr_pdf_to_scratch,
    promote_scratch_material,
    resolve_material_asset_file,
    write_lesson_materials_json,
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
from app.teacher_agent.planning_state import (
    planning_api_payload,
    render_briefs,
    render_lesson_planning_state,
    render_session_state,
)
from app.teacher_agent.executive_verification import (
    WriteVerificationBlocked,
    enforce_applied_write_verification,
)
from app.teacher_agent.prompt_trace import build_plan_chat_prompt_trace
from app.teacher_agent.wiki_store import WikiStore
from app.teacher_agent.memory_capture import (
    discipline_memory_candidates,
    occasion_key_for,
    runtime_candidates_to_ledger_rows,
)

MODE = "plan"


class PlanService:
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

    def _to_model(self, s: ArtifactSession) -> PlanSession:
        return PlanSession(
            session_id=s.session_id,
            draft_id=s.draft_id,
            artifact_revision=s.artifact_revision,
            artifact_hash=s.artifact_hash,
            turn_in_progress=s.turn_in_progress,
            latest_turn_complete=s.latest_turn_complete,
            class_id=s.class_id,
            status=PlanSessionStatus(s.status),
            messages=s.messages,
            opening_message=s.opening_message,
        )

    async def start_session(self, class_id: str) -> PlanSession:
        session = await self.core.start_session(
            MODE,
            class_id,
            draft_identity=WorkflowDraftIdentity(
                workspace_id=self.workspace_id,
                class_id=class_id,
                mode=MODE,
                intent="create_plan",
            )
            if self.workflow_drafts is not None
            else None,
        )
        return self._to_model(session)

    def get_session(self, session_id: str) -> ArtifactSession:
        return self.core.get_session(session_id)

    def get_draft(self, session_id: str) -> PlanDraft:
        draft = self.core.get_draft(session_id)
        assert isinstance(draft, PlanDraft)
        session = self.core.get_session(session_id)
        if session.runtime and session.runtime.materials:
            draft.materials = [
                self._material_summary(entry) for entry in session.runtime.materials
            ]
        return draft

    def _material_summary(self, entry) -> PlanMaterialSummary:
        return PlanMaterialSummary(
            material_id=entry.material_id,
            arm=entry.arm,
            title=entry.title,
            summary=entry.summary,
            page_count=entry.page_count or len(entry.page_numbers),
            asset_counts=dict(entry.asset_counts or {}),
            promoted=bool(entry.promoted),
        )

    def upload_material(
        self,
        class_id: str,
        session_id: str,
        *,
        pdf_bytes: bytes,
        filename: str,
        arm: MaterialArmName,
        page_range: str | None = None,
        ocr_runner=None,
    ) -> PlanMaterialSummary:
        session = self.core.get_session(session_id)
        if session.class_id != class_id:
            raise KeyError("Session class mismatch")
        if session.runtime is None:
            from app.teacher_agent.planning_state import PlanRuntime

            session.runtime = PlanRuntime()
        ocr_context = materials_ocr_context_from_wiki(self.wiki, class_id, arm)
        entry = ocr_pdf_to_scratch(
            pdf_bytes=pdf_bytes,
            filename=filename,
            session_id=session_id,
            class_id=class_id,
            arm=arm,
            ocr_context=ocr_context,
            page_range=page_range,
            ocr_runner=ocr_runner,
        )
        session.runtime.upsert_material(entry)
        self.core._persist_session(session)
        return self._material_summary(entry)

    def attach_prebuilt_material(
        self,
        class_id: str,
        session_id: str,
        *,
        package_dir: Path,
        arm: MaterialArmName = "textbook",
        material_id: str | None = None,
    ) -> PlanMaterialSummary:
        """Seed session materials from a prebuilt OCR package (evals)."""
        session = self.core.get_session(session_id)
        if session.class_id != class_id:
            raise KeyError("Session class mismatch")
        if session.runtime is None:
            from app.teacher_agent.planning_state import PlanRuntime

            session.runtime = PlanRuntime()
        entry = attach_prebuilt_package(
            session_id=session_id,
            package_src=Path(package_dir),
            arm=arm,
            material_id=material_id,
        )
        session.runtime.upsert_material(entry)
        self.core._persist_session(session)
        return self._material_summary(entry)

    def resolve_material_asset(
        self,
        class_id: str,
        session_id: str,
        material_id: str,
        filename: str,
    ) -> Path:
        session = self.core.get_session(session_id)
        if session.class_id != class_id:
            raise KeyError("Session class mismatch")
        entry = None
        if session.runtime and session.runtime.materials:
            for item in session.runtime.materials:
                if item.material_id == material_id:
                    entry = item
                    break
        if entry is None:
            raise KeyError(f"Unknown material_id: {material_id}")
        return resolve_material_asset_file(
            session_id=session_id,
            material_id=material_id,
            filename=filename,
            entry=entry,
            wiki_root=Path(self.wiki.root),
            class_id=class_id,
        )

    async def chat(
        self,
        session_id: str,
        message: str,
        plan_markdown: str | None = None,
        attachments: list[ChatAttachment] | None = None,
    ) -> PlanChatResponse:
        result = await self.core.chat(session_id, message, plan_markdown, attachments)
        session = self.core.get_session(session_id)
        planning = result.planning or {}
        return PlanChatResponse(
            reply=result.reply,
            plan_markdown=result.markdown,
            draft_id=session.draft_id,
            artifact_revision=session.artifact_revision,
            artifact_hash=session.artifact_hash,
            ready_to_save=result.ready,
            phase=planning.get("phase"),
            last_change_summary=planning.get("last_change_summary", ""),
            session_state=planning.get("session_state"),
            lesson_planning_state=planning.get("lesson_planning_state"),
            memory_candidates=planning.get("memory_candidates", []),
            executive_state=result.executive,
        )

    async def chat_stream(
        self,
        session_id: str,
        message: str,
        plan_markdown: str | None = None,
        attachments: list[ChatAttachment] | None = None,
    ) -> AsyncIterator[str]:
        async for line in self.core.chat_stream(
            session_id, message, plan_markdown, attachments
        ):
            yield line

    def update_draft(self, session_id: str, plan_markdown: str) -> PlanDraft:
        draft = self.core.update_draft(session_id, plan_markdown)
        assert isinstance(draft, PlanDraft)
        return draft

    def trace(self, class_id: str, session_id: str) -> PlanTraceResponse:
        session = self.core.get_session(session_id)
        if session.class_id != class_id:
            raise KeyError("Session class mismatch")
        runtime = session.runtime
        runtime_payload = planning_api_payload(runtime) if runtime else {}
        teacher_context = self.wiki.build_teacher_context_trace()["text"]
        active_class_core = self.wiki.build_active_class_core_context_trace(class_id)[
            "text"
        ]
        prompt_stack = {
            "teacher_context": teacher_context,
            "active_class_core": active_class_core,
            "class_slice": active_class_core,
            "teacher_profile": self.wiki.read_user_profile(),
            "copilot_profile": self.wiki.read_copilot_profile(class_id),
            "session_state": render_session_state(runtime.session_state)
            if runtime
            else "",
            "lesson_planning_state": render_lesson_planning_state(
                runtime.lesson_planning_state
            )
            if runtime
            else "",
            "current_lessonplan_md": session.partial_markdown,
            "evidence_briefs": render_briefs(runtime.evidence_briefs)
            if runtime
            else "",
        }
        return PlanTraceResponse(
            class_id=class_id,
            session_id=session_id,
            status=session.status,
            prompt_stack=prompt_stack,
            prompt_assembly=build_plan_chat_prompt_trace(
                self.wiki,
                class_id,
                messages=session.messages,
                current_plan=session.partial_markdown,
                runtime=runtime,
                executive=session.executive,
            ),
            runtime=runtime_payload,
            messages=session.messages,
            artifact_markdown=session.partial_markdown,
            event_trace=session.debug_events,
            raw_evidence=dict(runtime.raw_store) if runtime else {},
        )

    async def save(self, class_id: str, req: SavePlanRequest) -> SavePlanResponse:
        session = self.core.get_session(req.session_id)
        if session.class_id != class_id:
            raise KeyError("Session class mismatch")
        try:
            lesson_date = date.fromisoformat(req.lesson_date).isoformat()
        except ValueError as exc:
            raise ValueError("lesson_date must be YYYY-MM-DD") from exc
        plan_markdown = req.plan_markdown
        if req.draft_id:
            if req.draft_id != session.draft_id:
                raise KeyError("Draft/session mismatch")
            if req.expected_artifact_revision is None or req.expected_artifact_hash is None:
                raise ValueError("draft revision/hash required")
            if self.workflow_drafts is None:
                if (
                    session.artifact_revision != req.expected_artifact_revision
                    or session.artifact_hash != req.expected_artifact_hash
                ):
                    raise ValueError("draft_changed_since_review_created")
            else:
                try:
                    row = self.workflow_drafts.validate_current_snapshot(
                        req.draft_id,
                        expected_revision=req.expected_artifact_revision,
                        expected_hash=req.expected_artifact_hash,
                    )
                except WorkflowDraftConflict as exc:
                    raise ValueError(str(exc)) from exc
                plan_markdown = row.artifact_markdown
        if not plan_markdown.strip():
            raise ValueError("plan_markdown must not be empty")
        # Verify and gate the EXACT (undated) draft the teacher reviewed. The
        # lesson date is a deterministic final-write stamp, not reviewed content,
        # so it must not enter the verified fingerprint: stamping before the gate
        # changed the artifact fingerprint and let a completed safety-hold review
        # slip past evaluate_write_gate (the report stayed pinned to the un-stamped
        # fingerprint). The draft/session therefore stays undated; only the
        # persisted file carries the date, stamped after the gate passes.
        await self.core.ensure_plan_judgement(req.session_id, plan_markdown)
        verification = await self.agents.verify_artifact_for_write(
            class_id, "lesson plan", plan_markdown, session.executive
        )
        try:
            enforce_applied_write_verification(
                session.executive,
                artifact=plan_markdown,
                verification=verification,
                action="plan_save",
                # Markdown format is teacher-controlled. The write gate owns
                # revision integrity and severe-safety findings, not headings.
                structurally_ready=True,
            )
        except WriteVerificationBlocked:
            self.core._persist_session(session)
            raise
        # Gate passed — stamp the chosen lesson date only into the persisted plan
        # so the stored file matches its lesson folder (audit H2). The reviewed
        # draft stays undated.
        stamped_markdown = self.wiki.normalize_plan_target_date(plan_markdown, lesson_date)
        title = self.wiki.extract_title(stamped_markdown) or "Lesson plan"
        path = self.wiki.save_lesson_plan(class_id, lesson_date, stamped_markdown)
        promoted_ids: list[str] = []
        if session.runtime and session.runtime.materials:
            for entry in list(session.runtime.materials):
                if not entry.scratch_path:
                    continue
                promoted = promote_scratch_material(
                    wiki_root=self.wiki.root,
                    class_id=class_id,
                    entry=entry,
                )
                session.runtime.upsert_material(promoted)
                promoted_ids.append(promoted.material_id)
            if promoted_ids:
                write_lesson_materials_json(
                    wiki_root=self.wiki.root,
                    class_id=class_id,
                    lesson_date=lesson_date,
                    material_ids=promoted_ids,
                )
            self.core._persist_session(session)
        self.core.set_status(req.session_id, PlanSessionStatus.saved.value)
        if self.workflow_drafts is not None and session.draft_id:
            self.workflow_drafts.mark_saved(session.draft_id)
        candidates: list[dict] = []
        if session.runtime:
            subject = self.wiki.get_class(class_id).subject
            turn_index = sum(1 for msg in session.messages if msg.role == "user")
            last_teacher_message = next(
                (msg.content for msg in reversed(session.messages) if msg.role == "user"),
                "",
            )
            disciplined_candidates = discipline_memory_candidates(
                session.runtime.memory_candidates,
                teacher_message=last_teacher_message,
            )
            # Match the anchor persisted during chat turns: plan sessions
            # anchor on the session, not the lesson (the chat-turn captures
            # already landed with this key; save only builds the display
            # payload, it does not re-persist).
            occasion_key = occasion_key_for(session.mode, session.session_id)
            rows = runtime_candidates_to_ledger_rows(
                disciplined_candidates,
                class_id=class_id,
                subject=subject,
                workflow=session.mode,
                session_id=session.session_id,
                turn_index=turn_index,
                occasion_key=occasion_key,
            )
            for candidate, row in zip(disciplined_candidates, rows):
                payload = candidate.model_dump()
                payload["candidate_id"] = row.id
                payload["occasion_key"] = row.occasion_key
                candidates.append(payload)
        planning = planning_api_payload(session.runtime) if session.runtime else {}
        return SavePlanResponse(
            lesson_date=lesson_date,
            title=title,
            plan_path=path,
            session_state=planning.get("session_state"),
            lesson_planning_state=planning.get("lesson_planning_state"),
            memory_candidates=candidates,
            material_ids=promoted_ids,
        )

    async def generate(self, class_id: str, req: PlanLessonRequest) -> LessonPlan:
        anchor = req.anchor_lesson_date.isoformat() if req.anchor_lesson_date else None
        return await self.agents.plan_lesson(class_id, req.duration_minutes, anchor)

    def save_plan(self, class_id: str, lesson_date: str, plan: LessonPlan) -> str:
        markdown = self.wiki.normalize_plan_target_date(
            plan.to_markdown(), lesson_date
        )
        return self.wiki.save_lesson_plan(class_id, lesson_date, markdown)

    def discard_draft(self, draft_id: str) -> None:
        if self.workflow_drafts is None:
            raise KeyError(f"Unknown workflow draft: {draft_id}")
        row = self.workflow_drafts.discard(draft_id)
        if row.backend_session_id in self.core.sessions:
            del self.core.sessions[row.backend_session_id]
