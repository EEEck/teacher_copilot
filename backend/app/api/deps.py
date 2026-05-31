from functools import lru_cache

from app.config import Settings, get_settings
from app.services.ingest_service import IngestService
from app.services.plan_service import PlanService
from app.teacher_agent.agents import AgentRunner
from app.teacher_agent.wiki_store import WikiStore


@lru_cache
def get_wiki() -> WikiStore:
    settings = get_settings()
    return WikiStore(root=settings.wiki_root)


@lru_cache
def get_agents() -> AgentRunner:
    settings = get_settings()
    return AgentRunner(settings=settings, wiki=get_wiki())


@lru_cache
def get_ingest_service() -> IngestService:
    return IngestService(wiki=get_wiki(), agents=get_agents())


@lru_cache
def get_plan_service() -> PlanService:
    return PlanService(wiki=get_wiki(), agents=get_agents())
