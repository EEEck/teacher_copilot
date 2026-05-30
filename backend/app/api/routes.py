from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_agents, get_ingest_service, get_plan_service, get_wiki
from app.config import get_settings
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
    LessonDetail,
    LessonPlan,
    PlanChatRequest,
    PlanChatResponse,
    PlanDraft,
    PlanLessonRequest,
    PlanSession,
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
from app.services.plan_service import PlanService
from app.teacher_agent.agents import AgentRunner
from app.teacher_agent.wiki_store import WikiStore

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(agent_max_turns=settings.agent_max_turns)


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
def get_snapshot(class_id: str, wiki: WikiStore = Depends(get_wiki)) -> ClassMemorySnapshot:
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
            raise HTTPException(status_code=400, detail="path query parameter is required")
        full = wiki.resolve_path(rel)
        if not full.exists():
            raise HTTPException(status_code=404, detail=f"Wiki file not found: {rel}")
        markdown = wiki.read_wiki_page(rel)
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


@router.post("/classes/{class_id}/ingest/sessions", response_model=IngestSession)
async def start_ingest_session(
    class_id: str,
    ingest: IngestService = Depends(get_ingest_service),
    wiki: WikiStore = Depends(get_wiki),
) -> IngestSession:
    try:
        wiki.get_class(class_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return await ingest.start_session(class_id)


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


@router.post(
    "/classes/{class_id}/ingest/commit",
    response_model=CommitIngestResponse,
)
def ingest_commit(
    class_id: str,
    body: CommitIngestRequest,
    ingest: IngestService = Depends(get_ingest_service),
) -> CommitIngestResponse:
    try:
        session = ingest.get_session(body.session_id)
        if session.class_id != class_id:
            raise HTTPException(status_code=404, detail="Session not found")
        return ingest.commit(body)
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
