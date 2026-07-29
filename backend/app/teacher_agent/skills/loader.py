"""Load reviewable, backend-owned lesson-production skill Markdown."""

from __future__ import annotations

from pathlib import Path


_SKILL_DIR = Path(__file__).parent
_SKILL_FILES = {
    "lesson_planning": "lesson_planning_procedure.md",
    "differentiation": "lesson_differentiation_procedure.md",
}


def _read_markdown(filename: str) -> str:
    return (_SKILL_DIR / filename).read_text(encoding="utf-8").strip()


def load_skill(name: str) -> str:
    """Return a named backend-owned production skill, or an empty string."""
    filename = _SKILL_FILES.get(name.strip().lower())
    return _read_markdown(filename) if filename else ""


# Backend-owned subject references, keyed by the exact route each one covers.
# A reference is written for one subject/grade/branch and does not generalise to
# another, so routes without an entry correctly get nothing rather than
# borrowing guidance written for a different course.
_SUBJECT_REFERENCES: dict[tuple[str, int, str], str] = {
    ("chemie", 9, "NTG"): "chemie_bayern_reference.md",
}

_SUBJECT_ALIASES = {"chemistry": "chemie", "physics": "physik"}


def load_subject_reference(subject: str, grade: int, branch: str | None) -> str:
    """Return mandatory subject/grade guidance when a reference covers the route."""
    normalized = subject.strip().lower()
    normalized = _SUBJECT_ALIASES.get(normalized, normalized)
    key = (normalized, grade, (branch or "").strip().upper())
    filename = _SUBJECT_REFERENCES.get(key)
    return _read_markdown(filename) if filename else ""


def compose_active_skill(subject: str, grade: int, branch: str | None, task: str) -> str:
    """Compose the mandatory procedure and scoped subject reference for a task."""
    normalized_task = task.strip().lower()
    reference = load_subject_reference(subject, grade, branch)
    if normalized_task == "differentiation":
        parts = (load_skill("differentiation"), reference)
    else:
        parts = (load_skill("lesson_planning"), reference, load_skill("differentiation"))
    return "\n\n".join(part for part in parts if part)
