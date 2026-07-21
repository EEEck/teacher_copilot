"""Bounded deterministic checks for the lesson-plan verification pack.

The pack deliberately treats format and provenance gaps as teacher-facing notes.
The durable write gate still owns only revision integrity and severe safety
findings; a teacher may use a different Markdown layout.
"""

from __future__ import annotations

import hashlib
import re
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


def _audience_body(markdown: str, audience: str) -> str:
    """Return the body under the first matching audience heading, if any."""
    text = markdown or ""
    patterns = {
        "teacher": (r"(?im)^##\s+Teacher(?:\s+Lesson\s+Plan)?\s*$",),
        "student": (r"(?im)^##\s+Student(?:\s+Materials)?\s*$",),
        "observation": (
            r"(?im)^##\s+Observation(?:\s+and\s+Update\s+Capture)?\s*$",
        ),
    }
    for pattern in patterns[audience]:
        match = re.search(pattern, text)
        if not match:
            continue
        start = match.end()
        next_heading = re.search(r"(?m)^##\s+", text[start:])
        end = start + next_heading.start() if next_heading else len(text)
        return text[start:end]
    return ""


_TASK_LABEL_RE = re.compile(
    r"(?im)^\s*(?:[-*]|\d+[.)])?\s*"
    r"(?:core\s+evidence\s+task|student\s+task|evidence\s+task|shared\s+task)"
    r"\s*[:—-]\s*(.+?)\s*$"
)

_STUDENT_LEAK_RE = re.compile(
    r"(?i)\b(?:look[- ]?fors?|misconceptions?|scaffolds?|confer(?:ring|s)?|"
    r"teacher\s+move)\b"
)

_EXIT_HEADING_RE = re.compile(
    r"^#{2,4}\s+.*\bexit\b.*$|^\s*[-*]\s+(?:exit\s+(?:evidence|ticket|check)|exit)\s*[:—-]",
    re.IGNORECASE | re.MULTILINE,
)

_EXIT_BUCKET_RE = re.compile(
    r"\b(?:secure|developing|needs\s+revisit|got\s+it|almost)\b|"
    r"got\s+it\s*/\s*almost\s*/\s*needs\b",
    re.IGNORECASE,
)


def _named_teacher_tasks(teacher_body: str) -> list[str]:
    """Extract explicitly labeled student/evidence tasks from the teacher section."""
    tasks: list[str] = []
    for match in _TASK_LABEL_RE.finditer(teacher_body or ""):
        task = " ".join(match.group(1).split()).strip(" .;")
        if len(task) >= 12:
            tasks.append(task)
    return tasks


def _task_appears_in_student(task: str, student_body: str) -> bool:
    """Prefer false negatives: require a substantial contiguous fragment."""
    student = " ".join((student_body or "").lower().split())
    normalized = " ".join(task.lower().split())
    if len(normalized) < 12 or not student:
        return True
    if normalized in student:
        return True
    # Allow minor wording drift: check a long leading/trailing fragment.
    words = normalized.split()
    if len(words) >= 5:
        fragment = " ".join(words[:5])
        if len(fragment) >= 12 and fragment in student:
            return True
        fragment = " ".join(words[-5:])
        if len(fragment) >= 12 and fragment in student:
            return True
    return False


def _check_task_alignment(markdown: str) -> PlanVerificationRow:
    teacher = _audience_body(markdown, "teacher")
    student = _audience_body(markdown, "student")
    missing = [
        task
        for task in _named_teacher_tasks(teacher)
        if student and not _task_appears_in_student(task, student)
    ]
    if missing:
        return PlanVerificationRow(
            row_id="task_alignment",
            label="Teacher–student task alignment",
            status="note",
            summary=(
                "A labeled student/evidence task in the teacher plan was not "
                "found under Student Materials."
            ),
        )
    return PlanVerificationRow(
        row_id="task_alignment",
        label="Teacher–student task alignment",
        status="clear",
        summary="No labeled teacher/student task mismatch was found.",
    )


def _check_student_leak(markdown: str) -> PlanVerificationRow:
    student = _audience_body(markdown, "student")
    if student and _STUDENT_LEAK_RE.search(student):
        return PlanVerificationRow(
            row_id="student_leak",
            label="Student materials stay student-facing",
            status="note",
            summary=(
                "Student Materials appear to include teacher-only diagnostic "
                "language (for example look-for, misconception, scaffold, "
                "confer, or teacher move)."
            ),
        )
    return PlanVerificationRow(
        row_id="student_leak",
        label="Student materials stay student-facing",
        status="clear",
        summary="No teacher-only diagnostic keywords were found in Student Materials.",
    )


def _check_exit_buckets(markdown: str) -> PlanVerificationRow:
    """Only advise when an exit section is clearly present but lacks sort language."""
    bodies = [
        _audience_body(markdown, "teacher"),
        _audience_body(markdown, "student"),
        _audience_body(markdown, "observation"),
        markdown or "",
    ]
    exit_present = any(_EXIT_HEADING_RE.search(body) for body in bodies)
    if not exit_present:
        return PlanVerificationRow(
            row_id="exit_buckets",
            label="Exit evidence sort buckets",
            status="clear",
            summary="No explicit exit section was found to check for sort buckets.",
        )
    if any(_EXIT_BUCKET_RE.search(body) for body in bodies):
        return PlanVerificationRow(
            row_id="exit_buckets",
            label="Exit evidence sort buckets",
            status="clear",
            summary="Exit evidence includes usable sort-bucket language.",
        )
    return PlanVerificationRow(
        row_id="exit_buckets",
        label="Exit evidence sort buckets",
        status="note",
        summary=(
            "An exit section is present but no sort-bucket language was found "
            "(secure/developing/needs revisit or Got it/Almost/Needs)."
        ),
    )


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

    task_row = _check_task_alignment(markdown)
    leak_row = _check_student_leak(markdown)
    exit_row = _check_exit_buckets(markdown)

    rows = [package_row, source_row, duration_row, task_row, leak_row, exit_row]
    # Package integrity checks stay advisory notes only; they never block save.
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
