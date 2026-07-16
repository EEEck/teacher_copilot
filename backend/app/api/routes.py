from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.deps import (
    get_agents,
    get_beta_auth_service,
    get_class_brief_service,
    get_discussion_service,
    get_ingest_service,
    get_memory_candidate_ledger,
    get_memory_sweep_review_store,
    get_plan_service,
    get_request_identity,
    get_workflow_draft_store,
    get_wiki,
)
from app.config import get_settings
from app.openai_bootstrap import is_openai_configured
from app.schemas.api import (
    ActiveWorkItem,
    ActiveWorkResponse,
    BetaIdentityResponse,
    BetaLoginRequest,
    ChatRequest,
    ChatResponse,
    ClassesResponse,
    ClassBriefResponse,
    ClassMemorySnapshot,
    ClassTimeline,
    CommitIngestRequest,
    CommitIngestResponse,
    DiscussChatRequest,
    DiscussChatResponse,
    DiscussDraft,
    DiscussSession,
    DiscussTraceResponse,
    HealthResponse,
    IngestDraft,
    IngestSession,
    IngestSessionStartRequest,
    LessonDetail,
    LessonPlan,
    MemoryApplyRequest,
    MemoryApplyResponse,
    MemoryCandidateStatusRequest,
    MemoryCandidateStatusResponse,
    MemoryCompactApplyRequest,
    MemoryCompactRequest,
    MemoryCompactResponse,
    MemoryProposalResponse,
    MemorySweepApplyRequest,
    MemorySweepApplyResponse,
    MemorySweepCandidate,
    MemorySweepProposalResponse,
    MemorySweepReviewOpenRequest,
    MemorySweepReviewPatchRequest,
    MemorySweepReviewResponse,
    MemoryTraceResponse,
    PlanChatRequest,
    PlanChatResponse,
    PlanDraft,
    PlanLessonRequest,
    PlanSession,
    PlanTraceResponse,
    ProfileProposalRequest,
    ProfileProposalResponse,
    ReviseLessonRequest,
    ReviseLessonResponse,
    SavePlanRequest,
    SavePlanResponse,
    UpdateDraftRequest,
    UpdatePlanDraftRequest,
    WriteVerificationBlockedResponse,
    WikiFileResponse,
    WikiLintResponse,
    WikiPageSummary,
    WikiPagesResponse,
)
from app.services.beta import BetaAuthService, RequestIdentity
from app.services.class_brief_service import ClassBriefService
from app.services.discussion_service import DiscussionService
from app.services.ingest_service import IngestService
from app.services.memory_skills import (
    apply_curated_memory,
    apply_curated_sweep_decisions,
)
from app.services.memory_candidate_ledger import MemoryCandidateLedger, OPEN_STATUSES
from app.services.memory_sweep import (
    is_synthetic_student_summary_candidate_id,
    propose_memory_sweep_review,
    synthetic_student_summary_candidate_ids,
)
from app.services.memory_sweep_reviews import (
    MemorySweepReviewRecord,
    MemorySweepReviewStore,
    build_memory_sweep_source_snapshot,
    memory_sweep_source_fingerprint,
    memory_sweep_stale_reasons,
)
from app.services.memory_gate import expire_stale_candidates
from app.services.plan_service import PlanService
from app.services.workflow_drafts import WorkflowDraftStore
from app.teacher_agent.agents import AgentRunner
from app.teacher_agent.memory_targets import canonical_memory_target, compact_key_for_target
from app.teacher_agent.stream_events import SseError, sse_encode
from app.teacher_agent.executive_verification import (
    WriteVerificationBlocked,
    executive_api_payload,
)
from app.teacher_agent.wiki_store import WikiStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

_COPILOT_PROFILE_LABELS = {
    "avoid",
    "copilot",
    "copilot profile",
    "copilot working agreement",
    "planning pattern",
    "planning patterns",
    "practice task",
    "practice tasks",
}
_TEACHER_PROFILE_LABELS = {
    "communication",
    "lesson style",
    "teacher",
    "teacher profile",
}


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _memory_sweep_api_queues(grouped_cards) -> dict[str, list[MemorySweepCandidate]]:
    return {
        queue: [MemorySweepCandidate(**card.__dict__) for card in cards]
        for queue, cards in grouped_cards.items()
    }


def _memory_sweep_review_response(
    record: MemorySweepReviewRecord | None,
    *,
    class_id: str,
    is_stale: bool = False,
    stale_reasons: list[str] | None = None,
) -> MemorySweepReviewResponse:
    if record is None:
        return MemorySweepReviewResponse(class_id=class_id, status="none")
    proposals = record.proposals or {}
    decisions = [
        decision
        for decision in MemorySweepApplyRequest(decisions=record.decisions).decisions
    ]
    return MemorySweepReviewResponse(
        review_id=record.review_id,
        class_id=record.class_id,
        status=record.status,
        source_fingerprint=record.source_fingerprint,
        generated_at=record.generated_at,
        updated_at=record.updated_at,
        completed_at=record.completed_at,
        is_stale=is_stale or record.status == "stale",
        stale_reasons=stale_reasons or [],
        has_teacher_edits=record.has_teacher_edits,
        queues={
            queue: [MemorySweepCandidate(**card) for card in cards]
            for queue, cards in (proposals.get("queues") or {}).items()
        },
        decisions=decisions,
        warnings=list(proposals.get("warnings") or []),
        error=record.error,
    )


def _memory_sweep_status_for_action(action: str) -> str | None:
    return {
        "apply": "applied",
        "already_covered": "applied",
        "reject": "rejected",
        "snooze": "snoozed",
        "delete": "deleted",
    }.get(action)


def _resolve_memory_sweep_statuses(body: MemorySweepApplyRequest) -> dict[str, str]:
    priority = {
        "applied": 4,
        "rejected": 3,
        "snoozed": 2,
        "deleted": 1,
    }
    resolved: dict[str, str] = {}
    for decision in body.decisions:
        status = _memory_sweep_status_for_action(decision.action)
        if not status:
            continue
        for candidate_id in decision.candidate_ids:
            current = resolved.get(candidate_id)
            if current is None or priority[status] > priority[current]:
                resolved[candidate_id] = status
    return resolved


def _read_wiki_rel(wiki: WikiStore, rel_path: str) -> str:
    try:
        return wiki.read_text(wiki.resolve_path(rel_path))
    except FileNotFoundError:
        return ""


def _memory_apply_candidate_paths(wiki: WikiStore, class_id: str, items) -> list[str]:
    paths: list[str] = []
    cls = wiki.get_class(class_id)
    subject_target = f"wiki/subjects/{cls.subject}.md"
    for item in items:
        target = canonical_memory_target(item.target)
        compact_key = compact_key_for_target(target)
        rel = ""
        if target == "teacher_profile.md":
            rel = "wiki/teacher_profile.md"
        elif target == "copilot_profile.md":
            rel = wiki.rel_wiki(wiki.memory_paths(class_id)["copilot_profile"])
        elif compact_key:
            rel = wiki.rel_wiki(wiki.memory_paths(class_id)[compact_key])
        elif target == subject_target:
            rel = subject_target
        if rel and rel not in paths:
            paths.append(rel)
    return paths


def _apply_memory_sweep_decision_batch(
    *,
    class_id: str,
    body: MemorySweepApplyRequest,
    request: Request,
    wiki: WikiStore,
    ledger: MemoryCandidateLedger,
    beta_auth: BetaAuthService,
) -> MemorySweepApplyResponse:
    try:
        cls = wiki.get_class(class_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    if not body.decisions:
        raise HTTPException(
            status_code=400, detail="No Memory Sweep decisions provided"
        )

    open_rows = ledger.list_candidates(
        class_id=class_id,
        subject=cls.subject,
        statuses=OPEN_STATUSES,
        include_global=True,
    )
    open_ids = {row.id for row in open_rows}
    synthetic_ids = synthetic_student_summary_candidate_ids(wiki, class_id)
    requested_ids = {
        candidate_id
        for decision in body.decisions
        for candidate_id in decision.candidate_ids
    }
    unknown_ids = sorted(requested_ids - open_ids - synthetic_ids)
    if unknown_ids:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown or closed Memory Sweep candidate ids: {', '.join(unknown_ids)}",
        )

    applied: list[str] = []
    skipped: list[str] = []
    warnings: list[str] = []
    successful_apply_indexes: list[int] = []
    candidate_paths = _memory_apply_candidate_paths(wiki, class_id, body.decisions)
    before_by_path = {path: _read_wiki_rel(wiki, path) for path in candidate_paths}
    if any(decision.action == "apply" for decision in body.decisions):
        applied, skipped, warnings, successful_apply_indexes = (
            apply_curated_sweep_decisions(wiki, class_id, body.decisions)
        )
        _record_beta_wiki_diff(
            request,
            beta_auth,
            wiki,
            class_id=class_id,
            app_session_id=None,
            mode="memory",
            action="memory_sweep_apply",
            before_by_path=before_by_path,
            changed_paths=applied,
            metadata={"review_batch_id": body.review_batch_id, "skipped": skipped},
        )

    successful_apply_index_set = set(successful_apply_indexes)
    applied_decisions = [
        decision
        for index, decision in enumerate(body.decisions)
        if decision.action == "apply" and index in successful_apply_index_set
    ]
    effective_body = MemorySweepApplyRequest(
        decisions=[
            *applied_decisions,
            *[decision for decision in body.decisions if decision.action != "apply"],
        ],
        review_batch_id=body.review_batch_id,
    )
    statuses = _resolve_memory_sweep_statuses(effective_body)
    now = _utc_now()
    review_batch_id = body.review_batch_id or f"memory_sweep_{now}"
    updated_ids: list[str] = []
    try:
        for candidate_id, status in statuses.items():
            if is_synthetic_student_summary_candidate_id(candidate_id):
                continue
            rejection_reason = None
            for decision in body.decisions:
                if candidate_id in decision.candidate_ids and decision.rejection_reason:
                    rejection_reason = decision.rejection_reason
                    break
            ledger.update_status(
                candidate_id,
                status,
                updated_at=now,
                rejection_reason=rejection_reason,
                review_batch_id=review_batch_id,
                promoted_at=now if status in {"approved", "applied"} else None,
            )
            updated_ids.append(candidate_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return MemorySweepApplyResponse(
        class_id=class_id,
        applied_wiki_paths=applied,
        updated_candidate_ids=updated_ids,
        skipped=skipped,
        warnings=warnings,
    )


def _record_beta_wiki_diff(
    request: Request,
    beta_auth: BetaAuthService,
    wiki: WikiStore,
    *,
    class_id: str,
    app_session_id: str | None,
    mode: str,
    action: str,
    before_by_path: dict[str, str],
    changed_paths: list[str],
    metadata: dict | None = None,
) -> None:
    identity = getattr(request.state, "identity", None)
    if identity is None or getattr(identity, "workspace_id", "local") == "local":
        return
    changed_files = [
        (path, before_by_path.get(path, ""), _read_wiki_rel(wiki, path))
        for path in changed_paths
    ]
    beta_auth.telemetry.record_wiki_commit(
        identity,
        app_session_id=app_session_id,
        class_id=class_id,
        mode=mode,
        action=action,
        changed_files=changed_files,
        metadata=metadata,
    )


def _record_beta_app_session(
    request: Request,
    beta_auth: BetaAuthService,
    *,
    app_session_id: str,
    class_id: str,
    mode: str,
    status: str,
) -> None:
    identity = getattr(request.state, "identity", None)
    if identity is None or getattr(identity, "workspace_id", "local") == "local":
        return
    beta_auth.telemetry.record_app_session(
        identity,
        app_session_id=app_session_id,
        class_id=class_id,
        mode=mode,
        status=status,
    )


def _record_beta_event(
    request: Request,
    beta_auth: BetaAuthService,
    *,
    event_type: str,
    class_id: str,
    app_session_id: str | None,
    mode: str,
    payload: dict | None = None,
) -> None:
    identity = getattr(request.state, "identity", None)
    if identity is None or getattr(identity, "workspace_id", "local") == "local":
        return
    beta_auth.telemetry.record_event(
        identity,
        event_type=event_type,
        class_id=class_id,
        app_session_id=app_session_id,
        mode=mode,
        payload=payload,
    )


def _record_beta_artifact_snapshot(
    request: Request,
    beta_auth: BetaAuthService,
    *,
    app_session_id: str,
    class_id: str,
    mode: str,
    artifact_kind: str,
    markdown: str,
) -> None:
    identity = getattr(request.state, "identity", None)
    if identity is None or getattr(identity, "workspace_id", "local") == "local":
        return
    beta_auth.telemetry.record_artifact_snapshot(
        identity,
        app_session_id=app_session_id,
        class_id=class_id,
        mode=mode,
        artifact_kind=artifact_kind,
        markdown=markdown,
    )


def _record_beta_message(
    request: Request,
    beta_auth: BetaAuthService,
    *,
    app_session_id: str,
    class_id: str,
    mode: str,
    role: str,
    content: str,
) -> None:
    identity = getattr(request.state, "identity", None)
    if identity is None or getattr(identity, "workspace_id", "local") == "local":
        return
    beta_auth.telemetry.record_message(
        identity,
        app_session_id=app_session_id,
        class_id=class_id,
        mode=mode,
        role=role,
        content=content,
    )


def _sse_payload_of_type(line: str, event_type: str) -> dict | None:
    if not line.startswith("data:"):
        return None
    try:
        payload = json.loads(line.removeprefix("data:").strip())
    except json.JSONDecodeError:
        return None
    if payload.get("type") != event_type:
        return None
    return payload


def _sse_final_payload(line: str) -> dict | None:
    return _sse_payload_of_type(line, "final")


def _raise_workflow_value_error(exc: ValueError, *, default_status: int) -> None:
    if str(exc) == "draft_changed_since_review_created":
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    raise HTTPException(status_code=default_status, detail=str(exc)) from exc


async def _stream_chat_with_beta_telemetry(
    stream: AsyncIterator[str],
    *,
    request: Request,
    beta_auth: BetaAuthService,
    session_id: str,
    class_id: str,
    mode: str,
    artifact_kind: str,
    completed_payload: Callable[[dict], dict],
) -> AsyncIterator[str]:
    """Pass SSE lines through while recording beta chat-turn telemetry.

    Every turn ends in exactly one terminal event: chat_turn_completed on the
    final payload, otherwise chat_turn_failed (agent error line, mid-stream
    exception, or a stream that ends without a final). Exceptions are turned
    into an SSE error line so the client shows a retryable error instead of a
    silently dropped turn.
    """

    def _record_failed(payload: dict) -> None:
        _record_beta_event(
            request,
            beta_auth,
            event_type="chat_turn_failed",
            class_id=class_id,
            app_session_id=session_id,
            mode=mode,
            payload={**payload, "stream": True},
        )

    terminal_seen = False
    try:
        async for line in stream:
            final = _sse_final_payload(line)
            if final is not None:
                terminal_seen = True
                _record_beta_message(
                    request,
                    beta_auth,
                    app_session_id=session_id,
                    class_id=class_id,
                    mode=mode,
                    role="assistant",
                    content=final.get("reply", ""),
                )
                _record_beta_artifact_snapshot(
                    request,
                    beta_auth,
                    app_session_id=session_id,
                    class_id=class_id,
                    mode=mode,
                    artifact_kind=artifact_kind,
                    markdown=final.get("artifact_markdown", ""),
                )
                _record_beta_event(
                    request,
                    beta_auth,
                    event_type="chat_turn_completed",
                    class_id=class_id,
                    app_session_id=session_id,
                    mode=mode,
                    payload=completed_payload(final),
                )
            else:
                error = _sse_payload_of_type(line, "error")
                if error is not None:
                    terminal_seen = True
                    _record_failed(
                        {
                            "reason": "agent_error",
                            "code": error.get("code"),
                            "message": (error.get("message") or "")[:300],
                        }
                    )
            yield line
    except Exception as e:  # noqa: BLE001 — turn any stream crash into a client-visible error
        logger.exception("Chat stream failed (mode=%s, session=%s)", mode, session_id)
        _record_failed({"reason": "exception", "error": str(e)[:300]})
        yield sse_encode(
            SseError(
                message="Something went wrong while generating the reply. Please send your message again.",
                code="stream_error",
            )
        )
        return
    if not terminal_seen:
        _record_failed({"reason": "no_final_event"})


def _compact_page_paths(
    wiki: WikiStore, class_id: str, pages: dict[str, str]
) -> list[str]:
    memory_paths = wiki.memory_paths(class_id)
    paths: list[str] = []
    for key in pages:
        if key not in memory_paths:
            continue
        rel = wiki.rel_wiki(memory_paths[key])
        if rel not in paths:
            paths.append(rel)
    return paths


def _normalize_profile_candidate_target(target: str) -> str:
    normalized = canonical_memory_target(target)
    if normalized in {
        "teacher_profile.md",
        "copilot_profile.md",
        "planning_brief.md",
        "teaching_patterns.md",
    } or normalized.startswith("wiki/subjects/"):
        return normalized
    label = " ".join((target or "").strip().lower().replace("_", " ").split())
    if label in _TEACHER_PROFILE_LABELS:
        return "teacher_profile.md"
    if label in _COPILOT_PROFILE_LABELS:
        return "copilot_profile.md"
    return "copilot_profile.md"


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        agent_max_turns=settings.agent_max_turns,
        openai_configured=is_openai_configured(settings),
    )


@router.post("/beta/login", response_model=BetaIdentityResponse)
def beta_login(
    body: BetaLoginRequest,
    response: Response,
    beta_auth: BetaAuthService = Depends(get_beta_auth_service),
) -> BetaIdentityResponse:
    login = beta_auth.login(body.invite_code)
    if login is None:
        raise HTTPException(status_code=401, detail="Invalid invite code")
    response.set_cookie(
        beta_auth.cookie_name,
        login.session_token,
        max_age=beta_auth.session_days * 24 * 60 * 60,
        httponly=True,
        secure=beta_auth.cookie_secure,
        samesite="lax",
        path="/",
    )
    return BetaIdentityResponse(
        tester_id=login.tester_id,
        workspace_id=login.workspace_id,
        role=login.role,
    )


@router.post("/beta/logout")
def beta_logout(
    request: Request,
    response: Response,
    beta_auth: BetaAuthService = Depends(get_beta_auth_service),
) -> dict[str, str]:
    token = request.cookies.get(beta_auth.cookie_name)
    if token:
        beta_auth.revoke_session_token(token)
    response.delete_cookie(beta_auth.cookie_name, path="/")
    return {"status": "ok"}


@router.get("/beta/me", response_model=BetaIdentityResponse)
def beta_me(
    request: Request,
    beta_auth: BetaAuthService = Depends(get_beta_auth_service),
) -> BetaIdentityResponse:
    token = request.cookies.get(beta_auth.cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Beta login required")
    try:
        identity = beta_auth.resolve_session_token(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    return BetaIdentityResponse(
        tester_id=identity.tester_id,
        workspace_id=identity.workspace_id,
        role=identity.role,
    )


@router.get("/classes", response_model=ClassesResponse)
def list_classes(wiki: WikiStore = Depends(get_wiki)) -> ClassesResponse:
    return ClassesResponse(classes=wiki.list_classes())


@router.get("/workflow/active", response_model=ActiveWorkResponse)
def list_active_work(
    identity: RequestIdentity = Depends(get_request_identity),
    workflow_drafts: WorkflowDraftStore = Depends(get_workflow_draft_store),
    memory_sweep_reviews: MemorySweepReviewStore = Depends(
        get_memory_sweep_review_store
    ),
) -> ActiveWorkResponse:
    """Jobs running right now for this workspace, across every class.

    The single source of truth for the Running-tasks box and completion
    toasts: the frontend asks what is running instead of keeping its own
    sessionStorage markers.
    """
    items: list[ActiveWorkItem] = [
        ActiveWorkItem(
            kind="draft_turn",
            class_id=draft.class_id,
            mode=draft.mode,
            draft_id=draft.draft_id,
            session_id=draft.backend_session_id,
            lesson_date=draft.lesson_date,
            lesson_title=draft.lesson_title,
            updated_at=draft.updated_at,
        )
        for draft in workflow_drafts.list_in_progress(
            workspace_id=identity.workspace_id
        )
    ]
    items.extend(
        ActiveWorkItem(
            kind="memory_sweep",
            class_id=review.class_id,
            review_id=review.review_id,
            updated_at=review.updated_at,
        )
        for review in memory_sweep_reviews.list_generating(
            workspace_id=identity.workspace_id
        )
    )
    return ActiveWorkResponse(items=items)


@router.get("/classes/{class_id}/timeline", response_model=ClassTimeline)
def get_timeline(
    class_id: str,
    wiki: WikiStore = Depends(get_wiki),
    workflow_drafts: WorkflowDraftStore = Depends(get_workflow_draft_store),
) -> ClassTimeline:
    try:
        wiki.get_class(class_id)
        timeline = wiki.get_timeline(class_id)
        active_by_date: dict[str, str] = {}
        for draft in workflow_drafts.list_active_for_class(class_id, mode="ingest"):
            if draft.lesson_date and draft.lesson_date not in active_by_date:
                active_by_date[draft.lesson_date] = draft.draft_id
        for entry in timeline.entries:
            entry.memory_draft_id = active_by_date.get(entry.date)
        return timeline
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/classes/{class_id}/lessons/{lesson_date}", response_model=LessonDetail)
def get_lesson_detail(
    class_id: str,
    lesson_date: str,
    wiki: WikiStore = Depends(get_wiki),
) -> LessonDetail:
    try:
        wiki.get_class(class_id)
        return wiki.get_lesson_detail(class_id, lesson_date)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.patch(
    "/classes/{class_id}/lessons/{lesson_date}",
    response_model=ReviseLessonResponse,
)
def revise_lesson(
    class_id: str,
    lesson_date: str,
    body: ReviseLessonRequest,
    request: Request,
    wiki: WikiStore = Depends(get_wiki),
    beta_auth: BetaAuthService = Depends(get_beta_auth_service),
) -> ReviseLessonResponse:
    try:
        wiki.get_class(class_id)
        rel_path = wiki.rel_wiki(
            wiki.lesson_dir(class_id, lesson_date) / "lesson_results.md"
        )
        before_by_path = {rel_path: _read_wiki_rel(wiki, rel_path)}
        entry, applied = wiki.revise_lesson(class_id, lesson_date, body.diary_markdown)
        _record_beta_wiki_diff(
            request,
            beta_auth,
            wiki,
            class_id=class_id,
            app_session_id=None,
            mode="memory",
            action="lesson_revised",
            before_by_path=before_by_path,
            changed_paths=applied,
            metadata={"lesson_date": lesson_date},
        )
        return ReviseLessonResponse(entry=entry, applied_wiki_paths=applied)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/classes/{class_id}/snapshot", response_model=ClassMemorySnapshot)
def get_snapshot(
    class_id: str, wiki: WikiStore = Depends(get_wiki)
) -> ClassMemorySnapshot:
    try:
        return wiki.get_snapshot(class_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/classes/{class_id}/wiki/file", response_model=WikiFileResponse)
def get_wiki_file(
    class_id: str,
    path: str,
    wiki: WikiStore = Depends(get_wiki),
) -> WikiFileResponse:
    try:
        wiki.get_class(class_id)
        rel = path.strip().lstrip("/")
        if not rel:
            raise HTTPException(
                status_code=400, detail="path query parameter is required"
            )
        full = wiki.resolve_path(rel)
        if not full.exists():
            raise HTTPException(status_code=404, detail=f"Wiki file not found: {rel}")
        markdown = wiki.read_wiki_page(rel, max_chars=120_000)
        return WikiFileResponse(wiki_path=rel, markdown=markdown)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/classes/{class_id}/wiki/pages", response_model=WikiPagesResponse)
def list_wiki_pages(
    class_id: str,
    kind: str = "",
    wiki: WikiStore = Depends(get_wiki),
) -> WikiPagesResponse:
    try:
        wiki.get_class(class_id)
        pages = wiki.list_class_pages(class_id, kind=kind.strip() or None)
        return WikiPagesResponse(
            class_id=class_id,
            pages=[WikiPageSummary(**page) for page in pages],
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/classes/{class_id}/brief", response_model=ClassBriefResponse)
async def get_class_brief(
    class_id: str,
    brief_service: ClassBriefService = Depends(get_class_brief_service),
) -> ClassBriefResponse:
    try:
        return await brief_service.get_brief(class_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/classes/{class_id}/brief/refresh", response_model=ClassBriefResponse)
async def refresh_class_brief(
    class_id: str,
    request: Request,
    brief_service: ClassBriefService = Depends(get_class_brief_service),
    beta_auth: BetaAuthService = Depends(get_beta_auth_service),
) -> ClassBriefResponse:
    try:
        response = await brief_service.refresh_brief(class_id)
        _record_beta_event(
            request,
            beta_auth,
            event_type="class_brief_refreshed",
            class_id=class_id,
            app_session_id=None,
            mode="brief",
            payload={"cached": response.cached},
        )
        return response
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.post(
    "/classes/{class_id}/discussion/sessions",
    response_model=DiscussSession,
)
async def start_discussion_session(
    class_id: str,
    request: Request,
    discussion_svc: DiscussionService = Depends(get_discussion_service),
    wiki: WikiStore = Depends(get_wiki),
    beta_auth: BetaAuthService = Depends(get_beta_auth_service),
) -> DiscussSession:
    try:
        wiki.get_class(class_id)
        session = await discussion_svc.start_session(class_id)
        _record_beta_app_session(
            request,
            beta_auth,
            app_session_id=session.session_id,
            class_id=class_id,
            mode="discuss",
            status=session.status.value,
        )
        for message in session.messages:
            _record_beta_message(
                request,
                beta_auth,
                app_session_id=session.session_id,
                class_id=class_id,
                mode="discuss",
                role=message.role,
                content=message.content,
            )
        return session
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.get(
    "/classes/{class_id}/discussion/sessions/{session_id}/draft",
    response_model=DiscussDraft,
)
def discussion_draft(
    class_id: str,
    session_id: str,
    discussion_svc: DiscussionService = Depends(get_discussion_service),
) -> DiscussDraft:
    try:
        session = discussion_svc.get_session(session_id)
        if session.class_id != class_id:
            raise HTTPException(status_code=404, detail="Session not found")
        return discussion_svc.get_draft(session_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post(
    "/classes/{class_id}/discussion/sessions/{session_id}/chat",
    response_model=DiscussChatResponse,
)
async def discussion_chat(
    class_id: str,
    session_id: str,
    body: DiscussChatRequest,
    request: Request,
    discussion_svc: DiscussionService = Depends(get_discussion_service),
    beta_auth: BetaAuthService = Depends(get_beta_auth_service),
) -> DiscussChatResponse:
    try:
        session = discussion_svc.get_session(session_id)
        if session.class_id != class_id:
            raise HTTPException(status_code=404, detail="Session not found")
        _record_beta_event(
            request,
            beta_auth,
            event_type="chat_turn_started",
            class_id=class_id,
            app_session_id=session_id,
            mode="discuss",
            payload={"attachments": len(body.attachments)},
        )
        _record_beta_message(
            request,
            beta_auth,
            app_session_id=session_id,
            class_id=class_id,
            mode="discuss",
            role="user",
            content=body.message,
        )
        response = await discussion_svc.chat(
            session_id,
            body.message,
            attachments=body.attachments,
        )
        _record_beta_message(
            request,
            beta_auth,
            app_session_id=session_id,
            class_id=class_id,
            mode="discuss",
            role="assistant",
            content=response.reply,
        )
        _record_beta_event(
            request,
            beta_auth,
            event_type="class_discussion_turn",
            class_id=class_id,
            app_session_id=session_id,
            mode="discuss",
            payload={
                "memory_candidates": len(response.memory_candidates),
                "source_paths": response.source_paths,
            },
        )
        return response
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.post("/classes/{class_id}/discussion/sessions/{session_id}/chat/stream")
async def discussion_chat_stream(
    class_id: str,
    session_id: str,
    body: DiscussChatRequest,
    request: Request,
    discussion_svc: DiscussionService = Depends(get_discussion_service),
    beta_auth: BetaAuthService = Depends(get_beta_auth_service),
) -> StreamingResponse:
    try:
        session = discussion_svc.get_session(session_id)
        if session.class_id != class_id:
            raise HTTPException(status_code=404, detail="Session not found")
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    _record_beta_event(
        request,
        beta_auth,
        event_type="chat_turn_started",
        class_id=class_id,
        app_session_id=session_id,
        mode="discuss",
        payload={"attachments": len(body.attachments), "stream": True},
    )
    _record_beta_message(
        request,
        beta_auth,
        app_session_id=session_id,
        class_id=class_id,
        mode="discuss",
        role="user",
        content=body.message,
    )
    return StreamingResponse(
        _stream_chat_with_beta_telemetry(
            discussion_svc.chat_stream(
                session_id,
                body.message,
                attachments=body.attachments,
            ),
            request=request,
            beta_auth=beta_auth,
            session_id=session_id,
            class_id=class_id,
            mode="discuss",
            artifact_kind="discussion",
            completed_payload=lambda final: {
                "ready": final.get("ready"),
                "memory_candidates": len(final.get("memory_candidates") or []),
                "stream": True,
            },
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get(
    "/classes/{class_id}/discussion/sessions/{session_id}/trace",
    response_model=DiscussTraceResponse,
)
def discussion_trace(
    class_id: str,
    session_id: str,
    discussion_svc: DiscussionService = Depends(get_discussion_service),
) -> DiscussTraceResponse:
    if not get_settings().is_agent_trace_enabled():
        return DiscussTraceResponse(
            class_id=class_id,
            session_id=session_id,
            status="chatting",
            prompt_assembly={},
            event_trace=[],
        )
    try:
        return discussion_svc.trace(class_id, session_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/classes/{class_id}/workflow-drafts/{draft_id}/discard")
def discard_workflow_draft(
    class_id: str,
    draft_id: str,
    store: WorkflowDraftStore = Depends(get_workflow_draft_store),
) -> dict[str, str]:
    try:
        row = store.get(draft_id)
        if row.class_id != class_id:
            raise HTTPException(status_code=404, detail="Workflow draft not found")
        row = store.discard(draft_id)
        return {"draft_id": row.draft_id, "status": row.status}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/classes/{class_id}/wiki/lint", response_model=WikiLintResponse)
async def lint_wiki(
    class_id: str,
    agents: AgentRunner = Depends(get_agents),
    wiki: WikiStore = Depends(get_wiki),
) -> WikiLintResponse:
    try:
        wiki.get_class(class_id)
        report = await agents.lint_wiki(class_id)
        return WikiLintResponse(class_id=class_id, report_markdown=report)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.post("/classes/{class_id}/memory/compact", response_model=MemoryCompactResponse)
async def compact_memory(
    class_id: str,
    request: Request,
    body: MemoryCompactRequest | None = None,
    agents: AgentRunner = Depends(get_agents),
    wiki: WikiStore = Depends(get_wiki),
    beta_auth: BetaAuthService = Depends(get_beta_auth_service),
) -> MemoryCompactResponse:
    try:
        req = body or MemoryCompactRequest()
        wiki.get_class(class_id)
        output, source_paths, warnings = await agents.compact_memory(
            class_id,
            start_date=req.start_date,
            end_date=req.end_date,
        )
        pages = _compaction_pages(output)
        candidate_paths = _compact_page_paths(wiki, class_id, pages)
        before_by_path = {path: _read_wiki_rel(wiki, path) for path in candidate_paths}
        applied, log_id = wiki.commit_memory_compaction(
            class_id, pages, source_paths=source_paths
        )
        _record_beta_wiki_diff(
            request,
            beta_auth,
            wiki,
            class_id=class_id,
            app_session_id=None,
            mode="memory",
            action="memory_compact",
            before_by_path=before_by_path,
            changed_paths=applied,
            metadata={"source_paths": source_paths, "warnings": warnings},
        )
        return MemoryCompactResponse(
            class_id=class_id,
            applied_wiki_paths=applied,
            log_entry_id=log_id,
            source_paths=source_paths,
            stale_report=list(output.stale_report),
            warnings=warnings,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.post(
    "/classes/{class_id}/memory/compact/apply",
    response_model=MemoryCompactResponse,
)
def apply_compact_memory_proposal(
    class_id: str,
    body: MemoryCompactApplyRequest,
    request: Request,
    wiki: WikiStore = Depends(get_wiki),
    beta_auth: BetaAuthService = Depends(get_beta_auth_service),
) -> MemoryCompactResponse:
    """Write teacher-reviewed compact memory pages exactly as approved."""
    try:
        wiki.get_class(class_id)
        if not body.pages:
            raise HTTPException(
                status_code=400, detail="No compact memory pages provided"
            )
        candidate_paths = _compact_page_paths(wiki, class_id, body.pages)
        before_by_path = {path: _read_wiki_rel(wiki, path) for path in candidate_paths}
        applied, log_id = wiki.commit_memory_compaction(
            class_id,
            body.pages,
            source_paths=body.source_paths,
        )
        _record_beta_wiki_diff(
            request,
            beta_auth,
            wiki,
            class_id=class_id,
            app_session_id=None,
            mode="memory",
            action="memory_compact_apply",
            before_by_path=before_by_path,
            changed_paths=applied,
            metadata={"source_paths": body.source_paths},
        )
        return MemoryCompactResponse(
            class_id=class_id,
            applied_wiki_paths=applied,
            log_entry_id=log_id,
            source_paths=body.source_paths,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


def _compaction_pages(output) -> dict[str, str]:
    pages = {
        "planning_brief": output.planning_brief_markdown,
        "teaching_patterns": output.teaching_patterns_markdown,
        "copilot_profile": output.copilot_profile_markdown,
    }
    if output.session_summaries_markdown.strip():
        pages["session_summaries"] = output.session_summaries_markdown
    return pages


@router.post(
    "/classes/{class_id}/memory/refresh", response_model=MemoryProposalResponse
)
async def refresh_memory(
    class_id: str,
    body: MemoryCompactRequest | None = None,
    agents: AgentRunner = Depends(get_agents),
    wiki: WikiStore = Depends(get_wiki),
) -> MemoryProposalResponse:
    """Propose refreshed derived memory pages WITHOUT writing.

    Teacher reviews the proposal, then commits via /memory/compact or /memory/apply.
    """
    try:
        req = body or MemoryCompactRequest()
        wiki.get_class(class_id)
        output, source_paths, warnings = await agents.compact_memory(
            class_id, start_date=req.start_date, end_date=req.end_date
        )
        return MemoryProposalResponse(
            class_id=class_id,
            pages=_compaction_pages(output),
            source_paths=source_paths,
            stale_report=list(output.stale_report),
            warnings=warnings,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.post(
    "/classes/{class_id}/memory/profile/propose",
    response_model=ProfileProposalResponse,
)
async def propose_profile(
    class_id: str,
    body: ProfileProposalRequest | None = None,
    agents: AgentRunner = Depends(get_agents),
    wiki: WikiStore = Depends(get_wiki),
) -> ProfileProposalResponse:
    """Propose teacher_profile.md / copilot_profile.md updates from a finished session."""
    try:
        req = body or ProfileProposalRequest()
        wiki.get_class(class_id)
        out = await agents.propose_profile_updates(
            class_id,
            final_lesson_markdown=req.final_lesson_markdown,
            session_state=req.session_state,
            lesson_planning_state=req.lesson_planning_state,
            memory_candidates=req.memory_candidates,
        )
        candidates = [
            {
                "target": _normalize_profile_candidate_target(c.target),
                "section": c.section,
                "content": c.content,
                "basis": c.basis,
                "confidence": c.confidence,
                "evidence": c.evidence,
            }
            for c in (list(out.user_candidates) + list(out.copilot_candidates))
            if c.content.strip()
        ]
        return ProfileProposalResponse(
            class_id=class_id, candidates=candidates, warnings=list(out.warnings)
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.post("/classes/{class_id}/memory/apply", response_model=MemoryApplyResponse)
def apply_memory(
    class_id: str,
    body: MemoryApplyRequest,
    request: Request,
    wiki: WikiStore = Depends(get_wiki),
    ledger: MemoryCandidateLedger = Depends(get_memory_candidate_ledger),
    beta_auth: BetaAuthService = Depends(get_beta_auth_service),
) -> MemoryApplyResponse:
    """Write only teacher-approved memory items via the bounded helpers (HITL).

    When an item's write lands, close its originating ledger rows to ``applied``
    so the Memory Sweep never re-proposes an already-applied fact (fast-lane
    candidates surfaced on the post-save panel).
    """
    try:
        cls = wiki.get_class(class_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    candidate_paths = _memory_apply_candidate_paths(wiki, class_id, body.items)
    before_by_path = {path: _read_wiki_rel(wiki, path) for path in candidate_paths}
    applied, skipped, warnings, successful_indexes = apply_curated_memory(
        wiki, class_id, body.items
    )

    # Close the ledger rows for items that actually wrote. Only rows still open
    # are touched, so a re-apply (or an item with no candidate_ids) is a no-op.
    open_rows = ledger.list_candidates(
        class_id=class_id,
        subject=cls.subject,
        statuses=OPEN_STATUSES,
        include_global=True,
    )
    open_ids = {row.id for row in open_rows}
    now = _utc_now()
    review_batch_id = f"memory_apply_{now}"
    updated_ids: list[str] = []
    for index in successful_indexes:
        for candidate_id in body.items[index].candidate_ids:
            if candidate_id not in open_ids or candidate_id in updated_ids:
                continue
            ledger.update_status(
                candidate_id,
                "applied",
                updated_at=now,
                review_batch_id=review_batch_id,
                promoted_at=now,
            )
            updated_ids.append(candidate_id)

    _record_beta_wiki_diff(
        request,
        beta_auth,
        wiki,
        class_id=class_id,
        app_session_id=None,
        mode="memory",
        action="memory_apply",
        before_by_path=before_by_path,
        changed_paths=applied,
        metadata={"item_count": len(body.items), "skipped": skipped, "warnings": warnings},
    )
    return MemoryApplyResponse(
        class_id=class_id,
        applied_wiki_paths=applied,
        skipped=skipped,
        warnings=warnings,
        updated_candidate_ids=updated_ids,
    )


@router.post(
    "/classes/{class_id}/memory/sweep/propose",
    response_model=MemorySweepProposalResponse,
)
async def propose_memory_sweep(
    class_id: str,
    request: Request,
    queue: str | None = None,
    wiki: WikiStore = Depends(get_wiki),
    ledger: MemoryCandidateLedger = Depends(get_memory_candidate_ledger),
    agents: AgentRunner = Depends(get_agents),
    beta_auth: BetaAuthService = Depends(get_beta_auth_service),
) -> MemorySweepProposalResponse:
    """Return grouped Memory Sweep candidates without writing wiki files."""
    try:
        wiki.get_class(class_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    result = await propose_memory_sweep_review(
        wiki=wiki,
        ledger=ledger,
        agents=agents,
        class_id=class_id,
        include_student_summaries=True,
        queue=queue,
    )
    queue_counts = {
        queue: len(cards) for queue, cards in result.cards_by_queue.items()
    }
    _record_beta_event(
        request,
        beta_auth,
        event_type="memory_sweep_propose",
        class_id=class_id,
        app_session_id=None,
        mode="memory",
        payload={
            "card_count": sum(queue_counts.values()),
            "queue_counts": queue_counts,
            "warning_count": len(result.warnings),
            "warnings": result.warnings,
            "queue": queue,
        },
    )
    return MemorySweepProposalResponse(
        class_id=result.class_id,
        subject=result.subject,
        queues=_memory_sweep_api_queues(result.cards_by_queue),
        warnings=result.warnings,
    )


def _memory_sweep_source(
    *,
    wiki: WikiStore,
    ledger: MemoryCandidateLedger,
    class_id: str,
) -> tuple[dict, str]:
    # The sweep itself expires stale singleton candidates. Do that before
    # snapshotting so its own housekeeping cannot stale a newly created review.
    expire_stale_candidates(ledger, datetime.now(timezone.utc))
    source = build_memory_sweep_source_snapshot(
        wiki=wiki,
        ledger=ledger,
        class_id=class_id,
    )
    return source, memory_sweep_source_fingerprint(source)


def _create_memory_sweep_review(
    *,
    class_id: str,
    source: dict,
    fingerprint: str,
    wiki: WikiStore,
    ledger: MemoryCandidateLedger,
    agents: AgentRunner,
    store: MemorySweepReviewStore,
) -> MemorySweepReviewRecord:
    review = store.create_generating(
        class_id=class_id,
        source_fingerprint=fingerprint,
        source=source,
    )
    asyncio.create_task(
        _generate_memory_sweep_review(
            review_id=review.review_id,
            class_id=class_id,
            wiki=wiki,
            ledger=ledger,
            agents=agents,
            store=store,
        ),
        name=f"memory-sweep-review:{review.review_id}",
    )
    return review


async def _generate_memory_sweep_review(
    *,
    review_id: str,
    class_id: str,
    wiki: WikiStore,
    ledger: MemoryCandidateLedger,
    agents: AgentRunner,
    store: MemorySweepReviewStore,
) -> None:
    try:
        result = await propose_memory_sweep_review(
            wiki=wiki,
            ledger=ledger,
            agents=agents,
            class_id=class_id,
            include_student_summaries=True,
        )
        queues = {
            queue: [
                MemorySweepCandidate(**card.__dict__).model_dump()
                for card in cards
            ]
            for queue, cards in result.cards_by_queue.items()
        }
        store.mark_ready(
            review_id,
            proposals={
                "class_id": result.class_id,
                "subject": result.subject,
                "queues": queues,
                "warnings": result.warnings,
            },
        )
    except Exception as exc:
        logger.exception("Memory Sweep review generation failed")
        store.mark_failed(review_id, error=str(exc))


@router.get(
    "/classes/{class_id}/memory/sweep/review",
    response_model=MemorySweepReviewResponse,
)
def get_memory_sweep_review(
    class_id: str,
    wiki: WikiStore = Depends(get_wiki),
    ledger: MemoryCandidateLedger = Depends(get_memory_candidate_ledger),
    store: MemorySweepReviewStore = Depends(get_memory_sweep_review_store),
) -> MemorySweepReviewResponse:
    try:
        wiki.get_class(class_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    active = store.get_active(class_id)
    if active is None:
        return _memory_sweep_review_response(None, class_id=class_id)
    # A review generation already owns a source snapshot. Rebuilding it on
    # every frontend status poll is expensive and cannot affect the result in
    # flight; validate freshness once generation has reached a terminal state.
    if active.status == "generating":
        return _memory_sweep_review_response(active, class_id=class_id)
    source, fingerprint = _memory_sweep_source(wiki=wiki, ledger=ledger, class_id=class_id)
    is_stale = active.source_fingerprint != fingerprint
    if is_stale and active.status != "stale":
        active = store.mark_stale(active.review_id)
    return _memory_sweep_review_response(
        active,
        class_id=class_id,
        is_stale=is_stale,
        stale_reasons=memory_sweep_stale_reasons(active.source, source) if is_stale else [],
    )


@router.post(
    "/classes/{class_id}/memory/sweep/review",
    response_model=MemorySweepReviewResponse,
)
async def open_memory_sweep_review(
    class_id: str,
    body: MemorySweepReviewOpenRequest | None = None,
    wiki: WikiStore = Depends(get_wiki),
    ledger: MemoryCandidateLedger = Depends(get_memory_candidate_ledger),
    agents: AgentRunner = Depends(get_agents),
    store: MemorySweepReviewStore = Depends(get_memory_sweep_review_store),
) -> MemorySweepReviewResponse:
    try:
        wiki.get_class(class_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    request_body = body or MemorySweepReviewOpenRequest()
    source, fingerprint = _memory_sweep_source(wiki=wiki, ledger=ledger, class_id=class_id)
    active = store.get_active(class_id)
    if active is not None and request_body.refresh:
        store.discard(active.review_id)
        active = None
    if active is not None and active.source_fingerprint == fingerprint:
        return _memory_sweep_review_response(active, class_id=class_id)
    if active is not None and active.source_fingerprint != fingerprint:
        if active.has_teacher_edits and not request_body.keep_stale:
            stale = store.mark_stale(active.review_id)
            return _memory_sweep_review_response(
                stale,
                class_id=class_id,
                is_stale=True,
                stale_reasons=memory_sweep_stale_reasons(active.source, source),
            )
        store.discard(active.review_id)
    review = _create_memory_sweep_review(
        class_id=class_id,
        source=source,
        fingerprint=fingerprint,
        wiki=wiki,
        ledger=ledger,
        agents=agents,
        store=store,
    )
    return _memory_sweep_review_response(review, class_id=class_id)


@router.patch(
    "/classes/{class_id}/memory/sweep/review/{review_id}",
    response_model=MemorySweepReviewResponse,
)
def patch_memory_sweep_review(
    class_id: str,
    review_id: str,
    body: MemorySweepReviewPatchRequest,
    wiki: WikiStore = Depends(get_wiki),
    store: MemorySweepReviewStore = Depends(get_memory_sweep_review_store),
) -> MemorySweepReviewResponse:
    try:
        wiki.get_class(class_id)
        review = store.get(review_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    if review.class_id != class_id:
        raise HTTPException(status_code=404, detail="Memory Sweep review not found")
    updated = store.save_decisions(
        review_id,
        decisions=[decision.model_dump() for decision in body.decisions],
    )
    return _memory_sweep_review_response(updated, class_id=class_id)


@router.post(
    "/classes/{class_id}/memory/sweep/review/{review_id}/discard",
    response_model=MemorySweepReviewResponse,
)
def discard_memory_sweep_review(
    class_id: str,
    review_id: str,
    wiki: WikiStore = Depends(get_wiki),
    store: MemorySweepReviewStore = Depends(get_memory_sweep_review_store),
) -> MemorySweepReviewResponse:
    try:
        wiki.get_class(class_id)
        review = store.get(review_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    if review.class_id != class_id:
        raise HTTPException(status_code=404, detail="Memory Sweep review not found")
    discarded = store.discard(review_id)
    return _memory_sweep_review_response(discarded, class_id=class_id)


@router.post(
    "/classes/{class_id}/memory/sweep/review/{review_id}/apply",
    response_model=MemorySweepApplyResponse,
)
def apply_memory_sweep_review(
    class_id: str,
    review_id: str,
    request: Request,
    wiki: WikiStore = Depends(get_wiki),
    ledger: MemoryCandidateLedger = Depends(get_memory_candidate_ledger),
    store: MemorySweepReviewStore = Depends(get_memory_sweep_review_store),
    beta_auth: BetaAuthService = Depends(get_beta_auth_service),
) -> MemorySweepApplyResponse:
    try:
        wiki.get_class(class_id)
        review = store.get(review_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    if review.class_id != class_id:
        raise HTTPException(status_code=404, detail="Memory Sweep review not found")
    _, fingerprint = _memory_sweep_source(wiki=wiki, ledger=ledger, class_id=class_id)
    if review.source_fingerprint != fingerprint:
        store.mark_stale(review_id)
        raise HTTPException(status_code=409, detail="stale_review")
    store.mark_applying(review_id)
    result = _apply_memory_sweep_decision_batch(
        class_id=class_id,
        body=MemorySweepApplyRequest(
            decisions=review.decisions,
            review_batch_id=review.review_id,
        ),
        request=request,
        wiki=wiki,
        ledger=ledger,
        beta_auth=beta_auth,
    )
    store.mark_completed(review_id)
    return result


@router.post(
    "/classes/{class_id}/memory/sweep/apply",
    response_model=MemorySweepApplyResponse,
)
def apply_memory_sweep(
    class_id: str,
    body: MemorySweepApplyRequest,
    request: Request,
    wiki: WikiStore = Depends(get_wiki),
    ledger: MemoryCandidateLedger = Depends(get_memory_candidate_ledger),
    beta_auth: BetaAuthService = Depends(get_beta_auth_service),
) -> MemorySweepApplyResponse:
    """Apply a teacher-reviewed sweep decision set, then update ledger status."""
    return _apply_memory_sweep_decision_batch(
        class_id=class_id,
        body=body,
        request=request,
        wiki=wiki,
        ledger=ledger,
        beta_auth=beta_auth,
    )


@router.post(
    "/classes/{class_id}/memory/candidates/{candidate_id}/status",
    response_model=MemoryCandidateStatusResponse,
)
def update_memory_candidate_status(
    class_id: str,
    candidate_id: str,
    body: MemoryCandidateStatusRequest,
    wiki: WikiStore = Depends(get_wiki),
    ledger: MemoryCandidateLedger = Depends(get_memory_candidate_ledger),
) -> MemoryCandidateStatusResponse:
    """Update review status for one candidate; does not write wiki memory."""
    try:
        wiki.get_class(class_id)
        now = _utc_now()
        ledger.update_status(
            candidate_id,
            body.status,
            updated_at=now,
            rejection_reason=body.rejection_reason,
            review_batch_id=body.review_batch_id,
            promoted_at=now if body.status in {"approved", "applied"} else None,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return MemoryCandidateStatusResponse(candidate_id=candidate_id, status=body.status)


@router.post("/classes/{class_id}/ingest/sessions", response_model=IngestSession)
async def start_ingest_session(
    class_id: str,
    request: Request,
    body: IngestSessionStartRequest | None = None,
    ingest: IngestService = Depends(get_ingest_service),
    wiki: WikiStore = Depends(get_wiki),
    beta_auth: BetaAuthService = Depends(get_beta_auth_service),
) -> IngestSession:
    try:
        wiki.get_class(class_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    session = await ingest.start_session(class_id, body)
    _record_beta_app_session(
        request,
        beta_auth,
        app_session_id=session.session_id,
        class_id=class_id,
        mode="ingest",
        status=session.status.value,
    )
    for message in session.messages:
        _record_beta_message(
            request,
            beta_auth,
            app_session_id=session.session_id,
            class_id=class_id,
            mode="ingest",
            role=message.role,
            content=message.content,
        )
    return session


@router.post(
    "/classes/{class_id}/ingest/sessions/{session_id}/chat",
    response_model=ChatResponse,
)
async def ingest_chat(
    class_id: str,
    session_id: str,
    body: ChatRequest,
    request: Request,
    ingest: IngestService = Depends(get_ingest_service),
    beta_auth: BetaAuthService = Depends(get_beta_auth_service),
) -> ChatResponse:
    try:
        session = ingest.get_session(session_id)
        if session.class_id != class_id:
            raise HTTPException(status_code=404, detail="Session not found")
        _record_beta_event(
            request,
            beta_auth,
            event_type="chat_turn_started",
            class_id=class_id,
            app_session_id=session_id,
            mode="ingest",
            payload={"attachments": len(body.attachments)},
        )
        _record_beta_message(
            request,
            beta_auth,
            app_session_id=session_id,
            class_id=class_id,
            mode="ingest",
            role="user",
            content=body.message,
        )
        response = await ingest.chat(
            session_id, body.message, body.diary_markdown, attachments=body.attachments
        )
        _record_beta_message(
            request,
            beta_auth,
            app_session_id=session_id,
            class_id=class_id,
            mode="ingest",
            role="assistant",
            content=response.reply,
        )
        _record_beta_artifact_snapshot(
            request,
            beta_auth,
            app_session_id=session_id,
            class_id=class_id,
            mode="ingest",
            artifact_kind="diary",
            markdown=response.diary_markdown,
        )
        _record_beta_event(
            request,
            beta_auth,
            event_type="chat_turn_completed",
            class_id=class_id,
            app_session_id=session_id,
            mode="ingest",
            payload={"ready": response.ready_to_propose},
        )
        return response
    except KeyError as e:
        msg = e.args[0] if e.args else str(e)
        if isinstance(msg, str) and msg.startswith("Unknown session:"):
            raise HTTPException(status_code=404, detail=msg) from e
        raise  # unexpected KeyError -> global handler logs full traceback
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/classes/{class_id}/ingest/sessions/{session_id}/chat/stream")
async def ingest_chat_stream(
    class_id: str,
    session_id: str,
    body: ChatRequest,
    request: Request,
    ingest: IngestService = Depends(get_ingest_service),
    beta_auth: BetaAuthService = Depends(get_beta_auth_service),
):
    try:
        session = ingest.get_session(session_id)
        if session.class_id != class_id:
            raise HTTPException(status_code=404, detail="Session not found")
        _record_beta_event(
            request,
            beta_auth,
            event_type="chat_turn_started",
            class_id=class_id,
            app_session_id=session_id,
            mode="ingest",
            payload={"attachments": len(body.attachments), "stream": True},
        )
        _record_beta_message(
            request,
            beta_auth,
            app_session_id=session_id,
            class_id=class_id,
            mode="ingest",
            role="user",
            content=body.message,
        )

        return StreamingResponse(
            _stream_chat_with_beta_telemetry(
                ingest.chat_stream(
                    session_id,
                    body.message,
                    body.diary_markdown,
                    attachments=body.attachments,
                ),
                request=request,
                beta_auth=beta_auth,
                session_id=session_id,
                class_id=class_id,
                mode="ingest",
                artifact_kind="diary",
                completed_payload=lambda final: {
                    "ready": final.get("ready"),
                    "stream": True,
                },
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    except KeyError as e:
        msg = e.args[0] if e.args else str(e)
        if isinstance(msg, str) and msg.startswith("Unknown session:"):
            raise HTTPException(status_code=404, detail=msg) from e
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.patch(
    "/classes/{class_id}/ingest/sessions/{session_id}/draft",
    response_model=IngestDraft,
)
def ingest_update_draft(
    class_id: str,
    session_id: str,
    body: UpdateDraftRequest,
    request: Request,
    ingest: IngestService = Depends(get_ingest_service),
    beta_auth: BetaAuthService = Depends(get_beta_auth_service),
) -> IngestDraft:
    try:
        session = ingest.get_session(session_id)
        if session.class_id != class_id:
            raise HTTPException(status_code=404, detail="Session not found")
        draft = ingest.update_draft(session_id, body.diary_markdown)
        _record_beta_event(
            request,
            beta_auth,
            event_type="draft_updated",
            class_id=class_id,
            app_session_id=session_id,
            mode="ingest",
            payload={"artifact_chars": len(body.diary_markdown)},
        )
        _record_beta_artifact_snapshot(
            request,
            beta_auth,
            app_session_id=session_id,
            class_id=class_id,
            mode="ingest",
            artifact_kind="diary",
            markdown=body.diary_markdown,
        )
        return draft
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post(
    "/classes/{class_id}/ingest/sessions/{session_id}/propose",
    response_model=IngestDraft,
)
async def ingest_propose(
    class_id: str,
    session_id: str,
    request: Request,
    ingest: IngestService = Depends(get_ingest_service),
    beta_auth: BetaAuthService = Depends(get_beta_auth_service),
) -> IngestDraft:
    try:
        session = ingest.get_session(session_id)
        if session.class_id != class_id:
            raise HTTPException(status_code=404, detail="Session not found")
        draft = await ingest.propose(session_id)
        _record_beta_event(
            request,
            beta_auth,
            event_type="review_proposed",
            class_id=class_id,
            app_session_id=session_id,
            mode="ingest",
            payload={"proposal_count": len(draft.wiki_proposals)},
        )
        _record_beta_artifact_snapshot(
            request,
            beta_auth,
            app_session_id=session_id,
            class_id=class_id,
            mode="ingest",
            artifact_kind="diary",
            markdown=draft.diary_markdown,
        )
        return draft
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except WriteVerificationBlocked as exc:
        return JSONResponse(
            status_code=409,
            content=WriteVerificationBlockedResponse(
                action=exc.action,
                artifact_fingerprint=exc.result.artifact_fingerprint,
                executive_state=executive_api_payload(exc.runtime),
                message=str(exc),
            ).model_dump(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/classes/{class_id}/ingest/sessions/{session_id}/draft",
    response_model=IngestDraft,
)
def ingest_draft(
    class_id: str,
    session_id: str,
    ingest: IngestService = Depends(get_ingest_service),
) -> IngestDraft:
    try:
        session = ingest.get_session(session_id)
        if session.class_id != class_id:
            raise HTTPException(status_code=404, detail="Session not found")
        return ingest.get_draft(session_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get(
    "/classes/{class_id}/ingest/sessions/{session_id}/trace",
    response_model=MemoryTraceResponse,
)
def ingest_trace(
    class_id: str,
    session_id: str,
    ingest: IngestService = Depends(get_ingest_service),
) -> MemoryTraceResponse:
    """Return a deterministic debug bundle for an update-memory session."""
    if not get_settings().is_agent_trace_enabled():
        raise HTTPException(status_code=404, detail="Memory trace endpoint is disabled")
    try:
        return ingest.trace(class_id, session_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post(
    "/classes/{class_id}/ingest/commit",
    response_model=CommitIngestResponse,
)
async def ingest_commit(
    class_id: str,
    body: CommitIngestRequest,
    request: Request,
    ingest: IngestService = Depends(get_ingest_service),
    agents: AgentRunner = Depends(get_agents),
    wiki: WikiStore = Depends(get_wiki),
    beta_auth: BetaAuthService = Depends(get_beta_auth_service),
) -> CommitIngestResponse:
    try:
        session = ingest.get_session(body.session_id)
        if session.class_id != class_id:
            raise HTTPException(status_code=404, detail="Session not found")
        approved_paths = [
            update.wiki_path
            for update in body.approved_updates
            if update.approved
        ]
        before_by_path = {
            path: _read_wiki_rel(wiki, path)
            for path in approved_paths
        }
        response = await ingest.commit(body)
        _record_beta_wiki_diff(
            request,
            beta_auth,
            wiki,
            class_id=class_id,
            app_session_id=body.session_id,
            mode="ingest",
            action="memory_committed",
            before_by_path=before_by_path,
            changed_paths=response.applied_wiki_paths,
            metadata={
                "raw_diary_path": response.raw_diary_path,
                "log_entry_id": response.log_entry_id,
                "lesson_date": response.lesson_date,
                "approved_count": len(approved_paths),
            },
        )
        try:
            output, source_paths, warnings = await agents.compact_memory(class_id)
            response.class_memory_proposal = MemoryProposalResponse(
                class_id=class_id,
                pages=_compaction_pages(output),
                source_paths=source_paths,
                stale_report=list(output.stale_report),
                warnings=warnings,
            )
        except RuntimeError as e:
            response.class_memory_proposal = MemoryProposalResponse(
                class_id=class_id,
                warnings=[f"Post-commit class memory proposal failed: {e}"],
            )
        return response
    except ValueError as e:
        _raise_workflow_value_error(e, default_status=400)
    except WriteVerificationBlocked as exc:
        return JSONResponse(
            status_code=409,
            content=WriteVerificationBlockedResponse(
                action=exc.action,
                artifact_fingerprint=exc.result.artifact_fingerprint,
                executive_state=executive_api_payload(exc.runtime),
                message=str(exc),
            ).model_dump(),
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/classes/{class_id}/plan/sessions", response_model=PlanSession)
async def start_plan_session(
    class_id: str,
    request: Request,
    plan_svc: PlanService = Depends(get_plan_service),
    wiki: WikiStore = Depends(get_wiki),
    beta_auth: BetaAuthService = Depends(get_beta_auth_service),
) -> PlanSession:
    try:
        wiki.get_class(class_id)
        session = await plan_svc.start_session(class_id)
        _record_beta_app_session(
            request,
            beta_auth,
            app_session_id=session.session_id,
            class_id=class_id,
            mode="plan",
            status=session.status.value,
        )
        for message in session.messages:
            _record_beta_message(
                request,
                beta_auth,
                app_session_id=session.session_id,
                class_id=class_id,
                mode="plan",
                role=message.role,
                content=message.content,
            )
        return session
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.post(
    "/classes/{class_id}/plan/sessions/{session_id}/chat",
    response_model=PlanChatResponse,
)
async def plan_chat(
    class_id: str,
    session_id: str,
    body: PlanChatRequest,
    request: Request,
    plan_svc: PlanService = Depends(get_plan_service),
    beta_auth: BetaAuthService = Depends(get_beta_auth_service),
) -> PlanChatResponse:
    try:
        session = plan_svc.get_session(session_id)
        if session.class_id != class_id:
            raise HTTPException(status_code=404, detail="Session not found")
        _record_beta_event(
            request,
            beta_auth,
            event_type="chat_turn_started",
            class_id=class_id,
            app_session_id=session_id,
            mode="plan",
            payload={"attachments": len(body.attachments)},
        )
        _record_beta_message(
            request,
            beta_auth,
            app_session_id=session_id,
            class_id=class_id,
            mode="plan",
            role="user",
            content=body.message,
        )
        response = await plan_svc.chat(
            session_id,
            body.message,
            body.plan_markdown,
            attachments=body.attachments,
        )
        _record_beta_message(
            request,
            beta_auth,
            app_session_id=session_id,
            class_id=class_id,
            mode="plan",
            role="assistant",
            content=response.reply,
        )
        _record_beta_artifact_snapshot(
            request,
            beta_auth,
            app_session_id=session_id,
            class_id=class_id,
            mode="plan",
            artifact_kind="plan",
            markdown=response.plan_markdown,
        )
        _record_beta_event(
            request,
            beta_auth,
            event_type="chat_turn_completed",
            class_id=class_id,
            app_session_id=session_id,
            mode="plan",
            payload={"ready": response.ready_to_save, "phase": response.phase},
        )
        return response
    except KeyError as e:
        msg = e.args[0] if e.args else str(e)
        if isinstance(msg, str) and msg.startswith("Unknown session:"):
            raise HTTPException(status_code=404, detail=msg) from e
        raise  # unexpected KeyError -> global handler logs full traceback


@router.post("/classes/{class_id}/plan/sessions/{session_id}/chat/stream")
async def plan_chat_stream(
    class_id: str,
    session_id: str,
    body: PlanChatRequest,
    request: Request,
    plan_svc: PlanService = Depends(get_plan_service),
    beta_auth: BetaAuthService = Depends(get_beta_auth_service),
):
    try:
        session = plan_svc.get_session(session_id)
        if session.class_id != class_id:
            raise HTTPException(status_code=404, detail="Session not found")
        _record_beta_event(
            request,
            beta_auth,
            event_type="chat_turn_started",
            class_id=class_id,
            app_session_id=session_id,
            mode="plan",
            payload={"attachments": len(body.attachments), "stream": True},
        )
        _record_beta_message(
            request,
            beta_auth,
            app_session_id=session_id,
            class_id=class_id,
            mode="plan",
            role="user",
            content=body.message,
        )

        return StreamingResponse(
            _stream_chat_with_beta_telemetry(
                plan_svc.chat_stream(
                    session_id,
                    body.message,
                    body.plan_markdown,
                    attachments=body.attachments,
                ),
                request=request,
                beta_auth=beta_auth,
                session_id=session_id,
                class_id=class_id,
                mode="plan",
                artifact_kind="plan",
                completed_payload=lambda final: {
                    "ready": final.get("ready"),
                    "phase": final.get("phase"),
                    "stream": True,
                },
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    except KeyError as e:
        msg = e.args[0] if e.args else str(e)
        if isinstance(msg, str) and msg.startswith("Unknown session:"):
            raise HTTPException(status_code=404, detail=msg) from e
        raise


@router.get(
    "/classes/{class_id}/plan/sessions/{session_id}/draft",
    response_model=PlanDraft,
)
def plan_draft(
    class_id: str,
    session_id: str,
    plan_svc: PlanService = Depends(get_plan_service),
) -> PlanDraft:
    try:
        session = plan_svc.get_session(session_id)
        if session.class_id != class_id:
            raise HTTPException(status_code=404, detail="Session not found")
        return plan_svc.get_draft(session_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get(
    "/classes/{class_id}/plan/sessions/{session_id}/trace",
    response_model=PlanTraceResponse,
)
def plan_trace(
    class_id: str,
    session_id: str,
    plan_svc: PlanService = Depends(get_plan_service),
) -> PlanTraceResponse:
    """Return a deterministic debug bundle for a plan session."""
    if not get_settings().is_agent_trace_enabled():
        raise HTTPException(status_code=404, detail="Plan trace endpoint is disabled")
    try:
        return plan_svc.trace(class_id, session_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.patch(
    "/classes/{class_id}/plan/sessions/{session_id}/draft",
    response_model=PlanDraft,
)
def plan_update_draft(
    class_id: str,
    session_id: str,
    body: UpdatePlanDraftRequest,
    request: Request,
    plan_svc: PlanService = Depends(get_plan_service),
    beta_auth: BetaAuthService = Depends(get_beta_auth_service),
) -> PlanDraft:
    try:
        session = plan_svc.get_session(session_id)
        if session.class_id != class_id:
            raise HTTPException(status_code=404, detail="Session not found")
        draft = plan_svc.update_draft(session_id, body.plan_markdown)
        _record_beta_event(
            request,
            beta_auth,
            event_type="draft_updated",
            class_id=class_id,
            app_session_id=session_id,
            mode="plan",
            payload={"artifact_chars": len(body.plan_markdown)},
        )
        _record_beta_artifact_snapshot(
            request,
            beta_auth,
            app_session_id=session_id,
            class_id=class_id,
            mode="plan",
            artifact_kind="plan",
            markdown=body.plan_markdown,
        )
        return draft
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/classes/{class_id}/plan/save", response_model=SavePlanResponse)
async def plan_save(
    class_id: str,
    body: SavePlanRequest,
    request: Request,
    plan_svc: PlanService = Depends(get_plan_service),
    wiki: WikiStore = Depends(get_wiki),
    beta_auth: BetaAuthService = Depends(get_beta_auth_service),
) -> SavePlanResponse:
    try:
        wiki.get_class(class_id)
        try:
            lesson_date = date.fromisoformat(body.lesson_date).isoformat()
        except ValueError as exc:
            raise ValueError("lesson_date must be YYYY-MM-DD") from exc
        rel_path = wiki.rel_wiki(
            wiki.lesson_dir(class_id, lesson_date) / "lesson_plan.md"
        )
        before_by_path = {rel_path: _read_wiki_rel(wiki, rel_path)}
        response = await plan_svc.save(class_id, body)
        _record_beta_wiki_diff(
            request,
            beta_auth,
            wiki,
            class_id=class_id,
            app_session_id=body.session_id,
            mode="plan",
            action="plan_saved",
            before_by_path=before_by_path,
            changed_paths=[response.plan_path],
            metadata={"lesson_date": response.lesson_date, "title": response.title},
        )
        return response
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except WriteVerificationBlocked as exc:
        return JSONResponse(
            status_code=409,
            content=WriteVerificationBlockedResponse(
                action=exc.action,
                artifact_fingerprint=exc.result.artifact_fingerprint,
                executive_state=executive_api_payload(exc.runtime),
                message=str(exc),
            ).model_dump(),
        )
    except ValueError as e:
        _raise_workflow_value_error(e, default_status=422)


@router.post("/classes/{class_id}/plan-lesson", response_model=LessonPlan)
async def plan_lesson(
    class_id: str,
    body: PlanLessonRequest,
    plan_svc: PlanService = Depends(get_plan_service),
    wiki: WikiStore = Depends(get_wiki),
) -> LessonPlan:
    try:
        wiki.get_class(class_id)
        return await plan_svc.generate(class_id, body)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
