"""ArtifactSpec — the per-mode configuration that the generic ArtifactSessionService runs.

The *artifact session* is the core product pattern: a chat thread continuously
rewrites a markdown **artifact** (diary / plan / future: exam, student report)
that the teacher can edit and approve. Every such mode differs only in a small
set of policies captured here, so adding a new artifact type is "define a spec",
not "fork pages, services, providers, and threads".
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional

from app.schemas.api import (
    ChatAttachment,
    ChatMessage,
    CompletenessChecklist,
    IngestDraft,
    PlanDraft,
)

from app.teacher_agent.memory_update_state import MemoryRuntime, memory_api_payload
from app.teacher_agent.planning_state import PlanRuntime, planning_api_payload
from app.teacher_agent.prompt_trace import (
    build_ingest_chat_prompt_trace,
    build_plan_chat_prompt_trace,
    build_plan_opening_prompt_trace,
)
from app.teacher_agent.wiki_store import dedupe_wiki_proposals
from app.teacher_agent.stream_events import SseEvent, SseFinal
from app.teacher_agent.workflow_contract import (
    FinalEventToTurnResult,
    WorkflowContract,
    WorkflowHistoryPolicy,
    WorkflowTraceContract,
)

if TYPE_CHECKING:  # avoid import cycles; these are only used for typing
    from app.teacher_agent.agents import AgentRunner
    from app.teacher_agent.wiki_store import WikiStore

PromptTraceHook = Callable[
    [
        "WikiStore",
        str,
        list[ChatMessage],
        str,
        Any,
        list[ChatAttachment],
        str,
    ],
    dict,
]


@dataclass(frozen=True)
class TurnResult:
    """Normalized output of one chat turn, independent of artifact type."""

    reply: str
    markdown: str
    ready: bool
    completeness: Optional[CompletenessChecklist] = None
    # Plan mode only: compact runtime state (phase, session/lesson state,
    # memory candidates) for the API response. None for other modes.
    planning: Optional[dict] = None
    # Ingest/update-memory mode only: target/date identification and
    # lesson-results collection state.
    memory: Optional[dict] = None


# Commit strategies (the spec picks one; future artifact types reuse them).
SINGLE_FILE_SAVE = "single_file_save"
PROPOSE_REVIEW_COMMIT = "propose_review_commit"


@dataclass(frozen=True)
class ArtifactSpec:
    mode: str
    chatting_status: str
    ready_status: str
    commit_strategy: str
    empty_template: Callable[["WikiStore"], str]
    readiness: Callable[["WikiStore", str], bool]
    completeness_of: Callable[["WikiStore", str], Optional[CompletenessChecklist]]
    build_draft: Callable[["WikiStore", str, str], object]
    run_turn: Callable[
        [
            "AgentRunner",
            str,
            list[ChatMessage],
            str,
            list[ChatAttachment],
            Any,
        ],
        Awaitable[TurnResult],
    ]
    opening: Optional[Callable[["AgentRunner", str], Awaitable[str]]] = None
    lazy_opening: Optional[Callable[["AgentRunner", str], Awaitable[str]]] = None
    runtime_factory: Optional[Callable[[], Any]] = None
    prompt_trace: Optional[PromptTraceHook] = None
    stream_turn: Optional[
        Callable[
            [
                "AgentRunner",
                str,
                list[ChatMessage],
                str,
                list[ChatAttachment],
                Any,
            ],
            AsyncIterator[SseEvent],
        ]
    ] = None
    final_event_to_turn_result: Optional[FinalEventToTurnResult] = None
    workflow_contract: Optional[WorkflowContract] = None


# --- ingest (lesson diary) -------------------------------------------------


def _ingest_empty(wiki: "WikiStore") -> str:
    return wiki.empty_diary_template()


def _ingest_readiness(wiki: "WikiStore", md: str) -> bool:
    return wiki.is_diary_complete(md)


def _ingest_completeness(wiki: "WikiStore", md: str) -> CompletenessChecklist:
    return wiki.checklist_from_diary(md)


def _ingest_build_draft(wiki: "WikiStore", class_id: str, md: str) -> IngestDraft:
    _, proposals = wiki.compile_from_diary(class_id, md)
    return IngestDraft(
        diary_markdown=md,
        wiki_proposals=dedupe_wiki_proposals(proposals),
        completeness=wiki.checklist_from_diary(md),
    )


async def _ingest_run_turn(
    agents: "AgentRunner",
    class_id: str,
    messages: list[ChatMessage],
    partial: str,
    attachments: list[ChatAttachment],
    planning: Optional[Any] = None,
) -> TurnResult:
    memory = planning if isinstance(planning, MemoryRuntime) else None
    reply, md, checklist, ready = await agents.ingest_chat(
        class_id, messages, partial, attachments=attachments, memory=memory
    )
    payload = memory_api_payload(memory) if memory is not None else None
    return TurnResult(
        reply=reply,
        markdown=md,
        ready=ready,
        completeness=checklist,
        memory=payload,
    )


def _ingest_stream_turn(
    agents: "AgentRunner",
    class_id: str,
    messages: list[ChatMessage],
    partial: str,
    attachments: list[ChatAttachment],
    runtime: Any,
) -> AsyncIterator[SseEvent]:
    return agents.ingest_chat_stream(
        class_id,
        messages,
        partial,
        attachments=attachments,
        memory=runtime if isinstance(runtime, MemoryRuntime) else None,
    )


def _ingest_final_event_to_turn_result(event: SseFinal) -> TurnResult:
    return TurnResult(
        reply=event.reply,
        markdown=event.artifact_markdown,
        ready=event.ready,
        completeness=event.completeness,
        memory=event.memory_state,
    )


def _ingest_prompt_trace(
    wiki: "WikiStore",
    class_id: str,
    messages: list[ChatMessage],
    current_markdown: str,
    runtime: Any,
    attachments: list[ChatAttachment],
    stage: str,
) -> dict:
    return build_ingest_chat_prompt_trace(
        wiki,
        class_id,
        messages=messages,
        current_diary=current_markdown,
        runtime=runtime if isinstance(runtime, MemoryRuntime) else None,
        attachments=attachments,
    )


# --- plan (lesson plan) ----------------------------------------------------


def _plan_empty(wiki: "WikiStore") -> str:
    return wiki.empty_plan_template()


def _plan_readiness(wiki: "WikiStore", md: str) -> bool:
    return wiki.is_plan_ready(md)


def _plan_completeness(wiki: "WikiStore", md: str) -> None:
    return None


def _plan_build_draft(wiki: "WikiStore", class_id: str, md: str) -> PlanDraft:
    return PlanDraft(plan_markdown=md)


async def _plan_run_turn(
    agents: "AgentRunner",
    class_id: str,
    messages: list[ChatMessage],
    partial: str,
    attachments: list[ChatAttachment],
    planning: Optional[PlanRuntime] = None,
) -> TurnResult:
    reply, md, ready = await agents.plan_chat(
        class_id, messages, partial, attachments=attachments, planning=planning
    )
    payload = planning_api_payload(planning) if planning is not None else None
    return TurnResult(
        reply=reply, markdown=md, ready=ready, completeness=None, planning=payload
    )


def _plan_stream_turn(
    agents: "AgentRunner",
    class_id: str,
    messages: list[ChatMessage],
    partial: str,
    attachments: list[ChatAttachment],
    runtime: Any,
) -> AsyncIterator[SseEvent]:
    return agents.plan_chat_stream(
        class_id,
        messages,
        partial,
        attachments=attachments,
        planning=runtime if isinstance(runtime, PlanRuntime) else None,
    )


def _plan_final_event_to_turn_result(event: SseFinal) -> TurnResult:
    return TurnResult(
        reply=event.reply,
        markdown=event.artifact_markdown,
        ready=event.ready,
        completeness=event.completeness,
        planning={
            "phase": event.phase,
            "last_change_summary": event.last_change_summary,
            "session_state": event.session_state,
            "lesson_planning_state": event.lesson_planning_state,
            "memory_candidates": event.memory_candidates or [],
        },
    )


async def _plan_opening(agents: "AgentRunner", class_id: str) -> str:
    return await agents.plan_opening(class_id)


def _plan_prompt_trace(
    wiki: "WikiStore",
    class_id: str,
    messages: list[ChatMessage],
    current_markdown: str,
    runtime: Any,
    attachments: list[ChatAttachment],
    stage: str,
) -> dict:
    if stage == "plan_opening":
        return build_plan_opening_prompt_trace(wiki, class_id)
    return build_plan_chat_prompt_trace(
        wiki,
        class_id,
        messages=messages,
        current_plan=current_markdown,
        runtime=runtime if isinstance(runtime, PlanRuntime) else None,
        attachments=attachments,
    )


INGEST_SPEC = ArtifactSpec(
    mode="ingest",
    chatting_status="chatting",
    ready_status="ready_to_propose",
    commit_strategy=PROPOSE_REVIEW_COMMIT,
    empty_template=_ingest_empty,
    readiness=_ingest_readiness,
    completeness_of=_ingest_completeness,
    build_draft=_ingest_build_draft,
    run_turn=_ingest_run_turn,
    opening=None,
    runtime_factory=MemoryRuntime,
    prompt_trace=_ingest_prompt_trace,
    stream_turn=_ingest_stream_turn,
    final_event_to_turn_result=_ingest_final_event_to_turn_result,
    workflow_contract=WorkflowContract(
        history=WorkflowHistoryPolicy(
            conversation_turns_setting="ingest_history_turns",
            artifact_location="user_input",
        ),
        trace=WorkflowTraceContract(
            expected_sections=(
                "Teacher layer",
                "Active class core",
                "Update Memory task context",
                "Memory target state",
                "Memory session state",
                "Lesson result state",
                "Memory evidence briefs",
            )
        ),
        stream_turn=_ingest_stream_turn,
        final_event_to_turn_result=_ingest_final_event_to_turn_result,
    ),
)

PLAN_SPEC = ArtifactSpec(
    mode="plan",
    chatting_status="chatting",
    ready_status="ready_to_save",
    commit_strategy=SINGLE_FILE_SAVE,
    empty_template=_plan_empty,
    readiness=_plan_readiness,
    completeness_of=_plan_completeness,
    build_draft=_plan_build_draft,
    run_turn=_plan_run_turn,
    opening=None,
    lazy_opening=_plan_opening,
    runtime_factory=PlanRuntime,
    prompt_trace=_plan_prompt_trace,
    stream_turn=_plan_stream_turn,
    final_event_to_turn_result=_plan_final_event_to_turn_result,
    workflow_contract=WorkflowContract(
        history=WorkflowHistoryPolicy(
            conversation_turns_setting="plan_history_turns",
            artifact_location="system_prompt",
        ),
        trace=WorkflowTraceContract(
            expected_sections=(
                "Teacher layer",
                "Active class core",
                "Session state",
                "Lesson planning state",
                "Evidence briefs",
            )
        ),
        stream_turn=_plan_stream_turn,
        final_event_to_turn_result=_plan_final_event_to_turn_result,
    ),
)


def default_specs() -> dict[str, ArtifactSpec]:
    return {INGEST_SPEC.mode: INGEST_SPEC, PLAN_SPEC.mode: PLAN_SPEC}
