"""Contracts for the reviewable lesson-production skill files."""

from app.teacher_agent.skills.loader import (
    compose_active_skill,
    load_skill,
    load_subject_reference,
)


def test_planning_core_is_reviewable_and_requires_subject_grounding():
    skill = load_skill("lesson_planning")

    assert "# Lesson Planning Production Procedure" in skill
    assert "Route" in skill
    assert "mandatory" in skill.lower()
    assert "subject reference" in skill.lower()
    assert "Ground" in skill


def test_chemie_9_ntg_reference_contains_required_science_pedagogy():
    reference = load_subject_reference("chemie", 9, "NTG")

    assert "# Bavaria Chemistry - Gymnasium Grade 9 NTG" in reference
    assert "Investigation before explanation" in reference
    assert "What / why / teacher move" in reference
    assert "particle" in reference.lower()
    assert "NGSS" not in reference
    assert "Learning Commons" not in reference


def test_composed_planning_skill_combines_core_reference_and_differentiation():
    skill = compose_active_skill("chemie", 9, "NTG", "planning")

    assert "# Lesson Planning Production Procedure" in skill
    assert "# Bavaria Chemistry - Gymnasium Grade 9 NTG" in skill
    assert "# Lesson Differentiation Procedure" in skill


def test_unknown_subject_or_grade_has_no_subject_reference():
    assert load_subject_reference("physik", 9, "NTG") == ""
    assert load_subject_reference("chemie", 10, "NTG") == ""
