"""Shared test fixtures.

Provides an offline, deterministic test client:
- the real `WikiStore` pointed at a **copy** of the seed wiki in a tmp dir
  (so commit/save can't mutate the repo), and
- a `StubAgentRunner` that returns canned, well-formed outputs instead of
  calling OpenAI. Every API/service test runs fast, free, and offline.
"""

from __future__ import annotations

import shutil
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.main import app
from app.schemas.api import (
    ChatAttachment,
    ChatMessage,
    CompletenessChecklist,
    LessonFlowPhase,
    LessonPlan,
)
from app.teacher_agent.models import MemoryCompactOutput
from app.services.ingest_service import IngestService
from app.services.plan_service import PlanService
from app.teacher_agent.stream_events import (
    SseFinal,
    SseReasoningDelta,
    SseToolCall,
    SseToolResult,
)
from app.teacher_agent.wiki_store import WikiStore

CLASS_ID = "chemie_9b_2026_27"
_SEED_WIKI = Path(__file__).resolve().parent.parent / "teacher_wiki"

COMPLETE_DIARY = """# Lesson Results — 2026-10-01 — Stub Lesson

## What was covered
- Topic A

## Student participation
- Active discussion

## What went well
- Good engagement

## What didn't go well
- Rushed ending

## Student observations
- S-014: Strong

## Homework & follow-ups
- Homework: Sheet 3
"""

READY_PLAN = """# Lesson Plan — Stub Plan

> Duration: 45 min

## Learning goals
- Understand the topic thoroughly enough to apply it.

## Lesson flow
- **Opening** (5 min): recap
- **Main** (30 min): new material
- **Close** (10 min): practice

## Warmup
- Quick diagnostic on last lesson.

## Practice tasks
- Worksheet 1

## Homework
- Read chapter 4

## Teacher notes
- Watch for the usual misconception.
"""


class StubAgentRunner:
    """Deterministic stand-in for AgentRunner — no network calls."""

    def __init__(self, wiki: WikiStore) -> None:
        self.wiki = wiki
        self.model = "stub-model"
        self.client = object()  # truthy: behaves as "configured"

    async def plan_opening(self, class_id: str) -> str:
        return f"Opening planning session for {class_id}."

    async def plan_chat(
        self,
        class_id: str,
        messages: list[ChatMessage],
        partial_plan: str = "",
        attachments: list[ChatAttachment] | None = None,
    ) -> tuple[str, str, bool]:
        return "Here is an updated plan draft.", READY_PLAN, True

    async def ingest_chat(
        self,
        class_id: str,
        messages: list[ChatMessage],
        partial_diary: str = "",
        attachments: list[ChatAttachment] | None = None,
    ) -> tuple[str, str, CompletenessChecklist, bool]:
        checklist = self.wiki.checklist_from_diary(COMPLETE_DIARY)
        return "Logged the lesson.", COMPLETE_DIARY, checklist, True

    async def compile_diary(self, class_id: str, messages: list[ChatMessage]) -> str:
        return COMPLETE_DIARY

    async def plan_lesson(
        self, class_id: str, duration_minutes: int = 45, anchor_date=None
    ) -> LessonPlan:
        return LessonPlan(
            title="Stub Plan",
            duration_minutes=duration_minutes,
            learning_goals=["Goal A"],
            lesson_flow=[LessonFlowPhase(phase="Opening", minutes=5, description="recap")],
            warmup="Diagnostic",
            practice_tasks=["Worksheet 1"],
            homework="Read chapter 4",
            teacher_notes="Watch the misconception.",
        )

    async def lint_wiki(self, class_id: str) -> str:
        return "# Wiki lint report\n- All good."

    async def compact_memory(self, class_id: str, start_date=None, end_date=None):
        source = self.wiki.build_memory_compaction_source_packet(
            class_id, start_date=start_date, end_date=end_date
        )
        return (
            MemoryCompactOutput(
                taught_so_far_markdown=(
                    "# Taught So Far\n\n"
                    f"> Class: {class_id}\n\n"
                    "- Reaction writing, balancing, oxidation numbers, and redox have been taught.\n"
                ),
                planning_brief_markdown=(
                    "# Planning Brief\n\n"
                    "- Keep contrasting ion charge and oxidation number.\n"
                ),
                teaching_patterns_markdown=(
                    "# Teaching Patterns\n\n"
                    "- Peer checking helps reduce balancing errors.\n"
                ),
                copilot_profile_markdown=(
                    "# Class Copilot Profile\n\n"
                    "## Teacher Preferences\n"
                    "- Prefers concise 45-minute plans with Einstieg, practice, reflection.\n\n"
                    "## Class Learning Profile\n"
                    "- Concrete examples before symbolic abstraction work well.\n"
                ),
                warnings=[],
            ),
            source["source_paths"],
            source["warnings"],
        )

    async def ingest_chat_stream(
        self,
        class_id: str,
        messages: list[ChatMessage],
        partial_diary: str = "",
        attachments: list[ChatAttachment] | None = None,
    ) -> AsyncIterator:
        yield SseReasoningDelta(text="Reviewing class memory…")
        checklist = self.wiki.checklist_from_diary(COMPLETE_DIARY)
        yield SseFinal(
            reply="Logged the lesson.",
            artifact_markdown=COMPLETE_DIARY,
            ready=True,
            completeness=checklist,
        )

    async def plan_chat_stream(
        self,
        class_id: str,
        messages: list[ChatMessage],
        partial_plan: str = "",
        attachments: list[ChatAttachment] | None = None,
    ) -> AsyncIterator:
        latest = messages[-1].content.lower() if messages else ""
        if "fckw" in latest or "redox" in latest:
            yield SseToolCall(
                name="search_memory",
                args='{"query":"FCKW redox ozone layer", "max_results":5}',
                call_id="call-1",
            )
            yield SseToolResult(
                name="search_memory",
                output='[{"path":"wiki/classes/chemie_9b_2026_27/lessons/2026-05-25/lesson_results.md","kind":"lesson","title":"Redox Reactions with Metals","score":7.4,"matched_terms":["redox"]}]',
            )
            yield SseToolCall(
                name="read_lesson_range",
                args='{"start_date":"2026-05-21","end_date":"2026-05-29","topic":"redox"}',
                call_id="call-2",
            )
            plan = READY_PLAN + "\n## Sources\n- Based on the 2026-05-25 redox lesson notes.\n"
            yield SseFinal(
                reply="Using the recent redox lessons, including 2026-05-25.",
                artifact_markdown=plan,
                ready=True,
                completeness=None,
            )
            return

        yield SseToolCall(name="search_memory", args="{}", call_id="call-1")
        yield SseFinal(
            reply="Here is an updated plan draft.",
            artifact_markdown=READY_PLAN,
            ready=True,
            completeness=None,
        )


@pytest.fixture
def wiki(tmp_path: Path) -> WikiStore:
    dest = tmp_path / "teacher_wiki"
    shutil.copytree(_SEED_WIKI, dest)
    return WikiStore(root=dest)


@pytest.fixture
def agents(wiki: WikiStore) -> StubAgentRunner:
    return StubAgentRunner(wiki)


@pytest.fixture
def client(wiki: WikiStore, agents: StubAgentRunner) -> Iterator[TestClient]:
    ingest = IngestService(wiki=wiki, agents=agents)
    plan = PlanService(wiki=wiki, agents=agents)

    app.dependency_overrides[deps.get_wiki] = lambda: wiki
    app.dependency_overrides[deps.get_agents] = lambda: agents
    app.dependency_overrides[deps.get_ingest_service] = lambda: ingest
    app.dependency_overrides[deps.get_plan_service] = lambda: plan
    try:
        # raise_server_exceptions=False so the global handler's JSON envelope is
        # returned (mirrors production) instead of re-raising in the test client.
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
