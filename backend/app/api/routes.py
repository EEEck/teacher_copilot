from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import (
    get_agents,
    get_ingest_service,
    get_memory_candidate_ledger,
    get_plan_service,
    get_wiki,
)
from app.config import get_settings
from app.openai_bootstrap import is_openai_configured
from app.schemas.api import (
    ChatRequest,
    ChatResponse,
    ClassesResponse,
    ClassMemorySnapshot,
    ClassTimeline,
    CommitIngestRequest,
    CommitIngestResponse,
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
    WikiFileResponse,
    WikiLintResponse,
)
from app.services.ingest_service import IngestService
from app.services.memory_apply import apply_memory_items, apply_memory_sweep_decisions
from app.services.memory_candidate_ledger import MemoryCandidateLedger, OPEN_STATUSES
from app.services.memory_sweep import (
    is_synthetic_student_summary_candidate_id,
    propose_memory_sweep_review,
    synthetic_student_summary_candidate_ids,
)
from app.services.plan_service import PlanService
from app.teacher_agent.agents import AgentRunner
from app.teacher_agent.wiki_store import WikiStore

router = APIRouter(prefix="/api")


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


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        agent_max_turns=settings.agent_max_turns,
        openai_configured=is_openai_configured(settings),
    )


@router.get("/classes", response_model=ClassesResponse)
def list_classes(wiki: WikiStore = Depends(get_wiki)) -> ClassesResponse:
    return ClassesResponse(classes=wiki.list_classes())


@router.get("/classes/{class_id}/timeline", response_model=ClassTimeline)
def get_timeline(class_id: str, wiki: WikiStore = Depends(get_wiki)) -> ClassTimeline:
    try:
        wiki.get_class(class_id)
        return wiki.get_timeline(class_id)
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
    wiki: WikiStore = Depends(get_wiki),
) -> ReviseLessonResponse:
    try:
        wiki.get_class(class_id)
        entry, applied = wiki.revise_lesson(class_id, lesson_date, body.diary_markdown)
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
    body: MemoryCompactRequest | None = None,
    agents: AgentRunner = Depends(get_agents),
    wiki: WikiStore = Depends(get_wiki),
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
        applied, log_id = wiki.commit_memory_compaction(
            class_id, pages, source_paths=source_paths
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
    wiki: WikiStore = Depends(get_wiki),
) -> MemoryCompactResponse:
    """Write teacher-reviewed compact memory pages exactly as approved."""
    try:
        wiki.get_class(class_id)
        if not body.pages:
            raise HTTPException(
                status_code=400, detail="No compact memory pages provided"
            )
        applied, log_id = wiki.commit_memory_compaction(
            class_id,
            body.pages,
            source_paths=body.source_paths,
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
        "taught_so_far": output.taught_so_far_markdown,
        "planning_brief": output.planning_brief_markdown,
        "teaching_patterns": output.teaching_patterns_markdown,
        "copilot_profile": output.copilot_profile_markdown,
    }
    if output.class_state_markdown.strip():
        pages["class_state"] = output.class_state_markdown
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
    """Propose refreshed derived memory pages (incl. class_state) WITHOUT writing.

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
                "target": c.target,
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
    wiki: WikiStore = Depends(get_wiki),
) -> MemoryApplyResponse:
    """Write only teacher-approved memory items via the bounded helpers (HITL)."""
    try:
        wiki.get_class(class_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    applied, skipped, warnings = apply_memory_items(wiki, class_id, body.items)
    return MemoryApplyResponse(
        class_id=class_id,
        applied_wiki_paths=applied,
        skipped=skipped,
        warnings=warnings,
    )


@router.post(
    "/classes/{class_id}/memory/sweep/propose",
    response_model=MemorySweepProposalResponse,
)
async def propose_memory_sweep(
    class_id: str,
    wiki: WikiStore = Depends(get_wiki),
    ledger: MemoryCandidateLedger = Depends(get_memory_candidate_ledger),
    agents: AgentRunner = Depends(get_agents),
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
    )
    return MemorySweepProposalResponse(
        class_id=result.class_id,
        subject=result.subject,
        queues=_memory_sweep_api_queues(result.cards_by_queue),
        warnings=result.warnings,
    )


@router.post(
    "/classes/{class_id}/memory/sweep/apply",
    response_model=MemorySweepApplyResponse,
)
def apply_memory_sweep(
    class_id: str,
    body: MemorySweepApplyRequest,
    wiki: WikiStore = Depends(get_wiki),
    ledger: MemoryCandidateLedger = Depends(get_memory_candidate_ledger),
) -> MemorySweepApplyResponse:
    """Apply a teacher-reviewed sweep decision set, then update ledger status."""
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
    if any(decision.action == "apply" for decision in body.decisions):
        applied, skipped, warnings, successful_apply_indexes = (
            apply_memory_sweep_decisions(wiki, class_id, body.decisions)
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
    body: IngestSessionStartRequest | None = None,
    ingest: IngestService = Depends(get_ingest_service),
    wiki: WikiStore = Depends(get_wiki),
) -> IngestSession:
    try:
        wiki.get_class(class_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return await ingest.start_session(class_id, body)


@router.post(
    "/classes/{class_id}/ingest/sessions/{session_id}/chat",
    response_model=ChatResponse,
)
async def ingest_chat(
    class_id: str,
    session_id: str,
    body: ChatRequest,
    ingest: IngestService = Depends(get_ingest_service),
) -> ChatResponse:
    try:
        session = ingest.get_session(session_id)
        if session.class_id != class_id:
            raise HTTPException(status_code=404, detail="Session not found")
        return await ingest.chat(
            session_id, body.message, body.diary_markdown, attachments=body.attachments
        )
    except KeyError as e:
        msg = e.args[0] if e.args else str(e)
        if isinstance(msg, str) and msg.startswith("Unknown session:"):
            raise HTTPException(status_code=404, detail=msg) from e
        raise  # unexpected KeyError -> global handler logs full traceback


@router.post("/classes/{class_id}/ingest/sessions/{session_id}/chat/stream")
async def ingest_chat_stream(
    class_id: str,
    session_id: str,
    body: ChatRequest,
    ingest: IngestService = Depends(get_ingest_service),
):
    try:
        session = ingest.get_session(session_id)
        if session.class_id != class_id:
            raise HTTPException(status_code=404, detail="Session not found")

        async def event_generator():
            async for line in ingest.chat_stream(
                session_id,
                body.message,
                body.diary_markdown,
                attachments=body.attachments,
            ):
                yield line

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    except KeyError as e:
        msg = e.args[0] if e.args else str(e)
        if isinstance(msg, str) and msg.startswith("Unknown session:"):
            raise HTTPException(status_code=404, detail=msg) from e
        raise


@router.patch(
    "/classes/{class_id}/ingest/sessions/{session_id}/draft",
    response_model=IngestDraft,
)
def ingest_update_draft(
    class_id: str,
    session_id: str,
    body: UpdateDraftRequest,
    ingest: IngestService = Depends(get_ingest_service),
) -> IngestDraft:
    try:
        session = ingest.get_session(session_id)
        if session.class_id != class_id:
            raise HTTPException(status_code=404, detail="Session not found")
        return ingest.update_draft(session_id, body.diary_markdown)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post(
    "/classes/{class_id}/ingest/sessions/{session_id}/propose",
    response_model=IngestDraft,
)
async def ingest_propose(
    class_id: str,
    session_id: str,
    ingest: IngestService = Depends(get_ingest_service),
) -> IngestDraft:
    try:
        session = ingest.get_session(session_id)
        if session.class_id != class_id:
            raise HTTPException(status_code=404, detail="Session not found")
        return await ingest.propose(session_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


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
    ingest: IngestService = Depends(get_ingest_service),
    agents: AgentRunner = Depends(get_agents),
) -> CommitIngestResponse:
    try:
        session = ingest.get_session(body.session_id)
        if session.class_id != class_id:
            raise HTTPException(status_code=404, detail="Session not found")
        response = ingest.commit(body)
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
        raise HTTPException(status_code=400, detail=str(e)) from e
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/classes/{class_id}/plan/sessions", response_model=PlanSession)
async def start_plan_session(
    class_id: str,
    plan_svc: PlanService = Depends(get_plan_service),
    wiki: WikiStore = Depends(get_wiki),
) -> PlanSession:
    try:
        wiki.get_class(class_id)
        return await plan_svc.start_session(class_id)
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
    plan_svc: PlanService = Depends(get_plan_service),
) -> PlanChatResponse:
    try:
        session = plan_svc.get_session(session_id)
        if session.class_id != class_id:
            raise HTTPException(status_code=404, detail="Session not found")
        return await plan_svc.chat(
            session_id,
            body.message,
            body.plan_markdown,
            attachments=body.attachments,
        )
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
    plan_svc: PlanService = Depends(get_plan_service),
):
    try:
        session = plan_svc.get_session(session_id)
        if session.class_id != class_id:
            raise HTTPException(status_code=404, detail="Session not found")

        async def event_generator():
            async for line in plan_svc.chat_stream(
                session_id,
                body.message,
                body.plan_markdown,
                attachments=body.attachments,
            ):
                yield line

        return StreamingResponse(
            event_generator(),
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
    plan_svc: PlanService = Depends(get_plan_service),
) -> PlanDraft:
    try:
        session = plan_svc.get_session(session_id)
        if session.class_id != class_id:
            raise HTTPException(status_code=404, detail="Session not found")
        return plan_svc.update_draft(session_id, body.plan_markdown)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/classes/{class_id}/plan/save", response_model=SavePlanResponse)
def plan_save(
    class_id: str,
    body: SavePlanRequest,
    plan_svc: PlanService = Depends(get_plan_service),
    wiki: WikiStore = Depends(get_wiki),
) -> SavePlanResponse:
    try:
        wiki.get_class(class_id)
        return plan_svc.save(class_id, body)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


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
