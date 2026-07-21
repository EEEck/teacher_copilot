from app.teacher_agent.executive_verification import ExecutiveRuntime
from app.teacher_agent.memory_update_state import MemoryRuntime, MemoryTargetState
from app.teacher_agent.memory_verification import (
    apply_memory_verification_report,
    build_memory_verification_report,
)
from app.teacher_agent.roster_resolve import (
    ClassRosterIndex,
    RosterStudent,
    load_class_roster,
    normalize_person_key,
    recommended_alias,
    resolve_diary_student_references,
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
        "- Jens Haller: Explained the model clearly.\n\n",
    )

    report = build_memory_verification_report(wiki, CLASS_ID, diary, runtime)

    assert _row(report, "target").status == "needs_teacher_decision"
    assert _row(report, "student_references").status == "needs_teacher_decision"
    summary = _row(report, "student_references").summary
    assert "S-999" in summary
    assert "Jens Haller" in summary
    assert "S006" in summary or "S-006" in summary

    executive = ExecutiveRuntime()
    apply_memory_verification_report(executive, report)
    assert {finding.finding_id for finding in executive.open_blocking_findings()} == {
        "memory-target-date",
        "memory-student-references",
    }


def test_regression_s006_in_participation_blocks_write_gate(wiki):
    """Live miss: unknown S-006 lived only under ## Student participation.

    Observations had valid IDs, so the old observations-only pack stayed clear
    and Save applied. Full-diary scan must open memory-student-references.
    """
    runtime = MemoryRuntime(
        target=MemoryTargetState(
            lesson_date="2026-07-20",
            target_confirmed=True,
            target_kind="planned_lesson",
            needs_confirmation=False,
        )
    )
    diary = wiki.empty_diary_template("2026-07-20").replace(
        "## Student participation\n\n",
        "## Student participation\n\n"
        "- S-006 answered many recap questions and dominated the room.\n\n",
    ).replace(
        "## Student observations\n\n",
        "## Student observations\n\n- S-014: Asked strong bonding questions.\n\n",
    )

    report = build_memory_verification_report(wiki, CLASS_ID, diary, runtime)
    assert _row(report, "student_references").status == "needs_teacher_decision"
    assert "S-006" in _row(report, "student_references").summary

    executive = ExecutiveRuntime()
    apply_memory_verification_report(executive, report)
    assert any(
        finding.finding_id == "memory-student-references"
        for finding in executive.open_blocking_findings()
    )


def test_memory_verification_allows_unique_roster_names(wiki):
    runtime = MemoryRuntime(
        target=MemoryTargetState(
            lesson_date="2026-07-20",
            target_confirmed=True,
            target_kind="planned_lesson",
            needs_confirmation=False,
        )
    )
    diary = wiki.empty_diary_template("2026-07-20").replace(
        "## Student observations\n\n",
        "## Student observations\n\n"
        "- Matt: Explained the model clearly.\n"
        "- Mira Lange: Supported peers in discussion.\n\n",
    )

    report = build_memory_verification_report(wiki, CLASS_ID, diary, runtime)
    assert _row(report, "student_references").status == "clear"
    assert report.overall_status == "clear"


def test_memory_verification_suggests_typo_then_blocks_until_corrected(wiki):
    runtime = MemoryRuntime(
        target=MemoryTargetState(
            lesson_date="2026-07-20",
            target_confirmed=True,
            target_kind="planned_lesson",
            needs_confirmation=False,
        )
    )
    diary = wiki.empty_diary_template("2026-07-20").replace(
        "## Student observations\n\n",
        "## Student observations\n\n- Henry Schmit: Needed a scaffold.\n\n",
    )
    # No Henry on fixture roster — use Matt Keller typo instead.
    diary = wiki.empty_diary_template("2026-07-20").replace(
        "## Student observations\n\n",
        "## Student observations\n\n- Matt Keler: Needed a scaffold.\n\n",
    )

    report = build_memory_verification_report(wiki, CLASS_ID, diary, runtime)
    assert _row(report, "student_references").status == "needs_teacher_decision"
    summary = _row(report, "student_references").summary
    assert "Matt Keler" in summary
    assert "Matt" in summary  # recommended alias (unique first name)


def test_normalize_german_variants_match():
    assert normalize_person_key("Kai Müller") == normalize_person_key("Kai Mueller")
    assert normalize_person_key("Kai Müller") == normalize_person_key("Kai Müller")


def test_recommended_alias_uses_minimal_unique_last_prefix(wiki):
    index = load_class_roster(wiki, CLASS_ID)
    mira = index.by_id["S-046"]
    assert recommended_alias(mira, index) == "Mira"

    a = RosterStudent("S-001", "Kai Müller", "Kai", "Müller")
    b = RosterStudent("S-002", "Kai Mustermann", "Kai", "Mustermann")
    clash = ClassRosterIndex(students=[a, b], by_id={"S-001": a, "S-002": b})
    alias_a = recommended_alias(a, clash)
    alias_b = recommended_alias(b, clash)
    assert alias_a.startswith("Kai M")
    assert alias_b.startswith("Kai M")
    assert alias_a != alias_b


def test_resolve_ignores_unrelated_prose_capitalized_words(wiki):
    diary = wiki.empty_diary_template("2026-07-20").replace(
        "## What was covered\n\n",
        "## What was covered\n\n"
        "- Carbon bonding was introduced with methane and ethane.\n\n",
    )
    hits = resolve_diary_student_references(wiki, CLASS_ID, diary)
    assert not any(hit.decision == "block" and "Carbon" in hit.raw for hit in hits)


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
