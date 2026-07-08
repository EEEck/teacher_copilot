from __future__ import annotations

from app.config import get_settings
from tests.evals.conftest import _settings_for_live_agent_eval


def test_live_agent_eval_settings_default_to_production(monkeypatch):
    monkeypatch.setenv("MODEL_PROFILE", "economy")
    monkeypatch.setenv("OPENAI_CHAT_REASONING_EFFORT", "low")
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "none")
    get_settings.cache_clear()

    settings = _settings_for_live_agent_eval()

    assert settings.resolved_model_profile() == "production"
    assert settings.resolved_chat_effort() == "high"
    assert settings.resolved_important_effort() == "xhigh"


def test_live_agent_eval_model_profile_requires_eval_specific_override(monkeypatch):
    monkeypatch.setenv("MODEL_PROFILE", "production")
    monkeypatch.setenv("LIVE_AGENT_EVAL_MODEL_PROFILE", "economy")
    get_settings.cache_clear()

    settings = _settings_for_live_agent_eval()

    assert settings.resolved_model_profile() == "economy"
    assert settings.resolved_chat_effort() == "medium"
