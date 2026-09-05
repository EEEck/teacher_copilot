import pytest

from app.config import Settings
from app.services.class_provisioning import ClassSpec, create_class
from app.teacher_agent.agents import AgentRunner


@pytest.mark.parametrize("kind", ["course_network_adopt", "course_network_edit", "compact"])
def test_nonlesson_writes_never_make_a_fresh_class_look_taught_or_logged(wiki, kind):
    created = create_class(wiki, ClassSpec(label="Own new class", subject="chemie", grade=8, section="a"))
    wiki._append_log(created.id, "2026-09-05", "Course setup or memory maintenance", [f"wiki/classes/{created.id}/course_network/overview.md"], kind=kind)
    snapshot = wiki.get_snapshot(created.id)
    assert snapshot.last_lesson_date is None
    assert snapshot.last_committed_date is None
    assert snapshot.last_committed_at is None
    assert snapshot.last_committed_title is None
    assert snapshot.recent_lessons == []
    runner = AgentRunner(Settings(openai_api_key=""), wiki)
    brief = runner._class_brief_fallback(created.id)
    assert "Last logged lesson" not in " ".join(brief.reasons)
    assert "2026-09-05" not in brief.model_dump_json()


def test_last_logged_lesson_keeps_approved_results_when_later_map_log_exists(wiki):
    created = create_class(wiki, ClassSpec(label="Own class", subject="chemie", grade=8))
    results = wiki.lesson_dir(created.id, "2026-09-07") / "lesson_results.md"
    wiki.write_text(results, "# Lesson Results — 2026-09-07 — First taught lesson\n\n## What was covered\n- Particle model\n")
    wiki._append_log(created.id, "2026-09-07", "First taught lesson", [wiki.rel_wiki(results)], kind="ingest")
    wiki._append_log(created.id, "2026-09-09", "Course map edit", [f"wiki/classes/{created.id}/course_network/overview.md"], kind="course_network_edit")
    snapshot = wiki.get_snapshot(created.id)
    assert snapshot.last_committed_date == "2026-09-07"
    assert snapshot.last_committed_title == "First taught lesson"
    runner = AgentRunner(Settings(openai_api_key=""), wiki)
    assert "Last logged lesson: 2026-09-07." in runner._class_brief_fallback(created.id).reasons
