from app.teacher_agent.wiki.subject_frameworks import (
    framework_for_class,
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


def test_class_route_selects_shared_framework_without_class_profile_generation(wiki):
    framework = framework_for_class(wiki, "chemie_9b_2026_27")

    assert framework.path.endswith("teaching_frameworks/09/key_summary.md")
    assert not hasattr(wiki, "regenerate_framework_profile")


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


def test_framework_index_is_navigation_only_and_source_refs_resolve(wiki):
    index_path = (
        wiki.root / "wiki" / "subjects" / "chemie" / "teaching_frameworks" / "index.md"
    )
    index = wiki.read_text(index_path)
    source_ids = set(wiki.load_trusted_sources())

    assert "Chemistry Grade 9 NTG - key summary" not in index
    assert "by-lehrplanplus-chemie-9-ntg" in index
    for framework in load_framework_index(wiki, "chemie").entries:
        assert set(framework.source_refs) <= source_ids
