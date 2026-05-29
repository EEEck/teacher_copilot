from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _BACKEND_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = "gpt-4o-mini"
    agent_timeout_seconds: float = 90.0
    agent_max_turns: int = 16
    wiki_root: Path = Path(__file__).resolve().parent.parent / "teacher_wiki"
    cors_origins: list[str] = ["http://localhost:3000"]
    app_env: Literal["development", "production"] = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()
