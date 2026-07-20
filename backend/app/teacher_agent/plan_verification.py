"""Bounded deterministic checks for the lesson-plan verification pack.

The pack deliberately treats format and provenance gaps as teacher-facing notes.
The durable write gate still owns only revision integrity and severe safety
findings; a teacher may use a different Markdown layout.
"""

from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.context_limits import apply_char_limit
from app.teacher_agent.quality import validate_lesson_duration

ReportStatus = Literal["clear", "advisory", "safety_hold"]
RowStatus = Literal["clear", "note", "needs_teacher_decision"]
ReviewState = Literal["pending", "complete", "failed", "stale"]


class PlanVerificationRow(BaseModel):
    row_id: str
    label: str
    status: RowStatus
    summary: str
    evidence_refs: list[str] = Field(default_factory=list)


class PlanVerificationReport(BaseModel):
    pack_id: Literal["plan"] = "plan"
    overall_status: ReportStatus
    summary: str
    rows: list[PlanVerificationRow] = Field(default_factory=list)
    review_state: ReviewState = "pending"
    artifact_fingerprint: str = ""


JudgementRowId = Literal[
    "curriculum_scope",
    "class_context",
    "teacher_adjustments",
    "chemistry_pedagogy",
    "differentiation",
    "safety",
]


class PlanVerificationJudgementRow(BaseModel):
    """One economy-model conclusion, bounded to a teacher-facing report row."""

    row_id: JudgementRowId
    status: RowStatus
    summary: str
    evidence_refs: list[str] = Field(default_factory=list)


class PlanVerificationJudgement(BaseModel):
    """No-tools reviewer output; it is not an artifact rewrite instruction."""

    summary: str
    rows: list[PlanVerificationJudgementRow] = Field(default_factory=list)
    safety_hold: bool = False

    @model_validator(mode="after")
    def requires_complete_report_card(self):
        required = set(JudgementRowId.__args__)
        present = {row.row_id for row in self.rows}
        if present != required or len(self.rows) != len(required):
            raise ValueError("plan judgement requires one row for each review category")
        return self


def _bounded(value: str, limit: int) -> str:
    return apply_char_limit((value or "").strip(), limit)


def _artifact_fingerprint(markdown: str) -> str:
    normalized = (markdown or "").replace("\r\n", "\n").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_plan_review_packet(
    *,
    teacher_request: str,
    markdown: str,
    route: dict[str, str],
    class_context: str,
    teacher_context: str,
    subject_expert: str,
    consulted_sources: list[dict[str, str]],
) -> str:
    """Build the no-tools judge packet without raw source bodies or prompts."""
    source_refs = [
        f"{item.get('source_id', '').strip()}#{item.get('section_id', 'summary').strip() or 'summary'}"
        for item in consulted_sources
        if item.get("source_id", "").strip()
    ]
    route_text = ", ".join(
        f"{key}={route[key]}" for key in ("subject", "grade", "branch") if route.get(key)
    ) or "route unavailable"
    return "\n\n".join(
        (
            "# Plan verification packet",
            f"## Selected route\n{route_text}",
            f"## Teacher request\n{_bounded(teacher_request, 2_000)}",
            f"## Draft Markdown\n{_bounded(markdown, 12_000)}",
            f"## Class context\n{_bounded(class_context, 4_000)}",
            f"## Teacher preferences\n{_bounded(teacher_context, 3_000)}",
            f"## Active subject expert\n{_bounded(subject_expert, 5_000)}",
            "## Trusted sections read\n"
            + ("\n".join(f"- {ref}" for ref in source_refs[:12]) or "- None recorded"),
        )
    )


def merge_plan_verification_judgement(
    deterministic: PlanVerificationReport,
    judgement: PlanVerificationJudgement,
) -> PlanVerificationReport:
    """Overlay the bounded pedagogical review without weakening hard checks."""
    rows_by_id = {row.row_id: row for row in deterministic.rows}
    rows_by_id.update(
        {
            row.row_id: PlanVerificationRow(
                row_id=row.row_id,
                label={
                    "curriculum_scope": "Curriculum grounding and scope",
                    "class_context": "Class context and recent-lesson fit",
                    "teacher_adjustments": "Teacher preferences and framework adjustments",
                    "chemistry_pedagogy": "Chemistry pedagogy and best practices",
                    "differentiation": "Differentiation and common evidence task",
                    "safety": "Safety",
                }[row.row_id],
                status=row.status,
                summary=row.summary,
                evidence_refs=row.evidence_refs,
            )
            for row in judgement.rows
        }
    )
    rows = list(rows_by_id.values())
    if judgement.safety_hold:
        overall: ReportStatus = "safety_hold"
    elif any(row.status != "clear" for row in rows):
        overall = "advisory"
    else:
        overall = "clear"
    return PlanVerificationReport(
        overall_status=overall,
        summary=judgement.summary.strip()
        or (
            "Plan review has advisory notes for teacher review."
            if overall == "advisory"
            else "Plan review is clear."
        ),
        rows=rows,
        review_state="complete",
        artifact_fingerprint=deterministic.artifact_fingerprint,
    )


def _has_audience(markdown: str, audience: str) -> bool:
    text = (markdown or "").lower()
    aliases = {
        "teacher": ("## teacher lesson plan", "## teacher"),
        "student": ("## student materials", "## student"),
        "observation": (
            "## observation and update capture",
            "## observation",
        ),
    }
    return any(heading in text for heading in aliases[audience])


def build_plan_verification_report(
    markdown: str,
    *,
    consulted_sources: list[dict[str, str]],
) -> PlanVerificationReport:
    """Return deterministic, advisory Plan-pack report rows for one draft."""
    missing_audiences = [
        name
        for name in ("teacher", "student", "observation")
        if not _has_audience(markdown, name)
    ]
    if missing_audiences:
        package_row = PlanVerificationRow(
            row_id="markdown_package",
            label="Markdown package integrity",
            status="note",
            summary=(
                "Teacher-controlled Markdown does not clearly label: "
                + ", ".join(missing_audiences)
                + "."
            ),
        )
    else:
        package_row = PlanVerificationRow(
            row_id="markdown_package",
            label="Markdown package integrity",
            status="clear",
            summary="Teacher, student, and observation audiences are present.",
        )

    if consulted_sources:
        source_row = PlanVerificationRow(
            row_id="source_provenance",
            label="Curriculum-source provenance",
            status="clear",
            summary="The plan session recorded trusted-source reads.",
            evidence_refs=[
                f"{item.get('source_id', '')}#{item.get('section_id', 'summary')}"
                for item in consulted_sources
                if item.get("source_id")
            ],
        )
    else:
        source_row = PlanVerificationRow(
            row_id="source_provenance",
            label="Curriculum-source provenance",
            status="note",
            summary="No trusted-source section was read in this planning session.",
        )

    duration_errors = validate_lesson_duration(markdown)
    if duration_errors:
        duration_row = PlanVerificationRow(
            row_id="duration",
            label="Timing and practicality",
            status="note",
            summary=duration_errors[0],
        )
    else:
        duration_row = PlanVerificationRow(
            row_id="duration",
            label="Timing and practicality",
            status="clear",
            summary="No deterministic timing conflict was found.",
        )

    rows = [package_row, source_row, duration_row]
    overall = "advisory" if any(row.status == "note" for row in rows) else "clear"
    return PlanVerificationReport(
        overall_status=overall,
        summary=(
            "Plan review has advisory notes for teacher review."
            if overall == "advisory"
            else "Plan passes deterministic verification checks."
        ),
        rows=rows,
        artifact_fingerprint=_artifact_fingerprint(markdown),
    )
