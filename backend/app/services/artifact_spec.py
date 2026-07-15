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
    DiscussDraft,
    IngestDraft,
    PlanDraft,
)

from app.teacher_agent.memory_capture import MemoryCandidate
from app.teacher_agent.class_discussion_state import (
    ClassDiscussionRuntime,
    ClassDiscussionState,
    discussion_api_payload,
)
from app.teacher_agent.memory_update_state import (
    LessonResultState,
    MemoryEvidenceBrief,
    MemoryRuntime,
    MemorySessionState,
    MemoryTargetState,
    memory_api_payload,
)
from app.teacher_agent.executive_verification import (
    ExecutiveRuntime,
    executive_api_payload,
)
from app.teacher_agent.planning_state import (
    EvidenceBrief,
    LessonPlanningState,
    PlanRuntime,
    SessionState,
    planning_api_payload,
)
from app.teacher_agent.prompt_trace import (
    build_ingest_chat_prompt_trace,
    build_plan_chat_prompt_trace,
    build_plan_opening_prompt_trace,
)
from app.teacher_agent.prompt_assembly import build_class_discussion_prompt_assembly
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
        ExecutiveRuntime,
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
    # Discuss mode only: discussion runtime payload.
    discussion: Optional[dict] = None
    executive: Optional[dict] = None


# Commit strategies (the spec picks one; future artifact types reuse them).
SINGLE_FILE_SAVE = "single_file_save"
PROPOSE_REVIEW_COMMIT = "propose_review_commit"
NO_COMMIT = "no_commit"


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
            ExecutiveRuntime,
        ],
        Awaitable[TurnResult],
    ]
    opening: Optional[Callable[["AgentRunner", str], Awaitable[str]]] = None
    lazy_opening: Optional[Callable[["AgentRunner", str], Awaitable[str]]] = None
    runtime_factory: Optional[Callable[[], Any]] = None
    runtime_dump: Optional[Callable[[Any], dict]] = None
    runtime_load: Optional[Callable[[dict], Any]] = None
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
                ExecutiveRuntime,
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
    executive: ExecutiveRuntime | None = None,
) -> TurnResult:
    memory = planning if isinstance(planning, MemoryRuntime) else None
    reply, md, checklist, ready = await agents.ingest_chat(
        class_id,
        messages,
        partial,
        attachments=attachments,
        memory=memory,
        executive=executive,
    )
    payload = memory_api_payload(memory) if memory is not None else None
    return TurnResult(
        reply=reply,
        markdown=md,
        ready=ready,
        completeness=checklist,
        memory=payload,
        executive=executive_api_payload(executive) if executive else None,
    )


def _ingest_stream_turn(
    agents: "AgentRunner",
    class_id: str,
    messages: list[ChatMessage],
    partial: str,
    attachments: list[ChatAttachment],
    runtime: Any,
    executive: ExecutiveRuntime,
) -> AsyncIterator[SseEvent]:
    return agents.ingest_chat_stream(
        class_id,
        messages,
        partial,
        attachments=attachments,
        memory=runtime if isinstance(runtime, MemoryRuntime) else None,
        executive=executive,
    )


def _ingest_final_event_to_turn_result(event: SseFinal) -> TurnResult:
    return TurnResult(
        reply=event.reply,
        markdown=event.artifact_markdown,
        ready=event.ready,
        completeness=event.completeness,
        memory=event.memory_state,
        executive=event.executive_state,
    )


def _ingest_prompt_trace(
    wiki: "WikiStore",
    class_id: str,
    messages: list[ChatMessage],
    current_markdown: str,
    runtime: Any,
    executive: ExecutiveRuntime,
    attachments: list[ChatAttachment],
    stage: str,
) -> dict:
    return build_ingest_chat_prompt_trace(
        wiki,
        class_id,
        messages=messages,
        current_diary=current_markdown,
        runtime=runtime if isinstance(runtime, MemoryRuntime) else None,
        executive=executive,
        attachments=attachments,
    )


def _memory_runtime_dump(runtime: Any) -> dict:
    if not isinstance(runtime, MemoryRuntime):
        return {}
    return {
        "target": runtime.target.model_dump(),
        "session_state": runtime.session_state.model_dump(),
        "lesson_result_state": runtime.lesson_result_state.model_dump(),
        "evidence_briefs": [brief.model_dump() for brief in runtime.evidence_briefs],
        "memory_candidates": [candidate.model_dump() for candidate in runtime.memory_candidates],
        "raw_store": dict(runtime.raw_store),
        "diary_version": runtime.diary_version,
        "last_change_summary": runtime.last_change_summary,
        "unsupported_intent_reason": runtime.unsupported_intent_reason,
        "raw_counter": runtime._raw_counter,
    }


def _memory_runtime_load(data: dict) -> MemoryRuntime:
    runtime = MemoryRuntime()
    if not isinstance(data, dict):
        return runtime
    runtime.target = MemoryTargetState(**_dict_field(data, "target"))
    runtime.session_state = MemorySessionState(**_dict_field(data, "session_state"))
    runtime.lesson_result_state = LessonResultState(**_dict_field(data, "lesson_result_state"))
    runtime.evidence_briefs = [
        MemoryEvidenceBrief(**item)
        for item in _list_dict_field(data, "evidence_briefs")
    ]
    runtime.memory_candidates = [
        MemoryCandidate(**item) for item in _list_dict_field(data, "memory_candidates")
    ]
    runtime.raw_store = {
        str(key): str(value)
        for key, value in _dict_field(data, "raw_store").items()
    }
    runtime.diary_version = int(data.get("diary_version") or 0)
    runtime.last_change_summary = str(data.get("last_change_summary") or "")
    runtime.unsupported_intent_reason = str(data.get("unsupported_intent_reason") or "")
    runtime._raw_counter = int(data.get("raw_counter") or 0)
    return runtime


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
    executive: ExecutiveRuntime | None = None,
) -> TurnResult:
    reply, md, ready = await agents.plan_chat(
        class_id,
        messages,
        partial,
        attachments=attachments,
        planning=planning,
        executive=executive,
    )
    payload = planning_api_payload(planning) if planning is not None else None
    return TurnResult(
        reply=reply,
        markdown=md,
        ready=ready,
        completeness=None,
        planning=payload,
        executive=executive_api_payload(executive) if executive else None,
    )


def _plan_stream_turn(
    agents: "AgentRunner",
    class_id: str,
    messages: list[ChatMessage],
    partial: str,
    attachments: list[ChatAttachment],
    runtime: Any,
    executive: ExecutiveRuntime,
) -> AsyncIterator[SseEvent]:
    return agents.plan_chat_stream(
        class_id,
        messages,
        partial,
        attachments=attachments,
        planning=runtime if isinstance(runtime, PlanRuntime) else None,
        executive=executive,
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
        executive=event.executive_state,
    )


async def _plan_opening(agents: "AgentRunner", class_id: str) -> str:
    return await agents.plan_opening(class_id)


def _plan_prompt_trace(
    wiki: "WikiStore",
    class_id: str,
    messages: list[ChatMessage],
    current_markdown: str,
    runtime: Any,
    executive: ExecutiveRuntime,
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
        executive=executive,
        attachments=attachments,
    )


def _plan_runtime_dump(runtime: Any) -> dict:
    if not isinstance(runtime, PlanRuntime):
        return {}
    return {
        "session_state": runtime.session_state.model_dump(),
        "lesson_planning_state": runtime.lesson_planning_state.model_dump(),
        "evidence_briefs": [brief.model_dump() for brief in runtime.evidence_briefs],
        "raw_store": dict(runtime.raw_store),
        "memory_candidates": [candidate.model_dump() for candidate in runtime.memory_candidates],
        "plan_version": runtime.plan_version,
        "last_change_summary": runtime.last_change_summary,
        "raw_counter": runtime._raw_counter,
    }


def _plan_runtime_load(data: dict) -> PlanRuntime:
    runtime = PlanRuntime()
    if not isinstance(data, dict):
        return runtime
    runtime.session_state = SessionState(**_dict_field(data, "session_state"))
    runtime.lesson_planning_state = LessonPlanningState(
        **_dict_field(data, "lesson_planning_state")
    )
    runtime.evidence_briefs = [
        EvidenceBrief(**item) for item in _list_dict_field(data, "evidence_briefs")
    ]
    runtime.raw_store = {
        str(key): str(value)
        for key, value in _dict_field(data, "raw_store").items()
    }
    runtime.memory_candidates = [
        MemoryCandidate(**item) for item in _list_dict_field(data, "memory_candidates")
    ]
    runtime.plan_version = int(data.get("plan_version") or 0)
    runtime.last_change_summary = str(data.get("last_change_summary") or "")
    runtime._raw_counter = int(data.get("raw_counter") or 0)
    return runtime


def _dict_field(data: dict, key: str) -> dict:
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def _list_dict_field(data: dict, key: str) -> list[dict]:
    value = data.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


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
    runtime_dump=_memory_runtime_dump,
    runtime_load=_memory_runtime_load,
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
                "Executive state",
                "Memory target state",
                "Memory session state",
                "Lesson result state",
                "Memory evidence briefs",
                "Memory candidates",
            )
        ),
        stream_turn=_ingest_stream_turn,
        final_event_to_turn_result=_ingest_final_event_to_turn_result,
        executive_verification=True,
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
    runtime_dump=_plan_runtime_dump,
    runtime_load=_plan_runtime_load,
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
                "Executive state",
                "Session state",
                "Lesson planning state",
                "Evidence briefs",
            )
        ),
        stream_turn=_plan_stream_turn,
        final_event_to_turn_result=_plan_final_event_to_turn_result,
        executive_verification=True,
    ),
)


# --- discuss (read-only class state chat) ----------------------------------


def _discuss_empty(wiki: "WikiStore") -> str:
    return ""


def _discuss_readiness(wiki: "WikiStore", md: str) -> bool:
    return False


def _discuss_completeness(wiki: "WikiStore", md: str) -> None:
    return None


def _discuss_build_draft(wiki: "WikiStore", class_id: str, md: str) -> DiscussDraft:
    return DiscussDraft()


async def _discuss_run_turn(
    agents: "AgentRunner",
    class_id: str,
    messages: list[ChatMessage],
    partial: str,
    attachments: list[ChatAttachment],
    planning: Optional[Any] = None,
    executive: ExecutiveRuntime | None = None,
) -> TurnResult:
    runtime = planning if isinstance(planning, ClassDiscussionRuntime) else None
    reply = await agents.discuss_chat(
        class_id,
        messages,
        attachments=attachments,
        runtime=runtime,
        executive=executive,
    )
    payload = discussion_api_payload(runtime) if runtime is not None else None
    return TurnResult(
        reply=reply,
        markdown="",
        ready=False,
        completeness=None,
        discussion=payload,
        executive=executive_api_payload(executive) if executive else None,
    )


def _discuss_stream_turn(
    agents: "AgentRunner",
    class_id: str,
    messages: list[ChatMessage],
    partial: str,
    attachments: list[ChatAttachment],
    runtime: Any,
    executive: ExecutiveRuntime,
) -> AsyncIterator[SseEvent]:
    return agents.discuss_chat_stream(
        class_id,
        messages,
        attachments=attachments,
        runtime=runtime if isinstance(runtime, ClassDiscussionRuntime) else None,
        executive=executive,
    )


def _discuss_final_event_to_turn_result(event: SseFinal) -> TurnResult:
    return TurnResult(
        reply=event.reply,
        markdown="",
        ready=False,
        completeness=None,
        discussion=event.discussion_state,
        executive=event.executive_state,
    )


def _discuss_prompt_trace(
    wiki: "WikiStore",
    class_id: str,
    messages: list[ChatMessage],
    current_markdown: str,
    runtime: Any,
    executive: ExecutiveRuntime,
    attachments: list[ChatAttachment],
    stage: str,
) -> dict:
    return build_class_discussion_prompt_assembly(
        wiki,
        class_id,
        messages=messages,
        runtime=runtime if isinstance(runtime, ClassDiscussionRuntime) else None,
        executive=executive,
    )


def _discuss_runtime_dump(runtime: Any) -> dict:
    if not isinstance(runtime, ClassDiscussionRuntime):
        return {}
    return {
        "discussion_state": runtime.discussion_state.model_dump(),
        "evidence_briefs": [brief.model_dump() for brief in runtime.evidence_briefs],
        "raw_store": dict(runtime.raw_store),
        "memory_candidates": [
            candidate.model_dump() for candidate in runtime.memory_candidates
        ],
        "counters": dict(runtime.counters),
        "last_source_paths": list(runtime.last_source_paths),
        "last_suggested_actions": list(runtime.last_suggested_actions),
    }


def _discuss_runtime_load(data: dict) -> ClassDiscussionRuntime:
    runtime = ClassDiscussionRuntime()
    if not isinstance(data, dict):
        return runtime
    runtime.discussion_state = ClassDiscussionState(
        **_dict_field(data, "discussion_state")
    )
    runtime.evidence_briefs = [
        EvidenceBrief(**item) for item in _list_dict_field(data, "evidence_briefs")
    ]
    runtime.raw_store = {
        str(key): str(value) for key, value in _dict_field(data, "raw_store").items()
    }
    runtime.memory_candidates = [
        MemoryCandidate(**item) for item in _list_dict_field(data, "memory_candidates")
    ]
    runtime.counters = {
        str(key): int(value) for key, value in _dict_field(data, "counters").items()
    }
    runtime.last_source_paths = [
        str(item) for item in data.get("last_source_paths") or [] if str(item).strip()
    ]
    runtime.last_suggested_actions = [
        str(item)
        for item in data.get("last_suggested_actions") or []
        if str(item).strip()
    ]
    return runtime


DISCUSS_SPEC = ArtifactSpec(
    mode="discuss",
    chatting_status="chatting",
    ready_status="chatting",
    commit_strategy=NO_COMMIT,
    empty_template=_discuss_empty,
    readiness=_discuss_readiness,
    completeness_of=_discuss_completeness,
    build_draft=_discuss_build_draft,
    run_turn=_discuss_run_turn,
    opening=None,
    runtime_factory=ClassDiscussionRuntime,
    runtime_dump=_discuss_runtime_dump,
    runtime_load=_discuss_runtime_load,
    prompt_trace=_discuss_prompt_trace,
    stream_turn=_discuss_stream_turn,
    final_event_to_turn_result=_discuss_final_event_to_turn_result,
    workflow_contract=WorkflowContract(
        history=WorkflowHistoryPolicy(
            conversation_turns_setting="plan_history_turns",
            artifact_location="user_input",
        ),
        trace=WorkflowTraceContract(
            expected_sections=(
                "Teacher layer",
                "Active class core",
                "Executive state",
                "Class discussion state",
                "Evidence briefs",
                "Memory candidates",
            )
        ),
        stream_turn=_discuss_stream_turn,
        final_event_to_turn_result=_discuss_final_event_to_turn_result,
        executive_verification=True,
    ),
)


def default_specs() -> dict[str, ArtifactSpec]:
    return {
        INGEST_SPEC.mode: INGEST_SPEC,
        PLAN_SPEC.mode: PLAN_SPEC,
        DISCUSS_SPEC.mode: DISCUSS_SPEC,
    }
