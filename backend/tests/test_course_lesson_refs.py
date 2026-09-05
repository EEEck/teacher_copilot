import json
import asyncio

import pytest

from app.course_network.lesson_refs import (
    build_plan_course_refs,
    read_plan_course_refs,
    write_plan_course_refs,
)
from app.course_network.models import CourseNetworkDocument
from app.course_network.seeds import load_seed_for_class
from tests.conftest import CLASS_ID


def _material_linked_network(wiki, workflow_drafts):
    from app.course_materials.import_service import CourseMaterialImportService
    from tests.test_course_material_import import Reviewer, extracted

    service = CourseMaterialImportService(wiki=wiki, workflow_drafts=workflow_drafts, reviewer=Reviewer())
    row = extracted(service, wiki)
    asyncio.run(service.review(CLASS_ID, row.draft_id))
    material = service.approve(CLASS_ID, row.draft_id, row.artifact_revision, row.artifact_hash)
    payload = load_seed_for_class(wiki, CLASS_ID).model_dump(mode="json")
    for node in payload["nodes"]:
        node["status"] = "adopted"
    payload["material_mappings"] = [{
        "id": "saved-link", "node_id": payload["nodes"][0]["id"],
        "material_id": material.material_id, "section_id": material.sections[0].id,
        "relation": "explains", "origin": "teacher",
    }]
    network = CourseNetworkDocument.model_validate(payload)
    wiki.write_course_network(CLASS_ID, network)
    return network, material


def test_material_citation_saves_separate_snapshot_without_direct_concept_or_result_evidence(wiki, workflow_drafts):
    from app.course_network.lesson_refs import lesson_associations_for_node, result_evidence_for_nodes

    network, material = _material_linked_network(wiki, workflow_drafts)
    node, other = network.nodes[:2]
    plan = f"Discuss the experiment using Material: `{material.material_id}`."
    refs = build_plan_course_refs(wiki, CLASS_ID, plan)
    assert refs["node_ids"] == []
    assert refs["material_node_refs"] == [{"node_id": node.id, "material_id": material.material_id, "section_id": material.sections[0].id}]
    date = "2026-10-05"
    lesson = wiki.lesson_dir(CLASS_ID, date)
    lesson.mkdir(parents=True, exist_ok=True)
    (lesson / "lesson_plan.md").write_text(plan, encoding="utf-8")
    write_plan_course_refs(wiki, CLASS_ID, date, plan, refs)
    (lesson / "lesson_results.md").write_text("Class discussed an unrelated warmup.", encoding="utf-8")
    # Later edits must not rewrite what the saved plan's material was linked to.
    payload = network.model_dump(mode="json")
    payload["revision"] += 1
    payload["material_mappings"][0]["node_id"] = other.id
    wiki.write_course_network(CLASS_ID, CourseNetworkDocument.model_validate(payload))
    associations = lesson_associations_for_node(wiki, CLASS_ID, node)
    assert [(item["kind"], item["relation"]) for item in associations] == [("planned", "uses_linked_material")]
    assert lesson_associations_for_node(wiki, CLASS_ID, other) == []
    assert result_evidence_for_nodes(wiki, CLASS_ID, [node, other]) == []
    assert read_plan_course_refs(wiki, CLASS_ID, date)["network_revision"] == network.revision


@pytest.mark.parametrize("citation", ["A chapter may be useful", "Material: unknown", "Material: {material_id}-unrelated"])
def test_uncited_material_never_associates_its_mapped_concepts(wiki, workflow_drafts, citation):
    _, material = _material_linked_network(wiki, workflow_drafts)
    refs = build_plan_course_refs(wiki, CLASS_ID, citation.format(material_id=material.material_id))
    assert refs["node_ids"] == []
    assert refs["material_node_refs"] == []


def test_material_association_does_not_replace_a_direct_concept_citation(wiki, workflow_drafts):
    from app.course_network.lesson_refs import lesson_associations_for_node

    network, material = _material_linked_network(wiki, workflow_drafts)
    node = network.nodes[0]
    plan = f"Course: {node.id}. Material: {material.material_id}."
    refs = build_plan_course_refs(wiki, CLASS_ID, plan)
    assert refs["node_ids"] == [node.id]
    lesson = wiki.lesson_dir(CLASS_ID, "2026-10-05")
    lesson.mkdir(parents=True, exist_ok=True)
    (lesson / "lesson_plan.md").write_text(plan, encoding="utf-8")
    write_plan_course_refs(wiki, CLASS_ID, lesson.name, plan, refs)
    assert [item["relation"] for item in lesson_associations_for_node(wiki, CLASS_ID, node)] == ["explicit_plan_reference"]


def test_archived_material_citation_does_not_create_new_material_associations(wiki, workflow_drafts):
    from app.course_materials.store import set_course_material_archived

    _, material = _material_linked_network(wiki, workflow_drafts)
    set_course_material_archived(wiki, CLASS_ID, material.material_id, True)
    refs = build_plan_course_refs(wiki, CLASS_ID, f"Material: {material.material_id}")
    assert refs["material_ids"] == []
    assert refs["material_node_refs"] == []


def test_saved_refs_are_explicit_and_tied_to_actual_plan(wiki):
    payload = load_seed_for_class(wiki, CLASS_ID).model_dump(mode="json")
    for node in payload["nodes"]:
        node["status"] = "adopted"
    network = CourseNetworkDocument.model_validate(payload)
    wiki.write_course_network(CLASS_ID, network)
    selected = network.nodes[0].id
    plan = f"# Lesson\nUse Course: `{selected}`. Also Course: invented."
    refs = build_plan_course_refs(wiki, CLASS_ID, plan)
    assert refs["node_ids"] == [selected]
    lesson = wiki.lesson_dir(CLASS_ID, "2026-10-05")
    lesson.mkdir(parents=True, exist_ok=True)
    (lesson / "lesson_plan.md").write_text(plan, encoding="utf-8")
    write_plan_course_refs(wiki, CLASS_ID, "2026-10-05", plan, refs)
    assert read_plan_course_refs(wiki, CLASS_ID, "2026-10-05")["node_ids"] == [selected]
    (lesson / "lesson_plan.md").write_text("changed plan", encoding="utf-8")
    assert read_plan_course_refs(wiki, CLASS_ID, "2026-10-05") is None
    assert wiki.load_course_network(CLASS_ID).revision == 1


def test_results_context_never_comes_from_a_plan_alone(wiki):
    from app.course_network.lesson_refs import result_evidence_for_nodes

    seed = load_seed_for_class(wiki, CLASS_ID)
    node = seed.nodes[0]
    lesson = wiki.lesson_dir(CLASS_ID, "2026-10-05")
    lesson.mkdir(parents=True, exist_ok=True)
    plan = "A planned lesson"
    (lesson / "lesson_plan.md").write_text(plan, encoding="utf-8")
    write_plan_course_refs(
        wiki,
        CLASS_ID,
        "2026-10-05",
        plan,
        {"class_id": CLASS_ID, "node_ids": [node.id]},
    )
    assert result_evidence_for_nodes(wiki, CLASS_ID, [node]) == []
    result = "We did not finish the topic. Repeat the diagnostic next time."
    (lesson / "lesson_results.md").write_text(result, encoding="utf-8")
    evidence = result_evidence_for_nodes(wiki, CLASS_ID, [node])
    assert evidence[0]["quote"] == result
    assert evidence[0]["relation"] == "results_of_lesson_planned_around_concept"


@pytest.mark.parametrize("format_id", ["**{}**", "`{}`"])
def test_saved_refs_recognize_exact_formatted_concept_ids(wiki, format_id):
    payload = load_seed_for_class(wiki, CLASS_ID).model_dump(mode="json")
    for node in payload["nodes"]:
        node["status"] = "adopted"
    payload["nodes"][-1]["status"] = "retired"
    network = CourseNetworkDocument.model_validate(payload)
    wiki.write_course_network(CLASS_ID, network)
    selected, other, retired = network.nodes[0], network.nodes[1], network.nodes[-1]
    plan = (
        "Use the class concept map node "
        + format_id.format(selected.id)
        + ". Also "
        + format_id.format("invented-concept")
        + " and "
        + format_id.format(retired.id)
        + ". Mention a longer unrelated identifier "
        + format_id.format(other.id + "-extra")
        + ". A topic title alone is not a citation: "
        + format_id.format(other.title)
    )
    refs = build_plan_course_refs(wiki, CLASS_ID, plan)
    assert refs["node_ids"] == [selected.id]
    assert refs["kind"] == "planned"


def test_concept_lesson_associations_separate_plan_and_results_and_ignore_stale_refs(
    wiki,
):
    from app.course_network import lesson_refs

    node = load_seed_for_class(wiki, CLASS_ID).nodes[0]
    date = "2026-10-05"
    lesson = wiki.lesson_dir(CLASS_ID, date)
    lesson.mkdir(parents=True, exist_ok=True)
    (lesson / "lesson_plan.md").write_text("Plan only", encoding="utf-8")
    write_plan_course_refs(
        wiki, CLASS_ID, date, "Plan only", {"class_id": CLASS_ID, "node_ids": [node.id]}
    )
    links = lesson_refs.lesson_associations_for_node(wiki, CLASS_ID, node)
    assert [link["kind"] for link in links] == ["planned"]
    assert links[0]["lesson_date"] == date
    assert links[0]["quote"] == ""
    (lesson / "lesson_results.md").write_text(
        "Unfinished experiment; repeat next lesson.", encoding="utf-8"
    )
    links = lesson_refs.lesson_associations_for_node(wiki, CLASS_ID, node)
    assert {link["kind"] for link in links} == {"planned", "approved_results"}
    assert (
        next(link for link in links if link["kind"] == "approved_results")["quote"]
        == "Unfinished experiment; repeat next lesson."
    )
    (lesson / "lesson_plan.md").write_text("Changed", encoding="utf-8")
    assert lesson_refs.lesson_associations_for_node(wiki, CLASS_ID, node) == []
    (lesson / "lesson_results.md").write_text(
        f"{node.title}: practice still needed.", encoding="utf-8"
    )
    assert (
        lesson_refs.lesson_associations_for_node(wiki, CLASS_ID, node)[0]["kind"]
        == "approved_results"
    )


def test_explicit_result_citation_does_not_match_a_longer_concept_id(wiki):
    from app.course_network.lesson_refs import result_evidence_for_nodes

    node = load_seed_for_class(wiki, CLASS_ID).nodes[0]
    lesson = wiki.lesson_dir(CLASS_ID, "2026-10-05")
    lesson.mkdir(parents=True, exist_ok=True)
    (lesson / "lesson_results.md").write_text(
        f"Course: {node.id}-unrelated was discussed.", encoding="utf-8"
    )
    assert result_evidence_for_nodes(wiki, CLASS_ID, [node]) == []


def test_inspector_keeps_old_approved_results_after_unrelated_later_lessons(wiki):
    from app.course_network.lesson_refs import lesson_associations_for_node

    node = load_seed_for_class(wiki, CLASS_ID).nodes[0]
    lesson = wiki.lesson_dir(CLASS_ID, "2026-10-05")
    lesson.mkdir(parents=True, exist_ok=True)
    (lesson / "lesson_plan.md").write_text("Old plan", encoding="utf-8")
    write_plan_course_refs(
        wiki,
        CLASS_ID,
        "2026-10-05",
        "Old plan",
        {"class_id": CLASS_ID, "node_ids": [node.id]},
    )
    (lesson / "lesson_results.md").write_text(
        "Experiment still unfinished.", encoding="utf-8"
    )
    for day in range(1, 22):
        later = wiki.lesson_dir(CLASS_ID, f"2026-11-{day:02}")
        later.mkdir(parents=True, exist_ok=True)
        (later / "lesson_results.md").write_text("Unrelated topic.", encoding="utf-8")
    associations = lesson_associations_for_node(wiki, CLASS_ID, node)
    assert {item["kind"] for item in associations} == {"planned", "approved_results"}
    assert (
        next(item for item in associations if item["kind"] == "approved_results")[
            "quote"
        ]
        == "Experiment still unfinished."
    )
