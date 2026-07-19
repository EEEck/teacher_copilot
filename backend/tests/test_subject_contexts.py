from app.teacher_agent.wiki.context_packs import (
    build_active_subject_expert_context_trace,
    build_base_assistant_context_trace,
)


CLASS_ID = "chemie_9b_2026_27"


def test_plan_gets_one_compiled_subject_expert_not_the_base_summary(wiki):
    trace = build_active_subject_expert_context_trace(wiki, CLASS_ID, purpose="plan")

    assert "# Chemie" in trace["text"]
    assert "# Teaching Framework Profile - chemie_9b_2026_27" in trace["text"]
    assert "## Trusted source index" in trace["text"]
    assert "Chemistry Grade 9 NTG - key summary" not in trace["text"]
    assert {section["authority"] for section in trace["sections"]} >= {
        "curated_guidance",
        "teacher_adjusted_class_profile",
        "official_source_index",
    }


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
