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
    resolve_student_observations,
)


def _obs(wiki, diary):
    return resolve_student_observations(
        wiki, CLASS_ID, wiki._extract_section_body(diary, "Student observations")
    )

from tests.conftest import CLASS_ID


def _row(report, row_id):
    return next(row for row in report.rows if row.row_id == row_id)


def test_target_mismatch_blocks_but_unresolved_students_are_advisory(wiki):
    """Target-date mismatch is a hard block; unresolved student subjects are only
    advisory — the write path skips them, so a name/id it can't map must never
    hard-block a save (false positives are worse than false negatives here)."""
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
    assert _row(report, "student_references").status == "note"  # advisory
    summary = _row(report, "student_references").summary
    assert "S-999" in summary
    assert "Jens Haller" in summary
    assert "S006" in summary

    executive = ExecutiveRuntime()
    apply_memory_verification_report(executive, report)
    # Only the date mismatch blocks; student references never hard-block.
    assert {finding.finding_id for finding in executive.open_blocking_findings()} == {
        "memory-target-date",
    }
    student = executive.findings["memory-student-references"]
    assert student.severity == "advisory"


def test_unknown_student_in_observations_is_advisory_and_not_written(wiki):
    """An unknown student subject warns and is skipped at write time (never
    fabricated), but does not block the save (input-to-wiki reconciliation)."""
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
        "- S-006: dominated the recap.\n"
        "- S-014: Asked strong bonding questions.\n\n",
    )

    report = build_memory_verification_report(wiki, CLASS_ID, diary, runtime)
    assert _row(report, "student_references").status == "note"
    assert "S-006" in _row(report, "student_references").summary

    executive = ExecutiveRuntime()
    apply_memory_verification_report(executive, report)
    assert not any(
        finding.finding_id == "memory-student-references"
        for finding in executive.open_blocking_findings()
    )

    # Write path resolves the real id and drops the unknown one — no fabrication.
    resolved = _obs(wiki, diary)
    assert "S-014" in resolved.by_id
    assert "S-006" not in resolved.by_id


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


def test_typo_name_resolves_by_similarity_as_advisory(wiki):
    """A typo'd name (teachers write names, not ids) fuzzy-resolves to its
    roster id and IS written, with an advisory note to confirm the match —
    never a hard block."""
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
        "## Student observations\n\n- Matt Keler: Needed a scaffold.\n\n",
    )

    report = build_memory_verification_report(wiki, CLASS_ID, diary, runtime)
    assert _row(report, "student_references").status == "note"
    assert "Matt Keler" in _row(report, "student_references").summary

    executive = ExecutiveRuntime()
    apply_memory_verification_report(executive, report)
    assert not any(
        finding.finding_id == "memory-student-references"
        for finding in executive.open_blocking_findings()
    )

    # The typo is fuzzy-matched to Matt Keller (S-042) and written.
    resolved = _obs(wiki, diary)
    assert resolved.by_id.get("S-042") == ["Needed a scaffold."]


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


def test_bullet_labels_outside_student_sections_do_not_block(wiki):
    """F1 regression: '- Label:' bullets in non-student sections (What went well,
    Homework & follow-ups) must not be read as phantom roster students. Only the
    Student participation/observations sections supply name/label candidates;
    S-### ids stay globally checked (see the S-006-in-participation regression)."""
    runtime = MemoryRuntime(
        target=MemoryTargetState(
            lesson_date="2026-07-20",
            target_confirmed=True,
            target_kind="planned_lesson",
            needs_confirmation=False,
        )
    )
    diary = (
        wiki.empty_diary_template("2026-07-20")
        .replace(
            "## What went well\n\n",
            "## What went well\n\n"
            "- The redox bridge worked well when I said: we share electrons.\n\n",
        )
        .replace(
            "## Homework & follow-ups\n\n",
            "## Homework & follow-ups\n\n- Homework: read the alkanes section.\n\n",
        )
    )

    resolved = _obs(wiki, diary)
    assert resolved.by_id == {}
    assert resolved.warnings == []

    report = build_memory_verification_report(wiki, CLASS_ID, diary, runtime)
    assert _row(report, "student_references").status == "clear", _row(
        report, "student_references"
    ).summary


def test_prose_without_a_subject_is_not_treated_as_a_student(wiki):
    """A colon-less prose bullet in Student observations has no subject, so it is
    ignored — the resolver never guesses names out of free sentences."""
    diary = wiki.empty_diary_template("2026-07-20").replace(
        "## Student observations\n\n",
        "## Student observations\n\n"
        "- Carbon bonding was introduced with methane and ethane.\n\n",
    )
    resolved = _obs(wiki, diary)
    assert resolved.by_id == {}
    assert resolved.warnings == []


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
