import pytest

from app.teacher_agent.wiki.trusted_sources import (
    load_curriculum_profile,
    load_trusted_sources,
    read_source_for_class,
    search_sources_for_class,
)


def test_source_frontmatter_and_sections_are_parsed(wiki):
    sources = load_trusted_sources(wiki.root)
    source = sources["by-lehrplanplus-chemie-9-ntg"]
    assert source.authority == "official_curriculum"
    assert source.branch == "NTG"
    assert source.grade == "9"
    assert source.canonical_url.endswith("/fachlehrplan/gymnasium/9/chemie/ch-ntg")
    assert {section.id for section in source.sections} >= {"c9_atombau", "c9_molekuele"}


def test_class_profile_links_declared_sources(wiki):
    profile = load_curriculum_profile(wiki.root, "chemie_9b_2026_27")
    assert profile.branch == "NTG"
    assert profile.grade == "9"
    assert "by-lehrplanplus-chemie-9-ntg" in profile.source_ids


def test_search_returns_c9_source_for_atomic_structure_query(wiki):
    hits = search_sources_for_class(
        wiki.root, "chemie_9b_2026_27", "Atombau Periodensystem Elektronen", scope="active"
    )
    assert hits
    assert hits[0]["source_id"] == "by-lehrplanplus-chemie-9-ntg"
    assert hits[0]["section_id"] == "c9_atombau"


def test_read_rejects_unlinked_source(wiki):
    with pytest.raises(ValueError, match="not linked"):
        read_source_for_class(wiki.root, "chemie_9b_2026_27", "unlinked-source")


def test_compact_subject_guide_does_not_contain_full_source(wiki):
    subject = (wiki.root / "wiki" / "subjects" / "chemie.md").read_text(encoding="utf-8")
    assert "by-lehrplanplus-chemie-9-ntg" in subject
    assert "c9_atombau" not in subject
