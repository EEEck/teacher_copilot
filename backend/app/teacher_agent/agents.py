"""Agent prompts and OpenAI-backed agent runners."""

from __future__ import annotations

from typing import Optional

from openai import OpenAI
from pydantic import BaseModel, Field

from app.config import Settings
from app.schemas.api import ChatMessage, CompletenessChecklist, LessonPlan, LessonFlowPhase
from app.teacher_agent.wiki_store import DIARY_SECTION_HEADINGS, WikiStore

INGEST_SYSTEM = """You are KlassenPilot, a private teacher copilot for Gymnasium teachers.

You help teachers log lessons through conversation. Each turn you must:
1. Reply conversationally — reflect what you understood, ask at most ONE clarifying question when important diary sections are missing.
2. Update diary_markdown — the live lesson results draft shown in the teacher's side panel.

Required diary sections (all must be covered before save):
{sections}

Diary markdown format (use exactly these ## headings):
# Lesson Results — YYYY-MM-DD — {{short title}}

## What was covered
...

## Student participation
...

## What went well
...

## What didn't go well
...

## Student observations
...

## Homework & follow-ups
...

Rules:
- Use pseudonymous student IDs (S-001, S-014) — never real names.
- Do not infer sensitive facts beyond what the teacher said.
- Merge new information from the conversation into diary_markdown; preserve manual edits from the current draft.
- Be practical, concise, and teacher-friendly.
- When all sections are filled, tell the teacher they can click "Ready to save memory".

Class context:
{context}
"""

COMPILE_SYSTEM = """You compile a teacher conversation into a structured lesson results markdown document.

Output ONLY valid markdown with this exact structure:

# Lesson Results — YYYY-MM-DD — {title}

## What was covered
...

## Student participation
...

## What went well
...

## What didn't go well
...

## Student observations
...

## Homework & follow-ups
...

Use today's date if not specified. Fill every section. Use "None" only if teacher explicitly said nothing applied.
"""

PLAN_SYSTEM = """You create lesson plans for Gymnasium teachers grounded in class wiki memory.

Return structured JSON matching the LessonPlan schema.
Prefer 45-minute lessons with clear phases. Address open loops and misconceptions when relevant.
Use English. Be practical and specific to the class context provided.
"""


class CompileOutput(BaseModel):
    diary_markdown: str = Field(description="Full lesson results markdown with all sections")


class IngestTurnOutput(BaseModel):
    reply: str = Field(description="Conversational reply to the teacher")
    diary_markdown: str = Field(description="Updated full lesson results markdown with all sections")


class PlanOutput(BaseModel):
    title: str
    lesson_date: Optional[str] = None
    duration_minutes: int = 45
    learning_goals: list[str]
    lesson_flow: list[LessonFlowPhase]
    warmup: str
    practice_tasks: list[str]
    homework: str
    teacher_notes: str
    addresses_open_loops: list[str] = Field(default_factory=list)
    addresses_misconceptions: list[str] = Field(default_factory=list)


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

    def ingest_chat(
        self,
        class_id: str,
        messages: list[ChatMessage],
        partial_diary: str = "",
    ) -> tuple[str, str, CompletenessChecklist, bool]:
        context = self.wiki.load_class_context(class_id)
        sections = "\n".join(f"- {s}" for s in DIARY_SECTION_HEADINGS)
        system = INGEST_SYSTEM.format(sections=sections, context=context[:12000])

        current_draft = partial_diary.strip() or self.wiki.empty_diary_template()
        oai_messages = [
            {"role": "system", "content": system},
            {
                "role": "system",
                "content": f"Current diary draft (update this each turn):\n{current_draft[:6000]}",
            },
        ]
        for m in messages:
            oai_messages.append({"role": m.role, "content": m.content})

        response = self._require_client().beta.chat.completions.parse(
            model=self.model,
            messages=oai_messages,
            response_format=IngestTurnOutput,
            temperature=0.4,
        )
        parsed = response.choices[0].message.parsed
        if parsed is None:
            reply = "I had trouble processing that — could you try again?"
            diary_md = current_draft
        else:
            reply = parsed.reply
            diary_md = parsed.diary_markdown.strip() or current_draft

        checklist = self.wiki.checklist_from_diary(diary_md)
        ready = self.wiki.is_diary_complete(diary_md) or "ready to save" in reply.lower()
        return reply, diary_md, checklist, ready

    def compile_diary(self, class_id: str, messages: list[ChatMessage]) -> str:
        context = self.wiki.load_class_context(class_id)
        transcript = "\n".join(f"{m.role}: {m.content}" for m in messages)
        prompt = (
            f"Class context:\n{context[:8000]}\n\n"
            f"Conversation transcript:\n{transcript}\n\n"
            "Compile the lesson results markdown now."
        )
        response = self._require_client().beta.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": COMPILE_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            response_format=CompileOutput,
            temperature=0.3,
        )
        parsed = response.choices[0].message.parsed
        if parsed is None:
            return self.wiki.empty_diary_template()
        return parsed.diary_markdown

    def plan_lesson(
        self,
        class_id: str,
        duration_minutes: int = 45,
        anchor_date: Optional[str] = None,
    ) -> LessonPlan:
        context = self.wiki.load_class_context(class_id)
        user = (
            f"Create a {duration_minutes}-minute lesson plan for class {class_id}.\n"
            f"Anchor date: {anchor_date or 'next lesson after last logged entry'}.\n\n"
            f"Wiki context:\n{context[:12000]}"
        )
        response = self._require_client().beta.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": PLAN_SYSTEM},
                {"role": "user", "content": user},
            ],
            response_format=PlanOutput,
            temperature=0.5,
        )
        parsed = response.choices[0].message.parsed
        if parsed is None:
            raise RuntimeError("Failed to generate lesson plan")
        return LessonPlan(**parsed.model_dump())
