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
    # Two model ids. STRONG is the newest/best model; CHEAP is the small model.
    # Set the ids here when a newer model ships. Which call class uses which, and
    # at what reasoning effort, is decided by MODEL_PROFILE below.
    openai_strong_model: str = "gpt-5.5"
    openai_cheap_model: str = "gpt-5.4-mini"
    # Call classes (mem_v3 boundary):
    #   CHAT     = plan + ingest chat (high volume, user-facing; capture happens
    #              here, but the sweep backstops it).
    #   IMPORTANT= the Memory Sweep consolidation ONLY (durable-memory judgment;
    #              rare) -> always the strong model at max reasoning.
    #   UTILITY  = compile, lint, plan-lesson, opening, compact, profile-propose
    #              (one-shots, non-durable) -> cheap, minimal reasoning.
    # Profiles (production = one model, reasoning-tiered; economy = cheap chat):
    #                CHAT model / effort | IMPORTANT model / effort | UTILITY effort
    #   production:  strong / high        | strong / xhigh           | minimal
    #   economy:     cheap  / medium      | strong / high            | minimal
    # UTILITY always runs on the CHAT model. Unset MODEL_PROFILE derives from
    # app_env (production -> production, else economy).
    model_profile: Literal["production", "economy"] | None = None
    # Per-call-class reasoning-effort overrides. None = use the profile default
    # (production: chat high / important xhigh / utility minimal;
    #  economy: chat medium / important high / utility minimal).
    openai_chat_reasoning_effort: ReasoningEffort | None = None
    openai_important_reasoning_effort: ReasoningEffort | None = None
    openai_utility_reasoning_effort: ReasoningEffort | None = None
    # Legacy alias for the chat effort (kept so existing .env files keep working).
    openai_reasoning_effort: ReasoningEffort | None = None
    agent_timeout_seconds: float = 240.0
    # A full lesson package can legitimately need several source/history tool
    # rounds plus synthesis; keep that budget separate from shorter workflows.
    plan_agent_timeout_seconds: float = 600.0
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
    # Compact trusted-source metadata/TOC injected into active class context.
    trusted_source_index_chars: int = 1200
    # Runtime session memory (PlanRuntime) — see context_limits.py
    plan_state_list_limit: int = 24
    plan_state_bullet_max_chars: int = 160
    plan_briefs_inject_limit: int = 12
    plan_brief_lines_per_item: int = 4
    plan_briefs_store_cap: int = 40
    plan_raw_store_cap: int = 60
    plan_candidates_cap: int = 50
    # Operational guard for one teacher-turn capture batch. This is not a
    # semantic limit; overflow is preserved as one review bundle.
    memory_capture_batch_max_candidates: int = 8
    wiki_root: Path = Path(__file__).resolve().parent.parent / "teacher_wiki"
    cors_origins: list[str] = ["http://localhost:3000"]
    app_env: Literal["development", "production"] = "development"
    beta_enabled: bool = False
    beta_data_root: Path = Path(__file__).resolve().parent.parent / "beta_data"
    beta_cookie_name: str = "kp_beta_session"
    beta_session_days: int = 30
    beta_cookie_secure: bool = False
    # Use "none" when the browser frontend is on a different site than the API
    # (e.g. separate Railway *.up.railway.app hosts). Requires cookie_secure=true.
    beta_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    beta_dev_workspace_id: str = ""
    # Local beta-only Memory V4 diagnostic capture. This is intentionally
    # disabled unless beta + development + this explicit flag are all set.
    memory_v4_debug_capture: bool = False
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

    def is_memory_v4_debug_capture_enabled(self) -> bool:
        return (
            self.beta_enabled
            and self.app_env == "development"
            and self.memory_v4_debug_capture
        )

    def resolved_model_profile(self) -> str:
        if self.model_profile is not None:
            return self.model_profile
        return "production" if self.app_env == "production" else "economy"

    def resolved_chat_model(self) -> str:
        """CHAT (plan + ingest): strong in production, cheap in economy."""
        if self.resolved_model_profile() == "production":
            return self.openai_strong_model
        return self.openai_cheap_model

    def resolved_important_model(self) -> str:
        """IMPORTANT (Memory Sweep only): always the strong model."""
        return self.openai_strong_model

    def resolved_utility_model(self) -> str:
        """UTILITY (one-shots): follows the CHAT model tier."""
        return self.resolved_chat_model()

    def resolved_chat_effort(self) -> ReasoningEffort:
        override = self.openai_chat_reasoning_effort
        if override is None:
            override = self.openai_reasoning_effort  # legacy alias
        if override is not None:
            return override
        return "high" if self.resolved_model_profile() == "production" else "medium"

    def resolved_important_effort(self) -> ReasoningEffort:
        if self.openai_important_reasoning_effort is not None:
            return self.openai_important_reasoning_effort
        return "xhigh" if self.resolved_model_profile() == "production" else "high"

    def resolved_utility_effort(self) -> ReasoningEffort:
        if self.openai_utility_reasoning_effort is not None:
            return self.openai_utility_reasoning_effort
        return "minimal"


@lru_cache
def get_settings() -> Settings:
    return Settings()
