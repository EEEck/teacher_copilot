"""In-memory plan session store and orchestration."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.schemas.api import (
    ChatAttachment,
    ChatMessage,
    LessonPlan,
    PlanChatResponse,
    PlanDraft,
    PlanLessonRequest,
    PlanSession,
    PlanSessionStatus,
    SavePlanRequest,
    SavePlanResponse,
)
from app.teacher_agent.agents import AgentRunner
from app.teacher_agent.wiki_store import WikiStore


@dataclass
class PlanSessionStore:
    sessions: dict[str, PlanSession] = field(default_factory=dict)
    plan_markdown: dict[str, str] = field(default_factory=dict)


class PlanService:
    def __init__(self, wiki: WikiStore, agents: AgentRunner) -> None:
        self.wiki = wiki
        self.agents = agents
        self.store = PlanSessionStore()

    def start_session(self, class_id: str) -> PlanSession:
        session_id = str(uuid.uuid4())
        opening = self.agents.plan_opening(class_id)
        session = PlanSession(
            session_id=session_id,
            class_id=class_id,
            status=PlanSessionStatus.chatting,
            messages=[ChatMessage(role="assistant", content=opening)],
            opening_message=opening,
        )
        self.store.sessions[session_id] = session
        self.store.plan_markdown[session_id] = self.wiki.empty_plan_template()
        return session

    def get_session(self, session_id: str) -> PlanSession:
        if session_id not in self.store.sessions:
            raise KeyError(f"Unknown session: {session_id}")
        return self.store.sessions[session_id]

    def get_draft(self, session_id: str) -> PlanDraft:
        plan_md = self.store.plan_markdown.get(
            session_id, self.wiki.empty_plan_template()
        )
        return PlanDraft(plan_markdown=plan_md)

    def chat(
        self,
        session_id: str,
        message: str,
        plan_markdown: str | None = None,
        attachments: list[ChatAttachment] | None = None,
    ) -> PlanChatResponse:
        session = self.get_session(session_id)
        if plan_markdown is not None:
            self.store.plan_markdown[session_id] = plan_markdown

        session.messages.append(ChatMessage(role="user", content=message))
        partial = self.store.plan_markdown.get(session_id, "")

        reply, plan_md, ready = self.agents.plan_chat(
            session.class_id,
            session.messages,
            partial,
            attachments=attachments or [],
        )
        session.messages.append(ChatMessage(role="assistant", content=reply))
        self.store.plan_markdown[session_id] = plan_md
        if ready:
            session.status = PlanSessionStatus.ready_to_save

        return PlanChatResponse(reply=reply, plan_markdown=plan_md, ready_to_save=ready)

    def update_draft(self, session_id: str, plan_markdown: str) -> PlanDraft:
        session = self.get_session(session_id)
        self.store.plan_markdown[session_id] = plan_markdown
        if self.wiki.is_plan_ready(plan_markdown):
            session.status = PlanSessionStatus.ready_to_save
        return PlanDraft(plan_markdown=plan_markdown)

    def save(self, class_id: str, req: SavePlanRequest) -> SavePlanResponse:
        session = self.get_session(req.session_id)
        if session.class_id != class_id:
            raise KeyError("Session class mismatch")
        title = self.wiki._extract_title(req.plan_markdown) or "Lesson plan"
        path = self.wiki.save_lesson_plan(class_id, req.lesson_date, req.plan_markdown)
        session.status = PlanSessionStatus.saved
        return SavePlanResponse(
            lesson_date=req.lesson_date,
            title=title,
            plan_path=path,
        )

    def generate(self, class_id: str, req: PlanLessonRequest) -> LessonPlan:
        anchor = req.anchor_lesson_date.isoformat() if req.anchor_lesson_date else None
        return self.agents.plan_lesson(class_id, req.duration_minutes, anchor)

    def save_plan(self, class_id: str, lesson_date: str, plan: LessonPlan) -> str:
        return self.wiki.save_lesson_plan(class_id, lesson_date, plan.to_markdown())
