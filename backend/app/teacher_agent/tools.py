"""OpenAI Agents SDK tools for wiki read/query (no direct writes)."""

from __future__ import annotations

import json
from dataclasses import dataclass

from agents import function_tool

from app.teacher_agent.wiki_store import WikiStore


@dataclass
class WikiToolContext:
    wiki: WikiStore
    class_id: str


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
    """Minimal Karpathy-style read tools for ingest/plan chat."""
    wiki = ctx.wiki
    class_id = ctx.class_id

    @function_tool
    def recall_lesson(lesson_date: str) -> str:
        """Load one lesson by date (YYYY-MM-DD): diary + rollup excerpts."""
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
    def find_in_memory(query: str) -> str:
        """Find wiki paths: checks index lesson table first, then full-text scan."""
        hits = wiki.find_in_memory(class_id, query, max_results=5)
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

    return [recall_lesson, find_in_memory, read_memory_page]
