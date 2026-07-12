from functools import lru_cache
from pathlib import Path

from fastapi import Depends, HTTPException, Request

from app.config import get_settings
from app.services.beta import BetaAuthService, RequestIdentity
from app.services.ingest_service import IngestService
from app.services.memory_candidate_ledger import (
    MemoryCandidateLedger,
    default_memory_candidate_ledger_path,
)
from app.services.memory_sweep_reviews import (
    MemorySweepReviewStore,
    default_memory_sweep_review_store_path,
)
from app.services.plan_service import PlanService
from app.services.workflow_drafts import (
    WorkflowDraftStore,
    default_workflow_draft_store_path,
)
from app.teacher_agent.agents import AgentRunner
from app.teacher_agent.wiki_store import WikiStore

_AGENT_CACHE: dict[str, AgentRunner] = {}
_LEDGER_CACHE: dict[str, MemoryCandidateLedger] = {}
_MEMORY_SWEEP_REVIEW_CACHE: dict[str, MemorySweepReviewStore] = {}
_WORKFLOW_DRAFT_CACHE: dict[str, WorkflowDraftStore] = {}
_INGEST_CACHE: dict[str, IngestService] = {}
_PLAN_CACHE: dict[str, PlanService] = {}


def _resolved_wiki_root() -> Path:
    root = Path(get_settings().wiki_root)
    local_root = Path(__file__).resolve().parents[2] / "teacher_wiki"
    if (
        root.as_posix() == "/data/teacher_wiki"
        and not root.exists()
        and local_root.exists()
    ):
        return local_root
    return root


@lru_cache
def get_beta_auth_service() -> BetaAuthService:
    settings = get_settings()
    service = BetaAuthService(
        db_path=Path(settings.beta_data_root) / "beta.sqlite3",
        data_root=Path(settings.beta_data_root),
        seed_wiki_root=_resolved_wiki_root(),
        cookie_name=settings.beta_cookie_name,
        session_days=settings.beta_session_days,
        cookie_secure=settings.beta_cookie_secure,
    )
    service.initialize()
    return service


def get_request_identity(
    request: Request,
    beta_auth: BetaAuthService = Depends(get_beta_auth_service),
) -> RequestIdentity:
    settings = get_settings()
    if not settings.beta_enabled:
        identity = RequestIdentity(
            tester_id="local",
            workspace_id="local",
            role="developer",
            wiki_root=_resolved_wiki_root(),
        )
        request.state.identity = identity
        return identity
    token = request.cookies.get(settings.beta_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Beta login required")
    try:
        identity = beta_auth.resolve_session_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    request.state.identity = identity
    return identity


def get_wiki(identity: RequestIdentity = Depends(get_request_identity)) -> WikiStore:
    return WikiStore(root=identity.wiki_root)


def get_agents(wiki: WikiStore = Depends(get_wiki)) -> AgentRunner:
    key = str(wiki.root.resolve())
    if key in _AGENT_CACHE:
        return _AGENT_CACHE[key]
    settings = get_settings()
    agent = AgentRunner(settings=settings, wiki=wiki)
    _AGENT_CACHE[key] = agent
    return agent


def get_memory_candidate_ledger(
    wiki: WikiStore = Depends(get_wiki),
) -> MemoryCandidateLedger:
    key = str(wiki.root.resolve())
    if key in _LEDGER_CACHE:
        return _LEDGER_CACHE[key]
    ledger = MemoryCandidateLedger(default_memory_candidate_ledger_path(wiki.root))
    ledger.initialize()
    _LEDGER_CACHE[key] = ledger
    return ledger


def get_memory_sweep_review_store(
    wiki: WikiStore = Depends(get_wiki),
) -> MemorySweepReviewStore:
    key = str(wiki.root.resolve())
    if key in _MEMORY_SWEEP_REVIEW_CACHE:
        return _MEMORY_SWEEP_REVIEW_CACHE[key]
    store = MemorySweepReviewStore(default_memory_sweep_review_store_path(wiki.root))
    store.initialize()
    _MEMORY_SWEEP_REVIEW_CACHE[key] = store
    return store


def get_workflow_draft_store(
    wiki: WikiStore = Depends(get_wiki),
) -> WorkflowDraftStore:
    key = str(wiki.root.resolve())
    if key in _WORKFLOW_DRAFT_CACHE:
        return _WORKFLOW_DRAFT_CACHE[key]
    store = WorkflowDraftStore(default_workflow_draft_store_path(wiki.root))
    store.initialize()
    _WORKFLOW_DRAFT_CACHE[key] = store
    return store


def get_ingest_service(
    identity: RequestIdentity = Depends(get_request_identity),
    wiki: WikiStore = Depends(get_wiki),
    agents: AgentRunner = Depends(get_agents),
    memory_candidate_ledger: MemoryCandidateLedger = Depends(
        get_memory_candidate_ledger
    ),
    workflow_drafts: WorkflowDraftStore = Depends(get_workflow_draft_store),
) -> IngestService:
    key = str(wiki.root.resolve())
    if key in _INGEST_CACHE:
        return _INGEST_CACHE[key]
    service = IngestService(
        wiki=wiki,
        agents=agents,
        memory_candidate_ledger=memory_candidate_ledger,
        workflow_drafts=workflow_drafts,
        workspace_id=identity.workspace_id,
    )
    _INGEST_CACHE[key] = service
    return service


def get_plan_service(
    identity: RequestIdentity = Depends(get_request_identity),
    wiki: WikiStore = Depends(get_wiki),
    agents: AgentRunner = Depends(get_agents),
    memory_candidate_ledger: MemoryCandidateLedger = Depends(
        get_memory_candidate_ledger
    ),
    workflow_drafts: WorkflowDraftStore = Depends(get_workflow_draft_store),
) -> PlanService:
    key = str(wiki.root.resolve())
    if key in _PLAN_CACHE:
        return _PLAN_CACHE[key]
    service = PlanService(
        wiki=wiki,
        agents=agents,
        memory_candidate_ledger=memory_candidate_ledger,
        workflow_drafts=workflow_drafts,
        workspace_id=identity.workspace_id,
    )
    _PLAN_CACHE[key] = service
    return service
