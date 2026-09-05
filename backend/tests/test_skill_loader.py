"""Contracts for the reviewable lesson-production skill files."""

from app.teacher_agent.skills import loader
from app.teacher_agent.skills.loader import (
    compose_active_skill,
    load_skill,
    load_subject_reference,
)


def test_local_skill_filenames_are_product_neutral():
    assert loader._SKILL_FILES == {
        "course_network": "course_network_procedure.md",
        "lesson_planning": "lesson_planning_procedure.md",
        "differentiation": "lesson_differentiation_procedure.md",
        "materials_use": "materials_use_procedure.md",
    }


def test_materials_use_skill_treats_remaining_uploads_as_a_set():
    skill = load_skill("materials_use")
    assert "Remaining session materials are a **set**" in skill
    assert "every** listed material" in skill or "cover **every** listed material" in skill
    assert "Material: material_id" in skill


def test_planning_core_is_reviewable_and_requires_subject_grounding():
    skill = load_skill("lesson_planning")

    assert "# Lesson Planning Production Procedure" in skill
    assert "Route" in skill
    assert "mandatory" in skill.lower()
    assert "subject reference" in skill.lower()
    assert "Ground" in skill


def test_planning_pre_delivery_check_lists_package_integrity_items():
    skill = load_skill("lesson_planning")

    assert "Pre-delivery check" in skill
    assert "Materials ↔ phases agree both ways" in skill
    assert "Shared task wording matches" in skill
    assert "Phase minutes include transitions" in skill
    assert "Student section has no teacher diagnostic language" in skill
    assert "Exit evidence has sort buckets" in skill
    assert "central question and core evidence task across routes" in skill
    assert "scaffolds appear as" in skill
    assert "Consistency sweep" in skill
    assert "lesson_artifact" not in skill


def test_chemie_9_ntg_reference_contains_required_science_pedagogy():
    reference = load_subject_reference("chemie", 9, "NTG")

    assert "# Bavaria Chemistry - Gymnasium Grade 9 NTG" in reference
    assert "Investigation before explanation" in reference
    assert "What / why / teacher move" in reference
    assert "particle" in reference.lower()
    assert "NGSS" not in reference
    assert "Learning Commons" not in reference


def test_chemie_9_ntg_reference_has_the_subject_specific_production_map():
    reference = load_subject_reference("chemie", 9, "NTG")

    for heading in (
        "## Clarify",
        "## Standards grounding",
        "## Build the lesson",
        "## Course branch",
        "## Section structure",
        "## Exit evidence guidance",
        "## Writing the canonical Markdown package",
    ):
        assert heading in reference

    assert "C8" in reference
    assert "C9" in reference
    assert "observation" in reference
    assert "particle model" in reference
    assert "explanation" in reference


def test_composed_planning_skill_combines_core_reference_and_differentiation():
    skill = compose_active_skill("chemie", 9, "NTG", "planning")

    assert "# Lesson Planning Production Procedure" in skill
    assert "# Bavaria Chemistry - Gymnasium Grade 9 NTG" in skill
    assert "# Lesson Differentiation Procedure" in skill


def test_differentiation_core_preserves_routed_workflow_and_eight_rules():
    skill = load_skill("differentiation")

    for heading in (
        "## Step 0 — Route",
        "## Step 1 — Identify the source lesson",
        "## Step 2 — Ground in trusted sources",
        "## Step 3 — The differentiation rules",
        "## Step 4 — The draft offer",
        "## Step 5 — Output",
        "## Step 6 — Complete",
    ):
        assert heading in skill

    for rule in range(1, 9):
        assert f"### R{rule} —" in skill

    assert "same central Chemistry question" in skill
    assert "Consistency sweep" in skill
    assert "Materials ↔ phases agree both ways" in skill
    assert "Shared task wording matches" in skill
    assert "Exit evidence has sort buckets" in skill
    assert "scaffolds appear as task design" in skill
    assert "lesson_artifact" not in skill


def test_unknown_subject_or_grade_has_no_subject_reference():
    assert load_subject_reference("physik", 9, "NTG") == ""
    assert load_subject_reference("chemie", 10, "NTG") == ""
