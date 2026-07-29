"""Backward-compatible re-exports for the wiki package."""

from app.teacher_agent.wiki.constants import (
    DIARY_SECTION_HEADINGS,
    INDEX_WIKI_PATH_RE,
    LESSON_RESULTS_SECTIONS,
    LOG_HEADER_LEGACY_RE,
    LOG_HEADER_RE,
    ROLLUP_LABELS,
    STUDENT_ID_RE,
    dedupe_wiki_proposals,
)
from app.teacher_agent.wiki.store import WikiStore

__all__ = [
    "DIARY_SECTION_HEADINGS",
    "INDEX_WIKI_PATH_RE",
    "LESSON_RESULTS_SECTIONS",
    "LOG_HEADER_LEGACY_RE",
    "LOG_HEADER_RE",
    "ROLLUP_LABELS",
    "STUDENT_ID_RE",
    "WikiStore",
    "dedupe_wiki_proposals",
]
