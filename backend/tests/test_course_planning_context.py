import asyncio

from app.course_materials.import_service import CourseMaterialImportService
from app.course_network.planning import build_course_planning_context
from app.course_network.models import CourseNetworkDocument
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
    assert rt.course_context["network_revision"] == 1
    assert len(rt.course_context["node_ids"]) <= 6
    assert wiki.load_course_network(CLASS_ID).revision == 1
