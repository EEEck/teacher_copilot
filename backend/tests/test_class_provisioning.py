import pytest

from app.services import class_provisioning as cp
from app.teacher_agent.wiki.context_packs import (
    build_active_subject_expert_context_trace,
)


def _spec(**overrides) -> cp.ClassSpec:
    base = {
        "label": "Chemie 9c — 2026/27",
        "subject": "chemie",
        "grade": 9,
        "section": "c",
        "school_year": "2026_27",
    }
    base.update(overrides)
    return cp.ClassSpec(**base)


def test_offered_routes_are_exactly_chemie_8_and_9_ntg(wiki):
    assert cp.available_routes(wiki) == [
        cp.CurriculumRoute("chemie", 8, "NTG"),
        cp.CurriculumRoute("chemie", 9, "NTG"),
    ]


def test_create_class_writes_every_file_the_wiki_expects(wiki):
    summary = cp.create_class(wiki, _spec())

    assert summary.id == "chemie_9c_2026_27"
    written = {
        path.relative_to(wiki.class_dir(summary.id)).as_posix()
        for path in wiki.class_dir(summary.id).rglob("*.md")
    }
    assert {
        "class_config.md",
        "course_state.md",
        "curriculum_profile.md",
        "misconceptions.md",
        "open_loops.md",
        "students.md",
        "timeline.md",
        "trusted_sources.md",
        "memory/teaching_framework_adjustments.md",
    } <= written
    assert {
        f"memory/{path.name}" for path in wiki.memory_paths(summary.id).values()
    } <= written


def test_created_class_is_discoverable_and_correctly_routed(wiki):
    summary = cp.create_class(wiki, _spec())

    assert summary.id in {item.id for item in wiki.list_classes()}
    found = wiki.get_class(summary.id)
    assert (found.label, found.subject) == ("Chemie 9c — 2026/27", "chemie")
    profile = wiki.get_curriculum_profile(summary.id)
    assert (profile.grade, profile.branch, profile.subject) == ("9", "NTG", "chemie")


def test_created_class_loads_its_shared_framework(wiki):
    summary = cp.create_class(wiki, _spec())

    trace = build_active_subject_expert_context_trace(wiki, summary.id, purpose="plan")
    assert "No reviewed teaching framework" not in trace["text"]
    assert "Effective teaching framework" in trace["text"]


def test_a1_does_not_adopt_a_course_network(wiki):
    summary = cp.create_class(
        wiki, _spec(label="Chemie 8a — 2026/27", grade=8, section="a")
    )

    assert not (wiki.class_dir(summary.id) / "course_network" / "network.json").exists()


def test_prior_learning_and_roster_do_not_create_history(wiki):
    summary = cp.create_class(
        wiki,
        _spec(
            label="Chemie 8a — 2026/27",
            grade=8,
            section="a",
            prior_learning="Atombau und Periodensystem wurden bereits wiederholt.",
            student_names=("Ada Beispiel", "Ben Beispiel"),
        ),
    )

    course_state = wiki.read_text(wiki.class_dir(summary.id) / "course_state.md")
    students = wiki.read_text(wiki.class_dir(summary.id) / "students.md")
    assert "Atombau und Periodensystem" in course_state
    assert "S-001 | Ada Beispiel" in students
    assert "S-002 | Ben Beispiel" in students
    assert wiki.get_timeline(summary.id).entries == []
    assert wiki.get_snapshot(summary.id).recent_lessons == []


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"subject": "biologie"}, "not supported"),
        ({"grade": 7}, "No shared teaching framework"),
        ({"branch": "SG"}, "NTG"),
        ({"label": "  "}, "label is required"),
        ({"section": "ab"}, "single letter"),
    ],
)
def test_rejected_specs_do_not_create_a_class(wiki, overrides, expected):
    with pytest.raises(cp.ClassProvisioningError, match=expected):
        cp.create_class(wiki, _spec(**overrides))


def test_duplicate_class_is_rejected(wiki):
    cp.create_class(wiki, _spec())

    with pytest.raises(cp.ClassProvisioningError, match="already exists"):
        cp.create_class(wiki, _spec())
