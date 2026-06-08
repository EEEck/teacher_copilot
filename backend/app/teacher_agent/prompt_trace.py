"""Compatibility wrappers for local prompt diagnostics.

Prompt/context assembly lives in ``prompt_assembly.py``. Keep these names while
call sites and trace schemas are migrated so local traces and live model calls
share one assembly path.
"""

from __future__ import annotations

from app.teacher_agent.prompt_assembly import (
    build_plan_chat_prompt_assembly,
    build_plan_opening_prompt_assembly,
    build_plan_user_input_assembly,
    build_profiles_assembly,
)

build_plan_chat_prompt_trace = build_plan_chat_prompt_assembly
build_plan_opening_prompt_trace = build_plan_opening_prompt_assembly
build_plan_user_input_trace = build_plan_user_input_assembly
build_profiles_trace = build_profiles_assembly
