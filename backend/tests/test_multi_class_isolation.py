"""A second class must not inherit the first one's memory, log, or index.

These behaviors were correct by accident while `chemie_9b_2026_27` was the only
class in the wiki. Creating classes makes them reachable.
"""

from app.teacher_agent.wiki import parsing
from app.teacher_agent.wiki.context_packs import (
    build_active_subject_expert_context_trace,
)


ACTIVE_CLASS = "chemie_9b_2026_27"


def _add_bare_class(wiki, class_id="physik_9a_2026_27", *, curriculum=True):
    """A class the factory could produce: config, no lessons, no framework."""
    root = wiki.root / "wiki" / "classes" / class_id
    root.mkdir(parents=True)
    (root / "class_config.md").write_text(
        "# Physik 9a — 2026/27\n\nsubject: physik\n", encoding="utf-8"
    )
    if curriculum:
        (root / "curriculum_profile.md").write_text(
            "---\n"
            "state: BY\n"
            "school_type: Gymnasium\n"
            "branch: NTG\n"
            "grade: 9\n"
            "subject: physik\n"
            "---\n"
            "# Curriculum Profile — Physik 9a\n",
            encoding="utf-8",
        )
    return class_id


def test_plan_context_degrades_when_no_framework_covers_the_route(wiki):
    class_id = _add_bare_class(wiki)

    trace = build_active_subject_expert_context_trace(wiki, class_id, purpose="plan")

    assert "No reviewed teaching framework" in trace["text"]
    names = [section["name"] for section in trace["sections"]]
    assert "Selected teaching framework" in names


def test_plan_context_degrades_when_curriculum_profile_is_missing(wiki):
    class_id = _add_bare_class(wiki, curriculum=False)

    trace = build_active_subject_expert_context_trace(wiki, class_id, purpose="plan")

    assert "No reviewed teaching framework" in trace["text"]


def test_covered_route_still_loads_its_framework(wiki):
    trace = build_active_subject_expert_context_trace(
        wiki, ACTIVE_CLASS, purpose="plan"
    )

    assert "No reviewed teaching framework" not in trace["text"]
    assert "Effective teaching framework" in trace["text"]


def test_snapshot_last_commit_does_not_leak_across_classes(wiki):
    class_id = _add_bare_class(wiki)

    seeded = wiki.get_snapshot(ACTIVE_CLASS)
    fresh = wiki.get_snapshot(class_id)

    assert seeded.last_committed_date is not None
    assert fresh.last_committed_date is None
    assert fresh.recent_lessons == []


def test_empty_course_state_does_not_report_a_heading_as_the_current_unit(wiki):
    class_id = _add_bare_class(wiki)
    (wiki.root / "wiki" / "classes" / class_id / "course_state.md").write_text(
        "# Course State\n\n## Current unit\n\n## Last lesson\n", encoding="utf-8"
    )

    assert wiki.get_snapshot(class_id).current_unit == "Not set"


def test_log_lookup_is_scoped_to_the_requested_class(wiki):
    class_id = _add_bare_class(wiki)

    assert wiki._parse_log_by_date(ACTIVE_CLASS)
    assert wiki._parse_log_by_date(class_id) == {}
    assert wiki._latest_log_commit(class_id) == {}


def test_legacy_log_entry_is_attributed_from_its_written_paths(wiki):
    """The seeded log predates the `> Class:` line and beta workspaces hold copies."""
    header = "## [2026-05-01T12:00:00] ingest | 2026-10-01 — Demo (id:abc12345)"
    block = (
        header
        + "\n> Lesson date: 2026-10-01"
        + "\n- Updated: wiki/classes/chemie_9b_2026_27/lessons/2026-10-01/lesson_results.md"
    )

    meta = parsing.parse_log_entry(header, block)

    assert meta["class_id"] == ACTIVE_CLASS


def test_explicit_class_line_wins_over_paths(wiki):
    header = "## [2026-05-01T12:00:00] ingest | 2026-10-01 — Demo (id:abc12345)"
    block = (
        header
        + "\n> Class: physik_9a_2026_27"
        + "\n> Lesson date: 2026-10-01"
        + "\n- Updated: wiki/classes/physik_9a_2026_27/timeline.md"
    )

    assert parsing.parse_log_entry(header, block)["class_id"] == "physik_9a_2026_27"


def test_index_context_does_not_fall_back_to_the_whole_file(wiki):
    class_id = _add_bare_class(wiki)

    index_text = wiki.read_wiki_index(class_id)

    assert ACTIVE_CLASS not in index_text


def test_class_label_strips_the_legacy_file_title_prefix(wiki):
    """The seeded page is titled "# Class Config — Chemie 9b"; that is not a label."""
    assert wiki.get_class(ACTIVE_CLASS).label == "Chemie 9b"


def test_workspace_without_class_directories_reports_no_classes(wiki, tmp_path):
    import shutil

    shutil.rmtree(wiki.root / "wiki" / "classes")

    assert wiki.list_classes() == []
