"""Tests for OpenAI env bootstrap."""

from pydantic import SecretStr

from app.config import Settings
from app.openai_bootstrap import configure_openai_from_settings, is_openai_configured


def test_is_openai_configured_false_when_empty():
    settings = Settings(openai_api_key=SecretStr(""))
    assert is_openai_configured(settings) is False


def test_is_openai_configured_true_when_set():
    settings = Settings(openai_api_key=SecretStr("sk-test"))
    assert is_openai_configured(settings) is True


def test_configure_openai_from_settings_sets_env(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = Settings(openai_api_key=SecretStr("sk-bootstrap-test"))
    assert configure_openai_from_settings(settings) is True
    import os

    assert os.environ.get("OPENAI_API_KEY") == "sk-bootstrap-test"
