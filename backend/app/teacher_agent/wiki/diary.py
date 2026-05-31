"""Wiki diary operations (delegated from WikiStore)."""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from app.schemas.api import (
    ApprovedWikiUpdate,
    ClassMemorySnapshot,
    ClassSummary,
    ClassTimeline,
    CompletenessChecklist,
    CompletenessItem,
    LessonDetail,
    RollupExcerpt,
    TimelineEntry,
    WikiUpdateProposal,
)

from app.teacher_agent.wiki.constants import (
    CLASS_REGISTRY,
    DIARY_SECTION_HEADINGS,
    INDEX_WIKI_PATH_RE,
    LESSON_RESULTS_SECTIONS,
    LOG_HEADER_LEGACY_RE,
    LOG_HEADER_RE,
    ROLLUP_LABELS,
    STUDENT_ID_RE,
    dedupe_wiki_proposals,
)

from app.teacher_agent.wiki import parsing



def checklist_from_diary(store, diary_md: str) -> CompletenessChecklist:
    items: list[CompletenessItem] = []
    for key, label, required in LESSON_RESULTS_SECTIONS:
        section = parsing.extract_section_body(diary_md, label)
        complete = bool(section.strip()) and section.strip().lower() not in {"none", "n/a", "tbd", "-"}
        items.append(
            CompletenessItem(field=key, label=label, complete=complete, required=required)
        )
    return CompletenessChecklist(items=items)

def is_diary_complete(store, diary_md: str) -> bool:
    checklist = store.checklist_from_diary(diary_md)
    return all(i.complete for i in checklist.items if i.required)
