"""Deterministic creation of a new class wiki."""

from __future__ import annotations

import errno
import os
import re
import shutil
import tempfile
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from app.schemas.api import (
    CLASS_BRANCH_MAX_LENGTH,
    CLASS_LABEL_MAX_LENGTH,
    CLASS_PRIOR_LEARNING_MAX_LENGTH,
    CLASS_ROSTER_MAX_SIZE,
    CLASS_SCHOOL_TYPE_MAX_LENGTH,
    CLASS_SCHOOL_YEAR_MAX_LENGTH,
    CLASS_STATE_MAX_LENGTH,
    CLASS_STUDENT_NAME_MAX_LENGTH,
    CLASS_SUBJECT_MAX_LENGTH,
    ClassSummary,
)
from app.teacher_agent.wiki.constants import LESSON_RESULTS_SECTIONS
from app.teacher_agent.wiki.subject_frameworks import load_framework_index
from app.teacher_agent.wiki.trusted_sources import load_trusted_sources

SUPPORTED_SUBJECTS = ("chemie",)
SUPPORTED_BRANCH = "NTG"
SUPPORTED_SCHOOL_TYPE = "Gymnasium"
SUPPORTED_STATE = "BY"

_SECTION_RE = re.compile(r"^[a-z]$")
_SLUG_RE = re.compile(r"^[a-z0-9_]+$")
_PROCESS_LOCKS_GUARD = threading.Lock()
_PROCESS_LOCKS: dict[str, threading.Lock] = {}


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
    """Return the reviewed Chemie routes that can be provisioned."""
    routes = [
        CurriculumRoute(subject="chemie", grade=entry.grade, branch=entry.branch)
        for entry in load_framework_index(store, "chemie").entries
        if entry.grade in {8, 9} and entry.branch == SUPPORTED_BRANCH
    ]
    return sorted(routes, key=lambda route: (route.subject, route.grade, route.branch))


def class_id_for(spec: ClassSpec) -> str:
    """`chemie_9b_2026_27` — the scheme the seeded class already uses."""
    section = spec.section.strip().lower()
    year = spec.school_year.strip()
    parts = [spec.subject.strip().lower(), f"{spec.grade}{section}"]
    if year:
        parts.append(year.replace("/", "_").replace("-", "_"))
    return "_".join(parts)


def validate(store, spec: ClassSpec) -> str:
    """Return the class id, or raise ``ClassProvisioningError``."""
    _validate_bounded_text("Class label", spec.label, CLASS_LABEL_MAX_LENGTH)
    _validate_bounded_text("Subject", spec.subject, CLASS_SUBJECT_MAX_LENGTH)
    _validate_bounded_text(
        "School year", spec.school_year, CLASS_SCHOOL_YEAR_MAX_LENGTH
    )
    _validate_bounded_text("Branch", spec.branch, CLASS_BRANCH_MAX_LENGTH)
    _validate_bounded_text(
        "School type", spec.school_type, CLASS_SCHOOL_TYPE_MAX_LENGTH
    )
    _validate_bounded_text("State", spec.state, CLASS_STATE_MAX_LENGTH)
    _validate_bounded_text(
        "Prior learning",
        spec.prior_learning,
        CLASS_PRIOR_LEARNING_MAX_LENGTH,
        allow_newlines=True,
    )
    _validate_student_names(spec.student_names)
    subject = spec.subject.strip().lower()
    if subject not in SUPPORTED_SUBJECTS:
        raise ClassProvisioningError(
            f"Subject '{spec.subject}' is not supported yet. "
            f"Supported: {', '.join(SUPPORTED_SUBJECTS)}."
        )
    branch = spec.branch.strip().upper()
    if branch != SUPPORTED_BRANCH:
        raise ClassProvisioningError(
            f"Only the {SUPPORTED_BRANCH} branch is supported."
        )
    if spec.school_type.strip() != SUPPORTED_SCHOOL_TYPE:
        raise ClassProvisioningError(f"Only {SUPPORTED_SCHOOL_TYPE} is supported.")
    if spec.state.strip() != SUPPORTED_STATE:
        raise ClassProvisioningError(f"Only {SUPPORTED_STATE} is supported.")
    if not spec.label.strip():
        raise ClassProvisioningError("A class label is required.")
    if spec.section and not _SECTION_RE.match(spec.section.strip().lower()):
        raise ClassProvisioningError("Section must be a single letter, such as 'a'.")

    route = CurriculumRoute(subject=subject, grade=spec.grade, branch=branch)
    if route not in available_routes(store):
        raise ClassProvisioningError(
            f"No shared teaching framework covers {subject} grade {spec.grade} "
            f"{branch}. Add the shared framework before creating classes on this route."
        )

    class_id = class_id_for(spec)
    if not _SLUG_RE.match(class_id):
        raise ClassProvisioningError(
            f"Derived class id '{class_id}' is not a valid slug."
        )
    if store.class_dir(class_id).exists():
        raise ClassProvisioningError(f"Class '{class_id}' already exists.")
    return class_id


def create_class(store, spec: ClassSpec) -> ClassSummary:
    """Stage, atomically publish, and index one deterministic class skeleton."""
    class_id = validate(store, spec)
    subject = spec.subject.strip().lower()
    label = spec.label.strip()
    store.root.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(
        tempfile.mkdtemp(prefix=f".class-provisioning-{class_id}-", dir=store.root)
    )
    try:
        _write_staged_class(store, staging_dir, class_id, spec, subject, label)
        with _wiki_creation_lock(store.root):
            final_dir = store.class_dir(class_id)
            if final_dir.exists():
                raise ClassProvisioningError(f"Class '{class_id}' already exists.")

            previous_index = (
                store.index_path.read_bytes() if store.index_path.exists() else None
            )
            try:
                staging_dir.rename(final_dir)
            except OSError as exc:
                if exc.errno in {errno.EEXIST, errno.ENOTEMPTY} or final_dir.exists():
                    raise ClassProvisioningError(
                        f"Class '{class_id}' already exists."
                    ) from exc
                raise

            try:
                store.rebuild_index()
            except BaseException:
                try:
                    shutil.rmtree(final_dir)
                    _restore_index(store.index_path, previous_index)
                except Exception as rollback_exc:
                    raise RuntimeError(
                        f"Failed to roll back class '{class_id}' after index failure."
                    ) from rollback_exc
                raise
        return ClassSummary(id=class_id, label=label, subject=subject)
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)


def _write_staged_class(
    store,
    staging_dir: Path,
    class_id: str,
    spec: ClassSpec,
    subject: str,
    label: str,
) -> None:
    for name, body in _skeleton(store, class_id, spec, subject, label).items():
        store.write_text(staging_dir / name, body)

    for index, _student in enumerate(_clean_names(spec.student_names), start=1):
        student_id = f"S-{index:03d}"
        store.write_text(
            staging_dir / "students" / f"{student_id}.md",
            f"# {student_id}\n\n## Student Summary\n\n_No observations recorded yet._\n",
        )


def _validate_bounded_text(
    label: str, value: str, max_length: int, *, allow_newlines: bool = False
) -> None:
    if len(value) > max_length:
        raise ClassProvisioningError(
            f"{label} must be at most {max_length} characters."
        )
    if not allow_newlines and ("\n" in value or "\r" in value):
        raise ClassProvisioningError(f"{label} must stay on one line.")


def _validate_student_names(names) -> None:
    if len(names) > CLASS_ROSTER_MAX_SIZE:
        raise ClassProvisioningError(
            f"A roster may contain at most {CLASS_ROSTER_MAX_SIZE} students."
        )
    for name in _clean_names(names):
        if len(name) > CLASS_STUDENT_NAME_MAX_LENGTH:
            raise ClassProvisioningError(
                "Each student name must be at most "
                f"{CLASS_STUDENT_NAME_MAX_LENGTH} characters."
            )
        if "|" in name or "\n" in name or "\r" in name:
            raise ClassProvisioningError(
                "Each student name must not contain Markdown pipes or newlines."
            )


def _process_lock_for(root: Path) -> threading.Lock:
    key = os.path.normcase(str(root.resolve()))
    with _PROCESS_LOCKS_GUARD:
        return _PROCESS_LOCKS.setdefault(key, threading.Lock())


@contextmanager
def _wiki_creation_lock(root: Path):
    """Serialize class publication across threads and OS processes for one wiki."""
    process_lock = _process_lock_for(root)
    lock_path = root / ".class-provisioning.lock"
    with process_lock, lock_path.open("a+b") as lock_file:
        lock_file.seek(0, os.SEEK_END)
        if lock_file.tell() == 0:
            lock_file.write(b"\0")
            lock_file.flush()
        lock_file.seek(0)
        _lock_file(lock_file)
        try:
            yield
        finally:
            _unlock_file(lock_file)


def _lock_file(lock_file) -> None:
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        return

    import fcntl

    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)


def _unlock_file(lock_file) -> None:
    lock_file.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _restore_index(index_path: Path, previous: bytes | None) -> None:
    if previous is None:
        index_path.unlink(missing_ok=True)
        return
    temporary = index_path.with_name(f".{index_path.name}.{uuid.uuid4().hex}.rollback")
    try:
        temporary.write_bytes(previous)
        os.replace(temporary, index_path)
    finally:
        temporary.unlink(missing_ok=True)


def _clean_names(names) -> list[str]:
    return [name.strip() for name in names if name and name.strip()]


def _skeleton(
    store, class_id: str, spec: ClassSpec, subject: str, label: str
) -> dict[str, str]:
    results_sections = "\n".join(
        f"- {title}" for _, title, _ in LESSON_RESULTS_SECTIONS
    )
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
            f"{spec.school_type} {spec.branch.upper()}, grade {spec.grade}, {spec.state}. "
            "Set at class creation; correct it here if the route is wrong.\n"
        ),
        "trusted_sources.md": _trusted_sources_page(store, spec, subject, label),
        "course_state.md": (
            "# Course State\n\n"
            "> Canonical current class state derived from approved lessons: current "
            "unit, last lesson, next planned focus, and overall status.\n\n"
            "## Current unit\nNot set\n\n"
            "## Last lesson\n\n"
            "## Next planned focus\n\n"
            "## Prior learning (teacher-declared)\n"
            + (f"- {prior}\n" if prior else "_Not recorded._\n")
            + "\n## Overall status\n- Created; no lessons logged yet.\n"
        ),
        "timeline.md": (
            "# Lesson Timeline\n\n"
            "> Chronological lesson sequence. Entries appear after an approved memory update.\n"
        ),
        "open_loops.md": "# Open Loops\n\n_No open loops yet._\n",
        "misconceptions.md": "# Misconceptions\n\n_No misconceptions recorded yet._\n",
        "students.md": _students_page(spec),
        "memory/planning_brief.md": _memory_page(
            "Planning Brief",
            class_id,
            "Compact near-term planning brief: current priorities, open loops, misconception focus, assessment readiness, and immediate next-step pressure.",
        ),
        "memory/teaching_patterns.md": _memory_page(
            "Teaching Patterns",
            class_id,
            "Durable class learning profile: how this class learns and what scaffolds, materials, pacing, and activity formats work or fail.",
        ),
        "memory/copilot_profile.md": _memory_page(
            "Class Copilot Profile",
            class_id,
            "Copilot working agreement for this class: planning patterns to apply, avoid-rules, and repeated corrections.",
        ),
        "memory/session_summaries.md": _memory_page(
            "Session Summaries",
            class_id,
            "Sparse compact summaries of prior workflow sessions; not a transcript store.",
        ),
        "memory/teaching_framework_adjustments.md": (
            "# Teaching Framework Adjustments\n\n"
            f"> Class: {class_id}\n"
            f"> Teacher-approved refinements to the shared {subject} grade {spec.grade} {spec.branch.upper()} framework. This page never replaces or copies the shared framework.\n\n"
            "## Replace or refine\n\n_No approved adjustments yet._\n\n"
            "## Prefer\n\n_No approved preferences yet._\n\n"
            "## Avoid\n\n_No approved cautions yet._\n"
        ),
    }


def _memory_page(title: str, class_id: str, purpose: str) -> str:
    return f"# {title}\n\n> Class: {class_id}\n> {purpose}\n\n_Nothing recorded yet._\n"


def _students_page(spec: ClassSpec) -> str:
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
            f"| {student_id} | {name} | No observations yet. | [students/{student_id}.md](students/{student_id}.md) |"
        )
    return "\n".join(lines) + "\n"


def _trusted_sources_page(store, spec: ClassSpec, subject: str, label: str) -> str:
    active: list[str] = []
    prior: list[str] = []
    reference: list[str] = []
    for source in sorted(
        load_trusted_sources(store.root).values(), key=lambda item: item.source_id
    ):
        if source.subject.strip().lower() not in {subject, ""}:
            continue
        grade = re.search(r"\d+", source.grade or "")
        if not grade:
            reference.append(f"- `{source.source_id}` — {source.title}")
        elif int(grade.group(0)) == spec.grade:
            active.append(f"- `{source.source_id}` — {source.title}")
        elif int(grade.group(0)) < spec.grade:
            prior.append(f"- `{source.source_id}` — {source.title}")

    source_ids = [line.split("`")[1] for line in (*active, *prior, *reference)]
    lines = [
        "---",
        f"source_ids: {','.join(source_ids)}",
        "---",
        f"# Trusted Sources — {label}",
        "",
    ]
    for heading, entries in (
        ("Active", active),
        ("Prior learning", prior),
        ("Broader reference", reference),
    ):
        lines.append(f"## {heading}")
        lines.extend(entries or ["_None linked._"])
        lines.append("")
    return "\n".join(lines)
