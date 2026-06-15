"""DeepEval eval suite fixtures."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Iterator

import pytest
from agents import add_trace_processor
from deepeval.openai_agents import DeepEvalTracingProcessor
from fastapi.testclient import TestClient

from app.config import get_settings
from app.openai_bootstrap import configure_openai_from_settings
from app.teacher_agent.agents import AgentRunner
from app.teacher_agent.wiki_store import WikiStore
from tests.conftest import StubAgentRunner

_SEED_WIKI = Path(__file__).resolve().parents[2] / "teacher_wiki"
_EVAL_WIKI_OVERLAY = Path(__file__).resolve().parents[1] / "fixtures" / "eval_wiki"
_PROCESSOR_REGISTERED = False


def _register_deepeval_processor() -> None:
    global _PROCESSOR_REGISTERED
    if _PROCESSOR_REGISTERED:
        return
    add_trace_processor(DeepEvalTracingProcessor())
    _PROCESSOR_REGISTERED = True


@pytest.fixture(scope="session", autouse=True)
def _deepeval_openai_agents_processor() -> None:
    _register_deepeval_processor()


def _overlay_eval_wiki(dest: Path) -> None:
    overlay_root = _EVAL_WIKI_OVERLAY
    if not overlay_root.exists():
        return
    for src in overlay_root.rglob("*"):
        if src.is_dir():
            continue
        rel = src.relative_to(overlay_root)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)


@pytest.fixture
def eval_wiki(tmp_path: Path) -> WikiStore:
    """Seed wiki copy with eval-only engl_10c + ESL overlay."""
    dest = tmp_path / "teacher_wiki"
    shutil.copytree(_SEED_WIKI.resolve(), dest)
    _overlay_eval_wiki(dest)
    return WikiStore(root=dest)


@pytest.fixture
def eval_client(eval_wiki: WikiStore) -> Iterator[TestClient]:
    """Offline TestClient backed by eval wiki (includes engl_10c mock)."""
    from app.api import deps
    from app.main import app
    from app.services.ingest_service import IngestService
    from app.services.plan_service import PlanService

    agents = StubAgentRunner(eval_wiki)
    ingest = IngestService(wiki=eval_wiki, agents=agents)
    plan = PlanService(wiki=eval_wiki, agents=agents)

    app.dependency_overrides[deps.get_wiki] = lambda: eval_wiki
    app.dependency_overrides[deps.get_agents] = lambda: agents
    app.dependency_overrides[deps.get_ingest_service] = lambda: ingest
    app.dependency_overrides[deps.get_plan_service] = lambda: plan
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def live_eval_client(eval_wiki: WikiStore) -> Iterator[TestClient]:
    """TestClient with real AgentRunner (OpenAI Agents SDK). Opt-in via RUN_LIVE_AGENT_EVALS."""
    if os.getenv("RUN_LIVE_AGENT_EVALS") != "1":
        pytest.skip("live agent evals disabled")

    settings = get_settings()
    if not configure_openai_from_settings(settings):
        pytest.skip("OPENAI_API_KEY not configured for live agent evals")

    from app.api import deps
    from app.main import app
    from app.services.ingest_service import IngestService
    from app.services.plan_service import PlanService

    agents = AgentRunner(settings=settings, wiki=eval_wiki)
    ingest = IngestService(wiki=eval_wiki, agents=agents)
    plan = PlanService(wiki=eval_wiki, agents=agents)

    app.dependency_overrides[deps.get_wiki] = lambda: eval_wiki
    app.dependency_overrides[deps.get_agents] = lambda: agents
    app.dependency_overrides[deps.get_ingest_service] = lambda: ingest
    app.dependency_overrides[deps.get_plan_service] = lambda: plan
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
