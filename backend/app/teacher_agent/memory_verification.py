"""Deterministic integrity checks for Update Memory drafts."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from app.teacher_agent.executive_verification import (
    ExecutiveFinding,
    ExecutiveRuntime,
    VerificationCategory,
    artifact_fingerprint,
)
from app.teacher_agent.memory_update_state import MemoryRuntime
from app.teacher_agent.wiki.constants import STUDENT_ID_RE
from app.teacher_agent.wiki.parsing import extract_section_body

PACK_ID = "update_memory"
_ROSTER_ROW_RE = re.compile(
    r"^\|\s*(S-\d{3})\s*\|\s*([^|]+?)\s*\|", re.MULTILINE | re.IGNORECASE
)
_STUDENT_LABEL_RE = re.compile(r"^-\s*([^:]{1,80}):", re.MULTILINE)
_STUDENT_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_MALFORMED_STUDENT_ID_RE = re.compile(
    r"(?<![A-Za-z0-9-])S[-_ ]?(\d{3})(?!\d)", re.IGNORECASE
)


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


def _short(items: list[str], limit: int = 3) -> str:
    shown = items[:limit]
    suffix = "" if len(items) <= limit else f" and {len(items) - limit} more"
    return ", ".join(shown) + suffix


def _roster(wiki, class_id: str) -> tuple[set[str], dict[str, str]]:
    roster_md = wiki.read_text(wiki.roll_up_paths(class_id)["students"])
    ids = {match.upper() for match in STUDENT_ID_RE.findall(roster_md)}
    names: dict[str, str] = {}
    for match in _ROSTER_ROW_RE.finditer(roster_md):
        student_id = match.group(1).upper()
        full_name = " ".join(match.group(2).split())
        if full_name:
            names[full_name.lower()] = student_id
            first_name = full_name.split()[0]
            if first_name:
                names[first_name.lower()] = student_id
    return ids, names


def _student_reference_issues(
    wiki, class_id: str, diary_markdown: str
) -> tuple[list[str], list[str], list[str]]:
    """Return malformed IDs, unknown IDs, and non-pseudonym labels."""
    block = extract_section_body(diary_markdown, "Student observations")
    if not block:
        return [], [], []
    known_ids, known_names = _roster(wiki, class_id)
    referenced_ids = {match.upper() for match in STUDENT_ID_RE.findall(block)}
    unknown_ids = sorted(referenced_ids - known_ids)
    malformed = sorted(
        {
            f"S-{match.group(1)}"
            for match in _MALFORMED_STUDENT_ID_RE.finditer(block)
            if match.group(0).upper() != f"S-{match.group(1)}"
        }
    )

    labels = [
        " ".join(match.group(1).split())
        for match in [*_STUDENT_LABEL_RE.finditer(block), *_STUDENT_HEADING_RE.finditer(block)]
    ]
    non_pseudonym_labels: list[str] = []
    for label in labels:
        if STUDENT_ID_RE.fullmatch(label):
            continue
        if label.lower() in known_names:
            non_pseudonym_labels.append(label)
        elif re.fullmatch(r"S[-_ ]?\d{3}", label, re.IGNORECASE):
            continue
        elif label:
            non_pseudonym_labels.append(label)
    return malformed, unknown_ids, sorted(set(non_pseudonym_labels))


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

    malformed, unknown_ids, labels = _student_reference_issues(
        wiki, class_id, diary_markdown
    )
    student_issues: list[str] = []
    if malformed:
        student_issues.append(f"malformed ID(s): {_short(malformed)}")
    if unknown_ids:
        student_issues.append(f"unknown roster ID(s): {_short(unknown_ids)}")
    if labels:
        student_issues.append(f"non-pseudonym label(s): {_short(labels)}")
    student_row = MemoryVerificationRow(
        row_id="student_references",
        label="Student references",
        status="needs_teacher_decision" if student_issues else "clear",
        summary=(
            "Use only roster S-### IDs in Student observations; "
            + "; ".join(student_issues)
            if student_issues
            else "Student observation labels use known roster pseudonyms."
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
        question="Please replace each student reference with a known roster S-### ID.",
        should_block=student_references.status == "needs_teacher_decision",
    )
