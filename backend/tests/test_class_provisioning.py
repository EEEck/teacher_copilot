"""Deterministic class creation: skeleton contents, validation, isolation."""

import pytest

from app.services import class_provisioning as cp
from app.teacher_agent.wiki.context_packs import (
    build_active_subject_expert_context_trace,
)


def _spec(**overrides) -> cp.ClassSpec:
    base = dict(
        label="Chemie 9c — 2026/27",
        subject="chemie",
        grade=9,
        section="c",
        school_year="2026_27",
    )
    base.update(overrides)
    return cp.ClassSpec(**base)


def test_offered_routes_are_exactly_those_with_a_shared_framework(wiki):
    routes = cp.available_routes(wiki)

    assert cp.CurriculumRoute("chemie", 9, "NTG") in routes
    assert cp.CurriculumRoute("physik", 9, "NTG") in routes
    # A subject with no framework library at all is never offered.
    assert not [route for route in routes if route.subject == "biologie"]


def test_create_class_writes_every_file_the_wiki_expects(wiki):
    summary = cp.create_class(wiki, _spec())

    assert summary.id == "chemie_9c_2026_27"
    written = {
        path.relative_to(wiki.class_dir(summary.id)).as_posix()
        for path in wiki.class_dir(summary.id).rglob("*.md")
    }
    # The four rollups plus timeline are linked unconditionally by rebuild_index,
    # so a missing one is a dead link in the teacher-visible index.
    assert {
        "class_config.md",
        "course_state.md",
        "curriculum_profile.md",
        "misconceptions.md",
        "open_loops.md",
        "students.md",
        "timeline.md",
        "trusted_sources.md",
    } <= written
    assert {
        f"memory/{path.name}" for path in wiki.memory_paths(summary.id).values()
    } <= written


def test_created_class_is_discoverable_and_correctly_routed(wiki):
    summary = cp.create_class(wiki, _spec())

    assert summary.id in {c.id for c in wiki.list_classes()}
    found = wiki.get_class(summary.id)
    assert (found.label, found.subject) == ("Chemie 9c — 2026/27", "chemie")

    profile = wiki.get_curriculum_profile(summary.id)
    assert (profile.grade, profile.branch, profile.subject) == ("9", "NTG", "chemie")


def test_created_class_loads_its_shared_framework(wiki):
    summary = cp.create_class(wiki, _spec())

    trace = build_active_subject_expert_context_trace(wiki, summary.id, purpose="plan")

    assert "No reviewed teaching framework" not in trace["text"]
    assert "Effective teaching framework" in trace["text"]


def test_created_class_starts_empty_and_does_not_inherit_the_seeded_class(wiki):
    summary = cp.create_class(wiki, _spec())

    snapshot = wiki.get_snapshot(summary.id)
    assert snapshot.current_unit == "Not set"
    assert snapshot.last_committed_date is None
    assert snapshot.recent_lessons == []
    assert wiki.get_timeline(summary.id).entries == []
    assert "chemie_9b_2026_27" not in wiki.read_wiki_index(summary.id)


def test_class_brief_reads_naturally_for_a_class_with_no_lessons(wiki):
    from app.config import Settings
    from app.teacher_agent.agents import AgentRunner

    summary = cp.create_class(wiki, _spec())
    # The real fallback, not the stub runner: this is deterministic and needs no key.
    brief = AgentRunner(Settings(openai_api_key=""), wiki)._class_brief_fallback(
        summary.id
    )

    assert "no lessons logged yet" in brief.summary
    assert "is in Not set" not in brief.summary


def test_prior_learning_is_recorded_without_inventing_lessons(wiki):
    summary = cp.create_class(
        wiki, _spec(prior_learning="Atomic structure and the periodic table in grade 8.")
    )

    course_state = wiki.read_text(wiki.roll_up_paths(summary.id)["course_state"])
    assert "## Prior learning (teacher-declared)" in course_state
    assert "periodic table" in course_state
    # It is context, not a lesson record.
    assert wiki.get_timeline(summary.id).entries == []


def test_roster_names_become_pseudonymous_student_pages(wiki):
    summary = cp.create_class(wiki, _spec(student_names=("Anna Bauer", "Tom Klein")))

    roster = wiki.read_text(wiki.class_dir(summary.id) / "students.md")
    assert "| S-001 | Anna Bauer |" in roster
    assert wiki.student_path(summary.id, "S-002").exists()
    assert "## Student Summary" in wiki.read_text(wiki.student_path(summary.id, "S-002"))


def test_trusted_sources_are_linked_for_the_route(wiki):
    summary = cp.create_class(wiki, _spec())

    linked = {source.source_id for source in wiki.list_trusted_sources(summary.id)}
    assert "by-lehrplanplus-chemie-9-ntg" in linked
    assert "by-lehrplanplus-chemie-8-ntg" in linked


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({"subject": "biologie"}, "not supported"),
        ({"grade": 7}, "No shared teaching framework"),
        ({"grade": 12}, "No shared teaching framework"),
        ({"branch": "SG"}, "NTG branch"),
        ({"label": "  "}, "label is required"),
        ({"section": "ab"}, "single letter"),
    ],
)
def test_rejected_specs(wiki, overrides, expected):
    with pytest.raises(cp.ClassProvisioningError, match=expected):
        cp.create_class(wiki, _spec(**overrides))


def test_duplicate_class_is_rejected(wiki):
    cp.create_class(wiki, _spec())

    with pytest.raises(cp.ClassProvisioningError, match="already exists"):
        cp.create_class(wiki, _spec())
