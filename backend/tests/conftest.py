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
from app.teacher_agent.planning_state import (
    EvidenceBrief,
    LessonPlanningState,
    MemoryCandidate,
    PlanRuntime,
    SessionState,
    LessonPlanningStatePatch,
    SessionStatePatch,
    StatePatch,
    merge_turn_into_runtime,
    planning_api_payload,
)
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

    def _emit_plan_state(
        self,
        planning: PlanRuntime,
        messages: list[ChatMessage],
        plan_md: str,
        partial_plan: str,
        *,
        phase: str = "lesson_refinement",
    ) -> None:
        """Simulate the model emitting structured state for one plan turn."""
        latest = messages[-1].content if messages else ""
        briefs: list[EvidenceBrief] = []
        if "redox" in latest.lower() or "fckw" in latest.lower():
            ref = planning.next_raw_ref("wiki_search")
            planning.raw_store[ref] = (
                '[{"path":"wiki/classes/chemie_9b_2026_27/lessons/2026-05-25/'
                'lesson_results.md","title":"Redox Reactions with Metals"}]'
            )
            briefs.append(
                EvidenceBrief(
                    type="wiki_search",
                    purpose="Find prior redox context",
                    brief=["Redox covered on 2026-05-25."],
                    impact_on_plan="Reuse the 2026-05-25 redox examples.",
                    raw_ref=ref,
                    confidence="high",
                )
            )
        merge_turn_into_runtime(
            planning,
            state_patch=StatePatch(
                session_state=SessionStatePatch(
                    phase=phase,
                    teacher_goal=latest[:80],
                    decisions=[
                        "Use a 45-minute Einstieg/practice/reflection structure."
                    ],
                ),
                lesson_planning_state=LessonPlanningStatePatch(
                    lesson_topic="Stub topic",
                    duration_minutes=45,
                    accepted_plan_elements=["Warmup diagnostic"],
                ),
            ),
            session_state=SessionState(
                phase=phase,
                teacher_goal=latest[:80],
                decisions=["Use a 45-minute Einstieg/practice/reflection structure."],
            ),
            lesson_planning_state=LessonPlanningState(
                lesson_topic="Stub topic",
                duration_minutes=45,
                accepted_plan_elements=["Warmup diagnostic"],
            ),
            new_evidence_briefs=briefs,
            memory_candidates=[
                MemoryCandidate(
                    target="copilot.md",
                    candidate_update="Draft early, then refine the markdown directly.",
                    source="inferred_from_session",
                    confidence="medium",
                )
            ],
            last_change_summary="Updated plan draft.",
            plan_changed=plan_md.strip() != (partial_plan or "").strip(),
        )
        planning.session_state.phase = phase

    async def plan_chat(
        self,
        class_id: str,
        messages: list[ChatMessage],
        partial_plan: str = "",
        attachments: list[ChatAttachment] | None = None,
        planning: PlanRuntime | None = None,
    ) -> tuple[str, str, bool]:
        if planning is not None:
            self._emit_plan_state(planning, messages, READY_PLAN, partial_plan)
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
                    "## Planning Patterns\n"
                    "- Draft early, then refine the markdown artifact directly.\n"
                ),
                class_state_markdown=(
                    "# Class State\n\n"
                    "- Current unit: redox. Next: practice arrow direction.\n"
                ),
                stale_report=[],
                warnings=[],
            ),
            source["source_paths"],
            source["warnings"],
        )

    async def propose_profile_updates(
        self,
        class_id: str,
        final_lesson_markdown: str = "",
        session_state=None,
        lesson_planning_state=None,
        memory_candidates=None,
    ):
        from app.teacher_agent.models import ProfileCandidateOut, ProfileProposalOutput

        return ProfileProposalOutput(
            user_candidates=[
                ProfileCandidateOut(
                    target="user.md",
                    section="Communication",
                    content="Prefers concise, practical plans with one strong main activity.",
                    basis="inferred",
                    confidence="medium",
                )
            ],
            copilot_candidates=[
                ProfileCandidateOut(
                    target="copilot.md",
                    section="Planning Patterns",
                    content="Draft early, then refine the markdown directly.",
                    basis="explicit",
                    confidence="high",
                )
            ],
            warnings=[],
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

    def _plan_final(
        self,
        reply: str,
        plan_md: str,
        planning: PlanRuntime | None,
    ) -> SseFinal:
        payload = planning_api_payload(planning) if planning is not None else {}
        return SseFinal(
            reply=reply,
            artifact_markdown=plan_md,
            ready=True,
            completeness=None,
            phase=payload.get("phase"),
            last_change_summary=payload.get("last_change_summary"),
            session_state=payload.get("session_state"),
            lesson_planning_state=payload.get("lesson_planning_state"),
            memory_candidates=payload.get("memory_candidates"),
        )

    async def plan_chat_stream(
        self,
        class_id: str,
        messages: list[ChatMessage],
        partial_plan: str = "",
        attachments: list[ChatAttachment] | None = None,
        planning: PlanRuntime | None = None,
    ) -> AsyncIterator:
        latest = messages[-1].content.lower() if messages else ""

        if "very happy" in latest or ("refinement" in latest and "recall" in latest):
            plan = (partial_plan or READY_PLAN).rstrip()
            if "2 min" not in plan.lower() and "2-minute" not in plan.lower():
                plan += "\n\n## Active recall\n- 2-minute student recall of key learning.\n"
            if planning is not None:
                self._emit_plan_state(
                    planning, messages, plan, partial_plan, phase="finalize"
                )
            yield self._plan_final(
                "Added a short active-recall close.", plan, planning
            )
            return

        if "last 4 lectures" in latest or ("review" in latest and "lectures" in latest):
            yield SseToolCall(
                name="read_lesson_range",
                args='{"start_date":"2026-05-21","end_date":"2026-05-29","max_lessons":4}',
                call_id="call-review",
            )
            yield SseToolResult(
                name="read_lesson_range",
                output="raw_ref: read_lesson_range_stub\nPrior lessons show confusion on ion charge vs oxidation number.",
            )
            plan = (partial_plan or READY_PLAN).rstrip()
            plan += (
                "\n\n## Review of recent lessons (5 min)\n"
                "- Recap what the class confused in the last four lectures, "
                "especially ion charge vs oxidation number.\n"
            )
            if planning is not None:
                self._emit_plan_state(planning, messages, plan, partial_plan)
            yield self._plan_final(
                "Added a review block grounded in recent lesson confusion.", plan, planning
            )
            return

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
            plan = (
                "# Lesson Plan — FCKW Redox\n\n"
                "> Duration: 45 min\n\n"
                "## Learning goals\n- Apply redox to FCKW/CFC compounds.\n\n"
                "## Lesson flow\n- 5 min recap, 15 min FCKW structure, 10 min Montreal Protocol, "
                "10 min practice, 5 min exit ticket.\n\n"
                "## Warmup\n- Redox recap.\n\n"
                "## Practice tasks\n- Differentiated worksheet.\n\n"
                "## Homework\n- Two exam-style questions.\n\n"
                "## Teacher notes\n- No real CFCs in the lab; demo alternatives only. "
                "Address oxidation number vs charge.\n"
                "## Sources\n- Based on the 2026-05-25 redox lesson notes.\n"
            )
            if planning is not None:
                self._emit_plan_state(planning, messages, plan, partial_plan)
            yield self._plan_final(
                "Using the recent redox lessons, including 2026-05-25.", plan, planning
            )
            return

        yield SseToolCall(name="search_memory", args="{}", call_id="call-1")
        if planning is not None:
            self._emit_plan_state(planning, messages, READY_PLAN, partial_plan)
        yield self._plan_final(
            "Here is an updated plan draft.", READY_PLAN, planning
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
