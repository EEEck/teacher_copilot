from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.services.ingest_service import IngestService
from app.services.memory_candidate_ledger import (
    MemoryCandidateLedger,
    default_memory_candidate_ledger_path,
)
from app.services.plan_service import PlanService
from app.teacher_agent.agents import AgentRunner
from app.teacher_agent.wiki_store import WikiStore


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
def get_wiki() -> WikiStore:
    return WikiStore(root=_resolved_wiki_root())


@lru_cache
def get_agents() -> AgentRunner:
    settings = get_settings()
    return AgentRunner(settings=settings, wiki=get_wiki())


@lru_cache
def get_memory_candidate_ledger() -> MemoryCandidateLedger:
    ledger = MemoryCandidateLedger(
        default_memory_candidate_ledger_path(_resolved_wiki_root())
    )
    ledger.initialize()
    return ledger


@lru_cache
def get_ingest_service() -> IngestService:
    return IngestService(
        wiki=get_wiki(),
        agents=get_agents(),
        memory_candidate_ledger=get_memory_candidate_ledger(),
    )


@lru_cache
def get_plan_service() -> PlanService:
    return PlanService(
        wiki=get_wiki(),
        agents=get_agents(),
        memory_candidate_ledger=get_memory_candidate_ledger(),
    )
