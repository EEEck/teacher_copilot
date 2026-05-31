"""SSE event models and OpenAI Agents SDK → wire-format translation."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.api import CompletenessChecklist

_SSE_TRUNCATE = 500


class SseReasoningDelta(BaseModel):
    type: Literal["reasoning_delta"] = "reasoning_delta"
    text: str


class SseToolCall(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    name: str
    args: str = ""
    call_id: str | None = None


class SseToolResult(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    name: str = ""
    output: str = ""
    call_id: str | None = None


class SseFinal(BaseModel):
    type: Literal["final"] = "final"
    reply: str
    artifact_markdown: str
    ready: bool
    completeness: CompletenessChecklist | None = None


class SseError(BaseModel):
    type: Literal["error"] = "error"
    message: str
    code: str | None = None


SseEvent = SseReasoningDelta | SseToolCall | SseToolResult | SseFinal | SseError


def _truncate(value: Any, limit: int = _SSE_TRUNCATE) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def _event_data_type(event: Any) -> str | None:
    data = getattr(event, "data", None)
    if data is None:
        return None
    if isinstance(data, dict):
        return data.get("type")
    return getattr(data, "type", None)


def _event_data_delta(event: Any) -> str:
    data = getattr(event, "data", None)
    if data is None:
        return ""
    if isinstance(data, dict):
        return str(data.get("delta") or "")
    return str(getattr(data, "delta", None) or "")


def _tool_name_from_item(item: Any) -> str:
    if hasattr(item, "tool_name"):
        name = item.tool_name
        if name:
            return str(name)
    raw = getattr(item, "raw_item", None)
    if raw is None:
        return "tool"
    if isinstance(raw, dict):
        return str(raw.get("name") or raw.get("type") or "tool")
    return str(getattr(raw, "name", None) or getattr(raw, "type", None) or "tool")


def _tool_args_from_item(item: Any) -> str:
    raw = getattr(item, "raw_item", None)
    if raw is None:
        return ""
    if isinstance(raw, dict):
        args = raw.get("arguments")
    else:
        args = getattr(raw, "arguments", None)
    if args is None:
        return ""
    return _truncate(args)


def _tool_call_id_from_item(item: Any) -> str | None:
    if hasattr(item, "call_id"):
        cid = item.call_id
        if cid:
            return str(cid)
    raw = getattr(item, "raw_item", None)
    if isinstance(raw, dict):
        cid = raw.get("call_id") or raw.get("id")
    else:
        cid = getattr(raw, "call_id", None) or getattr(raw, "id", None)
    return str(cid) if cid is not None else None


def translate_sdk_event(event: Any) -> list[SseEvent]:
    """Map one Agents SDK StreamEvent to zero or more SSE payloads."""
    event_type = getattr(event, "type", None)

    if event_type == "raw_response_event":
        data_type = _event_data_type(event) or ""
        if "reasoning" in data_type and "delta" in data_type:
            delta = _event_data_delta(event)
            if delta:
                return [SseReasoningDelta(text=delta)]
        return []

    if event_type != "run_item_stream_event":
        return []

    name = getattr(event, "name", None)
    item = getattr(event, "item", None)
    if item is None:
        return []

    if name == "tool_called" or getattr(item, "type", None) == "tool_call_item":
        return [
            SseToolCall(
                name=_tool_name_from_item(item),
                args=_tool_args_from_item(item),
                call_id=_tool_call_id_from_item(item),
            )
        ]

    if name == "tool_output" or getattr(item, "type", None) == "tool_call_output_item":
        output = getattr(item, "output", None)
        return [
            SseToolResult(
                name=_tool_name_from_item(item),
                output=_truncate(output),
                call_id=_tool_call_id_from_item(item),
            )
        ]

    if name == "reasoning_item_created":
        raw = getattr(item, "raw_item", None)
        text = ""
        if raw is not None:
            summary = getattr(raw, "summary", None)
            if summary:
                parts = []
                for block in summary:
                    t = getattr(block, "text", None) if not isinstance(block, dict) else block.get("text")
                    if t:
                        parts.append(str(t))
                text = "\n".join(parts)
        if text.strip():
            return [SseReasoningDelta(text=text)]
        return []

    return []


def sse_encode(event: SseEvent) -> str:
    """Format one SSE data line (caller adds blank line separator)."""
    return f"data: {event.model_dump_json(exclude_none=True)}\n\n"
