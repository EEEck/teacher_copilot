"""Bridge pydantic Settings to the OpenAI Agents SDK process environment."""

from __future__ import annotations

import os

from agents import set_default_openai_key

from app.config import Settings


def configure_openai_from_settings(settings: Settings) -> bool:
    """
    Load OPENAI_API_KEY from Settings into os.environ and the Agents SDK.

    Call once at app startup (see app.main). Returns True when a non-empty key
    was configured.
    """
    api_key = settings.openai_api_key.get_secret_value()
    if not api_key:
        return False
    os.environ.setdefault("OPENAI_API_KEY", api_key)
    set_default_openai_key(api_key)
    return True


def is_openai_configured(settings: Settings) -> bool:
    """True when Settings has a non-empty API key (does not validate with OpenAI)."""
    return bool(settings.openai_api_key.get_secret_value().strip())
