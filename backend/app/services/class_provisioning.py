"""Deterministic creation of a new class wiki.

This is the config layer's write path, and it is deliberately *not* part of
`memory_skills.py`. Class identity (`class_config.md`, `curriculum_profile.md`,
`trusted_sources.md`) is configuration, not memory: it is not proposed by a
model, not folded through the candidate ledger, and not reviewed by Sweep. The
teacher supplies typed values, backend code renders the Markdown from templates,
and nothing here writes lesson records or curated memory.

Both front ends (the create form, and later the layer-0 setup agent) call
`create_class` with the same validated spec, so the write stays deterministic
regardless of who filled in the arguments.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.schemas.api import ClassSummary
from app.teacher_agent.wiki.constants import LESSON_RESULTS_SECTIONS
from app.teacher_agent.wiki.subject_frameworks import load_framework_index
from app.teacher_agent.wiki.trusted_sources import load_trusted_sources


SUPPORTED_SUBJECTS = ("chemie", "physik")
SUPPORTED_BRANCH = "NTG"
SUPPORTED_SCHOOL_TYPE = "Gymnasium"
SUPPORTED_STATE = "BY"

_SECTION_RE = re.compile(r"^[a-z]$")
_SLUG_RE = re.compile(r"^[a-z0-9_]+$")


class ClassProvisioningError(ValueError):
    """A class spec the backend refuses to write."""


@dataclass(frozen=True)
class CurriculumRoute:
    """One (subject, grade, branch) that has a reviewed shared framework."""

    subject: str
    grade: int
    branch: str


@dataclass(frozen=True)
class ClassSpec:
    label: str
    subject: str
    grade: int
    section: str = ""
    school_year: str = ""
    branch: str = SUPPORTED_BRANCH
    school_type: str = SUPPORTED_SCHOOL_TYPE
    state: str = SUPPORTED_STATE
    prior_learning: str = ""
    student_names: tuple[str, ...] = field(default_factory=tuple)


def available_routes(store) -> list[CurriculumRoute]:
    """Routes a class may be created for: those with a reviewed framework.

    The picker offers only these. `build_active_subject_expert_context_trace`
    degrades gracefully for anything else, but that is a safety net for wikis
    edited by hand — not a route we hand a teacher.
    """
    routes: list[CurriculumRoute] = []
    for subject in SUPPORTED_SUBJECTS:
        for entry in load_framework_index(store, subject).entries:
            routes.append(
                CurriculumRoute(subject=subject, grade=entry.grade, branch=entry.branch)
            )
    routes.sort(key=lambda r: (r.subject, r.grade, r.branch))
    return routes


def class_id_for(spec: ClassSpec) -> str:
    """`chemie_9b_2026_27` — the scheme the seeded class already uses."""
    section = spec.section.strip().lower()
    year = spec.school_year.strip()
    parts = [spec.subject.strip().lower(), f"{spec.grade}{section}"]
    if year:
        parts.append(year.replace("/", "_").replace("-", "_"))
    return "_".join(parts)


def validate(store, spec: ClassSpec) -> str:
    """Return the class id, or raise `ClassProvisioningError`."""
    subject = spec.subject.strip().lower()
    if subject not in SUPPORTED_SUBJECTS:
        raise ClassProvisioningError(
            f"Subject '{spec.subject}' is not supported yet. "
            f"Supported: {', '.join(SUPPORTED_SUBJECTS)}."
        )
    branch = spec.branch.strip().upper()
    if branch != SUPPORTED_BRANCH:
        raise ClassProvisioningError(f"Only the {SUPPORTED_BRANCH} branch is supported.")
    if spec.school_type.strip() != SUPPORTED_SCHOOL_TYPE:
        raise ClassProvisioningError(f"Only {SUPPORTED_SCHOOL_TYPE} is supported.")
    if not spec.label.strip():
        raise ClassProvisioningError("A class label is required.")
    if spec.section and not _SECTION_RE.match(spec.section.strip().lower()):
        raise ClassProvisioningError("Section must be a single letter, such as 'a'.")

    route = CurriculumRoute(subject=subject, grade=spec.grade, branch=branch)
    if route not in available_routes(store):
        raise ClassProvisioningError(
            f"No reviewed teaching framework covers {subject} grade {spec.grade} "
            f"{branch}. Add the shared framework before creating classes on this route."
        )

    class_id = class_id_for(spec)
    if not _SLUG_RE.match(class_id):
        raise ClassProvisioningError(f"Derived class id '{class_id}' is not a valid slug.")
    if store.class_dir(class_id).exists():
        raise ClassProvisioningError(f"Class '{class_id}' already exists.")
    return class_id


def create_class(store, spec: ClassSpec) -> ClassSummary:
    """Write the class skeleton and refresh the wiki index."""
    class_id = validate(store, spec)
    subject = spec.subject.strip().lower()
    label = spec.label.strip()

    for name, body in _skeleton(store, class_id, spec, subject, label).items():
        store.write_text(store.class_dir(class_id) / name, body)

    for index, student in enumerate(_clean_names(spec.student_names), start=1):
        student_id = f"S-{index:03d}"
        store.write_text(
            store.student_path(class_id, student_id),
            f"# {student_id}\n\n## Student Summary\n\n_No observations recorded yet._\n",
        )

    store.rebuild_index()
    return ClassSummary(id=class_id, label=label, subject=subject)


def _clean_names(names) -> list[str]:
    return [name.strip() for name in names if name and name.strip()]


def _skeleton(store, class_id: str, spec: ClassSpec, subject: str, label: str) -> dict:
    """Every file a class needs before any workflow touches it.

    The rollups and compact memory pages are seeded empty rather than omitted:
    `rebuild_index` links them unconditionally, so a missing file is a dead link
    in the teacher-visible index.
    """
    results_sections = "\n".join(f"- {title}" for _, title, _ in LESSON_RESULTS_SECTIONS)
    prior = spec.prior_learning.strip()

    return {
        "class_config.md": (
            f"# {label}\n\n"
            f"subject: {subject}\n\n"
            "## Lesson results sections (fixed v1)\n"
            f"{results_sections}\n\n"
            "## Lesson plan sections\n"
            "- Learning goals\n- Lesson flow\n- Warmup\n- Practice\n- Homework\n"
            "- Teacher notes\n"
        ),
        "curriculum_profile.md": (
            "---\n"
            f"state: {spec.state}\n"
            f"school_type: {spec.school_type}\n"
            f"branch: {spec.branch.upper()}\n"
            f"grade: {spec.grade}\n"
            f"subject: {subject}\n"
            "---\n"
            f"# Curriculum Profile — {label}\n\n"
            "## Interpretation\n"
            f"{spec.school_type} {spec.branch.upper()}, grade {spec.grade}, "
            f"{spec.state}. Set at class creation; correct it here if the route "
            "is wrong.\n"
        ),
        "trusted_sources.md": _trusted_sources_page(store, spec, subject, label),
        "course_state.md": (
            "# Course State\n\n"
            "> Canonical current class state derived from approved lessons: current "
            "unit, last lesson, next planned focus, and overall status.\n\n"
            "## Current unit\n\n"
            "## Last lesson\n\n"
            "## Next planned focus\n\n"
            "## Prior learning (teacher-declared)\n"
            + (f"- {prior}\n" if prior else "_Not recorded._\n")
            + "\n## Overall status\n- Created; no lessons logged yet.\n"
        ),
        "timeline.md": (
            "# Lesson Timeline\n\n"
            "> Chronological lesson sequence. Entries appear after an approved "
            "memory update.\n"
        ),
        "open_loops.md": "# Open Loops\n\n_No open loops yet._\n",
        "misconceptions.md": "# Misconceptions\n\n_No misconceptions recorded yet._\n",
        "students.md": _students_page(spec, label),
        "memory/planning_brief.md": _memory_page(
            "Planning Brief",
            class_id,
            "Compact near-term planning brief: current priorities, open loops, "
            "misconception focus, assessment readiness, and immediate next-step "
            "pressure.",
        ),
        "memory/teaching_patterns.md": _memory_page(
            "Teaching Patterns",
            class_id,
            "Durable class learning profile: how THIS class learns, what "
            "scaffolds/materials/pacing/activity formats work or fail.",
        ),
        "memory/copilot_profile.md": _memory_page(
            "Class Copilot Profile",
            class_id,
            "Copilot working agreement for this class: planning patterns to apply, "
            "avoid-rules, repeated corrections.",
        ),
        "memory/session_summaries.md": _memory_page(
            "Session Summaries",
            class_id,
            "Sparse compact summaries of prior workflow sessions; not a transcript "
            "store.",
        ),
        "memory/teaching_framework_adjustments.md": (
            f"# Teaching Framework Adjustments\n\n"
            f"> Class: {class_id}\n"
            f"> Teacher-approved refinements to the shared {subject} grade "
            f"{spec.grade} {spec.branch.upper()} framework. This page never "
            "replaces or copies the shared framework.\n\n"
            "## Replace or refine\n\n_No approved adjustments yet._\n\n"
            "## Prefer\n\n_No approved preferences yet._\n\n"
            "## Avoid\n\n_No approved cautions yet._\n"
        ),
    }


def _memory_page(title: str, class_id: str, purpose: str) -> str:
    return f"# {title}\n\n> Class: {class_id}\n> {purpose}\n\n_Nothing recorded yet._\n"


def _students_page(spec: ClassSpec, label: str) -> str:
    lines = [
        "# Students",
        "",
        "> Class roster and student index. Details live in `students/S-###.md`.",
        "",
        "| ID | Name | Note | Page |",
        "|---|---|---|---|",
    ]
    for index, name in enumerate(_clean_names(spec.student_names), start=1):
        student_id = f"S-{index:03d}"
        lines.append(
            f"| {student_id} | {name} | No observations yet. "
            f"| [students/{student_id}.md](students/{student_id}.md) |"
        )
    return "\n".join(lines) + "\n"


def _trusted_sources_page(store, spec: ClassSpec, subject: str, label: str) -> str:
    """Link the class to the library sources that cover its route."""
    active: list[str] = []
    prior: list[str] = []
    reference: list[str] = []
    for source in sorted(load_trusted_sources(store.root).values(), key=lambda s: s.source_id):
        if source.subject.strip().lower() not in {subject, ""}:
            continue
        grade = re.search(r"\d+", source.grade or "")
        if not grade:
            reference.append(f"- `{source.source_id}` — {source.title}")
        elif int(grade.group(0)) == spec.grade:
            active.append(f"- `{source.source_id}` — {source.title}")
        elif int(grade.group(0)) < spec.grade:
            prior.append(f"- `{source.source_id}` — {source.title}")

    source_ids = [
        line.split("`")[1] for line in (*active, *prior, *reference)
    ]
    lines = ["---", f"source_ids: {','.join(source_ids)}", "---", f"# Trusted Sources — {label}", ""]
    for heading, entries in (
        ("Active", active),
        ("Prior learning", prior),
        ("Broader reference", reference),
    ):
        lines.append(f"## {heading}")
        lines.extend(entries or ["_None linked._"])
        lines.append("")
    return "\n".join(lines)
