"""Lesson-plan flow — thin adapter over ArtifactSessionService.

Session lifecycle + chat turn loop live in the shared core; this adapter only
maps the generic session/draft into the plan API schemas and owns the
plan-specific single_file_save step plus the standalone one-shot generator.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date

from app.schemas.api import (
    ChatAttachment,
    LessonPlan,
    PlanChatResponse,
    PlanDraft,
    PlanLessonRequest,
    PlanSession,
    PlanSessionStatus,
    PlanTraceResponse,
    SavePlanRequest,
    SavePlanResponse,
)
from app.services.artifact_session_service import (
    ArtifactSession,
    ArtifactSessionService,
)
from app.services.memory_candidate_ledger import MemoryCandidateLedger
from app.teacher_agent.agents import AgentRunner
from app.teacher_agent.planning_state import (
    planning_api_payload,
    render_briefs,
    render_lesson_planning_state,
    render_session_state,
)
from app.teacher_agent.executive_verification import (
    WriteVerificationBlocked,
    apply_write_verification,
    evaluate_write_gate,
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
    ) -> None:
        self.wiki = wiki
        self.agents = agents
        self.core = ArtifactSessionService(
            wiki, agents, memory_candidate_ledger=memory_candidate_ledger
        )

    def _to_model(self, s: ArtifactSession) -> PlanSession:
        return PlanSession(
            session_id=s.session_id,
            class_id=s.class_id,
            status=PlanSessionStatus(s.status),
            messages=s.messages,
            opening_message=s.opening_message,
        )

    async def start_session(self, class_id: str) -> PlanSession:
        session = await self.core.start_session(MODE, class_id)
        return self._to_model(session)

    def get_session(self, session_id: str) -> ArtifactSession:
        return self.core.get_session(session_id)

    def get_draft(self, session_id: str) -> PlanDraft:
        draft = self.core.get_draft(session_id)
        assert isinstance(draft, PlanDraft)
        return draft

    async def chat(
        self,
        session_id: str,
        message: str,
        plan_markdown: str | None = None,
        attachments: list[ChatAttachment] | None = None,
    ) -> PlanChatResponse:
        result = await self.core.chat(session_id, message, plan_markdown, attachments)
        planning = result.planning or {}
        return PlanChatResponse(
            reply=result.reply,
            plan_markdown=result.markdown,
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
        verification = await self.agents.verify_artifact_for_write(
            class_id, "lesson plan", req.plan_markdown, session.executive
        )
        apply_write_verification(
            session.executive,
            artifact=req.plan_markdown,
            patch=verification.patch,
            message=verification.message,
        )
        gate = evaluate_write_gate(
            session.executive,
            req.plan_markdown,
            structurally_ready=self.wiki.is_plan_ready(req.plan_markdown),
        )
        if not gate.allowed:
            raise WriteVerificationBlocked(
                "plan_save", verification, gate, session.executive
            )
        title = self.wiki.extract_title(req.plan_markdown) or "Lesson plan"
        path = self.wiki.save_lesson_plan(class_id, lesson_date, req.plan_markdown)
        self.core.set_status(req.session_id, PlanSessionStatus.saved.value)
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
        )

    async def generate(self, class_id: str, req: PlanLessonRequest) -> LessonPlan:
        anchor = req.anchor_lesson_date.isoformat() if req.anchor_lesson_date else None
        return await self.agents.plan_lesson(class_id, req.duration_minutes, anchor)

    def save_plan(self, class_id: str, lesson_date: str, plan: LessonPlan) -> str:
        return self.wiki.save_lesson_plan(class_id, lesson_date, plan.to_markdown())
