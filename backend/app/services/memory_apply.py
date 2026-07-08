"""Apply teacher-approved memory items via the bounded wiki helpers.

Pure dispatch over the `WikiStore` facade so the HITL apply flow is unit-testable
without going through HTTP. Only approved, supported targets are written; durable
writes stay bounded by the same helpers used elsewhere.
"""

from __future__ import annotations

import re
from typing import Protocol

from app.teacher_agent.memory_targets import (
    canonical_memory_target,
    compact_key_for_target,
    is_student_page_target,
    student_id_from_target,
)
from app.teacher_agent.wiki.memory import (
    PROFILE_ENTRY_LIMIT,
    USER_PROFILE_ENTRY_LIMIT,
    clamp_memory_page,
)


class _ApplyItem(Protocol):
    target: str
    section: str
    content: str


class _SweepDecision(Protocol):
    action: str
    target: str
    section: str
    content: str
    operation: str
    replaces_content: str


def apply_memory_items(
    wiki, class_id: str, items
) -> tuple[list[str], list[str], list[str], list[int]]:
    """Write supported items; return (applied_paths, skipped, warnings, indexes).

    ``indexes`` are the item positions whose write actually landed — the caller
    closes those items' ledger rows to ``applied`` and leaves skipped/failed
    items reviewable (mirrors ``apply_memory_sweep_decisions``).

    Supported targets:
    - ``teacher_profile.md`` -> global teacher profile (bounded)
    - ``copilot_profile.md`` -> class copilot working agreement (bounded)
    - ``planning_brief.md`` / ``teaching_patterns.md``
      -> bounded compact class memory bullets
    - ``wiki/subjects/{active_subject}.md`` -> bounded subject-guide bullet

    Unsupported targets (e.g. ``canonical_wiki``) are skipped, never written.
    """
    applied: list[str] = []
    skipped: list[str] = []
    warnings: list[str] = []
    successful_indexes: list[int] = []
    subject_target = f"wiki/subjects/{wiki.get_class(class_id).subject}.md"
    for index, item in enumerate(items):
        path, skip, warning = _apply_add_item(wiki, class_id, item, subject_target)
        if path:
            applied.append(path)
            successful_indexes.append(index)
        if skip:
            skipped.append(skip)
        if warning:
            warnings.append(warning)
    return applied, skipped, warnings, successful_indexes


def apply_memory_sweep_decisions(
    wiki, class_id: str, decisions: list[_SweepDecision]
) -> tuple[list[str], list[str], list[str], list[int]]:
    """Apply writing sweep decisions and return successful decision indexes.

    The caller updates ledger rows only for these successful indexes. This keeps
    failed exact replacements and unsupported targets reviewable in the ledger.
    """
    applied: list[str] = []
    skipped: list[str] = []
    warnings: list[str] = []
    successful_indexes: list[int] = []
    subject_target = f"wiki/subjects/{wiki.get_class(class_id).subject}.md"

    for index, decision in enumerate(decisions):
        if decision.action != "apply":
            continue
        operation = _normalize_operation(getattr(decision, "operation", "add"))
        if is_student_page_target(decision.target):
            if operation not in {"add", "adjust"}:
                skipped.append(f"non-writing operation for apply: {operation}")
                continue
            try:
                paths = _apply_student_summary_item(
                    wiki, class_id, decision, operation
                )
            except ValueError as exc:
                warnings.append(f"{decision.target}: {exc}")
                continue
            applied.extend(paths)
            successful_indexes.append(index)
            continue
        if operation == "add":
            path, skip, warning = _apply_add_item(
                wiki, class_id, decision, subject_target
            )
            if path:
                applied.append(path)
                successful_indexes.append(index)
            if skip:
                skipped.append(skip)
            if warning:
                warnings.append(warning)
            continue
        if operation == "adjust":
            try:
                path = _apply_adjust_item(wiki, class_id, decision, subject_target)
            except ValueError as exc:
                warnings.append(f"{decision.target}: {exc}")
                continue
            if path:
                applied.append(path)
                successful_indexes.append(index)
            else:
                skipped.append(f"unsupported target: {decision.target}")
            continue
        skipped.append(f"non-writing operation for apply: {operation}")

    return applied, skipped, warnings, successful_indexes


def _apply_student_summary_item(
    wiki, class_id: str, item, operation: str
) -> list[str]:
    student_id = student_id_from_target(item.target)
    if not student_id:
        raise ValueError(f"unsupported target: {item.target}")
    section = getattr(item, "section", "") or "Student Summary"
    if section.strip().lower() != "student summary":
        raise ValueError("student updates may only target Student Summary")
    new_content = _clean_entry(item.content)
    if not new_content:
        raise ValueError("student summary content cannot be empty")

    path = wiki.student_path(class_id, student_id)
    existing = wiki.read_text(path)
    if operation == "adjust":
        old_content = _clean_entry(getattr(item, "replaces_content", ""))
        if not old_content:
            raise ValueError("adjust requires replaces_content")
        current_summary = _clean_entry(wiki._student_summary_note(existing))
        if _bullet_key(current_summary) != _bullet_key(old_content):
            raise ValueError(
                "replaces_content was not found exactly in target section"
            )

    wiki.write_text(path, wiki._set_student_summary(class_id, student_id, new_content))
    students_path = wiki.roll_up_paths(class_id)["students"]
    wiki.write_text(students_path, wiki._rebuild_students_index(class_id, previews={}))
    return [wiki.rel_wiki(path), wiki.rel_wiki(students_path)]


def _apply_add_item(wiki, class_id: str, item, subject_target: str):
    content = (item.content or "").strip()
    section = getattr(item, "section", "") or "General"
    if not content:
        return "", "empty item", ""
    target = canonical_memory_target(item.target)
    compact_key = compact_key_for_target(target)
    try:
        if target == "teacher_profile.md":
            return wiki.add_user_profile_conclusion(section, content), "", ""
        if target == "copilot_profile.md":
            return wiki.add_profile_conclusion(class_id, section, content), "", ""
        if compact_key:
            return (
                wiki.add_compact_memory_conclusion(
                    class_id, compact_key, section, content
                ),
                "",
                "",
            )
        if target == subject_target:
            return wiki.add_subject_guide_conclusion(class_id, section, content), "", ""
        return "", f"unsupported target: {item.target}", ""
    except ValueError as exc:
        return "", "", f"{item.target}: {exc}"


def _apply_adjust_item(wiki, class_id: str, item, subject_target: str) -> str:
    new_content = _clean_entry(item.content)
    old_content = _clean_entry(getattr(item, "replaces_content", ""))
    if not new_content:
        raise ValueError("adjust content cannot be empty")
    if not old_content:
        raise ValueError("adjust requires replaces_content")
    target = canonical_memory_target(item.target)
    compact_key = compact_key_for_target(target)
    section = getattr(item, "section", "") or "General"
    page_key = ""
    path = None
    entry_limit = PROFILE_ENTRY_LIMIT
    if target == "teacher_profile.md":
        path = wiki.root / "wiki" / "teacher_profile.md"
        page_key = "user"
        entry_limit = USER_PROFILE_ENTRY_LIMIT
    elif target == "copilot_profile.md":
        path = wiki.memory_paths(class_id)["copilot_profile"]
        page_key = "copilot_profile"
    elif compact_key:
        path = wiki.memory_paths(class_id)[compact_key]
        page_key = compact_key
    elif target == subject_target:
        path = (
            wiki.root / "wiki" / "subjects" / f"{wiki.get_class(class_id).subject}.md"
        )
        page_key = "subject_guide"
    else:
        return ""
    if len(new_content) > entry_limit:
        raise ValueError(f"adjust content must be <= {entry_limit} chars")

    text = wiki.read_text(path)
    updated = _replace_section_bullet(text, section, old_content, new_content)
    wiki.write_text(path, clamp_memory_page(page_key, updated))
    return wiki.rel_wiki(path)


def _replace_section_bullet(
    text: str,
    section: str,
    old_content: str,
    new_content: str,
) -> str:
    sec = _normalize_section(section)
    heading_pattern = rf"(^##\s+{re.escape(sec)}\s*\n)(.*?)(?=^##\s+|\Z)"
    match = re.search(heading_pattern, text, flags=re.M | re.S)
    if not match:
        raise ValueError(f"section not found for adjust: {sec}")

    body_lines = match.group(2).splitlines()
    new_line = f"- {new_content}"
    old_key = _bullet_key(old_content)
    new_key = _bullet_key(new_content)
    already_has_new = any(
        line.strip().startswith("-") and _bullet_key(line) == new_key
        for line in body_lines
    )
    found = False
    replacement_lines: list[str] = []
    for line in body_lines:
        if line.strip().startswith("-") and _bullet_key(line) == old_key:
            found = True
            if not already_has_new:
                replacement_lines.append(new_line)
            continue
        replacement_lines.append(line)

    if not found:
        raise ValueError("replaces_content was not found exactly in target section")

    replacement = match.group(1) + "\n".join(replacement_lines).rstrip() + "\n\n"
    return text[: match.start()] + replacement + text[match.end() :]


def _normalize_operation(value: str) -> str:
    operation = (value or "add").strip()
    return operation if operation in {"add", "adjust"} else operation


def _normalize_section(section: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9 &/_-]+", "", section or "").strip()
    return cleaned[:80] or "General"


def _clean_entry(content: str) -> str:
    return " ".join((content or "").strip().split())


def _bullet_key(value: str) -> str:
    text = _clean_entry(value)
    if text.startswith("- "):
        text = _clean_entry(text[2:])
    text = re.sub(r"\s+\(source:\s*`[^`]+`\)\s*$", "", text)
    return text
