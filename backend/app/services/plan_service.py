"""Lesson-plan flow — thin adapter over ArtifactSessionService.

Session lifecycle + chat turn loop live in the shared core; this adapter only
maps the generic session/draft into the plan API schemas and owns the
plan-specific single_file_save step plus the standalone one-shot generator.
"""

from __future__ import annotations

from app.schemas.api import (
    ChatAttachment,
    LessonPlan,
    PlanChatResponse,
    PlanDraft,
    PlanLessonRequest,
    PlanSession,
    PlanSessionStatus,
    SavePlanRequest,
    SavePlanResponse,
)
from app.services.artifact_session_service import ArtifactSession, ArtifactSessionService
from app.teacher_agent.agents import AgentRunner
from app.teacher_agent.wiki_store import WikiStore

MODE = "plan"


class PlanService:
    def __init__(self, wiki: WikiStore, agents: AgentRunner) -> None:
        self.wiki = wiki
        self.agents = agents
        self.core = ArtifactSessionService(wiki, agents)

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
        return PlanChatResponse(
            reply=result.reply,
            plan_markdown=result.markdown,
            ready_to_save=result.ready,
        )

    def update_draft(self, session_id: str, plan_markdown: str) -> PlanDraft:
        draft = self.core.update_draft(session_id, plan_markdown)
        assert isinstance(draft, PlanDraft)
        return draft

    def save(self, class_id: str, req: SavePlanRequest) -> SavePlanResponse:
        session = self.core.get_session(req.session_id)
        if session.class_id != class_id:
            raise KeyError("Session class mismatch")
        title = self.wiki._extract_title(req.plan_markdown) or "Lesson plan"
        path = self.wiki.save_lesson_plan(class_id, req.lesson_date, req.plan_markdown)
        self.core.set_status(req.session_id, PlanSessionStatus.saved.value)
        return SavePlanResponse(
            lesson_date=req.lesson_date,
            title=title,
            plan_path=path,
        )

    async def generate(self, class_id: str, req: PlanLessonRequest) -> LessonPlan:
        anchor = req.anchor_lesson_date.isoformat() if req.anchor_lesson_date else None
        return await self.agents.plan_lesson(class_id, req.duration_minutes, anchor)

    def save_plan(self, class_id: str, lesson_date: str, plan: LessonPlan) -> str:
        return self.wiki.save_lesson_plan(class_id, lesson_date, plan.to_markdown())
