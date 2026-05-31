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
    index_hits = [h for h in hits if h.get("source") == "index"]
    assert index_hits, "expected index.md lesson table match for Redox"
    assert any("lesson_results.md" in h["path"] for h in index_hits)
    assert all(h["path"].startswith(f"wiki/classes/{CLASS_ID}/") for h in hits)


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
    assert dates == ["2026-05-25", "2026-05-29"]
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
