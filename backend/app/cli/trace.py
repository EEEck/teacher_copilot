"""Terminal trace formatting and JSONL logging for agent debug CLI."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

from app.teacher_agent.stream_events import (
    SseError,
    SseEvent,
    SseFinal,
    SseReasoningDelta,
    SseToolCall,
    SseToolResult,
)

# ANSI (Windows Terminal / modern consoles)
_DIM = "\033[2m"
_CYAN = "\033[36m"
_GRAY = "\033[90m"
_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_RESET = "\033[0m"


def _supports_color(stream: TextIO) -> bool:
    if not hasattr(stream, "isatty") or not stream.isatty():
        return False
    return True


class TracePrinter:
    def __init__(self, *, verbose: bool = True, stream: TextIO | None = None) -> None:
        self.verbose = verbose
        self.stream = stream or sys.stdout
        self.color = _supports_color(self.stream)
        self._reasoning_buf = ""
        self.last_turn_tools: list[tuple[str, str, str]] = []

    def _c(self, code: str, text: str) -> str:
        if not self.color:
            return text
        return f"{code}{text}{_RESET}"

    def reset_turn_buffers(self) -> None:
        self._reasoning_buf = ""
        self.last_turn_tools = []

    def print_event(self, event: SseEvent) -> None:
        if isinstance(event, SseReasoningDelta):
            if not self.verbose:
                return
            self._reasoning_buf += event.text
            self.stream.write(self._c(_DIM, event.text))
            self.stream.flush()
            return

        if isinstance(event, SseToolCall):
            if self._reasoning_buf:
                self.stream.write("\n")
                self._reasoning_buf = ""
            self.stream.write(
                self._c(_CYAN, f"\n[tool] {event.name}")
                + (f" call_id={event.call_id}" if event.call_id else "")
                + "\n"
            )
            if event.args:
                self.stream.write(self._c(_GRAY, f"  args: {event.args}\n"))
            self.last_turn_tools.append((event.name, event.args, ""))
            self.stream.flush()
            return

        if isinstance(event, SseToolResult):
            self.stream.write(self._c(_GRAY, f"[tool result] {event.name or 'tool'}\n"))
            body = event.output or "(empty)"
            for line in body.splitlines():
                self.stream.write(self._c(_GRAY, f"  {line}\n"))
            if self.last_turn_tools:
                name, args, _ = self.last_turn_tools[-1]
                self.last_turn_tools[-1] = (name, args, body[:200] + "…" if len(body) > 200 else body)
            else:
                self.last_turn_tools.append((event.name or "tool", "", body[:200]))
            self.stream.flush()
            return

        if isinstance(event, SseError):
            if self._reasoning_buf:
                self.stream.write("\n")
            self.stream.write(self._c(_RED, f"\n[error] {event.message}\n"))
            if event.code:
                self.stream.write(self._c(_RED, f"  code: {event.code}\n"))
            self.stream.flush()
            return

        if isinstance(event, SseFinal):
            if self._reasoning_buf:
                self.stream.write("\n")
                self._reasoning_buf = ""
            self.stream.write(self._c(_GREEN, "\n[assistant]\n"))
            for line in event.reply.splitlines():
                self.stream.write(f"  {line}\n")
            draft_len = len(event.artifact_markdown)
            ready = "ready" if event.ready else "not ready"
            comp = ""
            if event.completeness:
                done = sum(1 for i in event.completeness.items if i.complete)
                comp = f", completeness {done}/{len(event.completeness.items)}"
            self.stream.write(
                self._c(
                    _YELLOW,
                    f"\n[draft] {draft_len} chars, {ready}{comp}\n",
                )
            )
            self.stream.flush()
            return

    def print_tools_summary(self) -> None:
        if not self.last_turn_tools:
            self.stream.write("(no tools last turn)\n")
            return
        for name, args, preview in self.last_turn_tools:
            self.stream.write(f"  - {name}")
            if args:
                short = args if len(args) <= 80 else args[:80] + "…"
                self.stream.write(f" ({short})")
            if preview:
                self.stream.write(f" → {preview[:60]}…" if len(preview) > 60 else f" → {preview}")
            self.stream.write("\n")


class JsonlTraceWriter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = path.open("a", encoding="utf-8")
        self._turn = 0

    def start_turn(self) -> int:
        self._turn += 1
        return self._turn

    def write_event(self, event: SseEvent, *, turn: int) -> None:
        payload = event.model_dump(exclude_none=True)
        payload["turn"] = turn
        payload["ts"] = datetime.now(timezone.utc).isoformat()
        self._file.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()


def format_event_line(event: SseEvent) -> str:
    """Single-line summary for tests."""
    if isinstance(event, SseToolCall):
        return f"tool_call:{event.name}"
    if isinstance(event, SseToolResult):
        return f"tool_result:{event.name}:{len(event.output)}"
    if isinstance(event, SseReasoningDelta):
        return f"reasoning:{len(event.text)}"
    if isinstance(event, SseFinal):
        return f"final:ready={event.ready}"
    if isinstance(event, SseError):
        return f"error:{event.code}"
    return "unknown"
