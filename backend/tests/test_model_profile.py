"""Two-tier model config + testing/production profile switch.

STRONG runs important/infrequent calls (sweep always; capture chat in the
quality profile); CHEAP runs frequent/utility calls (and capture chat in the
economy profile). The profile derives from APP_ENV when unset.
"""

from __future__ import annotations

from app.config import Settings

_MODELS = {"openai_strong_model": "STRONG", "openai_cheap_model": "CHEAP"}


def test_quality_profile_runs_capture_on_the_strong_model():
    s = Settings(model_profile="quality", **_MODELS)
    assert s.resolved_chat_model() == "STRONG"
    assert s.resolved_sweep_model() == "STRONG"
    assert s.resolved_utility_model() == "CHEAP"


def test_economy_profile_runs_capture_on_the_cheap_model():
    s = Settings(model_profile="economy", **_MODELS)
    assert s.resolved_chat_model() == "CHEAP"
    # The sweep is important + infrequent, so it stays strong even in economy.
    assert s.resolved_sweep_model() == "STRONG"
    assert s.resolved_utility_model() == "CHEAP"


def test_profile_derives_from_app_env_when_unset():
    assert Settings(app_env="development", model_profile=None).resolved_model_profile() == "quality"
    assert Settings(app_env="production", model_profile=None).resolved_model_profile() == "economy"


def test_explicit_profile_overrides_app_env():
    s = Settings(app_env="production", model_profile="quality", **_MODELS)
    assert s.resolved_model_profile() == "quality"
    assert s.resolved_chat_model() == "STRONG"
