"""Load reviewable, backend-owned lesson-production skill Markdown."""

from __future__ import annotations

from pathlib import Path


_SKILL_DIR = Path(__file__).parent
_SKILL_FILES = {
    "course_network": "course_network_procedure.md",
    "lesson_planning": "lesson_planning_procedure.md",
    "differentiation": "lesson_differentiation_procedure.md",
    "materials_use": "materials_use_procedure.md",
}


def _read_markdown(filename: str) -> str:
    return (_SKILL_DIR / filename).read_text(encoding="utf-8").strip()


def load_skill(name: str) -> str:
    """Return a named backend-owned production skill, or an empty string."""
    filename = _SKILL_FILES.get(name.strip().lower())
    return _read_markdown(filename) if filename else ""


def load_subject_reference(subject: str, grade: int, branch: str | None) -> str:
    """Return mandatory subject/grade guidance for the supported initial scope."""
    if (
        subject.strip().lower() not in {"chemie", "chemistry"}
        or grade != 9
        or (branch or "").strip().upper() != "NTG"
    ):
        return ""
    return _read_markdown("chemie_bayern_reference.md")


def compose_active_skill(
    subject: str,
    grade: int,
    branch: str | None,
    task: str,
    *,
    include_materials_use: bool = False,
) -> str:
    """Compose the mandatory procedure and scoped subject reference for a task."""
    normalized_task = task.strip().lower()
    reference = load_subject_reference(subject, grade, branch)
    materials = load_skill("materials_use") if include_materials_use else ""
    if normalized_task == "differentiation":
        parts = (load_skill("differentiation"), reference, materials)
    else:
        parts = (
            load_skill("lesson_planning"),
            reference,
            load_skill("differentiation"),
            materials,
        )
    return "\n\n".join(part for part in parts if part)
