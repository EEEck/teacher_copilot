"""Offline tests for CLI trace formatting."""

import json
import tempfile
from pathlib import Path

import io

from app.cli.trace import JsonlTraceWriter, TracePrinter, format_event_line
from app.teacher_agent.stream_events import (
    SseFinal,
    SseReasoningDelta,
    SseToolCall,
    SseToolResult,
)


def test_format_event_line_tool_call():
    assert format_event_line(SseToolCall(name="search_wiki", args="{}")) == "tool_call:search_wiki"


def test_format_event_line_tool_result_length():
    assert format_event_line(SseToolResult(name="read_wiki_page", output="abc")) == (
        "tool_result:read_wiki_page:3"
    )


def test_trace_printer_tool_result_no_color():
    buf = io.StringIO()
    printer = TracePrinter(verbose=True, stream=buf)
    printer.print_event(SseToolResult(name="read_wiki_page", output="# Title\nbody"))
    out = buf.getvalue()
    assert "read_wiki_page" in out
    assert "Title" in out


def test_jsonl_trace_skips_reasoning_deltas():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "trace.jsonl"
        writer = JsonlTraceWriter(path)
        writer.write_user_message("Plan a redox lesson", turn=1)
        writer.write_event(SseReasoningDelta(text="think "), turn=1)
        writer.write_event(SseReasoningDelta(text="more"), turn=1)
        writer.write_event(
            SseToolCall(name="search_memory", args='{"query":"redox"}', call_id="c1"),
            turn=1,
        )
        writer.write_event(
            SseToolResult(name="search_memory", output='[{"path":"x"}]'),
            turn=1,
        )
        writer.close()
        lines = path.read_text(encoding="utf-8").strip().splitlines()
    types = [json.loads(line)["type"] for line in lines]
    assert "reasoning_delta" not in types
    assert "user_message" in types
    assert "tool_call" in types
    assert "tool_result" in types
    assert "reasoning" not in types


def test_jsonl_trace_aggregates_reasoning_when_enabled():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "trace.jsonl"
        writer = JsonlTraceWriter(path, include_reasoning=True)
        writer.write_event(SseReasoningDelta(text="alpha "), turn=1)
        writer.write_event(SseToolCall(name="search_memory", args="{}", call_id="c1"), turn=1)
        writer.close()
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    reasoning = [r for r in records if r["type"] == "reasoning"]
    assert len(reasoning) == 1
    assert reasoning[0]["text"] == "alpha "


def test_trace_printer_final_summary():
    buf = io.StringIO()
    printer = TracePrinter(verbose=True, stream=buf)
    printer.print_event(
        SseFinal(
            reply="Done.",
            artifact_markdown="# Diary\n\n## Section\n",
            ready=False,
            completeness=None,
        )
    )
    out = buf.getvalue()
    assert "[assistant]" in out
    assert "Done." in out
    assert "[draft]" in out
