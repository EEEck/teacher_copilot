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
    assert "## Shared subject frameworks" in index
    assert "Chemistry teaching frameworks" in index
    assert "Teaching Framework Adjustments" in index
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


def test_latest_log_commit_is_class_scoped_with_interleaved_legacy_entries(
    tmp_path: Path,
):
    wiki = WikiStore(root=tmp_path)
    wiki.write_text(
        wiki.log_path,
        """# Wiki Log

## [2026-09-01T10:00:00] ingest | 2026-09-01 - Alpha One (id:a1000001)
> Lesson date: 2026-09-01
- Updated: wiki/classes/chemie_8a_2026_27/timeline.md

## [2026-09-02T10:00:00] ingest | 2026-09-02 - Beta One (id:b1000001)
> Class: chemie_9b_2026_27
> Lesson date: 2026-09-02
- Updated: wiki/classes/chemie_9b_2026_27/timeline.md

## [2026-09-03T10:00:00] ingest | 2026-09-03 - Alpha Two (id:a2000002)
> Class: chemie_8a_2026_27
> Lesson date: 2026-09-03
- Updated: wiki/classes/chemie_8a_2026_27/timeline.md

## [2026-09-04T10:00:00] ingest | 2026-09-04 - Beta Two (id:b2000002)
> Lesson date: 2026-09-04
- Updated: raw/classes/chemie_9b_2026_27/2026-09-04-beta-two.md
""",
    )

    assert wiki._latest_log_commit("chemie_8a_2026_27") == {
        "lesson_date": "2026-09-03",
        "committed_at": "2026-09-03T10:00:00",
        "title": "Alpha Two",
    }
    assert wiki._latest_log_commit("chemie_9b_2026_27") == {
        "lesson_date": "2026-09-04",
        "committed_at": "2026-09-04T10:00:00",
        "title": "Beta Two",
    }
