"""Offline tests for CLI trace formatting."""

from app.teacher_agent.stream_events import (
    SseFinal,
    SseToolCall,
    SseToolResult,
)
from app.cli.trace import TracePrinter, format_event_line
import io


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
