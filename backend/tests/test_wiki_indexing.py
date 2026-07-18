"""Tests for wiki index and log."""

import re
import shutil
from pathlib import Path

from app.teacher_agent.wiki_store import WikiStore


def test_rebuild_index_includes_sections(tmp_path: Path):
    seed = Path(__file__).resolve().parent.parent / "teacher_wiki"
    root = tmp_path / "teacher_wiki"
    shutil.copytree(seed, root)
    wiki = WikiStore(root=root)
    wiki.rebuild_index()
    index = wiki.read_text(wiki.index_path)
    assert "## Classes" in index
    assert "### Lessons" in index
    assert "### Students" in index
    assert "### Curriculum & trusted sources" in index
    assert "Curriculum profile" in index
    assert "Trusted source index" in index
    assert "chemie_9b_2026_27" in index


def test_append_log_iso_timestamp(tmp_path: Path):
    wiki = WikiStore(root=tmp_path)
    wiki.write_text(wiki.log_path, "# Wiki Log\n")
    wiki._append_log(
        "test_class",
        "2099-01-01",
        "Test Log Entry",
        ["wiki/test.md"],
        kind="test",
    )
    log_after = wiki.read_text(wiki.log_path)
    assert re.search(r"##\s*\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\]", log_after)
    assert "> Lesson date: 2099-01-01" in log_after
