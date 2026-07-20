from app.teacher_agent.executive_verification import ExecutiveRuntime
from app.teacher_agent.memory_update_state import MemoryRuntime, MemoryTargetState
from app.teacher_agent.memory_verification import (
    apply_memory_verification_report,
    build_memory_verification_report,
)

from tests.conftest import CLASS_ID


def _row(report, row_id):
    return next(row for row in report.rows if row.row_id == row_id)


def test_memory_verification_blocks_mismatched_target_and_student_references(wiki):
    runtime = MemoryRuntime(
        target=MemoryTargetState(
            lesson_date="2026-07-20",
            target_confirmed=True,
            target_kind="planned_lesson",
            needs_confirmation=False,
        )
    )
    diary = wiki.empty_diary_template("2026-09-28").replace(
        "## Student observations\n\n",
        "## Student observations\n\n"
        "- S006: Needed a model prompt.\n"
        "- S-999: Needs a notation check.\n"
        "- Matt: Explained the model clearly.\n\n",
    )

    report = build_memory_verification_report(wiki, CLASS_ID, diary, runtime)

    assert _row(report, "target").status == "needs_teacher_decision"
    assert _row(report, "student_references").status == "needs_teacher_decision"
    assert "S-006" in _row(report, "student_references").summary
    assert "S-999" in _row(report, "student_references").summary
    assert "Matt" in _row(report, "student_references").summary

    executive = ExecutiveRuntime()
    apply_memory_verification_report(executive, report)
    assert {finding.finding_id for finding in executive.open_blocking_findings()} == {
        "memory-target-date",
        "memory-student-references",
    }


def test_memory_verification_clears_its_blockers_when_the_draft_is_corrected(wiki):
    runtime = MemoryRuntime(
        target=MemoryTargetState(
            lesson_date="2026-07-20",
            target_confirmed=True,
            target_kind="planned_lesson",
            needs_confirmation=False,
        )
    )
    executive = ExecutiveRuntime()
    invalid = wiki.empty_diary_template("2026-09-28").replace(
        "## Student observations\n\n",
        "## Student observations\n\n- S-999: Needs a notation check.\n\n",
    )
    apply_memory_verification_report(
        executive,
        build_memory_verification_report(wiki, CLASS_ID, invalid, runtime),
    )

    corrected = wiki.empty_diary_template("2026-07-20").replace(
        "## Student observations\n\n",
        "## Student observations\n\n- S-042: Needs a notation check.\n\n",
    )
    report = build_memory_verification_report(wiki, CLASS_ID, corrected, runtime)
    apply_memory_verification_report(executive, report)

    assert report.overall_status == "clear"
    assert executive.open_blocking_findings() == []
