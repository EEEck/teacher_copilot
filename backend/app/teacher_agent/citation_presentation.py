"""Deterministic presentation and validation for reviewed trusted-source summaries."""

from __future__ import annotations

import re
from typing import Any

from app.teacher_agent.quality import validate_source_citations


_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_SOURCE_LINE_RE = re.compile(r"(?im)^\s*(?:source|quelle)\s*:")


def validate_discussion_source_presentation(
    reply: str, consulted_sources: list[dict[str, str]]
) -> list[str]:
    """Reject model-owned citations; the backend renders trusted source links."""
    errors = validate_source_citations(reply, consulted_sources)
    if _SOURCE_LINE_RE.search(reply or ""):
        errors.append(
            "Model replies must not contain source citation lines; the backend renders source provenance."
        )
    if _URL_RE.search(reply or ""):
        errors.append(
            "Model replies must not contain source URLs; the backend renders trusted-source links."
        )
    return errors


def strip_model_source_presentation(reply: str) -> str:
    """Remove source-line/URL presentation after the single retry is exhausted."""
    kept: list[str] = []
    for line in (reply or "").splitlines():
        if _SOURCE_LINE_RE.search(line) or _URL_RE.search(line):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def render_reviewed_source_footer(
    wiki: Any, class_id: str, consulted_sources: list[dict[str, str]]
) -> str:
    """Render source provenance from the trusted registry, never model text."""
    linked = {
        source.source_id: source
        for source in wiki.list_trusted_sources(class_id, scope="all")
    }
    lines: list[str] = []
    seen: set[tuple[str, str]] = set()
    for item in consulted_sources:
        source_id = str(item.get("source_id", "")).strip()
        section_id = str(item.get("section_id", "summary")).strip() or "summary"
        key = (source_id, section_id)
        if not source_id or key in seen:
            continue
        seen.add(key)
        source = linked.get(source_id)
        if source is None:
            continue
        payload = wiki.read_trusted_source(class_id, source_id, section_id)
        section_title = str(payload.get("section_title", "Summary"))
        lines.append(
            "- KlassenPilot reviewed English summary: "
            f"**{source.title} — {section_title}**  \n"
            f"  Official German source: [{source.title}]({source.canonical_url})"
        )
    if not lines:
        return ""
    return "\n\n## Sources consulted\n" + "\n".join(lines)
