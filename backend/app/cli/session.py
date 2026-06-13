"""In-memory CLI session state (mirrors artifact session chat loop)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.schemas.api import ChatMessage
from app.teacher_agent.agents import AgentRunner
from app.teacher_agent.stream_events import SseError, SseEvent, SseFinal
from app.teacher_agent.wiki_store import WikiStore

CliMode = Literal["ingest", "plan"]


@dataclass
class CliSession:
    mode: CliMode
    class_id: str
    wiki: WikiStore
    agents: AgentRunner
    messages: list[ChatMessage] = field(default_factory=list)
    draft: str = ""
    plan_opening_done: bool = False

    def __post_init__(self) -> None:
        if not self.draft.strip():
            if self.mode == "ingest":
                self.draft = self.wiki.empty_diary_template()
            else:
                self.draft = self.wiki.empty_plan_template()

    def context_pack(self) -> str:
        if self.mode == "ingest":
            return self.wiki.build_ingest_context_slim(self.class_id)
        else:
            return self.wiki.build_plan_context_slim(self.class_id)

    async def ensure_plan_opening(self) -> None:
        if self.mode != "plan" or self.plan_opening_done or self.messages:
            return
        opening = await self.agents.plan_opening(self.class_id)
        self.messages.append(ChatMessage(role="assistant", content=opening))
        self.plan_opening_done = True

    def stream_fn(self):
        if self.mode == "ingest":
            return self.agents.ingest_chat_stream
        return self.agents.plan_chat_stream

    async def run_turn(self, user_message: str) -> tuple[list[SseEvent], SseFinal | None, SseError | None]:
        await self.ensure_plan_opening()
        self.messages.append(ChatMessage(role="user", content=user_message))
        events: list[SseEvent] = []
        final: SseFinal | None = None
        error: SseError | None = None

        async for event in self.stream_fn()(
            self.class_id,
            self.messages,
            self.draft,
        ):
            events.append(event)
            if isinstance(event, SseFinal):
                final = event
            elif isinstance(event, SseError):
                error = event
                break

        if final is not None:
            self.draft = final.artifact_markdown
            self.messages.append(ChatMessage(role="assistant", content=final.reply))
        elif error is not None:
            self.messages.pop()  # remove user message on hard failure

        return events, final, error

    def propose_paths(self) -> list[tuple[str, str]]:
        if self.mode != "ingest":
            return []
        _, proposals = self.wiki.compile_from_diary(self.class_id, self.draft)
        return [(p.wiki_path, p.rationale) for p in proposals]
