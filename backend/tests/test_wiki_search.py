"""Tests for index-first wiki search and chat read path guards."""

from datetime import date
from pathlib import Path

from app.teacher_agent.wiki_store import WikiStore
from app.teacher_agent.tools import _list_lessons_payload

CLASS_ID = "chemie_9b_2026_27"
_WIKI_ROOT = Path(__file__).resolve().parent.parent / "teacher_wiki"


def test_find_in_memory_matches_index_lesson_table():
    wiki = WikiStore(root=_WIKI_ROOT)
    hits = wiki.find_in_memory(CLASS_ID, "Redox", max_results=5)
    assert hits
    assert any("lesson_results.md" in h["path"] for h in hits)
    assert all({"path", "kind", "title", "snippet", "score", "matched_terms", "source"} <= set(h) for h in hits)
    assert all(h["path"].startswith(f"wiki/classes/{CLASS_ID}/") for h in hits)


def test_find_in_memory_ranks_long_query_by_terms():
    wiki = WikiStore(root=_WIKI_ROOT)
    hits = wiki.find_in_memory(
        CLASS_ID,
        "Plan the next 45-minute Chemie lesson: redox reactions applied to FCKW",
        max_results=5,
    )
    assert hits
    assert any("redox" in h["snippet"].lower() for h in hits)
    assert any("/lessons/" in h["path"] for h in hits)
    assert not any(h["path"].startswith("raw/") for h in hits)


def test_find_in_memory_prefers_compact_memory_for_profile_query():
    wiki = WikiStore(root=_WIKI_ROOT)
    hits = wiki.find_in_memory(
        CLASS_ID,
        "peer checking teaching patterns worked",
        max_results=5,
    )
    assert hits
    assert any(h["kind"] == "memory" for h in hits)
    assert any("matched_terms" in h and h["matched_terms"] for h in hits)


def test_build_class_relevance_corpus_is_class_scoped():
    wiki = WikiStore(root=_WIKI_ROOT)
    corpus = wiki.build_class_relevance_corpus(CLASS_ID)
    assert corpus["docs"]
    assert all(
        doc["path"].startswith(f"wiki/classes/{CLASS_ID}/")
        for doc in corpus["docs"]
    )


def test_list_class_pages_includes_compact_memory():
    wiki = WikiStore(root=_WIKI_ROOT)
    pages = wiki.list_class_pages(CLASS_ID, kind="memory")
    paths = {page["path"] for page in pages}
    assert f"wiki/classes/{CLASS_ID}/memory/teaching_patterns.md" in paths
    assert all(page["kind"] == "memory" for page in pages)


def test_find_in_memory_body_fallback_when_index_misses():
    wiki = WikiStore(root=_WIKI_ROOT)
    # Unlikely to appear in index one-liners but may appear in lesson body.
    hits = wiki.find_in_memory(CLASS_ID, "participation", max_results=3)
    assert hits
    assert all("path" in h and "snippet" in h for h in hits)


def test_search_wiki_compat_strips_source_field():
    wiki = WikiStore(root=_WIKI_ROOT)
    legacy = wiki.search_wiki(CLASS_ID, "Redox", max_results=3)
    assert legacy
    assert all(set(h.keys()) == {"path", "snippet"} for h in legacy)


def test_is_class_memory_path_allows_class_scoped_wiki():
    wiki = WikiStore(root=_WIKI_ROOT)
    ok = f"wiki/classes/{CLASS_ID}/lessons/2026-09-21/lesson_results.md"
    assert wiki.is_class_memory_path(CLASS_ID, ok)
    assert not wiki.is_class_memory_path(CLASS_ID, "wiki/classes/other_class/foo.md")
    assert not wiki.is_class_memory_path(CLASS_ID, "../../../etc/passwd")
    assert not wiki.is_class_memory_path(CLASS_ID, "index.md")


def test_list_lessons_payload_filters_by_date_range():
    wiki = WikiStore(root=_WIKI_ROOT)
    payload = _list_lessons_payload(
        wiki,
        CLASS_ID,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 31),
        max_results=10,
    )
    dates = [lesson["date"] for lesson in payload["lessons"]]
    assert dates == [
        "2026-05-07",
        "2026-05-14",
        "2026-05-21",
        "2026-05-25",
        "2026-05-29",
    ]
    assert all(lesson["paths"] for lesson in payload["lessons"])


def test_list_lessons_payload_topic_falls_back_to_lesson_body():
    wiki = WikiStore(root=_WIKI_ROOT)
    payload = _list_lessons_payload(
        wiki,
        CLASS_ID,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 31),
        topic="participation",
    )
    dates = [lesson["date"] for lesson in payload["lessons"]]
    assert "2026-05-25" in dates


def test_list_lessons_payload_reports_reversed_date_range():
    wiki = WikiStore(root=_WIKI_ROOT)
    payload = _list_lessons_payload(
        wiki,
        CLASS_ID,
        start_date=date(2026, 5, 31),
        end_date=date(2026, 5, 1),
    )
    assert payload["lessons"] == []
    assert payload["warnings"] == ["start_date must be on or before end_date"]
