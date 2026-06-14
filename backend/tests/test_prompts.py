"""Regression tests for prompt rendering.

The `'title'` 500 came from rendering prompts with ``str.format`` while injected
wiki content contained literal ``{...}`` (e.g. ``wiki/classes/{class_id}/...``).
These tests pin that prompts are rendered with ``apply_prompt`` (plain
``str.replace``) and never raise ``KeyError`` regardless of injected content.
"""

from __future__ import annotations

import pytest

from app.teacher_agent.prompts import (
    CHAT_WIKI_TOOLS_POLICY,
    INGEST_SYSTEM,
    MEMORY_SKILL,
    PLAN_CHAT_SYSTEM,
    PLAN_SKILL,
    PLAN_WIKI_TOOLS_POLICY,
    PLAN_OPENING_SYSTEM,
    apply_prompt,
)

# Content that would break str.format: literal braces and a colliding key name.
HOSTILE_CONTEXT = (
    "wiki/classes/{class_id}/index.md\n"
    "# Lesson Plan — {title}\n"
    "Some rollup with {curly} {0} {} placeholders."
)


def test_apply_prompt_does_not_treat_braces_as_format_fields():
    out = apply_prompt(
        PLAN_CHAT_SYSTEM,
        teacher_context="Teacher context",
        active_class_core=HOSTILE_CONTEXT,
    )
    assert "{class_id}" in out  # left untouched, not interpreted
    assert "{active_class_core}" not in out  # placeholder was substituted


@pytest.mark.parametrize(
    "template,kwargs",
    [
        (
            PLAN_CHAT_SYSTEM,
            {"teacher_context": "Teacher context", "active_class_core": HOSTILE_CONTEXT},
        ),
        (PLAN_OPENING_SYSTEM, {"context": HOSTILE_CONTEXT}),
        (
            INGEST_SYSTEM,
            {
                "memory_skill": "Active skill: update_memory.",
                "sections": "- A\n- B",
                "teacher_context": "Teacher context",
                "context": HOSTILE_CONTEXT,
                "memory_runtime": "## Update-memory runtime state\n- phase: identify_target",
                "wiki_tools_policy": CHAT_WIKI_TOOLS_POLICY,
            },
        ),
    ],
)
def test_prompts_render_with_hostile_content(template, kwargs):
    # Must not raise (KeyError/IndexError/ValueError) and must substitute.
    out = apply_prompt(template, **kwargs)
    assert HOSTILE_CONTEXT in out
    for key in kwargs:
        assert "{" + key + "}" not in out


def test_apply_prompt_ignores_unknown_keys_safely():
    # Extra replacement keys not present in the template are a no-op, not an error.
    out = apply_prompt("hello {name}", name="world", unused="x")
    assert out == "hello world"


def test_plan_policy_uses_information_need_not_keyword_triggers():
    policy = PLAN_WIKI_TOOLS_POLICY.lower()
    assert "information need" in policy
    assert "source-backed claims" in policy
    assert "list_lessons" in policy
    assert "read_lesson_range" in policy


def test_memory_phase_skill_documents_transitions():
    skill = MEMORY_SKILL.lower()
    ingest = INGEST_SYSTEM.lower()

    assert "identify_target" in skill
    assert "collect_results" in skill
    assert "review_draft" in skill
    assert "state_patch.session_state.phase" in skill
    assert "stay in collect_results" in skill
    assert "ready to save" in skill
    assert "{memory_skill}" in ingest


def test_plan_phase_finalize_uses_semantic_teacher_intent_not_keyword_triggers():
    skill = PLAN_SKILL.lower()
    chat_system = PLAN_CHAT_SYSTEM.lower()

    assert "intent clearly indicates" in skill
    assert "accepted/finished" in skill
    assert "phase as conversation state" in chat_system
    assert "stay in lesson_refinement" in chat_system
    assert "intent clearly indicates" in chat_system
    assert "do not keyword-match a trigger list" in chat_system
    assert "do not treat that alone as a reason to set phase=finalize" in chat_system
