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
from app.teacher_agent.roster_resolve import resolve_diary_student_references

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


def _short(items: list[str], limit: int = 5) -> str:
    shown = items[:limit]
    suffix = "" if len(items) <= limit else f" and {len(items) - limit} more"
    return ", ".join(shown) + suffix


def _student_reference_issues(
    wiki, class_id: str, diary_markdown: str
) -> tuple[list[str], list[str], list[str]]:
    """Return block issues, suggest notes, and allowed recommended aliases.

    Scans the full diary. Teachers typically write names; S-### is the internal
    key. Teacher-facing recommended form is the unique Firstname[+surname
    prefix] alias from the roster resolver.
    """
    hits = resolve_diary_student_references(wiki, class_id, diary_markdown)
    blocks: list[str] = []
    suggests: list[str] = []
    allowed_notes: list[str] = []
    for hit in hits:
        if hit.decision == "block":
            blocks.append(f"{hit.raw} ({hit.reason})")
        elif hit.decision == "suggest":
            alias = hit.recommended_alias or hit.student_id or "?"
            internal = f", internal {hit.student_id}" if hit.student_id else ""
            suggests.append(f"{hit.raw} → use '{alias}'{internal}")
        elif (
            hit.decision == "allow"
            and hit.recommended_alias
            and hit.raw != hit.recommended_alias
            and hit.raw.upper() != (hit.student_id or "")
        ):
            # Soft note only — does not block Ready.
            allowed_notes.append(
                f"{hit.raw} ok (key {hit.student_id}; preferred '{hit.recommended_alias}')"
            )
    return blocks, suggests, allowed_notes


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

    blocks, suggests, _allowed_notes = _student_reference_issues(
        wiki, class_id, diary_markdown
    )
    student_issues: list[str] = []
    # Suggests still block Ready until the teacher edits the diary; report-only.
    if blocks:
        student_issues.append(f"unresolved: {_short(blocks)}")
    if suggests:
        student_issues.append(f"suggested fix: {_short(suggests)}")
    student_row = MemoryVerificationRow(
        row_id="student_references",
        label="Student references",
        status="needs_teacher_decision" if student_issues else "clear",
        summary=(
            "Resolve student names against the class roster "
            "(recommended form: Firstname + unique last-name prefix); "
            + "; ".join(student_issues)
            if student_issues
            else (
                "Student references uniquely match the class roster "
                "(recommended Firstname[+last prefix] aliases)."
            )
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
    _set_or_resolve_blocker(
        executive,
        finding_id="memory-student-references",
        category="identity",
        summary=student_references.summary,
        question=(
            "Please use each student's recommended roster alias "
            "(Firstname + unique last-name prefix), or a known S-### ID."
        ),
        should_block=student_references.status == "needs_teacher_decision",
    )
