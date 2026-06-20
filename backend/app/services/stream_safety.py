"""Teacher-visible streaming event safety helpers."""

from __future__ import annotations

from dataclasses import dataclass

from app.teacher_agent.stream_events import (
    SseEvent,
    SseReasoningDelta,
    SseToolCall,
    SseToolResult,
)

SAFE_REASONING_STATUS = "Working through the request..."


@dataclass
class StreamSafetyState:
    """Small per-stream state for collapsing raw reasoning deltas."""

    reasoning_status_sent: bool = False


def sanitize_teacher_visible_stream_event(
    event: SseEvent,
    state: StreamSafetyState,
) -> SseEvent | None:
    """Return the production-safe version of a teacher-visible stream event.

    This strips raw reasoning text, tool arguments, and tool outputs. Final
    replies/artifacts are guarded separately by output_safety.
    """

    if isinstance(event, SseReasoningDelta):
        if state.reasoning_status_sent:
            return None
        state.reasoning_status_sent = True
        return SseReasoningDelta(text=SAFE_REASONING_STATUS)

    if isinstance(event, SseToolCall):
        return event.model_copy(update={"args": ""})

    if isinstance(event, SseToolResult):
        return event.model_copy(update={"output": ""})

    return event
