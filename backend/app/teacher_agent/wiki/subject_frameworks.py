"""Shared subject-framework selection and class-profile compilation."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class FrameworkSummary:
    subject: str
    grade: int
    branch: str
    path: str
    text: str
    source_refs: tuple[str, ...]
    version: str


@dataclass(frozen=True)
class FrameworkIndex:
    subject: str
    path: str
    entries: tuple[FrameworkSummary, ...]


def _frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    try:
        frontmatter, body = text[4:].split("\n---\n", 1)
    except ValueError:
        return {}, text
    values: dict[str, str] = {}
    for line in frontmatter.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"\'')
    return values, body


def _source_refs(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _framework_root(store, subject: str) -> Path:
    return store.root / "wiki" / "subjects" / subject / "teaching_frameworks"


def load_framework_index(store, subject: str) -> FrameworkIndex:
    """Read the shared, immutable framework summaries for one subject."""
    normalized = subject.strip().lower()
    root = _framework_root(store, normalized)
    entries: list[FrameworkSummary] = []
    for path in sorted(root.glob("*/key_summary.md")):
        metadata, body = _frontmatter(path.read_text(encoding="utf-8"))
        try:
            grade = int(metadata.get("grade", ""))
        except ValueError:
            continue
        branch = metadata.get("branch", "").upper()
        if not branch:
            continue
        entries.append(
            FrameworkSummary(
                subject=metadata.get("subject", normalized),
                grade=grade,
                branch=branch,
                path=store.rel_wiki(path),
                text=body.strip(),
                source_refs=_source_refs(metadata.get("source_refs", "")),
                version=metadata.get("version", ""),
            )
        )
    index_path = root / "index.md"
    return FrameworkIndex(
        subject=normalized,
        path=store.rel_wiki(index_path),
        entries=tuple(entries),
    )


def select_framework(store, subject: str, grade: int, branch: str | None) -> FrameworkSummary:
    """Return the exact shared framework for an active class route."""
    normalized_branch = (branch or "").strip().upper()
    for entry in load_framework_index(store, subject).entries:
        if entry.grade == grade and entry.branch == normalized_branch:
            return entry
    raise ValueError(
        f"No {subject} teaching framework for grade {grade} branch {normalized_branch or '<none>'}."
    )


def _effective_principles(text: str) -> str:
    marker = "## Effective principles"
    if marker not in text:
        return text.strip()
    after = text.split(marker, 1)[1].lstrip("\n")
    next_heading = after.find("\n## ")
    return (after if next_heading < 0 else after[:next_heading]).strip()


def compose_class_framework_profile(
    store,
    *,
    class_id: str,
    framework: FrameworkSummary,
    teacher_adjustments: list[str],
    class_cautions: list[str],
) -> str:
    """Compile inherited shared guidance and approved class adjustments."""
    base_revision = hashlib.sha256(framework.text.encode("utf-8")).hexdigest()[:16]
    generated_at = datetime.now(timezone.utc).isoformat()
    adjustments = teacher_adjustments or ["- None approved yet."]
    cautions = class_cautions or ["- None recorded yet."]

    def render_list(values: list[str]) -> str:
        return "\n".join(
            item if item.startswith("-") else f"- {item}" for item in values
        )

    return "\n".join(
        [
            "---",
            f"class_id: {class_id}",
            "inherits:",
            f"  - wiki/subjects/{framework.subject}.md",
            f"  - {framework.path}",
            f"source_index: wiki/subjects/{framework.subject}/teaching_frameworks/index.md",
            f"base_revision: {base_revision}",
            "authority: teacher_adjusted_class_profile",
            f"generated_at: {generated_at}",
            "---",
            "",
            f"# Teaching Framework Profile - {class_id}",
            "",
            "## Effective principles",
            _effective_principles(framework.text),
            "",
            "## Teacher-approved adjustments",
            render_list(adjustments),
            "",
            "## Class-specific cautions",
            render_list(cautions),
            "",
        ]
    )


def framework_profile_path(store, class_id: str) -> Path:
    """Return the class-scoped derived profile path (never a shared page)."""
    return store.memory_dir(class_id) / "teaching_framework_profile.md"


def _section_bullets(text: str, heading: str) -> list[str]:
    pattern = rf"^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s+|\Z)"
    match = re.search(pattern, text or "", flags=re.MULTILINE | re.DOTALL)
    if not match:
        return []
    return [
        line[2:].strip()
        for line in match.group(1).splitlines()
        if line.startswith("- ") and line[2:].strip()
    ]


def framework_for_class(store, class_id: str) -> FrameworkSummary:
    """Select one shared framework from the class's declared curriculum route."""
    class_config = store.get_class(class_id)
    curriculum = store.get_curriculum_profile(class_id)
    configured_subject = (class_config.subject or "").strip().lower()
    curriculum_subject = (curriculum.subject or configured_subject).strip().lower()
    if curriculum_subject != configured_subject:
        raise ValueError(
            "Curriculum profile subject does not match the class subject: "
            f"{curriculum_subject or '<none>'} != {configured_subject or '<none>'}."
        )
    try:
        grade = int(curriculum.grade)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Class {class_id} has no usable curriculum grade.") from exc
    return select_framework(store, configured_subject, grade, curriculum.branch)


def regenerate_class_framework_profile(store, class_id: str) -> str:
    """Recompile shared guidance while retaining only the approved local blocks.

    This is a class-setup / approved-apply operation. Planning itself remains
    read-only and must only consume the already materialized profile.
    """
    path = framework_profile_path(store, class_id)
    existing = store.read_text(path)
    rendered = compose_class_framework_profile(
        store,
        class_id=class_id,
        framework=framework_for_class(store, class_id),
        teacher_adjustments=_section_bullets(existing, "Teacher-approved adjustments"),
        class_cautions=_section_bullets(existing, "Class-specific cautions"),
    )
    store.write_text(path, rendered)
    return rendered
