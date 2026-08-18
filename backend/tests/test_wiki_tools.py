"""Tests for chat wiki tool wiring."""

import asyncio
import json

from agents.tool_context import ToolContext
from app.teacher_agent.tools import (
    WikiToolContext,
    create_chat_wiki_tools,
    create_executive_verification_tools,
    create_memory_update_tools,
)
from app.teacher_agent.wiki_store import WikiStore
from app.teacher_agent.planning_state import PlanRuntime
from app.teacher_agent.class_discussion_state import (
    ClassDiscussionRuntime,
    discussion_api_payload,
)
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
            "list_class_materials",
            "search_class_materials",
            "read_class_material",
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


def test_discussion_runtime_can_read_and_record_a_trusted_source_section():
    """Discuss must support the same source-read provenance as Plan chat."""
    wiki = WikiStore(root=_WIKI_ROOT)
    runtime = ClassDiscussionRuntime()
    tool = next(
        tool
        for tool in create_chat_wiki_tools(
            WikiToolContext(wiki=wiki, class_id=CLASS_ID, planning=runtime)
        )
        if tool.name == "read_trusted_source"
    )

    arguments = json.dumps(
        {
            "source_id": "by-lehrplanplus-chemie-9-ntg",
            "section_id": "c9_atombau",
        }
    )
    output = asyncio.run(
        tool.on_invoke_tool(
            ToolContext(
                None,
                tool_name="read_trusted_source",
                tool_call_id="test-trusted-source-read",
                tool_arguments=arguments,
            ),
            arguments,
        )
    )

    assert output.startswith("raw_ref: trusted_source_read_")
    assert runtime.consulted_sources == [
        {"source_id": "by-lehrplanplus-chemie-9-ntg", "section_id": "c9_atombau"}
    ]
    assert discussion_api_payload(runtime)["consulted_sources"] == runtime.consulted_sources


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
