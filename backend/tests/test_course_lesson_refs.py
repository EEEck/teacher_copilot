import json

import pytest

from app.course_network.lesson_refs import (
    build_plan_course_refs,
    read_plan_course_refs,
    write_plan_course_refs,
)
from app.course_network.models import CourseNetworkDocument
from app.course_network.seeds import load_seed_for_class
from tests.conftest import CLASS_ID


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
    write_plan_course_refs(wiki, CLASS_ID, "2026-10-05", plan, {"class_id": CLASS_ID, "node_ids": [node.id]})
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
        "Use the class concept map node " + format_id.format(selected.id)
        + ". Also " + format_id.format("invented-concept")
        + " and " + format_id.format(retired.id)
        + ". Mention a longer unrelated identifier " + format_id.format(other.id + "-extra")
        + ". A topic title alone is not a citation: " + format_id.format(other.title)
    )
    refs = build_plan_course_refs(wiki, CLASS_ID, plan)
    assert refs["node_ids"] == [selected.id]
    assert refs["kind"] == "planned"
