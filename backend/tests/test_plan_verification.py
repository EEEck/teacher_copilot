"""Deterministic foundations for the Plan verification pack."""

import asyncio

from pydantic import SecretStr
import pytest

from app.config import Settings
from app.schemas.api import SavePlanRequest
from app.teacher_agent.agents import AgentRunner
from app.teacher_agent.executive_verification import artifact_fingerprint
from app.teacher_agent.plan_verification import build_plan_verification_report
from app.services.artifact_session_service import ArtifactSessionService
from app.services.plan_service import PlanService


def _row(report, row_id: str):
    return next(row for row in report.rows if row.row_id == row_id)


_CONSULTED = [
    {"source_id": "by-lehrplanplus-chemie-9-ntg", "section_id": "c9_atombau"}
]


def _clean_plan_markdown() -> str:
    return """# Lesson Plan — Atomic structure

> Duration: 45 min

## Teacher Lesson Plan
- Einstieg (10 min)
- Erarbeitung (25 min)
- Sicherung (10 min)

- Core evidence task: Compare two atom models and explain one limit of each model.

### Exit evidence
Sort responses into secure / developing / needs revisit using whether students
link an observation to a model limit.

## Student Materials
Compare two atom models and explain one limit of each model.

## Observation and Update Capture
Collect the exit explanation and note which sort bucket fits.
"""


def test_plan_report_flags_missing_source_provenance_and_bad_duration():
    report = build_plan_verification_report(
        """# Lesson Plan — Carbon Bonding

> Duration: 45 min

## Teacher Lesson Plan
- Einstieg (10 min)
- Erarbeitung (30 min)
- Sicherung (10 min)

## Student Materials
Draw methane and explain the bond model.

## Observation and Update Capture
Collect one exit explanation.
""",
        consulted_sources=[],
    )

    assert report.pack_id == "plan"
    assert report.overall_status == "advisory"
    assert _row(report, "source_provenance").status == "note"
    assert _row(report, "duration").status == "note"
    assert _row(report, "markdown_package").status == "clear"


def test_plan_report_clean_package_passes_integrity_rows():
    report = build_plan_verification_report(
        _clean_plan_markdown(),
        consulted_sources=_CONSULTED,
    )

    assert report.overall_status == "clear"
    assert _row(report, "task_alignment").status == "clear"
    assert _row(report, "student_leak").status == "clear"
    assert _row(report, "exit_buckets").status == "clear"
    assert _row(report, "duration").status == "clear"


def test_plan_report_notes_student_leak_of_teacher_diagnostics():
    markdown = """# Lesson Plan

> Duration: 45 min

## Teacher Lesson Plan
- Einstieg (10 min)
- Erarbeitung (25 min)
- Sicherung (10 min)
- Core evidence task: Explain why sodium forms a positive ion.

## Student Materials
Explain why sodium forms a positive ion.
Look-for: students name electron loss.
Watch for the misconception that ions are molecules.

## Observation and Update Capture
Collect one exit explanation.
"""
    report = build_plan_verification_report(markdown, consulted_sources=_CONSULTED)

    assert report.overall_status == "advisory"
    assert _row(report, "student_leak").status == "note"
    assert _row(report, "task_alignment").status == "clear"


def test_plan_report_notes_missing_exit_buckets_when_exit_section_exists():
    markdown = """# Lesson Plan

> Duration: 45 min

## Teacher Lesson Plan
- Einstieg (10 min)
- Erarbeitung (25 min)
- Sicherung (10 min)
- Core evidence task: Revise a particle drawing after the electrolysis clip.

### Exit evidence
Ask students to revise one particle drawing from the demonstration.

## Student Materials
Revise a particle drawing after the electrolysis clip.

## Observation and Update Capture
Collect the exit drawing.
"""
    report = build_plan_verification_report(markdown, consulted_sources=_CONSULTED)

    assert report.overall_status == "advisory"
    assert _row(report, "exit_buckets").status == "note"


def test_plan_report_notes_teacher_student_task_mismatch():
    markdown = """# Lesson Plan

> Duration: 45 min

## Teacher Lesson Plan
- Einstieg (10 min)
- Erarbeitung (25 min)
- Sicherung (10 min)
- Core evidence task: Compare flame colors and link them to electron energy levels.

## Student Materials
Copy the shortened periodic table into your notebook.

## Observation and Update Capture
Collect one exit explanation.
"""
    report = build_plan_verification_report(markdown, consulted_sources=_CONSULTED)

    assert report.overall_status == "advisory"
    assert _row(report, "task_alignment").status == "note"
    # Advisory notes never raise overall to safety_hold.
    assert report.overall_status != "safety_hold"


def test_plan_review_packet_is_bounded_and_excludes_raw_source_bodies():
    from app.teacher_agent.plan_verification import build_plan_review_packet

    packet = build_plan_review_packet(
        teacher_request="Plan a 45-minute introductory ions lesson.",
        markdown="# Lesson Plan\n\n## Teacher Lesson Plan\nUse particle drawings.",
        route={"subject": "chemie", "grade": "9", "branch": "NTG"},
        class_context="Recent lesson: oxidation and reduction.",
        teacher_context="Prefer short paired investigations.",
        subject_expert="Use observation → model → explanation.",
        consulted_sources=[
            {
                "source_id": "bayern_lehrplanplus_chemie_9_ntg",
                "section_id": "9.1-ions",
                "raw_body": "This source body must never be in the judge packet.",
            }
        ],
    )

    assert "bayern_lehrplanplus_chemie_9_ntg#9.1-ions" in packet
    assert "This source body must never be in the judge packet." not in packet
    assert "Plan a 45-minute introductory ions lesson." in packet
    assert "observation → model → explanation" in packet


def test_judgement_merges_into_report_and_only_safety_can_hold():
    from app.teacher_agent.plan_verification import (
        PlanVerificationJudgement,
        PlanVerificationJudgementRow,
        merge_plan_verification_judgement,
    )

    deterministic = build_plan_verification_report(
        """# Lesson Plan

> Duration: 45 min

## Teacher Lesson Plan
- Einstieg (10 min)
- Erarbeitung (25 min)
- Sicherung (10 min)

## Student Materials
Explain one particle drawing.

## Observation and Update Capture
Collect one exit explanation.
""",
        consulted_sources=[
            {"source_id": "bayern_lehrplanplus_chemie_9_ntg", "section_id": "9.1"}
        ],
    )
    judgement = PlanVerificationJudgement(
        summary="The draft is pedagogically coherent; confirm the local scope choice.",
        rows=[
            PlanVerificationJudgementRow(
                row_id="curriculum_scope",
                status="needs_teacher_decision",
                summary="Organic chemistry is not established by the recorded Grade 9 section.",
            ),
            PlanVerificationJudgementRow(
                row_id="class_context",
                status="clear",
                summary="The recap connects to the recent redox lesson.",
            ),
            PlanVerificationJudgementRow(
                row_id="teacher_adjustments",
                status="clear",
                summary="The particle drawing comes before formal notation.",
            ),
            PlanVerificationJudgementRow(
                row_id="chemistry_pedagogy",
                status="clear",
                summary="The sequence moves from observation to model to explanation.",
            ),
            PlanVerificationJudgementRow(
                row_id="differentiation",
                status="clear",
                summary="All routes use the same exit evidence.",
            ),
            PlanVerificationJudgementRow(
                row_id="safety",
                status="clear",
                summary="No severe safety issue is identified.",
            ),
        ],
    )

    merged = merge_plan_verification_judgement(deterministic, judgement)

    assert merged.review_state == "complete"
    assert merged.overall_status == "advisory"
    assert _row(merged, "curriculum_scope").status == "needs_teacher_decision"


def test_plan_judgement_requires_each_teacher_facing_review_row():
    from pydantic import ValidationError
    from app.teacher_agent.plan_verification import PlanVerificationJudgement

    with pytest.raises(ValidationError, match="one row for each"):
        PlanVerificationJudgement(summary="Incomplete.", rows=[])


def test_plan_judge_receives_compact_context_without_raw_source_body(wiki, monkeypatch):
    from app.teacher_agent.plan_verification import PlanVerificationJudgement
    from app.teacher_agent.planning_state import PlanRuntime

    runner = AgentRunner(Settings(openai_api_key=SecretStr("test-key")), wiki)
    runtime = PlanRuntime()
    runtime.record_source_read("by-lehrplanplus-chemie-9-ntg", "c9_atombau")
    captured: list[str] = []

    async def fake_run(agent, user_input: str):
        captured.append(agent.instructions)
        assert user_input == "Review the supplied packet and return the report card."
        return PlanVerificationJudgement(
            summary="Clear.",
            rows=[
                {
                    "row_id": row_id,
                    "status": "clear",
                    "summary": "Clear.",
                }
                for row_id in (
                    "curriculum_scope",
                    "class_context",
                    "teacher_adjustments",
                    "chemistry_pedagogy",
                    "differentiation",
                    "safety",
                )
            ],
        )

    monkeypatch.setattr(runner, "_run_structured", fake_run)
    result = asyncio.run(
        runner.review_plan(
            "chemie_9b_2026_27",
            teacher_request="Plan an ions lesson.",
            markdown="# Lesson Plan",
            planning=runtime,
        )
    )

    assert result.summary == "Clear."
    assert "by-lehrplanplus-chemie-9-ntg#c9_atombau" in captured[0]
    assert "Raw source content" not in captured[0]


def test_plan_judge_runs_after_chat_and_updates_the_exact_draft_report(wiki, agents):
    async def scenario():
        service = ArtifactSessionService(wiki, agents)
        session = await service.start_session("plan", "chemie_9b_2026_27")
        await service.chat(session.session_id, "Plan the next chemistry lesson.")
        task = service._verification_tasks[session.session_id]
        await task
        return session.executive.verification_reports["plan"]

    report = asyncio.run(scenario())

    assert report["review_state"] == "complete"
    assert report["summary"] == "Pedagogical review completed for this draft."


def test_manual_plan_edit_marks_the_prior_pedagogical_review_stale(wiki, agents):
    async def scenario():
        service = ArtifactSessionService(wiki, agents)
        session = await service.start_session("plan", "chemie_9b_2026_27")
        await service.chat(session.session_id, "Plan the next chemistry lesson.")
        await service._verification_tasks[session.session_id]
        service.update_draft(session.session_id, "# Teacher-edited plan\n")
        return session.executive.verification_reports["plan"]

    report = asyncio.run(scenario())

    assert report["review_state"] == "stale"


def test_completed_plan_safety_hold_blocks_save_but_not_generation(wiki, agents, monkeypatch):
    from app.teacher_agent.executive_verification import WriteVerificationBlocked
    from app.teacher_agent.plan_verification import PlanVerificationJudgement

    async def safety_review(_class_id: str, **_kwargs):
        return PlanVerificationJudgement(
            summary="The proposed demonstration lacks a safe procedure.",
            safety_hold=True,
            rows=[
                {
                    "row_id": row_id,
                    "status": "needs_teacher_decision" if row_id == "safety" else "clear",
                    "summary": "Add and confirm the local safety procedure."
                    if row_id == "safety"
                    else "Clear.",
                }
                for row_id in (
                    "curriculum_scope",
                    "class_context",
                    "teacher_adjustments",
                    "chemistry_pedagogy",
                    "differentiation",
                    "safety",
                )
            ],
        )

    monkeypatch.setattr(agents, "review_plan", safety_review)

    async def scenario():
        service = PlanService(wiki, agents)
        session = await service.start_session("chemie_9b_2026_27")
        chat = await service.chat(session.session_id, "Plan the next chemistry lesson.")
        await service.core._verification_tasks[session.session_id]
        report = service.core.get_session(session.session_id).executive.verification_reports["plan"]
        assert report["overall_status"] == "safety_hold"
        assert report["artifact_fingerprint"] == artifact_fingerprint(chat.plan_markdown)
        with pytest.raises(WriteVerificationBlocked) as exc:
            await service.save(
                "chemie_9b_2026_27",
                SavePlanRequest(
                    session_id=session.session_id,
                    lesson_date="2026-10-05",
                    plan_markdown=chat.plan_markdown,
                ),
            )
        return chat, str(exc.value)

    chat, message = asyncio.run(scenario())

    assert chat.ready_to_save is True
    assert "severe safety issue" in message
