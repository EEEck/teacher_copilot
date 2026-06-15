"""Shared prompt render helpers for workflow runtime state."""

from __future__ import annotations

from typing import Iterable, Protocol

from app.context_limits import get_context_limits


class EvidenceBriefLike(Protocol):
    type: str
    purpose: str
    brief: list[str]
    source_refs: list[str]
    raw_ref: str
    confidence: str


def clean_inline(value: object) -> str:
    return " ".join(str(value or "").split())


def render_bullets(
    items: Iterable[object],
    *,
    limit: int | None = None,
    max_chars: int | None = None,
) -> list[str]:
    lim = get_context_limits()
    limit = lim.state_list_limit if limit is None else limit
    max_chars = lim.state_bullet_max_chars if max_chars is None else max_chars
    out = []
    for item in list(items)[:limit]:
        text = clean_inline(item)
        if text:
            out.append(f"- {text[:max_chars]}")
    return out


def render_scalar(label: str, value: object, *, max_chars: int = 200) -> str:
    text = clean_inline(value)
    return f"- {label}: {text[:max_chars]}" if text else ""


def append_bullet_section(parts: list[str], title: str, items: list[str]) -> None:
    bullets = render_bullets(items)
    if bullets:
        parts.append(f"### {title}")
        parts.extend(bullets)


def render_evidence_briefs(
    briefs: list[EvidenceBriefLike],
    *,
    title: str = "## Evidence briefs (compact; request raw via get_raw_evidence)",
    empty: str = "## Evidence briefs\n- None yet.",
    impact_field: str = "",
    max_briefs: int | None = None,
) -> str:
    lim = get_context_limits()
    max_briefs = lim.briefs_inject_limit if max_briefs is None else max_briefs
    if not briefs:
        return empty
    parts = [title]
    for brief in briefs[-max_briefs:]:
        head = (
            f"- [{brief.raw_ref or 'no-ref'}] "
            f"{brief.type}: {clean_inline(brief.purpose)[:160]}"
        ).rstrip()
        parts.append(head)
        for line in brief.brief[: lim.brief_lines_per_item]:
            parts.append(f"  - {clean_inline(line)[:200]}")
        impact = clean_inline(getattr(brief, impact_field, "")) if impact_field else ""
        if impact:
            parts.append(f"  - impact: {impact[:200]}")
    return "\n".join(parts)
