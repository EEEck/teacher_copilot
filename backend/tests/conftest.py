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
from app.teacher_agent.executive_verification import (
    ExecutiveFinding,
    ExecutiveRuntime,
    executive_api_payload,
)
from app.teacher_agent.memory_update_state import (
    LessonResultPatch,
    MemoryEvidenceBrief,
    MemoryRuntime,
    MemorySessionPatch,
    MemoryStatePatch,
    MemoryTargetPatch,
    memory_api_payload,
    merge_memory_turn,
    teacher_signals_finalize,
)
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
from app.services.memory_candidate_ledger import MemoryCandidateLedger
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

MEMORY_UPDATE_DIARY = """# Lesson Results — 2026-05-29 — Anions and Oxidation State Review

## What was covered
- Reviewed common anions and their charges.
- Separated ion charge from oxidation number.
- Reviewed metal displacement from 2026-05-25; the class should now have that concept.
- Not fully covered: connecting chloride, oxide, and phosphate back to the redox sequence.

## Student participation
- Students were engaged, but confusion surfaced too late.
- Interruptions were mainly connected to poor lesson organization rather than only student behavior.
- S-004 did well and helped other students.

## What went well
- Students understood common anions quickly.
- The common-anion concept was explained clearly.

## What didn't go well
- The lesson went into a phosphate rabbit hole and confused students.
- The class did not signal confusion early enough.
- There was no time for the other open-loop items from 2026-05-25.

## Student observations
- S-001: Strong understanding of phosphate redox states; doing very well.
- S-002: Frequently interrupted and was not following.
- S-003: Participated well, but some contributions were incorrect.
- S-004: Did well and supported other students.

## Homework & follow-ups
- Homework mainly focused on common anions.
- Follow up by explicitly connecting chloride, oxide, and phosphate to the redox sequence.
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

    def _emit_executive_state(
        self, executive: ExecutiveRuntime | None, messages: list[ChatMessage]
    ) -> None:
        if executive is None or not messages:
            return
        latest = messages[-1].content.lower()
        if "s-999" in latest:
            executive.findings["student-s999"] = ExecutiveFinding(
                finding_id="student-s999",
                category="identity",
                severity="blocking",
                summary="S-999 is not in the active-class roster.",
                question="Which student or class should receive this note?",
                evidence_refs=["reference_stub"],
            )
        elif "new organic chemistry unit" in latest:
            executive.findings["unit-transition"] = ExecutiveFinding(
                finding_id="unit-transition",
                category="time_state",
                severity="advisory",
                summary="Organic chemistry is treated as the explicit next unit.",
            )

    def _is_high_stakes_student_request(self, messages: list[ChatMessage]) -> bool:
        latest = messages[-1].content.lower() if messages else ""
        return any(
            term in latest
            for term in (
                "grade",
                "diagnose",
                "placement",
                "lower track",
                "admission",
                "discipline",
                "disciplinary",
            )
        )

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
                # Simulate a well-behaved capture model: a conduct request
                # addressed to the agent ("from now on ...") is emitted as an
                # explicit candidate with the teacher's sentence quoted;
                # anything else stays a weak inferred signal.
                MemoryCandidate(
                    target="copilot.md",
                    candidate_update="Draft early, then refine the markdown directly.",
                    source="teacher_explicit",
                    basis="explicit",
                    confidence="high",
                    speech_act="conduct_request",
                    evidence=f"Direct teacher quote: {latest.strip()}",
                )
                if "from now on" in latest.lower()
                else MemoryCandidate(
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

    def _memory_phase(self, messages: list[ChatMessage], scenario_0529: bool) -> str:
        latest = messages[-1].content if messages else ""
        if not scenario_0529:
            return "review_draft"
        if teacher_signals_finalize(latest):
            return "review_draft"
        if any("2026-05-29" in m.content or "05/29" in m.content for m in messages):
            return "collect_results"
        return "identify_target"

    def _emit_memory_state(
        self,
        memory: MemoryRuntime,
        messages: list[ChatMessage],
    ) -> None:
        """Simulate the model emitting structured update-memory state."""
        latest = messages[-1].content if messages else ""
        scenario_0529 = any(
            "2026-05-29" in m.content
            or "05/29" in m.content
            or "open loops from 5-25" in m.content.lower()
            for m in messages
        )
        if scenario_0529:
            covered = [
                "Reviewed common anions and their charges.",
                "Separated ion charge from oxidation number.",
                "Reviewed metal displacement from 2026-05-25.",
            ]
            participation = [
                "Students were engaged, but confusion surfaced too late.",
                "S-004 did well and helped other students.",
            ]
            went_well = ["Common anions were understood quickly."]
            did_not_go_well = [
                "Phosphate discussion confused students.",
                "Poor lesson organization contributed to interruptions.",
            ]
            observations = [
                "S-001 understood phosphate redox states well.",
                "S-002 interrupted and was not following.",
                "S-003 participated well but not always correctly.",
                "S-004 helped other students.",
            ]
            followups = [
                "Common anions homework assigned.",
                "Connect chloride, oxide, and phosphate back to the redox sequence.",
            ]
            lesson_date = "2026-05-29"
            lesson_title = "Anions and Oxidation State Review"
            target_kind = "taught_lesson"
            intent = "correct_existing_results"
            phase = self._memory_phase(messages, scenario_0529=True)
        else:
            covered = ["Topic A"]
            participation = ["Active discussion"]
            went_well = []
            did_not_go_well = []
            observations = []
            followups = []
            lesson_date = "2026-10-01"
            lesson_title = "Stub Lesson"
            target_kind = "new_lesson"
            intent = "log_new_results"
            phase = "review_draft"
        diary_md = MEMORY_UPDATE_DIARY if scenario_0529 else COMPLETE_DIARY
        merge_memory_turn(
            memory,
            state_patch=MemoryStatePatch(
                target=MemoryTargetPatch(
                    intent=intent,
                    lesson_date=lesson_date,
                    lesson_title=lesson_title,
                    target_kind=target_kind,
                    target_confirmed=True,
                    source="teacher_explicit",
                    confidence="high",
                    needs_confirmation=False,
                ),
                session_state=MemorySessionPatch(
                    phase=phase,
                    teacher_goal=latest[:80],
                    decisions=[f"Update lesson results for {lesson_date}."],
                ),
                lesson_result_state=LessonResultPatch(
                    covered=covered,
                    participation=participation,
                    went_well=went_well,
                    did_not_go_well=did_not_go_well,
                    student_observations=observations,
                    homework_followups=followups,
                    draft_confidence="high",
                ),
            ),
            new_evidence_briefs=[
                MemoryEvidenceBrief(
                    type="tool_call",
                    purpose=f"Read existing lesson target for {lesson_date}",
                    brief=[f"Target lesson identified as {lesson_date}."],
                    source_refs=[
                        f"wiki/classes/{CLASS_ID}/lessons/{lesson_date}/lesson_results.md"
                    ],
                    raw_ref="read_memory_target_stub" if scenario_0529 else "",
                    confidence="high",
                )
            ]
            if scenario_0529
            else [],
            memory_candidates=[
                MemoryCandidate(
                    target="teaching_patterns.md",
                    section="What Worked",
                    candidate_update=(
                        "Short diagnostic checks surfaced misconceptions early."
                    ),
                    evidence=f"Update-memory session for {lesson_date}.",
                    evidence_refs=[
                        f"wiki/classes/{CLASS_ID}/lessons/{lesson_date}/lesson_results.md"
                    ],
                    source="inferred_from_session",
                    basis="inferred",
                    confidence="medium",
                )
            ],
            last_change_summary="Updated lesson results.",
            unsupported_intent_reason="",
            diary_changed=True,
            teacher_message=latest,
            diary_complete=self.wiki.is_diary_complete(diary_md),
        )

    async def plan_chat(
        self,
        class_id: str,
        messages: list[ChatMessage],
        partial_plan: str = "",
        attachments: list[ChatAttachment] | None = None,
        planning: PlanRuntime | None = None,
        executive: ExecutiveRuntime | None = None,
    ) -> tuple[str, str, bool]:
        if self._is_high_stakes_student_request(messages):
            return (
                "I cannot make high-stakes student decisions. I can help review "
                "evidence and draft neutral observations for teacher review.",
                partial_plan or READY_PLAN,
                bool(partial_plan or READY_PLAN),
            )
        if planning is not None:
            self._emit_plan_state(planning, messages, READY_PLAN, partial_plan)
        self._emit_executive_state(executive, messages)
        ready = not (executive and executive.open_blocking_findings())
        return "Here is an updated plan draft.", READY_PLAN, ready

    async def ingest_chat(
        self,
        class_id: str,
        messages: list[ChatMessage],
        partial_diary: str = "",
        attachments: list[ChatAttachment] | None = None,
        memory: MemoryRuntime | None = None,
        executive: ExecutiveRuntime | None = None,
    ) -> tuple[str, str, CompletenessChecklist, bool]:
        scenario_0529 = any(
            "2026-05-29" in m.content
            or "05/29" in m.content
            or "open loops from 5-25" in m.content.lower()
            for m in messages
        )
        diary = MEMORY_UPDATE_DIARY if scenario_0529 else COMPLETE_DIARY
        checklist = self.wiki.checklist_from_diary(diary)
        if memory is not None:
            self._emit_memory_state(memory, messages)
        self._emit_executive_state(executive, messages)
        ready = not (executive and executive.open_blocking_findings())
        return "Logged the lesson.", diary, checklist, ready

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

    async def consolidate_memory_sweep(
        self,
        class_id: str,
        subject: str,
        claims,
        memory_indexes,
        *,
        applied_history=None,
        rejected_history=None,
        budget_usage=None,
        today: str = "",
        validation_error: str = "",
    ):
        """Mem V3 single-call stub: one add operation per input claim."""
        from app.teacher_agent.models import (
            MemoryConsolidationOpOutput,
            MemoryConsolidationOutput,
        )

        operations = [
            MemoryConsolidationOpOutput(
                claim_ids=[claim["claim_id"]],
                operation="add",
                target=claim["target"],
                section=claim["section"],
                new_text=claim["text"],
                rationale="Stub isolated sweep review.",
            )
            for claim in claims
        ]
        return MemoryConsolidationOutput(operations=operations, warnings=[])

    async def ingest_chat_stream(
        self,
        class_id: str,
        messages: list[ChatMessage],
        partial_diary: str = "",
        attachments: list[ChatAttachment] | None = None,
        memory: MemoryRuntime | None = None,
        executive: ExecutiveRuntime | None = None,
    ) -> AsyncIterator:
        yield SseReasoningDelta(text="Reviewing class memory…")
        latest = messages[-1].content.lower() if messages else ""
        scenario_0529 = any(
            "2026-05-29" in m.content
            or "05/29" in m.content
            or "open loops from 5-25" in m.content.lower()
            for m in messages
        )
        diary = MEMORY_UPDATE_DIARY if scenario_0529 else COMPLETE_DIARY
        if scenario_0529 and (
            "2026-05-29" in latest or "05/29" in latest or "lesson results" in latest
        ):
            yield SseToolCall(
                name="read_memory_target",
                args='{"lesson_date":"2026-05-29"}',
                call_id="memory-target-1",
            )
            target_detail = MEMORY_UPDATE_DIARY[:1200]
            if memory is not None:
                memory.raw_store["read_memory_target_stub"] = target_detail
            yield SseToolResult(
                name="read_memory_target",
                output=f"raw_ref: read_memory_target_stub\n{target_detail}",
                call_id="memory-target-1",
            )
        elif scenario_0529 and "open loops from 5-25" in latest:
            yield SseToolCall(
                name="read_memory_target",
                args='{"lesson_date":"2026-05-25"}',
                call_id="memory-target-2",
            )
            open_loop_detail = "2026-05-25 open loops: metal displacement; other redox sequence items."
            if memory is not None:
                memory.raw_store["read_memory_target_0525_stub"] = open_loop_detail
            yield SseToolResult(
                name="read_memory_target",
                output=f"raw_ref: read_memory_target_0525_stub\n{open_loop_detail}",
                call_id="memory-target-2",
            )
        checklist = self.wiki.checklist_from_diary(diary)
        if memory is not None:
            self._emit_memory_state(memory, messages)
        self._emit_executive_state(executive, messages)
        memory_payload = memory_api_payload(memory) if memory is not None else {}
        ready = bool(
            memory is not None
            and memory_payload.get("phase") == "review_draft"
            and self.wiki.is_diary_complete(diary)
            and not (executive and executive.open_blocking_findings())
        )
        yield SseFinal(
            reply="Logged the lesson.",
            artifact_markdown=diary,
            ready=ready,
            completeness=checklist,
            last_change_summary=(
                memory.last_change_summary if memory is not None else None
            ),
            memory_state=memory_payload or None,
            executive_state=(
                executive_api_payload(executive) if executive is not None else None
            ),
        )

    def _plan_final(
        self,
        reply: str,
        plan_md: str,
        planning: PlanRuntime | None,
        executive: ExecutiveRuntime | None = None,
    ) -> SseFinal:
        payload = planning_api_payload(planning) if planning is not None else {}
        return SseFinal(
            reply=reply,
            artifact_markdown=plan_md,
            ready=not (executive and executive.open_blocking_findings()),
            completeness=None,
            phase=payload.get("phase"),
            last_change_summary=payload.get("last_change_summary"),
            session_state=payload.get("session_state"),
            lesson_planning_state=payload.get("lesson_planning_state"),
            memory_candidates=payload.get("memory_candidates"),
            executive_state=(
                executive_api_payload(executive) if executive is not None else None
            ),
        )

    async def plan_chat_stream(
        self,
        class_id: str,
        messages: list[ChatMessage],
        partial_plan: str = "",
        attachments: list[ChatAttachment] | None = None,
        planning: PlanRuntime | None = None,
        executive: ExecutiveRuntime | None = None,
    ) -> AsyncIterator:
        latest = messages[-1].content.lower() if messages else ""
        self._emit_executive_state(executive, messages)

        if self._is_high_stakes_student_request(messages):
            yield self._plan_final(
                "I cannot make high-stakes student decisions. I can help review "
                "evidence and draft neutral observations for teacher review.",
                partial_plan or READY_PLAN,
                planning,
            )
            return

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
def memory_candidate_ledger(tmp_path: Path) -> MemoryCandidateLedger:
    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    return ledger


@pytest.fixture
def client(
    wiki: WikiStore,
    agents: StubAgentRunner,
    memory_candidate_ledger: MemoryCandidateLedger,
) -> Iterator[TestClient]:
    ingest = IngestService(
        wiki=wiki,
        agents=agents,
        memory_candidate_ledger=memory_candidate_ledger,
    )
    plan = PlanService(
        wiki=wiki,
        agents=agents,
        memory_candidate_ledger=memory_candidate_ledger,
    )

    app.dependency_overrides[deps.get_wiki] = lambda: wiki
    app.dependency_overrides[deps.get_agents] = lambda: agents
    app.dependency_overrides[deps.get_memory_candidate_ledger] = (
        lambda: memory_candidate_ledger
    )
    app.dependency_overrides[deps.get_ingest_service] = lambda: ingest
    app.dependency_overrides[deps.get_plan_service] = lambda: plan
    try:
        # raise_server_exceptions=False so the global handler's JSON envelope is
        # returned (mirrors production) instead of re-raising in the test client.
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
