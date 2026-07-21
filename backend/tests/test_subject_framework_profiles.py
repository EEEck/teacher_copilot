from app.teacher_agent.wiki.context_packs import build_active_subject_expert_context_trace
from app.teacher_agent.wiki.subject_frameworks import framework_for_class


CLASS_ID = "chemie_9b_2026_27"


def test_runtime_subject_expert_uses_route_and_adjustment_page_without_profile_file(wiki):
    old_profile = wiki.memory_dir(CLASS_ID) / "teaching_framework_profile.md"
    adjustment_path = wiki.memory_paths(CLASS_ID)["teaching_framework_adjustments"]
    adjustment = "Start formal terminology after a phenomenon-first observation."
    wiki.write_text(
        adjustment_path,
        "# Teaching Framework Adjustments\n\n## Prefer\n- " + adjustment + "\n",
    )

    trace = build_active_subject_expert_context_trace(wiki, CLASS_ID, purpose="plan")

    assert not old_profile.exists()
    assert "# Chemistry Grade 9 NTG - key summary" in trace["text"]
    assert adjustment in trace["text"]
    assert "teaching_framework_profile.md" not in trace["text"]


def test_framework_route_rejects_mismatched_curriculum_subject(wiki):
    path = wiki.class_dir(CLASS_ID) / "curriculum_profile.md"
    original = path.read_text(encoding="utf-8")
    path.write_text(original.replace("subject: chemie", "subject: physik"), encoding="utf-8")

    try:
        framework_for_class(wiki, CLASS_ID)
    except ValueError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("Expected mismatched curriculum subject to be rejected")
