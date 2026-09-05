import asyncio

import pytest

from app.course_materials.import_service import CourseMaterialImportService
from app.course_network.planning import build_course_planning_context
from app.course_network.models import CourseNetworkDocument, MaterialSectionReference
from app.course_network.seeds import load_seed_for_class
from app.teacher_agent.planning_state import PlanRuntime
from tests.conftest import CLASS_ID
from tests.test_course_material_import import Reviewer, extracted


def test_approved_library_sections_are_available_without_plan_upload(
    wiki, workflow_drafts
):
    service = CourseMaterialImportService(
        wiki=wiki, workflow_drafts=workflow_drafts, reviewer=Reviewer()
    )
    row = extracted(service, wiki)
    assert wiki.list_class_materials(CLASS_ID, inventory=[]) == []
    asyncio.run(service.review(CLASS_ID, row.draft_id))
    material = service.approve(
        CLASS_ID, row.draft_id, row.artifact_revision, row.artifact_hash
    )
    records = wiki.list_class_materials(CLASS_ID, inventory=[])
    assert records[0].sections[1].id == material.sections[1].id
    assert "alternative reaction path" in records[0].sections[1].body


def test_planning_context_is_bounded_and_never_claims_map_means_taught(wiki):
    seed = load_seed_for_class(wiki, CLASS_ID)
    payload = seed.model_dump(mode="json")
    for node in payload["nodes"]:
        node["status"] = "adopted"
    wiki.write_course_network(CLASS_ID, CourseNetworkDocument.model_validate(payload))
    rt = PlanRuntime()
    context = build_course_planning_context(wiki, CLASS_ID, "Chemische Reaktion", rt)
    assert len(context["text"]) <= 14000
    assert "not evidence" in context["text"]
    assert "retain Course: node_id with the exact canonical ID" in context["text"]
    assert "Do not cite unused concepts" in context["text"]
    assert rt.course_context["network_revision"] == 1
    assert len(rt.course_context["node_ids"]) <= 6
    assert wiki.load_course_network(CLASS_ID).revision == 1


def topic_network(wiki):
    payload = load_seed_for_class(wiki, CLASS_ID).model_dump(mode="json")
    payload.update(
        nodes=[
            {
                "id": "a-salts",
                "title": "Salze",
                "learning_goal": "Kristallgitter erklären",
            },
            {
                "id": "z-ph",
                "title": "pH",
                "learning_goal": "Saure Lösungen untersuchen",
            },
        ],
        edges=[],
        material_mappings=[],
        positions={},
    )
    network = CourseNetworkDocument.model_validate(payload)
    wiki.write_course_network(CLASS_ID, network)
    return network


def test_short_topic_and_current_request_take_priority_over_runtime(wiki):
    topic_network(wiki)
    rt = PlanRuntime()
    rt.lesson_planning_state.lesson_topic = "Salze"
    context = build_course_planning_context(
        wiki, CLASS_ID, "Plane eine Stunde zu pH", rt
    )
    assert context["node_ids"] == ["z-ph"]


def test_generic_german_planning_verb_does_not_override_continuation_topic(wiki):
    payload = load_seed_for_class(wiki, CLASS_ID).model_dump(mode="json")
    for node in payload["nodes"]:
        node["status"] = "adopted"
    wiki.write_course_network(CLASS_ID, CourseNetworkDocument.model_validate(payload))
    rt = PlanRuntime()
    rt.lesson_planning_state.lesson_topic = "Elektrolyse"
    context = build_course_planning_context(
        wiki, CLASS_ID, "Bitte die naechste Stunde planen", rt
    )
    assert context["selection_basis"] == "runtime_topic"
    assert "electrolysis-and-cells" in context["node_ids"]


def test_no_match_is_an_overview_not_arbitrary_selected_evidence(wiki):
    topic_network(wiki)
    rt = PlanRuntime()
    rt.lesson_planning_state.lesson_topic = "Salze"
    context = build_course_planning_context(wiki, CLASS_ID, "Photosynthese", rt)
    assert context["node_ids"] == []
    assert context["material_sections"] == []
    assert "Available topics" in context["text"]
    assert "Salze" in context["text"] and "pH" in context["text"]


@pytest.mark.parametrize("basis", ["runtime", "current_unit"])
def test_continuation_uses_explicit_topic_and_actual_unfinished_results(wiki, basis):
    from app.course_network.lesson_refs import write_plan_course_refs

    topic_network(wiki)
    rt = PlanRuntime()
    if basis == "runtime":
        rt.lesson_planning_state.lesson_topic = "pH"
    else:
        wiki.roll_up_paths(CLASS_ID)["course_state"].write_text(
            "## Current unit\n- pH\n", encoding="utf-8"
        )
    lesson = wiki.lesson_dir(CLASS_ID, "2026-10-05")
    lesson.mkdir(parents=True, exist_ok=True)
    (lesson / "lesson_plan.md").write_text("pH plan", encoding="utf-8")
    write_plan_course_refs(
        wiki,
        CLASS_ID,
        "2026-10-05",
        "pH plan",
        {"class_id": CLASS_ID, "node_ids": ["z-ph"]},
    )
    (lesson / "lesson_results.md").write_text(
        "Indicator experiment unfinished; repeat next lesson.", encoding="utf-8"
    )
    context = build_course_planning_context(wiki, CLASS_ID, "Plan the next lesson", rt)
    assert context["node_ids"] == ["z-ph"]
    assert "Indicator experiment unfinished" in context["text"]
    assert "never a mastery score" in context["text"]


def test_no_graph_clears_previous_runtime_evidence(wiki):
    rt = PlanRuntime(course_context={"node_ids": ["stale"]})
    assert build_course_planning_context(wiki, CLASS_ID, "pH", rt)["text"] == ""
    assert rt.course_context == {}


def test_complete_sections_fit_budget_and_runtime_lists_only_injected_evidence(
    wiki, workflow_drafts
):
    from app.course_materials.store import material_root

    service = CourseMaterialImportService(
        wiki=wiki, workflow_drafts=workflow_drafts, reviewer=Reviewer()
    )
    row = extracted(service, wiki)
    asyncio.run(service.review(CLASS_ID, row.draft_id))
    material = service.approve(
        CLASS_ID, row.draft_id, row.artifact_revision, row.artifact_hash
    )
    root = material_root(wiki, material)
    first, second = material.sections
    (root / "document.agent.md").write_text(
        f"<!-- course-section:{first.id} -->\n## Long\n\n"
        + "oversized " * 1600
        + f"\n<!-- /course-section -->\n<!-- course-section:{second.id} -->\n## Short\n\nComplete short evidence END.\n<!-- /course-section -->\n",
        encoding="utf-8",
    )
    network = topic_network(wiki)
    network.nodes[1].material_refs = [
        MaterialSectionReference(material_id=material.material_id, section_id=s.id)
        for s in material.sections
    ]
    wiki.write_course_network(CLASS_ID, network)
    context = build_course_planning_context(wiki, CLASS_ID, "pH", PlanRuntime())
    assert "oversized" not in context["text"]
    assert "Complete short evidence END." in context["text"]
    assert context["material_sections"] == [
        {"material_id": material.material_id, "section_id": second.id}
    ]
    assert len(context["text"]) <= 14000


def test_unrelated_chapters_are_not_retrieved_and_archive_keeps_historical_reads(
    wiki, workflow_drafts
):
    from app.course_materials.store import (
        read_course_material_section,
        set_course_material_archived,
    )

    service = CourseMaterialImportService(
        wiki=wiki, workflow_drafts=workflow_drafts, reviewer=Reviewer()
    )
    network = topic_network(wiki)
    materials = []
    for node, body in zip(
        network.nodes, ["Salt lattice evidence.", "pH indicator evidence."]
    ):
        row = service.create(
            CLASS_ID, title=node.title, arm="textbook", filename="chapter.pdf"
        )
        package = service.package_dir(row)
        package.mkdir(parents=True, exist_ok=True)
        (package / "document.agent.md").write_text(
            f"## PDF page 1\n# {node.title}\n{body}", encoding="utf-8"
        )
        (package / "provenance.json").write_text(
            '{"original_page_numbers": [1]}', encoding="utf-8"
        )
        (package / "source.pdf").write_bytes(node.id.encode())
        row = service.finish_extraction(CLASS_ID, row.draft_id, source_hash=node.id)
        asyncio.run(service.review(CLASS_ID, row.draft_id))
        material = service.approve(
            CLASS_ID, row.draft_id, row.artifact_revision, row.artifact_hash
        )
        materials.append(material)
        node.material_refs = [
            MaterialSectionReference(
                material_id=material.material_id, section_id=material.sections[0].id
            )
        ]
    wiki.write_course_network(CLASS_ID, network)
    context = build_course_planning_context(wiki, CLASS_ID, "pH", PlanRuntime())
    assert "pH indicator evidence." in context["text"]
    assert "Salt lattice evidence." not in context["text"]
    ph = materials[1]
    assert context["material_sections"] == [
        {"material_id": ph.material_id, "section_id": ph.sections[0].id}
    ]
    set_course_material_archived(wiki, CLASS_ID, ph.material_id, True)
    archived = build_course_planning_context(wiki, CLASS_ID, "pH", PlanRuntime())
    assert archived["material_sections"] == []
    assert "pH indicator evidence." not in archived["text"]
    assert (
        "pH indicator evidence."
        in read_course_material_section(
            wiki, CLASS_ID, ph.material_id, ph.sections[0].id
        )["content"]
    )
