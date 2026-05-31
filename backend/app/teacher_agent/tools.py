"""OpenAI Agents SDK tools for wiki read/query (no direct writes)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from agents import function_tool

from app.teacher_agent.wiki_store import WikiStore


@dataclass
class WikiToolContext:
    wiki: WikiStore
    class_id: str


def _lesson_paths(
    class_id: str, lesson_date: str, *, status: str, has_plan: bool
) -> list[str]:
    paths = []
    if status == "taught":
        paths.append(f"wiki/classes/{class_id}/lessons/{lesson_date}/lesson_results.md")
    if has_plan:
        paths.append(f"wiki/classes/{class_id}/lessons/{lesson_date}/lesson_plan.md")
    return paths


def _lesson_matches_topic(entry, topic: str) -> bool:
    q = topic.strip().lower()
    if not q:
        return True
    haystack = "\n".join(
        [
            entry.title,
            entry.summary,
            "\n".join(entry.covered),
            "\n".join(entry.highlights),
            "\n".join(entry.issues),
            "\n".join(entry.follow_ups),
        ]
    ).lower()
    return q in haystack


def _lesson_body_matches_topic(
    wiki: WikiStore, paths: list[str], topic: str
) -> bool:
    q = topic.strip().lower()
    if not q:
        return True
    for path in paths:
        try:
            text = wiki.read_text(wiki.resolve_path(path))
        except ValueError:
            continue
        if q in text.lower():
            return True
    return False


def _list_lessons_payload(
    wiki: WikiStore,
    class_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
    topic: str = "",
    max_results: int = 12,
) -> dict:
    start = start_date.isoformat() if start_date else None
    end = end_date.isoformat() if end_date else None
    if start and end and start > end:
        return {"lessons": [], "warnings": ["start_date must be on or before end_date"]}

    limit = max(1, min(max_results or 12, 30))
    timeline = wiki.get_timeline(class_id)
    lessons = []
    matched_before_limit = 0
    for entry in sorted(timeline.entries, key=lambda e: e.date):
        if start and entry.date < start:
            continue
        if end and entry.date > end:
            continue
        paths = entry.wiki_paths or _lesson_paths(
            class_id, entry.date, status=entry.status, has_plan=entry.has_plan
        )
        if not _lesson_matches_topic(entry, topic) and not _lesson_body_matches_topic(
            wiki, paths, topic
        ):
            continue
        matched_before_limit += 1
        if len(lessons) >= limit:
            continue
        lessons.append(
            {
                "date": entry.date,
                "title": entry.title,
                "status": entry.status,
                "summary": entry.summary,
                "covered": entry.covered[:5],
                "homework": entry.homework,
                "paths": paths,
            }
        )

    warnings = []
    if not lessons:
        warnings.append("No lessons found for the requested range/topic.")
    elif matched_before_limit > len(lessons):
        warnings.append(
            f"Returned {len(lessons)} of {matched_before_limit} matching lessons; narrow the range if more detail is needed."
        )
    return {
        "range": {"start_date": start, "end_date": end, "topic": topic.strip()},
        "lessons": lessons,
        "warnings": warnings,
    }


def _lesson_detail_payload(wiki: WikiStore, class_id: str, lesson_date: str) -> dict:
    detail = wiki.get_lesson_detail(class_id, lesson_date)
    paths = []
    if detail.primary_markdown:
        paths.append(f"wiki/classes/{class_id}/lessons/{lesson_date}/lesson_results.md")
    if detail.lesson_plan_markdown:
        paths.append(f"wiki/classes/{class_id}/lessons/{lesson_date}/lesson_plan.md")
    return {
        "date": detail.date,
        "title": detail.title,
        "source_paths": paths,
        "diary_markdown": detail.diary_markdown[:6000],
        "lesson_plan_markdown": (detail.lesson_plan_markdown or "")[:2500],
        "rollup_excerpts": [
            {"path": e.wiki_path, "label": e.label, "markdown": e.markdown[:1500]}
            for e in detail.rollup_excerpts
        ],
    }


def create_wiki_tools(ctx: WikiToolContext) -> list:
    wiki = ctx.wiki
    class_id = ctx.class_id

    @function_tool
    def read_wiki_page(path: str) -> str:
        """Read a markdown file under teacher_wiki by relative path (e.g. index.md or wiki/classes/...)."""
        try:
            return wiki.read_wiki_page(path)
        except ValueError as e:
            return f"Error: {e}"

    @function_tool
    def read_wiki_index() -> str:
        """Read the class wiki index. Rarely needed — index is already in the prompt context."""
        return wiki.read_wiki_index(class_id)

    @function_tool
    def list_class_pages(kind: str = "") -> str:
        """List wiki page paths. Use only when you need a path before read_wiki_page; avoid browsing."""
        k = kind.strip().lower() or None
        if k == "timeline":
            k = "rollups"
        pages = wiki.list_class_pages(class_id, kind=k)
        return json.dumps(pages, indent=2)

    @function_tool
    def get_class_snapshot() -> str:
        """Summary of class memory: unit, open loops, misconceptions, recent lessons."""
        snap = wiki.get_snapshot(class_id)
        return snap.model_dump_json(indent=2)

    @function_tool
    def get_lesson_detail(lesson_date: str) -> str:
        """Lesson diary + rollups for YYYY-MM-DD. Use when that date is not in the context pack."""
        try:
            detail = wiki.get_lesson_detail(class_id, lesson_date)
            payload = {
                "date": detail.date,
                "title": detail.title,
                "diary_markdown": detail.diary_markdown[:6000],
                "rollup_excerpts": [
                    {"path": e.wiki_path, "markdown": e.markdown[:1500]}
                    for e in detail.rollup_excerpts
                ],
            }
            return json.dumps(payload, indent=2)
        except KeyError as e:
            return f"Error: {e}"

    @function_tool
    def search_wiki(query: str) -> str:
        """Search class wiki markdown. Use for a specific missing fact, not exploratory browsing."""
        hits = wiki.search_wiki(class_id, query)
        return json.dumps(hits, indent=2)

    @function_tool
    def find_in_memory(query: str) -> str:
        """Search index.md first, then page bodies. Returns paths + snippets for read_memory_page."""
        hits = wiki.find_in_memory(class_id, query)
        return json.dumps(hits, indent=2)

    return [
        read_wiki_page,
        read_wiki_index,
        list_class_pages,
        get_class_snapshot,
        get_lesson_detail,
        search_wiki,
        find_in_memory,
    ]


def create_chat_wiki_tools(ctx: WikiToolContext) -> list:
    """Class-scoped read tools for lesson-planning chat."""
    wiki = ctx.wiki
    class_id = ctx.class_id

    @function_tool
    def list_lessons(
        start_date: date | None = None,
        end_date: date | None = None,
        topic: str = "",
        max_results: int = 12,
    ) -> str:
        """List class lessons by optional YYYY-MM-DD range and topic before reading details."""
        payload = _list_lessons_payload(
            wiki, class_id, start_date, end_date, topic, max_results
        )
        return json.dumps(payload, indent=2)

    @function_tool
    def read_lesson(lesson_date: date) -> str:
        """Read one lesson by date (YYYY-MM-DD): lesson notes, saved plan, and rollup excerpts."""
        try:
            payload = _lesson_detail_payload(wiki, class_id, lesson_date.isoformat())
            return json.dumps(payload, indent=2)
        except KeyError as e:
            return f"Error: {e}"

    @function_tool
    def read_lesson_range(
        start_date: date,
        end_date: date,
        topic: str = "",
        max_lessons: int = 12,
    ) -> str:
        """Read a compact packet for lessons in a YYYY-MM-DD range; use for reviews/tests spanning weeks."""
        listed = _list_lessons_payload(
            wiki, class_id, start_date, end_date, topic, max_lessons
        )
        lessons = []
        for lesson in listed.get("lessons", []):
            try:
                detail = wiki.get_lesson_detail(class_id, lesson["date"])
            except KeyError:
                continue
            source_paths = []
            if detail.primary_markdown:
                source_paths.append(
                    f"wiki/classes/{class_id}/lessons/{detail.date}/lesson_results.md"
                )
            if detail.lesson_plan_markdown:
                source_paths.append(
                    f"wiki/classes/{class_id}/lessons/{detail.date}/lesson_plan.md"
                )
            lessons.append(
                {
                    "date": detail.date,
                    "title": detail.title,
                    "source_paths": source_paths,
                    "summary": lesson.get("summary", ""),
                    "covered": lesson.get("covered", []),
                    "lesson_notes_excerpt": detail.diary_markdown[:2500],
                    "rollup_excerpts": [
                        {
                            "path": e.wiki_path,
                            "label": e.label,
                            "markdown": e.markdown[:800],
                        }
                        for e in detail.rollup_excerpts[:3]
                    ],
                }
            )
        payload = {
            "range": listed.get("range", {}),
            "lessons": lessons,
            "warnings": listed.get("warnings", []),
        }
        return json.dumps(payload, indent=2)

    @function_tool
    def search_memory(query: str, max_results: int = 8) -> str:
        """Find wiki paths: checks index lesson table first, then full-text scan."""
        limit = max(1, min(max_results or 8, 20))
        hits = wiki.find_in_memory(class_id, query, max_results=limit)
        return json.dumps(hits, indent=2)

    @function_tool
    def read_memory_page(path: str) -> str:
        """Read one class wiki page by path from find_in_memory (under wiki/classes/{class_id}/)."""
        if not wiki.is_class_memory_path(class_id, path):
            return f"Error: path must be under wiki/classes/{class_id}/"
        try:
            return wiki.read_wiki_page(path)
        except ValueError as e:
            return f"Error: {e}"

    return [
        list_lessons,
        read_lesson,
        read_lesson_range,
        search_memory,
        read_memory_page,
    ]
