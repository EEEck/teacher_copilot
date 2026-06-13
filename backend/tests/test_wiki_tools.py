"""Tests for chat wiki tool wiring."""

from app.teacher_agent.tools import WikiToolContext, create_chat_wiki_tools
from app.teacher_agent.wiki_store import WikiStore
from pathlib import Path

CLASS_ID = "chemie_9b_2026_27"
_WIKI_ROOT = Path(__file__).resolve().parent.parent / "teacher_wiki"


def test_create_chat_wiki_tools_exposes_mvp_names():
    wiki = WikiStore(root=_WIKI_ROOT)
    ctx = WikiToolContext(wiki=wiki, class_id=CLASS_ID)
    tools = create_chat_wiki_tools(ctx)
    names = {getattr(t, "name", None) for t in tools}
    assert names == {
        "list_lessons",
        "read_lesson",
        "read_lesson_range",
        "search_memory",
        "read_memory_page",
        "get_raw_evidence",
    }
