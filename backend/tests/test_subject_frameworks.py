from app.teacher_agent.wiki.subject_frameworks import (
    compose_class_framework_profile,
    load_framework_index,
    select_framework,
)


def test_selects_the_grade_9_ntg_framework_from_the_shared_library(wiki):
    index = load_framework_index(wiki, "chemie")
    framework = select_framework(wiki, "chemie", 9, "NTG")

    assert index.subject == "chemie"
    assert framework.grade == 9
    assert framework.branch == "NTG"
    assert framework.path.endswith("teaching_frameworks/09/key_summary.md")
    assert "particle" in framework.text.lower()
    assert "by-lehrplanplus-chemie-9-ntg" in framework.source_refs


def test_compiled_class_profile_inherits_base_and_keeps_only_approved_adjustments(wiki):
    framework = select_framework(wiki, "chemie", 9, "NTG")
    profile = compose_class_framework_profile(
        wiki,
        class_id="chemie_9b_2026_27",
        framework=framework,
        teacher_adjustments=["Use more particle-model drawings before equations."],
        class_cautions=["Contrast ion charge with oxidation number explicitly."],
    )

    assert "authority: teacher_adjusted_class_profile" in profile
    assert "wiki/subjects/chemie.md" in profile
    assert "teaching_frameworks/09/key_summary.md" in profile
    assert "Use more particle-model drawings before equations." in profile
    assert "Contrast ion charge with oxidation number explicitly." in profile
