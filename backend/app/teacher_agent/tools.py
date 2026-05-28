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
        """Read the wiki index for the current class (catalog of pages)."""
        return wiki.read_wiki_index(class_id)

    @function_tool
    def list_class_pages(kind: str = "") -> str:
        """List wiki pages for the class. kind: rollups, lessons, students, timeline, raw, or empty for all."""
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
        """Full lesson detail for YYYY-MM-DD (truncated)."""
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
        """Case-insensitive search over class wiki markdown files."""
        hits = wiki.search_wiki(class_id, query)
        return json.dumps(hits, indent=2)

    return [
        read_wiki_page,
        read_wiki_index,
        list_class_pages,
        get_class_snapshot,
        get_lesson_detail,
        search_wiki,
    ]
