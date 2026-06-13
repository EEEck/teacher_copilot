"""Apply teacher-approved memory items via the bounded wiki helpers.

Pure dispatch over the `WikiStore` facade so the HITL apply flow is unit-testable
without going through HTTP. Only approved, supported targets are written; durable
writes stay bounded by the same helpers used elsewhere.
"""

from __future__ import annotations

from typing import Protocol


class _ApplyItem(Protocol):
    target: str
    section: str
    content: str


def apply_memory_items(
    wiki, class_id: str, items
) -> tuple[list[str], list[str], list[str]]:
    """Write supported items; return (applied_paths, skipped, warnings).

    Supported targets:
    - ``user.md``       -> global teacher profile (bounded)
    - ``copilot.md``    -> class copilot working agreement (bounded)
    - ``class_state.md``-> class compact state page (clamped)

    Unsupported targets (e.g. ``canonical_wiki``) are skipped, never written.
    """
    applied: list[str] = []
    skipped: list[str] = []
    warnings: list[str] = []
    for item in items:
        content = (item.content or "").strip()
        section = getattr(item, "section", "") or "General"
        if not content:
            skipped.append("empty item")
            continue
        try:
            if item.target == "user.md":
                applied.append(wiki.add_user_profile_conclusion(section, content))
            elif item.target == "copilot.md":
                applied.append(wiki.add_profile_conclusion(class_id, section, content))
            elif item.target == "class_state.md":
                paths, _ = wiki.commit_memory_compaction(
                    class_id, {"class_state": content}
                )
                applied.extend(paths)
            else:
                skipped.append(f"unsupported target: {item.target}")
        except ValueError as exc:
            warnings.append(f"{item.target}: {exc}")
    return applied, skipped, warnings
