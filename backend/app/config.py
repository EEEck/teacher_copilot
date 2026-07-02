from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh"]

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
    openai_chat_model: str = "gpt-5.4-mini"
    openai_fast_model: str = "gpt-4o-mini"
    openai_reasoning_effort: ReasoningEffort = "medium"
    agent_timeout_seconds: float = 240.0
    agent_max_turns: int = 16

    # --- Context limits (see app/context_limits.py + context_management.md) ---
    # Verbatim teacher turns in the planning user message. Durable context lives
    # in structured session state; this window is for recent conversational tone.
    plan_history_turns: int = 8
    # Current lessonplan.md in plan system prompt. 0 = no char limit.
    plan_current_chars: int = 0
    # Emergency cap on full composed plan instructions. 0 = disabled (default).
    plan_instructions_backstop: int = 0
    # Emergency cap on stacked ingest context package. 0 = disabled (default).
    ingest_context_backstop: int = 0
    # One-shot / auxiliary agent context caps. 0 = no limit on that field.
    plan_opening_context_chars: int = 0
    compile_context_chars: int = 0
    plan_lesson_context_chars: int = 0
    lint_context_chars: int = 0
    profile_propose_field_chars: int = 0
    memory_compact_source_chars: int = 0
    # Ingest slim context / user-input field caps. 0 = no limit on that field.
    ingest_history_turns: int = 8
    ingest_previous_lesson_chars: int = 0
    ingest_student_roster_chars: int = 1800
    ingest_course_state_chars: int = 0
    ingest_open_loops_chars: int = 0
    ingest_saved_plan_chars: int = 0
    ingest_draft_chars: int = 0
    upload_attachment_chars: int = 0
    # Runtime session memory (PlanRuntime) — see context_limits.py
    plan_state_list_limit: int = 24
    plan_state_bullet_max_chars: int = 160
    plan_briefs_inject_limit: int = 12
    plan_brief_lines_per_item: int = 4
    plan_briefs_store_cap: int = 40
    plan_raw_store_cap: int = 60
    plan_candidates_cap: int = 50
    wiki_root: Path = Path(__file__).resolve().parent.parent / "teacher_wiki"
    cors_origins: list[str] = ["http://localhost:3000"]
    app_env: Literal["development", "production"] = "development"
    beta_enabled: bool = False
    beta_data_root: Path = Path(__file__).resolve().parent.parent / "beta_data"
    beta_cookie_name: str = "kp_beta_session"
    beta_session_days: int = 30
    beta_cookie_secure: bool = False
    beta_dev_workspace_id: str = ""
    # Debug endpoints exposing prompt assemblies, session messages, and raw tool
    # evidence. Default: enabled outside production, disabled in production.
    agent_trace_enabled: bool | None = None
    # Backward-compatible alias for existing local setups/docs.
    plan_trace_enabled: bool | None = None
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8010

    def is_agent_trace_enabled(self) -> bool:
        if self.agent_trace_enabled is not None:
            return self.agent_trace_enabled
        if self.plan_trace_enabled is not None:
            return self.plan_trace_enabled
        return self.app_env != "production"

    def is_plan_trace_enabled(self) -> bool:
        return self.is_agent_trace_enabled()


@lru_cache
def get_settings() -> Settings:
    return Settings()
