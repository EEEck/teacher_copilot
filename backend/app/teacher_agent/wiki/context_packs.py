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

from app.context_limits import apply_char_limit, get_context_limits
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


def _recent_taught_entries(store, class_id: str, limit: int = 2):
    entries = [e for e in store.get_timeline(class_id).entries if e.status == "taught"]
    return entries[:limit]


def _compact_memory_section(store, class_id: str, *, max_chars: int = 1400) -> list[str]:
    excerpts = store.compact_memory_excerpts(class_id, max_chars=max_chars)
    if not excerpts:
        return [
            "## Compact class memory",
            "- No compact memory pages found yet. Use the manual compact endpoint after lessons accumulate.",
            "",
        ]
    parts = ["## Compact class memory"]
    for rel, text in excerpts:
        parts.extend([f"### {rel}", text, ""])
    return parts


def _memory_page_excerpt(store, class_id: str, key: str, max_chars: int = 1200) -> str:
    path = store.memory_paths(class_id).get(key)
    if not path:
        return ""
    return store.read_text(path).strip()[:max_chars]


def _lesson_sequence_lines(store, class_id: str, limit: int = 6) -> list[str]:
    entries = [e for e in store.get_timeline(class_id).entries if e.status == "taught"]
    return [
        f"- {entry.date}: {entry.title} - {entry.summary}"
        for entry in entries[:limit]
    ]


def build_planning_query_pack(store, class_id: str) -> str:
    """AutoSci-style derived read-only pack for planning retrieval orientation."""
    snapshot = store.get_snapshot(class_id)
    parts = [
        "# Planning Query Pack",
        "Purpose: orient lesson planning before broader wiki search.",
        "",
        "## Recent taught sequence",
    ]
    sequence = _lesson_sequence_lines(store, class_id, limit=6)
    parts.extend(sequence or ["- No taught lessons found."])
    parts.extend(["", "## Misconception priorities"])
    parts.extend(
        [f"- {m}" for m in snapshot.top_misconceptions[:6]]
        if snapshot.top_misconceptions
        else ["- None listed."]
    )
    parts.extend(
        [
            "",
            "## Planning brief",
            _memory_page_excerpt(store, class_id, "planning_brief", 1200)
            or "- No compact planning brief yet.",
            "",
            "## Teaching patterns",
            _memory_page_excerpt(store, class_id, "teaching_patterns", 1200)
            or "- No compact teaching patterns yet.",
            "",
            "## Open loops",
            store.read_text(store.roll_up_paths(class_id)["open_loops"])[:1200],
        ]
    )
    return "\n".join(parts)


def build_ingest_query_pack(store, class_id: str) -> str:
    """AutoSci-style derived read-only pack for memory-update orientation."""
    snapshot = store.get_snapshot(class_id)
    parts = [
        "# Ingest Query Pack",
        "Purpose: orient lesson logging while keeping durable writes approval-gated.",
        "",
        "## Previous lesson",
    ]
    if snapshot.last_committed_date:
        try:
            detail = store.get_lesson_detail(class_id, snapshot.last_committed_date)
            parts.extend(
                [
                    f"### {snapshot.last_committed_date} - {detail.title}",
                    detail.diary_markdown[:1600],
                ]
            )
        except KeyError:
            parts.append("- Previous lesson detail not found.")
    else:
        parts.append("- No previous lesson found.")
    parts.extend(
        [
            "",
            "## Student roster excerpt",
            store.read_text(store.roll_up_paths(class_id)["students"])[:1600],
            "",
            "## Logging conventions",
            store.read_text(store.root / "AGENTS.md")[:900],
            "",
            "## Compact class memory",
            _memory_page_excerpt(store, class_id, "taught_so_far", 1000)
            or "- No compact taught-so-far memory yet.",
            "",
            "## Open loops",
            store.read_text(store.roll_up_paths(class_id)["open_loops"])[:900],
        ]
    )
    return "\n".join(parts)


def build_review_query_pack(store, class_id: str) -> str:
    """AutoSci-style derived read-only pack for reviews or assessment spanning memory."""
    snapshot = store.get_snapshot(class_id)
    taught = _memory_page_excerpt(store, class_id, "taught_so_far", 1600)
    if not taught:
        taught = "\n".join(_lesson_sequence_lines(store, class_id, limit=10))
    parts = [
        "# Review Query Pack",
        "Purpose: orient reviews, assessments, or cross-lesson synthesis.",
        "",
        "## Taught-so-far sequence",
        taught or "- No taught sequence available.",
        "",
        "## Recurring misconceptions",
    ]
    parts.extend(
        [f"- {m}" for m in snapshot.top_misconceptions[:8]]
        if snapshot.top_misconceptions
        else ["- None listed."]
    )
    parts.extend(
        [
            "",
            "## Unresolved issues and planning priorities",
            _memory_page_excerpt(store, class_id, "planning_brief", 1400)
            or store.read_text(store.roll_up_paths(class_id)["open_loops"])[:1400],
        ]
    )
    return "\n".join(parts)


def build_base_class_context(store, class_id: str) -> str:
    """Small class-scoped context shared by workflow packages."""
    snapshot = store.get_snapshot(class_id)
    cls = store.get_class(class_id)
    subject_guide = store.read_text(store.root / "wiki" / "subjects" / f"{cls.subject}.md")
    parts = [
        f"# Base class context - {snapshot.label} ({class_id})",
        f"Subject: {cls.subject}",
        f"Current unit: {snapshot.current_unit}",
        f"Last committed lesson: {snapshot.last_committed_date or 'None'}",
        f"Open loops (count): {snapshot.open_loop_count}",
        "",
        "## Recent timeline",
    ]
    if snapshot.recent_lessons:
        parts.extend(f"- {line}" for line in snapshot.recent_lessons[:5])
    else:
        parts.append("- No recent lessons")
    parts.extend(["", "## Core misconceptions"])
    if snapshot.top_misconceptions:
        parts.extend(f"- {m}" for m in snapshot.top_misconceptions[:6])
    else:
        parts.append("- None listed")
    parts.extend(
        [
            "",
            "## Class copilot profile",
            store.read_copilot_profile(class_id)[:1800] or "- No copilot profile yet.",
            "",
            f"## Subject guide: {cls.subject} (excerpt)",
            subject_guide[:1400],
        ]
    )
    return "\n".join(parts)


def build_context_package(store, class_id: str, mode: str) -> str:
    """Named frozen context package for a workflow session."""
    normalized = mode.strip().lower()
    if normalized in {"ingest", "memory", "update_memory"}:
        return build_ingest_context_slim(store, class_id)
    parts = [store.load_index_context(class_id), build_base_class_context(store, class_id)]
    if normalized in {"plan", "planning"}:
        parts.append(build_plan_context(store, class_id))
    else:
        raise ValueError(f"Unknown context package mode: {mode}")
    return "\n\n".join(part for part in parts if part.strip())



def _trace_section(
    *,
    name: str,
    function: str,
    source: str,
    text: str,
    included: bool = True,
) -> dict:
    return {
        "name": name,
        "function": function,
        "source": source,
        "included": included,
        "chars": len(text or ""),
        "text": text or "",
    }


def build_plan_context_slim_trace(store, class_id: str) -> dict:
    """Return the slim planning context plus a section-by-section debug trace.

    Unlike ``build_plan_context`` (which stacks index + base + plan packs and
    duplicates misconceptions/open loops several times), this returns each piece
    once, each clamped to its ``MEMORY_PAGE_BUDGETS`` size, so the prompt stays
    small and high-signal and never needs a blunt end-of-pack truncation.
    """
    from app.teacher_agent.wiki import memory as _mem

    snapshot = store.get_snapshot(class_id)
    cls = store.get_class(class_id)
    paths = store.memory_paths(class_id)
    sections: list[dict] = []
    parts: list[str] = []

    def add_section(
        name: str,
        source: str,
        lines: list[str],
        *,
        function: str = "build_plan_context_slim",
        included: bool = True,
    ) -> None:
        text = "\n".join(lines)
        sections.append(
            _trace_section(
                name=name,
                function=function,
                source=source,
                text=text,
                included=included,
            )
        )
        if included:
            parts.extend(lines)

    add_section(
        "Class identity snapshot",
        "get_snapshot() + get_class()",
        [
            f"# Class memory (compact) - {snapshot.label} ({class_id})",
            f"Subject: {cls.subject} | Current unit: {snapshot.current_unit}",
            f"Last committed lesson: {snapshot.last_committed_date or 'None'} | "
            f"Open loops: {snapshot.open_loop_count}",
        ],
    )
    add_section(
        "Top misconceptions",
        "snapshot.top_misconceptions",
        [
            "",
            "## Top misconceptions",
            *([f"- {m}" for m in snapshot.top_misconceptions[:6]] or ["- None listed"]),
        ],
    )
    if snapshot.recent_lessons:
        add_section(
            "Recent lessons",
            "snapshot.recent_lessons",
            [
                "",
                "## Recent lessons",
                *[f"- {line}" for line in snapshot.recent_lessons[:3]],
            ],
        )
    subject_path = store.root / "wiki" / "subjects" / f"{cls.subject}.md"
    subject_text = store.read_text(subject_path).strip()
    if subject_text:
        add_section(
            "Subject guide",
            store.rel_wiki(subject_path),
            [
                "",
                f"## Subject guide: {cls.subject}",
                _mem.clamp_memory_page("subject_guide", subject_text).rstrip(),
            ],
        )
    else:
        sections.append(
            _trace_section(
                name="Subject guide",
                function="build_plan_context_slim",
                source=store.rel_wiki(subject_path),
                text="",
                included=False,
            )
        )
    for key, label in (
        ("class_state", "Class state"),
        ("planning_brief", "Planning brief"),
        ("teaching_patterns", "Teaching patterns"),
    ):
        text = store.read_text(paths[key]).strip() if key in paths else ""
        source = store.rel_wiki(paths[key]) if key in paths else f"memory/{key}.md"
        if text:
            add_section(
                label,
                source,
                ["", f"## {label}", _mem.clamp_memory_page(key, text).rstrip()],
            )
        else:
            sections.append(
                _trace_section(
                    name=label,
                    function="build_plan_context_slim",
                    source=source,
                    text="",
                    included=False,
                )
            )
    rendered = "\n".join(parts)
    return {
        "function": "build_plan_context_slim",
        "chars": len(rendered),
        "text": rendered,
        "sections": sections,
    }


def build_plan_context_slim(store, class_id: str) -> str:
    """Deduped, budgeted compact class slice for the planning chat prompt."""
    return build_plan_context_slim_trace(store, class_id)["text"]


def build_ingest_context_slim(store, class_id: str) -> str:
    """Deduped, purpose-built context slice for lesson-memory ingest chat.

    Live ingest chat only needs continuity for logging today's lesson: class
    identity, previous lesson, roster IDs, course/open-loop state, compact memory,
    and logging conventions. It should not stack index + base + query pack,
    because that repeats the same roll-ups several times.
    """
    from app.teacher_agent.wiki import memory as _mem

    lim = get_context_limits()
    snapshot = store.get_snapshot(class_id)
    cls = store.get_class(class_id)
    rollups = store.roll_up_paths(class_id)
    mem_paths = store.memory_paths(class_id)

    parts = [
        f"# Ingest context (compact) - {snapshot.label} ({class_id})",
        f"Subject: {cls.subject} | Current unit: {snapshot.current_unit}",
        f"Last committed lesson: {snapshot.last_committed_date or 'None'} | "
        f"Open loops: {snapshot.open_loop_count}",
        "",
        "Use this context for continuity only. Log only what the teacher says happened today.",
        "Use pseudonymous student IDs only (S-001 style IDs).",
        "",
    ]

    if snapshot.last_committed_date:
        try:
            detail = store.get_lesson_detail(class_id, snapshot.last_committed_date)
            previous = apply_char_limit(
                detail.diary_markdown, lim.ingest_previous_lesson_chars
            )
            parts.extend(
                [
                    f"## Previous lesson ({snapshot.last_committed_date})",
                    previous or "- Previous lesson detail is empty.",
                    "",
                ]
            )
        except KeyError:
            parts.extend(["## Previous lesson", "- Previous lesson detail not found.", ""])
    else:
        parts.extend(["## Previous lesson", "- No previous lesson found.", ""])

    parts.extend(
        [
            "## Student roster excerpt",
            apply_char_limit(
                store.read_text(rollups["students"]), lim.ingest_student_roster_chars
            )
            or "- No student roster found.",
            "",
            "## Course state",
            apply_char_limit(
                store.read_text(rollups["course_state"]), lim.ingest_course_state_chars
            )
            or "- No course state found.",
            "",
            "## Open loops",
            apply_char_limit(
                store.read_text(rollups["open_loops"]), lim.ingest_open_loops_chars
            )
            or "- No open loops found.",
            "",
            "## Misconceptions to watch",
        ]
    )
    parts.extend(
        [f"- {m}" for m in snapshot.top_misconceptions[:5]]
        if snapshot.top_misconceptions
        else ["- None listed yet."]
    )

    compact_pages = [
        ("class_state", "Class state"),
        ("taught_so_far", "Taught so far"),
        ("planning_brief", "Planning brief"),
        ("teaching_patterns", "Teaching patterns"),
    ]
    any_compact = False
    parts.extend(["", "## Compact class memory"])
    for key, label in compact_pages:
        text = store.read_text(mem_paths[key]).strip() if key in mem_paths else ""
        if not text:
            continue
        any_compact = True
        parts.extend([f"### {label}", _mem.clamp_memory_page(key, text).rstrip()])
    if not any_compact:
        parts.append("- No compact class memory pages found yet.")

    planned = [e for e in store.get_timeline(class_id).entries if e.has_plan][:1]
    if planned:
        for entry in planned:
            try:
                detail = store.get_lesson_detail(class_id, entry.date)
            except KeyError:
                continue
            if detail.lesson_plan_markdown:
                parts.extend(
                    [
                        "",
                        f"## Most recent saved plan ({entry.date})",
                        apply_char_limit(
                            detail.lesson_plan_markdown, lim.ingest_saved_plan_chars
                        ),
                    ]
                )
                break

    parts.extend(
        [
            "",
            "## Wiki logging conventions",
            apply_char_limit(
                store.read_text(store.root / "AGENTS.md"),
                lim.ingest_logging_conventions_chars,
            )
            or "- No logging conventions found.",
        ]
    )
    return "\n".join(parts)


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

    parts.extend([build_planning_query_pack(store, class_id), ""])

    recent_taught = _recent_taught_entries(store, class_id, limit=2)
    if recent_taught:
        parts.append("## Last 2 taught lessons")
    for entry in recent_taught:
        try:
            detail = store.get_lesson_detail(class_id, entry.date)
            parts.extend(
                [
                    f"### {entry.date} - {entry.title}",
                    detail.diary_markdown[:3000],
                    "",
                ]
            )
            if detail.lesson_plan_markdown:
                parts.extend(
                    [
                        f"#### Saved plan ({entry.date})",
                        detail.lesson_plan_markdown[:1800],
                        "",
                    ]
                )
        except KeyError:
            continue

    parts.extend(_compact_memory_section(store, class_id, max_chars=1800))

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
        "Use pseudonyms only for student references (S-001 style IDs).",
        "",
        "## Student notes / roster",
        store.read_text(store.roll_up_paths(class_id)["students"])[:4500],
        "",
        "## Course state",
        store.read_text(store.roll_up_paths(class_id)["course_state"])[:2000],
        "",
    ]

    parts.extend([build_ingest_query_pack(store, class_id), ""])

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

    planned = [e for e in store.get_timeline(class_id).entries if e.has_plan][:3]
    if planned:
        parts.append("## Recent saved plans (continuity only)")
        for entry in planned:
            try:
                detail = store.get_lesson_detail(class_id, entry.date)
            except KeyError:
                continue
            if detail.lesson_plan_markdown:
                parts.extend(
                    [
                        f"### {entry.date} - {entry.title}",
                        detail.lesson_plan_markdown[:1200],
                        "",
                    ]
                )

    parts.extend(_compact_memory_section(store, class_id, max_chars=1200))

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
