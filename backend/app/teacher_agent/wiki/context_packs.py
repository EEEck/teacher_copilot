"""Wiki context packs operations (delegated from WikiStore)."""

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



def build_plan_context(store, class_id: str) -> str:
    """Memory pack for planning the *next* lesson — forward-looking rollups + last real lesson."""
    snapshot = store.get_snapshot(class_id)
    cls = store.get_class(class_id)
    timeline = store.get_timeline(class_id)
    parts = [
        f"# Session: Plan next lesson — {snapshot.label} ({class_id})",
        f"Subject: {cls.subject} | Current unit: {snapshot.current_unit}",
        f"Open loops (count): {snapshot.open_loop_count}",
        "",
        "Use this to propose activities, timing, and homework for the upcoming lesson.",
        "",
        "## Top misconceptions to address",
    ]
    if snapshot.top_misconceptions:
        parts.extend(f"- {m}" for m in snapshot.top_misconceptions)
    else:
        parts.append("- None listed")
    parts.append("")

    if snapshot.recent_lessons:
        parts.extend(["## Recent lessons (titles)", *[f"- {line}" for line in snapshot.recent_lessons], ""])

    if snapshot.last_committed_date:
        try:
            detail = store.get_lesson_detail(class_id, snapshot.last_committed_date)
            parts.extend(
                [
                    f"## Last committed lesson ({snapshot.last_committed_date})",
                    detail.diary_markdown[:5000],
                    "",
                ]
            )
            if detail.lesson_plan_markdown:
                parts.extend(
                    [
                        f"## Existing plan on file ({snapshot.last_committed_date})",
                        detail.lesson_plan_markdown[:3000],
                        "",
                    ]
                )
        except KeyError:
            pass

    for key in ("course_state", "students", "open_loops", "misconceptions"):
        path = store.roll_up_paths(class_id)[key]
        label = ROLLUP_LABELS.get(key, key)
        parts.extend([f"## {label}", store.read_text(path)[:2500], ""])

    planned = [e for e in timeline.entries if e.has_plan][:3]
    if planned:
        parts.append("## Lessons that already have a saved plan")
        for e in planned:
            parts.append(f"- {e.date} — {e.title}")
        parts.append("")

    parts.extend(
        [
            "## Teacher profile (excerpt)",
            store.read_text(store.root / "wiki" / "teacher_profile.md")[:1200],
            "",
            f"## Subject guide: {cls.subject} (excerpt)",
            store.read_text(store.root / "wiki" / "subjects" / f"{cls.subject}.md")[:1200],
        ]
    )
    return "\n".join(parts)

def build_ingest_context(store, class_id: str) -> str:
    """Memory pack for logging today's lesson — student IDs, prior lesson, light rollups."""
    snapshot = store.get_snapshot(class_id)
    cls = store.get_class(class_id)
    parts = [
        f"# Session: Update lesson notes — {snapshot.label} ({class_id})",
        f"Subject: {cls.subject} | Current unit: {snapshot.current_unit}",
        "",
        "Help the teacher record what happened today. Use only what they say; use context for IDs and continuity.",
        "",
        "## Students",
        store.read_text(store.roll_up_paths(class_id)["students"])[:4500],
        "",
        "## Course state",
        store.read_text(store.roll_up_paths(class_id)["course_state"])[:2000],
        "",
    ]

    if snapshot.last_committed_date:
        try:
            detail = store.get_lesson_detail(class_id, snapshot.last_committed_date)
            parts.extend(
                [
                    f"## Previous lesson ({snapshot.last_committed_date}) — continuity only",
                    detail.diary_markdown[:3500],
                    "",
                ]
            )
        except KeyError:
            pass

    parts.extend(
        [
            "## Open loops (teacher may close or add while logging)",
            store.read_text(store.roll_up_paths(class_id)["open_loops"])[:1500],
            "",
            "## Misconceptions (brief — note new ones if the teacher reports them)",
        ]
    )
    if snapshot.top_misconceptions:
        parts.extend(f"- {m}" for m in snapshot.top_misconceptions[:5])
    else:
        parts.append("- None listed yet")
    parts.extend(
        [
            "",
            "## Wiki logging conventions (excerpt)",
            store.read_text(store.root / "AGENTS.md")[:1200],
        ]
    )
    return "\n".join(parts)

def empty_plan_template(store, lesson_date: Optional[str] = None) -> str:
    d = lesson_date or date.today().isoformat()
    return (
        f"# Lesson Plan — Next lesson\n\n"
        f"> Duration: 45 min | Target date: {d}\n\n"
        "## Learning goals\n\n\n"
        "## Lesson flow\n\n"
        "- **Opening** (5 min):\n\n"
        "- **Main teaching** (25 min):\n\n"
        "- **Practice** (10 min):\n\n"
        "- **Close** (5 min):\n\n"
        "## Warmup\n\n\n"
        "## Practice tasks\n\n-\n\n"
        "## Homework\n\n\n"
        "## Teacher notes\n\n"
    )

def is_plan_ready(store, plan_md: str) -> bool:
    required = ("## Learning goals", "## Lesson flow", "## Warmup")
    text = plan_md.lower()
    return all(h.lower() in text for h in required) and len(plan_md.strip()) > 200

def load_index_context(
    store, class_id: str, max_chars: int = 4000, *, for_tool_loop: bool = False
) -> str:
    """Index-first context bundled into chat prompts."""
    cls = store.get_class(class_id)
    index_hint = (
        "read pages via tools as needed"
        if for_tool_loop
        else "see sections below for detail"
    )
    parts = [
        f"# Wiki index ({index_hint})",
        f"Class: {cls.label} ({class_id})",
        "",
        store.read_wiki_index(class_id)[:max_chars],
        "",
        "## Roll-up excerpts",
        store.read_text(store.roll_up_paths(class_id)["course_state"])[:1500],
        "",
        store.read_text(store.roll_up_paths(class_id)["open_loops"])[:1000],
    ]
    return "\n".join(parts)

def empty_diary_template(store, lesson_date: Optional[str] = None) -> str:
    d = lesson_date or date.today().isoformat()
    lines = [f"# Lesson Results — {d} — ", ""]
    for _, label, _ in LESSON_RESULTS_SECTIONS:
        lines.extend([f"## {label}", "", ""])
    return "\n".join(lines)
