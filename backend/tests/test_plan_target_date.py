"""H2 regression: the saved lesson plan carries the chosen lesson date, not the
draft-creation date. Deterministic; no agent/network."""

import re

from app.teacher_agent.wiki.context_packs import empty_plan_template
from app.teacher_agent.wiki.parsing import normalize_plan_target_date

_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")


def _target_date_line(markdown: str) -> str:
    for line in markdown.splitlines():
        if "Target date:" in line:
            return line
    return ""


def test_replaces_stale_date():
    plan = (
        "# Lesson Plan — Next lesson\n\n"
        "> Duration: 45 min | Target date: 2026-07-13\n\n"
        "## Learning goals\n\n- Understand carbon bonding\n"
    )
    out = normalize_plan_target_date(plan, "2026-09-28")
    assert "Target date: 2026-09-28" in out
    assert "2026-07-13" not in out
    # rest of the plan is untouched
    assert "## Learning goals" in out
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


def test_idempotent():
    plan = "# Lesson Plan\n\n> Duration: 45 min | Target date: 2026-09-28\n"
    once = normalize_plan_target_date(plan, "2026-09-28")
    twice = normalize_plan_target_date(once, "2026-09-28")
    assert once == twice
    assert once.count("Target date:") == 1


def test_inserts_when_missing():
    plan = "# Lesson Plan — Redox recap\n\n## Learning goals\n\n- x\n"
    out = normalize_plan_target_date(plan, "2026-09-28")
    assert "Target date: 2026-09-28" in out
    # inserted right after the title, only once
    assert out.count("Target date:") == 1
    assert out.index("Target date:") > out.index("# Lesson Plan")


def test_noop_when_no_lesson_date():
    plan = "# Lesson Plan\n\n> Duration: 45 min | Target date: 2026-07-13\n"
    assert normalize_plan_target_date(plan, "") == plan


def test_empty_template_has_no_baked_in_date():
    template = empty_plan_template(None)
    line = _target_date_line(template)
    assert line, "template should still carry a Target date line"
    assert not _ISO.search(line), f"template baked in a date: {line!r}"
    assert "(set when saving)" in line


def test_template_then_save_normalization_is_consistent():
    # Full path: draft template (placeholder) -> save with the chosen date.
    template = empty_plan_template(None)
    saved = normalize_plan_target_date(template, "2026-09-28")
    assert "Target date: 2026-09-28" in saved
    assert "(set when saving)" not in saved
    # structure preserved
    assert "## Learning goals" in saved
    assert "## Lesson flow" in saved
