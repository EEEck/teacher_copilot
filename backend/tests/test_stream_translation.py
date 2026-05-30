"""Unit tests for SDK event → SSE translation (offline fixtures)."""

from __future__ import annotations

from types import SimpleNamespace

from app.teacher_agent.stream_events import (
    SseReasoningDelta,
    SseToolCall,
    translate_sdk_event,
)


def test_raw_reasoning_delta():
    event = SimpleNamespace(
        type="raw_response_event",
        data=SimpleNamespace(type="response.reasoning_summary_text.delta", delta="Thinking…"),
    )
    out = translate_sdk_event(event)
    assert len(out) == 1
    assert isinstance(out[0], SseReasoningDelta)
    assert out[0].text == "Thinking…"


def test_tool_called_run_item():
    raw = SimpleNamespace(name="search_wiki", arguments='{"q":"redox"}', call_id="c1")
    item = SimpleNamespace(type="tool_call_item", raw_item=raw, tool_name="search_wiki", call_id="c1")
    event = SimpleNamespace(type="run_item_stream_event", name="tool_called", item=item)
    out = translate_sdk_event(event)
    assert len(out) == 1
    assert isinstance(out[0], SseToolCall)
    assert out[0].name == "search_wiki"
    assert "redox" in out[0].args


def test_ignores_output_text_delta():
    event = SimpleNamespace(
        type="raw_response_event",
        data=SimpleNamespace(type="response.output_text.delta", delta="Hello"),
    )
    assert translate_sdk_event(event) == []
