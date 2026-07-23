"""Deterministic integrity checks for Update Memory drafts."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.teacher_agent.executive_verification import (
    ExecutiveFinding,
    ExecutiveRuntime,
    VerificationCategory,
    artifact_fingerprint,
)
from app.teacher_agent.memory_update_state import MemoryRuntime
from app.teacher_agent.roster_resolve import resolve_student_observations

PACK_ID = "update_memory"


class MemoryVerificationRow(BaseModel):
    row_id: str
    label: str
    status: str = "clear"
    summary: str


class MemoryVerificationReport(BaseModel):
    pack_id: str = PACK_ID
    overall_status: str = "clear"
    artifact_fingerprint: str
    rows: list[MemoryVerificationRow] = Field(default_factory=list)


def _student_reference_warnings(wiki, class_id: str, diary_markdown: str) -> list[str]:
    """Advisory warnings for observation subjects that don't map to the roster.

    Runs the write-time resolver on the Student observations section only, so it
    mirrors exactly what the commit will (and won't) write: teachers write names
    (resolved via exact/alias/fuzzy). An unmappable subject is skipped at write
    time and flagged here — never a hard save block, never a silent drop.
    """
    block = wiki._extract_section_body(diary_markdown, "Student observations")
    return resolve_student_observations(wiki, class_id, block).warnings


def build_memory_verification_report(
    wiki, class_id: str, diary_markdown: str, runtime: MemoryRuntime
) -> MemoryVerificationReport:
    expected_date = runtime.target.lesson_date.strip()
    actual_date = wiki.extract_date_from_diary(diary_markdown) or ""
    target_mismatch = bool(
        runtime.target.target_confirmed
        and expected_date
        and actual_date
        and actual_date != expected_date
    )
    target_row = MemoryVerificationRow(
        row_id="target",
        label="Lesson target",
        status="needs_teacher_decision" if target_mismatch else "clear",
        summary=(
            f"The draft says {actual_date}, but this session targets {expected_date}."
            if target_mismatch
            else (
                f"Draft matches the confirmed lesson target {expected_date}."
                if runtime.target.target_confirmed and expected_date
                else "No confirmed lesson target is available yet."
            )
        ),
    )

    student_warnings = _student_reference_warnings(wiki, class_id, diary_markdown)
    # Advisory only: the write path skips unmappable observations, so this never
    # hard-blocks a save (a false positive must not stop a valid write).
    student_row = MemoryVerificationRow(
        row_id="student_references",
        label="Student references",
        status="note" if student_warnings else "clear",
        summary=(
            "; ".join(student_warnings)
            if student_warnings
            else "All student observations map to the class roster."
        ),
    )
    rows = [target_row, student_row]
    return MemoryVerificationReport(
        overall_status=(
            "needs_teacher_decision"
            if any(row.status == "needs_teacher_decision" for row in rows)
            else "clear"
        ),
        artifact_fingerprint=artifact_fingerprint(diary_markdown),
        rows=rows,
    )


def _set_or_resolve_blocker(
    executive: ExecutiveRuntime,
    *,
    finding_id: str,
    category: VerificationCategory,
    summary: str,
    question: str,
    should_block: bool,
) -> None:
    existing = executive.findings.get(finding_id)
    if should_block:
        executive.findings[finding_id] = ExecutiveFinding(
            finding_id=finding_id,
            category=category,
            severity="blocking",
            summary=summary,
            question=question,
            evidence_refs=[PACK_ID],
        )
    elif existing and existing.status == "open":
        executive.findings[finding_id] = existing.model_copy(
            update={"status": "resolved", "resolution": "Draft corrected."}
        )


def _set_or_resolve_advisory(
    executive: ExecutiveRuntime,
    *,
    finding_id: str,
    category: VerificationCategory,
    summary: str,
    present: bool,
) -> None:
    existing = executive.findings.get(finding_id)
    if present:
        executive.findings[finding_id] = ExecutiveFinding(
            finding_id=finding_id,
            category=category,
            severity="advisory",
            summary=summary,
            evidence_refs=[PACK_ID],
        )
    elif existing and existing.status == "open":
        executive.findings[finding_id] = existing.model_copy(
            update={"status": "resolved", "resolution": "Draft corrected."}
        )


def apply_memory_verification_report(
    executive: ExecutiveRuntime, report: MemoryVerificationReport
) -> None:
    executive.verification_reports[PACK_ID] = report.model_dump()
    rows = {row.row_id: row for row in report.rows}
    target = rows["target"]
    student_references = rows["student_references"]
    _set_or_resolve_blocker(
        executive,
        finding_id="memory-target-date",
        category="time_state",
        summary=target.summary,
        question="Which lesson date should this result be stored under?",
        should_block=target.status == "needs_teacher_decision",
    )
    _set_or_resolve_advisory(
        executive,
        finding_id="memory-student-references",
        category="identity",
        summary=student_references.summary,
        present=student_references.status == "note",
    )
