"""Call-class model + reasoning routing, by profile.

Three call classes (mem_v3 boundary): CHAT (plan+ingest), IMPORTANT (Memory
Sweep only), UTILITY (one-shots). Profiles:
- production: one model (strong) reasoning-tiered — chat high, important xhigh,
  utility minimal.
- economy: cheap chat/utility, strong important — chat medium, important high.
The profile derives from APP_ENV when unset.
"""

from __future__ import annotations

from app.config import Settings
from app.teacher_agent.agent import chat_model_settings

_MODELS = {"openai_strong_model": "STRONG", "openai_cheap_model": "CHEAP"}


def test_production_is_one_model_reasoning_tiered():
    s = Settings(model_profile="production", **_MODELS)
    assert s.resolved_chat_model() == "STRONG"
    assert s.resolved_important_model() == "STRONG"
    assert s.resolved_utility_model() == "STRONG"
    assert s.resolved_chat_effort() == "high"
    assert s.resolved_important_effort() == "xhigh"
    assert s.resolved_utility_effort() == "minimal"


def test_economy_uses_cheap_chat_and_utility_strong_important():
    s = Settings(model_profile="economy", **_MODELS)
    assert s.resolved_chat_model() == "CHEAP"
    assert s.resolved_utility_model() == "CHEAP"
    assert s.resolved_important_model() == "STRONG"  # sweep always strong
    assert s.resolved_chat_effort() == "medium"
    assert s.resolved_important_effort() == "high"
    assert s.resolved_utility_effort() == "minimal"


def test_profile_derives_from_app_env_when_unset():
    assert Settings(app_env="production", model_profile=None).resolved_model_profile() == "production"
    assert Settings(app_env="development", model_profile=None).resolved_model_profile() == "economy"


def test_plan_turns_have_a_longer_timeout_than_other_agent_workflows():
    settings = Settings(agent_timeout_seconds=240, **_MODELS)

    assert settings.agent_timeout_seconds == 240
    assert settings.plan_agent_timeout_seconds == 600


def test_explicit_profile_overrides_app_env():
    s = Settings(app_env="production", model_profile="economy", **_MODELS)
    assert s.resolved_model_profile() == "economy"
    assert s.resolved_chat_model() == "CHEAP"


def test_each_reasoning_effort_is_independently_overridable():
    s = Settings(
        model_profile="production",
        openai_chat_reasoning_effort="none",
        openai_important_reasoning_effort="low",
        openai_utility_reasoning_effort="medium",
        **_MODELS,
    )
    assert s.resolved_chat_effort() == "none"
    assert s.resolved_important_effort() == "low"
    assert s.resolved_utility_effort() == "medium"


def test_unset_reasoning_efforts_fall_back_to_profile_defaults():
    s = Settings(model_profile="production", **_MODELS)
    assert s.resolved_chat_effort() == "high"
    assert s.resolved_important_effort() == "xhigh"
    assert s.resolved_utility_effort() == "minimal"


def test_legacy_reasoning_effort_still_overrides_chat():
    s = Settings(model_profile="production", openai_reasoning_effort="low", **_MODELS)
    assert s.resolved_chat_effort() == "low"
    # The explicit chat override wins over the legacy alias when both are set.
    s2 = Settings(
        model_profile="production",
        openai_reasoning_effort="low",
        openai_chat_reasoning_effort="none",
        **_MODELS,
    )
    assert s2.resolved_chat_effort() == "none"


def test_gpt_5_4_models_normalize_unsupported_minimal_effort():
    settings = chat_model_settings("minimal", model="gpt-5.4-mini")

    assert settings is not None
    assert settings.reasoning is not None
    assert settings.reasoning.effort == "low"


def test_other_models_normalize_gpt_5_5_minimal_effort():
    settings = chat_model_settings("minimal", model="gpt-5.5")

    assert settings is not None
    assert settings.reasoning is not None
    assert settings.reasoning.effort == "low"


def test_gpt_5_6_models_normalize_unsupported_minimal_effort():
    settings = chat_model_settings("minimal", model="gpt-5.6-terra")

    assert settings is not None
    assert settings.reasoning is not None
    assert settings.reasoning.effort == "low"
