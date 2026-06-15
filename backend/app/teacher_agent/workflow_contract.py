"""Minimal workflow contracts for teacher-facing artifact chats."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from app.schemas.api import ChatAttachment, ChatMessage
from app.teacher_agent.stream_events import SseFinal, SseEvent


@dataclass(frozen=True)
class WorkflowHistoryPolicy:
    """How a workflow places artifact and conversation history in prompts."""

    conversation_turns_setting: str
    artifact_location: str


@dataclass(frozen=True)
class WorkflowTraceContract:
    """Trace sections that must exist for a registered workflow."""

    expected_sections: tuple[str, ...]


class WorkflowRuntimeContract(Protocol):
    """Adapter boundary for workflow-specific runtime state."""

    def __call__(self) -> Any: ...


StreamTurn = Callable[
    [
        Any,
        str,
        list[ChatMessage],
        str,
        list[ChatAttachment],
        Any,
    ],
    AsyncIterator[SseEvent],
]

FinalEventToTurnResult = Callable[[SseFinal], Any]


@dataclass(frozen=True)
class WorkflowContract:
    """Small spec-level contract that prevents mode branching from spreading."""

    history: WorkflowHistoryPolicy
    trace: WorkflowTraceContract
    stream_turn: StreamTurn
    final_event_to_turn_result: FinalEventToTurnResult
