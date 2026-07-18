"""Central context-size policy for agent prompts.

Why this module exists
----------------------
KlassenPilot previously applied a blunt ``context[:14_000]`` slice on stacked
context packs. That cut arbitrary tail content and caused the planning chat to
"forget" constraints — the original bug this architecture was built to fix.

Products like ChatGPT and Claude do **not** truncate composed prompts at a
fixed character boundary. They instead:

- keep recent turns in a session (trimming / compaction at phase boundaries)
- maintain structured working state outside the raw transcript
- inject curated, budgeted memory slices (not whole wiki dumps)
- fetch detail on demand via tools rather than stuffing everything upfront

Modern models (e.g. GPT-5.x with 200k+ token windows) can hold far more than
14k characters. The right limit is **signal quality**, not a legacy char cap.
We therefore:

1. **Never** blunt-cut composed instructions by default (backstop ``0``).
2. Use **per-section Hermes budgets** for durable wiki memory pages.
3. Use **structured session state** + configurable verbatim history for planning.
4. Reserve optional emergency backstops for pathological cases only.

All tunables live in ``Settings`` (``backend/app/config.py``) and are loaded
here via ``get_context_limits()``. See ``implementation_plans/context_management.md``.

References
----------
- OpenAI Agents SDK session memory & trimming:
  https://github.com/openai/openai-cookbook/blob/main/examples/agents_sdk/session_memory.ipynb
- OpenAI compaction at workflow boundaries:
  https://developers.openai.com/cookbook/examples/agents_sdk/building_reliable_agents_memory_compaction
- OpenAI context personalization (structured state):
  https://developers.openai.com/cookbook/examples/agents_sdk/context_personalization
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Settings

_BACKSTOP_MARKER = "\n\n[Context truncated at emergency backstop.]"


@dataclass(frozen=True)
class ContextLimits:
    """Resolved context policy for one process (from Settings / env)."""

    # --- Verbatim chat history (planning user message) -----------------------
    plan_history_turns: int

    # --- Plan chat system prompt ---------------------------------------------
    # Max chars for current lessonplan.md in system instructions. 0 = no limit.
    plan_current_chars: int
    # Emergency cap on full composed plan instructions. 0 = disabled.
    plan_instructions_backstop: int

    # --- Ingest / legacy stacked packs ---------------------------------------
    # Emergency cap on ingest context package before inject. 0 = disabled.
    # Prefer slim/budgeted packs over raising this.
    ingest_context_backstop: int

    # --- One-shot agents (opening, compile, lint, profile propose) ---------
    plan_opening_context_chars: int
    compile_context_chars: int
    plan_lesson_context_chars: int
    lint_context_chars: int
    profile_propose_field_chars: int
    memory_compact_source_chars: int

    # --- Ingest slim context / user input ------------------------------------
    ingest_history_turns: int
    ingest_previous_lesson_chars: int
    ingest_student_roster_chars: int
    ingest_course_state_chars: int
    ingest_open_loops_chars: int
    ingest_saved_plan_chars: int
    ingest_draft_chars: int
    upload_attachment_chars: int
    trusted_source_index_chars: int

    # --- Runtime session memory (PlanRuntime) --------------------------------
    state_list_limit: int
    state_bullet_max_chars: int
    briefs_inject_limit: int
    brief_lines_per_item: int
    briefs_store_cap: int
    raw_store_cap: int
    candidates_cap: int
    memory_capture_batch_max_candidates: int

    @classmethod
    def from_settings(cls, settings: Settings) -> ContextLimits:
        return cls(
            plan_history_turns=settings.plan_history_turns,
            plan_current_chars=settings.plan_current_chars,
            plan_instructions_backstop=settings.plan_instructions_backstop,
            ingest_context_backstop=settings.ingest_context_backstop,
            plan_opening_context_chars=settings.plan_opening_context_chars,
            compile_context_chars=settings.compile_context_chars,
            plan_lesson_context_chars=settings.plan_lesson_context_chars,
            lint_context_chars=settings.lint_context_chars,
            profile_propose_field_chars=settings.profile_propose_field_chars,
            memory_compact_source_chars=settings.memory_compact_source_chars,
            ingest_history_turns=settings.ingest_history_turns,
            ingest_previous_lesson_chars=settings.ingest_previous_lesson_chars,
            ingest_student_roster_chars=settings.ingest_student_roster_chars,
            ingest_course_state_chars=settings.ingest_course_state_chars,
            ingest_open_loops_chars=settings.ingest_open_loops_chars,
            ingest_saved_plan_chars=settings.ingest_saved_plan_chars,
            ingest_draft_chars=settings.ingest_draft_chars,
            upload_attachment_chars=settings.upload_attachment_chars,
            trusted_source_index_chars=settings.trusted_source_index_chars,
            state_list_limit=settings.plan_state_list_limit,
            state_bullet_max_chars=settings.plan_state_bullet_max_chars,
            briefs_inject_limit=settings.plan_briefs_inject_limit,
            brief_lines_per_item=settings.plan_brief_lines_per_item,
            briefs_store_cap=settings.plan_briefs_store_cap,
            raw_store_cap=settings.plan_raw_store_cap,
            candidates_cap=settings.plan_candidates_cap,
            memory_capture_batch_max_candidates=settings.memory_capture_batch_max_candidates,
        )


@lru_cache
def get_context_limits() -> ContextLimits:
    from app.config import get_settings

    return ContextLimits.from_settings(get_settings())


def apply_char_limit(text: str, limit: int, *, marker: str = _BACKSTOP_MARKER) -> str:
    """Return ``text`` unchanged when ``limit <= 0``; else truncate with marker."""
    text = text or ""
    if limit <= 0 or len(text) <= limit:
        return text
    return text[:limit] + marker


def clear_context_limits_cache() -> None:
    """Test helper: drop cached limits after Settings override."""
    get_context_limits.cache_clear()
