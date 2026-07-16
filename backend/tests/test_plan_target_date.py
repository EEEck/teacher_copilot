"""H2 regression (v2): drafts carry no target date; the chosen lesson date is
stamped at the save boundary. Deterministic; no agent/network."""

from app.teacher_agent.wiki.context_packs import empty_plan_template
from app.teacher_agent.wiki.parsing import normalize_plan_target_date


def test_template_has_no_target_date():
    template = empty_plan_template(None)
    assert "Target date" not in template
    assert "> Duration: 45 min" in template
    # Matches the plan prompt's mandated structure (prompts.py).
    assert "## Learning goals" in template
    assert "## Lesson flow" in template


def test_stamps_date_onto_duration_line():
    plan = "# Lesson Plan — Redox recap\n\n> Duration: 45 min\n\n## Learning goals\n\n- x\n"
    out = normalize_plan_target_date(plan, "2026-09-28")
    assert "> Duration: 45 min | Target date: 2026-09-28" in out
    assert out.count("Target date:") == 1
    assert "## Learning goals" in out


def test_replaces_stale_date_in_legacy_combined_line():
    # In-flight drafts created before v2 still carry a baked-in date.
    plan = (
        "# Lesson Plan — Next lesson\n\n"
        "> Duration: 45 min | Target date: 2026-07-13\n\n"
        "## Learning goals\n\n- Understand carbon bonding\n"
    )
    out = normalize_plan_target_date(plan, "2026-09-28")
    assert "Target date: 2026-09-28" in out
    assert "2026-07-13" not in out
    assert "Understand carbon bonding" in out


def test_replaces_placeholder():
    plan = (
        "# Lesson Plan — Next lesson\n\n"
        "> Duration: 45 min | Target date: (set when saving)\n\n"
        "## Learning goals\n"
    )
    out = normalize_plan_target_date(plan, "2026-09-28")
    assert "Target date: 2026-09-28" in out
    assert "(set when saving)" not in out


def test_replace_preserves_trailing_segment():
    # Regex must stop at "|" — never eat a following segment.
    plan = "# Lesson Plan\n\n> Target date: 2026-07-13 | Duration: 45 min\n"
    out = normalize_plan_target_date(plan, "2026-09-28")
    assert "Target date: 2026-09-28" in out
    assert "| Duration: 45 min" in out
    assert "2026-07-13" not in out


def test_idempotent():
    plan = "# Lesson Plan\n\n> Duration: 45 min\n"
    once = normalize_plan_target_date(plan, "2026-09-28")
    twice = normalize_plan_target_date(once, "2026-09-28")
    assert once == twice
    assert once.count("Target date:") == 1


def test_inserts_after_title_when_no_duration_line():
    plan = "# Lesson Plan — Redox recap\n\n## Learning goals\n\n- x\n"
    out = normalize_plan_target_date(plan, "2026-09-28")
    assert "Target date: 2026-09-28" in out
    assert out.count("Target date:") == 1
    assert out.index("Target date:") > out.index("# Lesson Plan")


def test_noop_when_no_lesson_date():
    plan = "# Lesson Plan\n\n> Duration: 45 min\n"
    assert normalize_plan_target_date(plan, "") == plan


def test_template_then_save_composition():
    # Full path: dateless draft template -> save with the chosen date.
    template = empty_plan_template(None)
    saved = normalize_plan_target_date(template, "2026-09-28")
    assert "> Duration: 45 min | Target date: 2026-09-28" in saved
    assert "## Learning goals" in saved
    assert "## Lesson flow" in saved
