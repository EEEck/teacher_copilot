import multiprocessing
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

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


def _create_with_process_barrier(
    wiki_root: str,
    label: str,
    prior_learning: str,
    student_name: str,
    barrier,
    result_queue,
) -> None:
    from app.teacher_agent.wiki_store import WikiStore

    process_wiki = WikiStore(root=Path(wiki_root))
    original_skeleton = cp._skeleton

    def synchronized_skeleton(*args, **kwargs):
        skeleton = original_skeleton(*args, **kwargs)
        barrier.wait(timeout=10)
        return skeleton

    cp._skeleton = synchronized_skeleton
    spec = cp.ClassSpec(
        label=label,
        subject="chemie",
        grade=9,
        section="c",
        school_year="2026_27",
        prior_learning=prior_learning,
        student_names=(student_name,),
    )
    try:
        summary = cp.create_class(process_wiki, spec)
        result_queue.put(("created", summary.label))
    except cp.ClassProvisioningError as exc:
        result_queue.put(("collision", str(exc)))


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


def test_same_id_concurrency_has_one_complete_winner_and_one_handled_collision(
    wiki, monkeypatch
):
    barrier = threading.Barrier(2)
    original_skeleton = cp._skeleton

    def synchronized_skeleton(*args, **kwargs):
        skeleton = original_skeleton(*args, **kwargs)
        barrier.wait(timeout=5)
        return skeleton

    monkeypatch.setattr(cp, "_skeleton", synchronized_skeleton)
    specs = (
        _spec(
            label="Chemie 9c Alpha",
            prior_learning="Alpha prior",
            student_names=("Alpha Student",),
        ),
        _spec(
            label="Chemie 9c Beta",
            prior_learning="Beta prior",
            student_names=("Beta Student",),
        ),
    )

    def create(spec):
        try:
            return ("created", cp.create_class(wiki, spec))
        except cp.ClassProvisioningError as exc:
            return ("collision", str(exc))

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(create, specs))

    created = [value for kind, value in outcomes if kind == "created"]
    collisions = [value for kind, value in outcomes if kind == "collision"]
    assert len(created) == 1
    assert len(collisions) == 1
    assert "already exists" in collisions[0]

    winner = created[0]
    if winner.label.endswith("Alpha"):
        winner_markers = ("Chemie 9c Alpha", "Alpha prior", "Alpha Student")
        loser_markers = ("Chemie 9c Beta", "Beta prior", "Beta Student")
    else:
        winner_markers = ("Chemie 9c Beta", "Beta prior", "Beta Student")
        loser_markers = ("Chemie 9c Alpha", "Alpha prior", "Alpha Student")
    class_root = wiki.class_dir(winner.id)
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(class_root.rglob("*.md"))
    )
    assert all(marker in combined for marker in winner_markers)
    assert all(marker not in combined for marker in loser_markers)
    assert [item.id for item in wiki.list_classes()].count(winner.id) == 1


def test_same_id_processes_have_one_winner_under_the_wiki_creation_lock(wiki):
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(2)
    result_queue = context.Queue()
    process_specs = (
        ("Chemie 9c Process Alpha", "Process Alpha prior", "Process Alpha Student"),
        ("Chemie 9c Process Beta", "Process Beta prior", "Process Beta Student"),
    )
    processes = [
        context.Process(
            target=_create_with_process_barrier,
            args=(str(wiki.root), *spec, barrier, result_queue),
        )
        for spec in process_specs
    ]

    try:
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=30)
        assert [process.exitcode for process in processes] == [0, 0]
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
            process.join(timeout=5)

    outcomes = [result_queue.get(timeout=5) for _ in processes]
    created = [value for kind, value in outcomes if kind == "created"]
    collisions = [value for kind, value in outcomes if kind == "collision"]
    assert len(created) == 1
    assert len(collisions) == 1
    assert "already exists" in collisions[0]

    winner_label = created[0]
    winner_prefix = (
        "Process Alpha" if winner_label.endswith("Alpha") else "Process Beta"
    )
    loser_prefix = (
        "Process Beta" if winner_prefix.endswith("Alpha") else "Process Alpha"
    )
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(wiki.class_dir("chemie_9c_2026_27").rglob("*.md"))
    )
    assert winner_prefix in combined
    assert loser_prefix not in combined


def test_failed_staged_file_write_leaves_no_visible_class_and_retry_is_clean(
    wiki, monkeypatch
):
    class_id = "chemie_9c_2026_27"
    before_index = wiki.index_path.read_bytes()
    original_write = wiki.write_text

    def fail_course_state(path, content):
        if path.name == "course_state.md":
            raise OSError("injected class file write failure")
        return original_write(path, content)

    monkeypatch.setattr(wiki, "write_text", fail_course_state)
    with pytest.raises(OSError, match="injected class file write failure"):
        cp.create_class(wiki, _spec())

    assert not wiki.class_dir(class_id).exists()
    assert class_id not in {item.id for item in wiki.list_classes()}
    assert wiki.index_path.read_bytes() == before_index
    assert not list(wiki.root.glob(".class-provisioning-*"))

    monkeypatch.setattr(wiki, "write_text", original_write)
    assert cp.create_class(wiki, _spec()).id == class_id


def test_failed_index_rebuild_rolls_back_publication_and_allows_clean_retry(
    wiki, monkeypatch
):
    class_id = "chemie_9c_2026_27"
    before_index = wiki.index_path.read_bytes()
    original_rebuild = wiki.rebuild_index

    def rebuild_then_fail(*args, **kwargs):
        original_rebuild(*args, **kwargs)
        raise OSError("injected index rebuild failure")

    monkeypatch.setattr(wiki, "rebuild_index", rebuild_then_fail)
    with pytest.raises(OSError, match="injected index rebuild failure"):
        cp.create_class(wiki, _spec())

    assert not wiki.class_dir(class_id).exists()
    assert class_id not in {item.id for item in wiki.list_classes()}
    assert wiki.index_path.read_bytes() == before_index
    assert not list(wiki.root.glob(".class-provisioning-*"))

    monkeypatch.setattr(wiki, "rebuild_index", original_rebuild)
    assert cp.create_class(wiki, _spec()).id == class_id


def test_failed_class_publication_rebuild_preserves_newer_unrelated_index(
    wiki, monkeypatch
):
    failed_class_id = "chemie_9c_2026_27"
    existing_class_id = wiki.list_classes()[0].id
    overview_path = wiki.class_dir(existing_class_id) / "course_network" / "overview.md"
    original_rebuild = wiki.rebuild_index
    first_rebuild = True

    def publish_unrelated_update_then_fail(*args, **kwargs):
        nonlocal first_rebuild
        publication = original_rebuild(*args, **kwargs)
        if first_rebuild:
            first_rebuild = False
            wiki.write_text(overview_path, "# Independently published course network\n")
            original_rebuild()
            raise OSError("injected provisioning completion failure")
        return publication

    monkeypatch.setattr(wiki, "rebuild_index", publish_unrelated_update_then_fail)

    with pytest.raises(OSError, match="injected provisioning completion failure"):
        cp.create_class(wiki, _spec())

    index = wiki.index_path.read_text(encoding="utf-8")
    assert not wiki.class_dir(failed_class_id).exists()
    assert overview_path.exists()
    assert f"wiki/classes/{existing_class_id}/course_network/overview.md" in index
    assert f"## Class: {failed_class_id}" not in index


def test_service_accepts_exactly_999_roster_entries(wiki):
    names = tuple(f"Student {index}" for index in range(1, 1000))

    summary = cp.create_class(wiki, _spec(student_names=names))

    assert wiki.student_path(summary.id, "S-999").exists()
    assert not wiki.student_path(summary.id, "S-1000").exists()


def test_service_rejects_1000_roster_entries_before_writing(wiki):
    names = tuple(f"Student {index}" for index in range(1, 1001))

    with pytest.raises(cp.ClassProvisioningError, match="999"):
        cp.create_class(wiki, _spec(student_names=names))

    assert not wiki.class_dir("chemie_9c_2026_27").exists()


@pytest.mark.parametrize("name", ["Ada | Beispiel", "Ada\nBeispiel", "Ada\rBeispiel"])
def test_service_rejects_roster_names_that_break_markdown_tables(wiki, name):
    with pytest.raises(cp.ClassProvisioningError, match="student name"):
        cp.create_class(wiki, _spec(student_names=(name,)))

    assert not wiki.class_dir("chemie_9c_2026_27").exists()


@pytest.mark.parametrize(
    "overrides",
    [
        {"label": "L" * 121},
        {"school_year": "Y" * 21},
        {"prior_learning": "P" * 4001},
        {"student_names": ("S" * 121,)},
    ],
)
def test_service_rejects_oversized_text_before_writing(wiki, overrides):
    with pytest.raises(cp.ClassProvisioningError, match="at most"):
        cp.create_class(wiki, _spec(**overrides))

    assert not wiki.class_dir("chemie_9c_2026_27").exists()
