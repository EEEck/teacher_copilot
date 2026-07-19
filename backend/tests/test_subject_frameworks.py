from app.teacher_agent.wiki.subject_frameworks import (
    compose_class_framework_profile,
    load_framework_index,
    read_subject_guidance,
    search_subject_guidance,
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


def test_subject_guidance_search_stays_in_active_grade_branch_and_keeps_source_refs(wiki):
    hits = search_subject_guidance(wiki, "chemie_9b_2026_27", "representation particle")

    assert hits
    assert all("teaching_frameworks/09/" in hit["path"] for hit in hits)
    assert all(hit["grade"] == 9 for hit in hits)
    assert "by-lehrplanplus-chemie-9-ntg" in hits[0]["source_refs"]
    assert hits[0]["matched_terms"]
    assert len(hits[0]["snippet"]) <= 900


def test_subject_guidance_read_rejects_other_grade_and_path_traversal(wiki):
    payload = read_subject_guidance(
        wiki,
        "chemie_9b_2026_27",
        "wiki/subjects/chemie/teaching_frameworks/09/differentiation.md",
    )

    assert payload["page"] == "differentiation"
    assert payload["section"] == "full_page"
    assert "by-lehrplanplus-chemie-9-ntg" in payload["source_refs"]

    for forbidden in (
        "wiki/subjects/chemie/teaching_frameworks/08/key_summary.md",
        "wiki/subjects/chemie/teaching_frameworks/09/../../chemie.md",
    ):
        try:
            read_subject_guidance(wiki, "chemie_9b_2026_27", forbidden)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected {forbidden} to be rejected")
