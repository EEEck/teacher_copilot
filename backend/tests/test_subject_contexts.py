from app.teacher_agent.wiki.context_packs import (
    build_active_class_core_context_trace,
    build_active_subject_expert_context_trace,
    build_base_assistant_context_trace,
)


CLASS_ID = "chemie_9b_2026_27"


def test_plan_composes_shared_framework_and_class_adjustments_once(wiki):
    trace = build_active_subject_expert_context_trace(wiki, CLASS_ID, purpose="plan")
    sources = {section["source"] for section in trace["sections"]}

    assert "# Chemie" in trace["text"]
    assert "# Chemistry Grade 9 NTG - key summary" in trace["text"]
    assert "# Teaching Framework Adjustments" in trace["text"]
    assert "## Trusted source index" in trace["text"]
    assert {section["authority"] for section in trace["sections"]} >= {
        "curated_guidance",
        "teacher_adjusted_class_profile",
        "official_source_index",
    }
    assert "wiki/subjects/chemie/teaching_frameworks/09/key_summary.md" in sources
    assert (
        "wiki/classes/chemie_9b_2026_27/memory/teaching_framework_adjustments.md"
        in sources
    )


def test_framework_adjustments_are_not_duplicated_in_active_class_core(wiki):
    adjustment_path = wiki.memory_paths(CLASS_ID)["teaching_framework_adjustments"]
    adjustment = "Use paired particle-model sketches before symbolic equations."
    wiki.write_text(
        adjustment_path,
        "# Teaching Framework Adjustments\n\n## Prefer\n- " + adjustment + "\n",
    )

    core = build_active_class_core_context_trace(wiki, CLASS_ID)
    subject = build_active_subject_expert_context_trace(wiki, CLASS_ID, purpose="plan")

    assert adjustment not in core["text"]
    assert adjustment in subject["text"]
    assert all(
        section["source"] != wiki.rel_wiki(adjustment_path)
        for section in core["sections"]
    )


def test_ingest_gets_subject_route_but_not_detailed_pedagogy(wiki):
    trace = build_active_subject_expert_context_trace(wiki, CLASS_ID, purpose="ingest")

    assert "Subject route: chemie | Grade: 9 | Branch: NTG" in trace["text"]
    assert "Teaching Framework Profile" not in trace["text"]
    assert "## Trusted source index" not in trace["text"]


def test_base_assistant_context_keeps_teacher_separate_from_class_facts(wiki):
    trace = build_base_assistant_context_trace(wiki, CLASS_ID, purpose="plan")

    assert "# Teacher context (global)" in trace["text"]
    assert "# Active class core context" in trace["text"]
    assert "Subject route: chemie | Grade: 9 | Branch: NTG" in trace["text"]
    assert trace["nested"]["teacher_layer"]["text"] not in trace["nested"]["active_class_core"]["text"]
