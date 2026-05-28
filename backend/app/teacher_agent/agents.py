"""Agent runners using OpenAI Agents SDK with wiki tools."""

from __future__ import annotations

from typing import Optional

from agents import Runner
from openai import OpenAI

from app.config import Settings
from app.schemas.api import ChatAttachment, ChatMessage, CompletenessChecklist, LessonPlan
from app.teacher_agent.agent import (
    build_compile_agent,
    build_ingest_agent,
    build_lint_agent,
    build_plan_chat_agent,
    build_plan_lesson_agent,
    build_plan_opening_agent,
)
from app.teacher_agent.models import CompileOutput, IngestTurnOutput, PlanOutput, PlanTurnOutput
from app.teacher_agent.tools import WikiToolContext
from app.teacher_agent.wiki_store import DIARY_SECTION_HEADINGS, WikiStore

MAX_AGENT_TURNS = 8


class AgentRunner:
    def __init__(self, settings: Settings, wiki: WikiStore) -> None:
        key = settings.openai_api_key.get_secret_value()
        if not key:
            self.client = None
        else:
            self.client = OpenAI(api_key=key)
        self.model = settings.openai_model
        self.wiki = wiki

    def _require_client(self) -> OpenAI:
        if self.client is None:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        return self.client

    def _wiki_ctx(self, class_id: str) -> WikiToolContext:
        return WikiToolContext(wiki=self.wiki, class_id=class_id)

    def _format_attachments(self, attachments: list[ChatAttachment]) -> str:
        if not attachments:
            return ""
        blocks = []
        for att in attachments:
            blocks.append(f"### Upload: {att.filename}\n{att.content[:8000]}")
        return "\n\n".join(blocks)

    def _build_user_input(
        self,
        messages: list[ChatMessage],
        draft_label: str,
        draft_content: str,
        attachments: list[ChatAttachment] | None = None,
    ) -> str:
        parts = [f"{draft_label}:\n{draft_content[:6000]}\n"]
        if attachments:
            parts.append(
                f"Uploaded materials this turn:\n{self._format_attachments(attachments)}\n"
            )
        for m in messages:
            parts.append(f"{m.role}: {m.content}")
        return "\n".join(parts)

    def _run_structured(self, agent, user_input: str):
        self._require_client()
        result = Runner.run_sync(agent, user_input, max_turns=MAX_AGENT_TURNS)
        return result.final_output

    def plan_opening(self, class_id: str) -> str:
        context = self.wiki.load_index_context(class_id) + "\n\n" + self.wiki.build_plan_context(class_id)
        agent = build_plan_opening_agent(context[:14000], self.model)
        out = self._run_structured(agent, "Open the planning session for this class.")
        text = out if isinstance(out, str) else str(out)
        return text.strip() or (
            "I've loaded your class memory. Tell me what you want to cover in the next lesson, "
            "or attach a worksheet or draft plan with the + button."
        )

    def plan_chat(
        self,
        class_id: str,
        messages: list[ChatMessage],
        partial_plan: str = "",
        attachments: list[ChatAttachment] | None = None,
    ) -> tuple[str, str, bool]:
        context = self.wiki.load_index_context(class_id)
        agent = build_plan_chat_agent(self._wiki_ctx(class_id), context, self.model)
        current_draft = partial_plan.strip() or self.wiki.empty_plan_template()
        user_input = self._build_user_input(
            messages, "Current plan draft (update each turn)", current_draft, attachments
        )
        parsed = self._run_structured(agent, user_input)
        if not isinstance(parsed, PlanTurnOutput):
            return "I had trouble processing that — could you try again?", current_draft, False
        reply = parsed.reply
        plan_md = parsed.plan_markdown.strip() or current_draft
        ready = self.wiki.is_plan_ready(plan_md) or "ready to save" in reply.lower()
        return reply, plan_md, ready

    def ingest_chat(
        self,
        class_id: str,
        messages: list[ChatMessage],
        partial_diary: str = "",
        attachments: list[ChatAttachment] | None = None,
    ) -> tuple[str, str, CompletenessChecklist, bool]:
        context = self.wiki.load_index_context(class_id) + "\n\n" + self.wiki.build_ingest_context(class_id)
        sections = "\n".join(f"- {s}" for s in DIARY_SECTION_HEADINGS)
        agent = build_ingest_agent(self._wiki_ctx(class_id), sections, context[:10000], self.model)
        current_draft = partial_diary.strip() or self.wiki.empty_diary_template()
        user_input = self._build_user_input(
            messages, "Current diary draft (update each turn)", current_draft, attachments
        )
        parsed = self._run_structured(agent, user_input)
        if not isinstance(parsed, IngestTurnOutput):
            return (
                "I had trouble processing that — could you try again?",
                current_draft,
                self.wiki.checklist_from_diary(current_draft),
                False,
            )
        reply = parsed.reply
        diary_md = parsed.diary_markdown.strip() or current_draft
        checklist = self.wiki.checklist_from_diary(diary_md)
        ready = self.wiki.is_diary_complete(diary_md) or "ready to save" in reply.lower()
        return reply, diary_md, checklist, ready

    def compile_diary(self, class_id: str, messages: list[ChatMessage]) -> str:
        context = self.wiki.load_index_context(class_id)
        transcript = "\n".join(f"{m.role}: {m.content}" for m in messages)
        prompt = (
            f"Class context:\n{context[:8000]}\n\n"
            f"Conversation transcript:\n{transcript}\n\n"
            "Compile the lesson results markdown now."
        )
        agent = build_compile_agent(self.model)
        parsed = self._run_structured(agent, prompt)
        if not isinstance(parsed, CompileOutput):
            return self.wiki.empty_diary_template()
        return parsed.diary_markdown

    def plan_lesson(
        self,
        class_id: str,
        duration_minutes: int = 45,
        anchor_date: Optional[str] = None,
    ) -> LessonPlan:
        context = self.wiki.load_index_context(class_id)
        user = (
            f"Create a {duration_minutes}-minute lesson plan for class {class_id}.\n"
            f"Anchor date: {anchor_date or 'next lesson after last logged entry'}.\n\n"
            f"Start from index.md via tools, then open relevant pages.\n"
            f"Context excerpt:\n{context[:4000]}"
        )
        agent = build_plan_lesson_agent(self._wiki_ctx(class_id), self.model)
        parsed = self._run_structured(agent, user)
        if not isinstance(parsed, PlanOutput):
            raise RuntimeError("Failed to generate lesson plan")
        return LessonPlan(**parsed.model_dump())

    def lint_wiki(self, class_id: str) -> str:
        context = self.wiki.read_wiki_index(class_id)
        agent = build_lint_agent(self._wiki_ctx(class_id), context, self.model)
        out = self._run_structured(
            agent,
            f"Lint the wiki for class {class_id}. Read index.md and scan lessons, students, roll-ups.",
        )
        return out if isinstance(out, str) else str(out)
