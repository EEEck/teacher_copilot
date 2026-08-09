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
_MODEL_PROFILES = {"production", "economy"}
_REASONING_EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh"}


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


def _env_choice(name: str, allowed: set[str]) -> str | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    normalized = value.strip().lower()
    if normalized not in allowed:
        options = ", ".join(sorted(allowed))
        raise pytest.UsageError(f"{name} must be one of: {options}")
    return normalized


def _settings_for_live_agent_eval():
    """Return live-eval settings pinned to production routing by default.

    Live goldens are meant to evaluate production model behavior, independent
    from local economy/dev settings. Use LIVE_AGENT_EVAL_MODEL_PROFILE only for
    explicit model-profile comparison runs.
    """
    base = get_settings()
    updates = {
        "model_profile": _env_choice("LIVE_AGENT_EVAL_MODEL_PROFILE", _MODEL_PROFILES)
        or "production",
        "openai_chat_reasoning_effort": None,
        "openai_important_reasoning_effort": None,
        "openai_utility_reasoning_effort": None,
        "openai_reasoning_effort": None,
    }
    effort_overrides = {
        "LIVE_AGENT_EVAL_CHAT_REASONING_EFFORT": "openai_chat_reasoning_effort",
        "LIVE_AGENT_EVAL_IMPORTANT_REASONING_EFFORT": "openai_important_reasoning_effort",
        "LIVE_AGENT_EVAL_UTILITY_REASONING_EFFORT": "openai_utility_reasoning_effort",
    }
    for env_name, field_name in effort_overrides.items():
        effort = _env_choice(env_name, _REASONING_EFFORTS)
        if effort is not None:
            updates[field_name] = effort
    return base.model_copy(update=updates)


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
            client.plan_service = plan  # type: ignore[attr-defined]
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def live_eval_client(eval_wiki: WikiStore) -> Iterator[TestClient]:
    """TestClient with real AgentRunner (OpenAI Agents SDK). Opt-in via RUN_LIVE_AGENT_EVALS."""
    if os.getenv("RUN_LIVE_AGENT_EVALS") != "1":
        pytest.skip("live agent evals disabled")

    settings = _settings_for_live_agent_eval()
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
            client.plan_service = plan  # type: ignore[attr-defined]
            yield client
    finally:
        app.dependency_overrides.clear()
