"""Tests for chat wiki tool wiring."""

from app.teacher_agent.tools import (
    WikiToolContext,
    create_chat_wiki_tools,
    create_executive_verification_tools,
    create_memory_update_tools,
)
from app.teacher_agent.wiki_store import WikiStore
from app.teacher_agent.planning_state import PlanRuntime
from pathlib import Path

CLASS_ID = "chemie_9b_2026_27"
_WIKI_ROOT = Path(__file__).resolve().parent.parent / "teacher_wiki"


def test_create_chat_wiki_tools_exposes_mvp_names():
    wiki = WikiStore(root=_WIKI_ROOT)
    ctx = WikiToolContext(wiki=wiki, class_id=CLASS_ID)
    tools = create_chat_wiki_tools(ctx)
    names = {getattr(t, "name", None) for t in tools}
    assert names == {
        "list_lessons",
        "read_lesson",
        "read_lesson_range",
        "search_memory",
        "read_memory_page",
        "list_trusted_sources",
        "search_trusted_sources",
        "read_trusted_source",
        "search_subject_guidance",
        "read_subject_guidance",
        "get_raw_evidence",
        "remember",
        "report_verification_finding",
        "resolve_wiki_references",
    }


def test_trusted_source_tools_have_bounded_planner_contracts():
    wiki = WikiStore(root=_WIKI_ROOT)
    tools = create_chat_wiki_tools(
        WikiToolContext(wiki=wiki, class_id=CLASS_ID, planning=PlanRuntime())
    )
    search = next(tool for tool in tools if tool.name == "search_trusted_sources")
    read = next(tool for tool in tools if tool.name == "read_trusted_source")

    assert {"query", "scope", "max_results"} <= set(
        search.params_json_schema["properties"]
    )
    assert {"source_id", "section_id"} <= set(read.params_json_schema["properties"])


def test_subject_guidance_tools_have_bounded_active_subject_contracts():
    wiki = WikiStore(root=_WIKI_ROOT)
    tools = create_chat_wiki_tools(
        WikiToolContext(wiki=wiki, class_id=CLASS_ID, planning=PlanRuntime())
    )
    search = next(tool for tool in tools if tool.name == "search_subject_guidance")
    read = next(tool for tool in tools if tool.name == "read_subject_guidance")

    assert {"query", "max_results"} <= set(search.params_json_schema["properties"])
    assert {"path"} <= set(read.params_json_schema["properties"])


def test_memory_update_tools_include_shared_verification_tools():
    wiki = WikiStore(root=_WIKI_ROOT)
    ctx = WikiToolContext(wiki=wiki, class_id=CLASS_ID)
    names = {tool.name for tool in create_memory_update_tools(ctx)}

    assert {"resolve_wiki_references", "report_verification_finding"} <= names


def test_reference_lookup_tool_is_limited_to_the_active_class():
    wiki = WikiStore(root=_WIKI_ROOT)
    ctx = WikiToolContext(wiki=wiki, class_id=CLASS_ID)
    tool = next(
        tool
        for tool in create_executive_verification_tools(ctx)
        if tool.name == "resolve_wiki_references"
    )

    assert "scope" not in tool.params_json_schema["properties"]
