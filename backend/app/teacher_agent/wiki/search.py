"""Wiki search operations (delegated from WikiStore)."""

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



def list_class_pages(
    store, class_id: str, kind: Optional[str] = None
) -> list[dict[str, str]]:
    store.get_class(class_id)
    pages: list[dict[str, str]] = []
    base = store.class_dir(class_id)
    kinds = {kind} if kind else {"rollups", "lessons", "students", "timeline", "raw"}

    if "rollups" in kinds:
        for key, path in store.roll_up_paths(class_id).items():
            pages.append(
                {"kind": "rollup", "id": key, "path": store.rel_wiki(path)}
            )
        for name in ("timeline.md", "class_config.md"):
            p = base / name
            if p.exists():
                pages.append({"kind": "meta", "id": name, "path": store.rel_wiki(p)})

    if "lessons" in kinds:
        lessons_root = base / "lessons"
        if lessons_root.exists():
            for day_dir in sorted(lessons_root.iterdir()):
                if not day_dir.is_dir():
                    continue
                for fname in ("lesson_results.md", "lesson_plan.md"):
                    p = day_dir / fname
                    if p.exists():
                        pages.append(
                            {
                                "kind": "lesson",
                                "id": day_dir.name,
                                "path": store.rel_wiki(p),
                            }
                        )

    if "students" in kinds:
        sdir = store.students_dir(class_id)
        if sdir.exists():
            for p in sorted(sdir.glob("S-*.md")):
                pages.append(
                    {
                        "kind": "student",
                        "id": p.stem,
                        "path": store.rel_wiki(p),
                    }
                )

    if "raw" in kinds:
        raw_root = store.root / "raw" / "classes" / class_id
        if raw_root.exists():
            for p in sorted(raw_root.glob("*.md")):
                pages.append(
                    {"kind": "raw", "id": p.stem, "path": store.rel_wiki(p)}
                )
    return pages

def find_in_memory(
    store, class_id: str, query: str, max_results: int = 5
) -> list[dict[str, str]]:
    """Index-first search: match class index.md, then scan page bodies."""
    store.get_class(class_id)
    q = query.lower().strip()
    if not q:
        return []

    hits: list[dict[str, str]] = []
    seen: set[str] = set()

    index_text = store.read_wiki_index(class_id)
    for line in index_text.splitlines():
        line_lower = line.lower()
        if q not in line_lower:
            continue
        for match in INDEX_WIKI_PATH_RE.finditer(line):
            path = match.group(1)
            if path in seen:
                continue
            seen.add(path)
            hits.append(
                {
                    "path": path,
                    "snippet": line.strip()[:200],
                    "source": "index",
                }
            )
            if len(hits) >= max_results:
                return hits

    for page in store.list_class_pages(class_id):
        path = page["path"]
        if path in seen:
            continue
        try:
            text = store.read_text(store.resolve_path(path))
        except ValueError:
            continue
        text_lower = text.lower()
        if q not in text_lower:
            continue
        idx = text_lower.index(q)
        start = max(0, idx - 80)
        snippet = " ".join(text[start : idx + 80].split())
        seen.add(path)
        hits.append(
            {
                "path": path,
                "snippet": snippet[:200],
                "source": "body",
            }
        )
        if len(hits) >= max_results:
            break
    return hits

def search_wiki(
    store, class_id: str, query: str, max_results: int = 15
) -> list[dict[str, str]]:
    """Backward-compatible search; delegates to find_in_memory."""
    return [
        {"path": h["path"], "snippet": h["snippet"]}
        for h in store.find_in_memory(class_id, query, max_results)
    ]

def is_class_memory_path(store, class_id: str, relative_path: str) -> bool:
    """True if path is readable class-scoped wiki (chat read_memory_page guard)."""
    rel = relative_path.strip().lstrip("/").replace("\\", "/")
    if ".." in rel.split("/"):
        return False
    prefix = f"wiki/classes/{class_id}/"
    return rel.startswith(prefix)
