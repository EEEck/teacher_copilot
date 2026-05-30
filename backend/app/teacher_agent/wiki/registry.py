"""Wiki registry operations (delegated from WikiStore)."""

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



def list_classes(store) -> list[ClassSummary]:
    discovered: list[ClassSummary] = []
    classes_root = store.root / "wiki" / "classes"
    if classes_root.exists():
        for class_dir in sorted(classes_root.iterdir()):
            if not class_dir.is_dir():
                continue
            class_id = class_dir.name
            label, subject = store._read_class_meta(class_id)
            discovered.append(
                ClassSummary(id=class_id, label=label, subject=subject)
            )
    if discovered:
        return discovered
    return CLASS_REGISTRY

def _read_class_meta(store, class_id: str) -> tuple[str, str]:
    config = store.read_text(store.class_config_path(class_id))
    label = class_id.replace("_", " ")
    subject = "general"
    m = re.search(r"^#\s+(.+)$", config, re.M)
    if m:
        label = m.group(1).strip()
    m = re.search(r"^subject:\s*(\S+)", config, re.M | re.I)
    if m:
        subject = m.group(1).strip().lower()
    for c in CLASS_REGISTRY:
        if c.id == class_id:
            return c.label, c.subject
    return label, subject

def get_class(store, class_id: str) -> ClassSummary:
    for c in store.list_classes():
        if c.id == class_id:
            return c
    raise KeyError(f"Unknown class: {class_id}")
