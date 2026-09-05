import asyncio
import pytest

from app.course_materials.import_service import CourseMaterialImportService
from app.course_materials.store import list_course_materials
from app.course_network.edit_service import CourseNetworkEditService
from app.course_network.operations import NetworkChangeSet
from app.services.workflow_drafts import WorkflowDraftConflict
from tests.conftest import CLASS_ID
from tests.test_course_material_import import Reviewer, extracted
from tests.test_course_network_edits import adopted


@pytest.mark.parametrize("kind", ["material", "graph"])
def test_publication_cannot_use_acceptance_superseded_after_initial_read(wiki, workflow_drafts, monkeypatch, kind):
    if kind == "material":
        service = CourseMaterialImportService(wiki=wiki, workflow_drafts=workflow_drafts, reviewer=Reviewer())
        row = extracted(service, wiki)
        publish = service.approve
    else:
        network = adopted(wiki)
        service = CourseNetworkEditService(wiki=wiki, workflow_drafts=workflow_drafts, reviewer=Reviewer())
        changes = NetworkChangeSet(class_id=CLASS_ID, base_revision=1, summary="Rename", operations=[{"op": "update_node", "node_id": network.nodes[0].id, "changes": {"title": "New title"}}])
        row = service.open(CLASS_ID, changes)
        publish = service.commit
    asyncio.run(service.review(CLASS_ID, row.draft_id))
    original = service.get
    first = True
    def superseding_review(class_id, draft_id):
        nonlocal first
        old = original(class_id, draft_id)
        if first:
            first = False
            reviewing = workflow_drafts.begin_course_network_review(draft_id, expected_revision=old.artifact_revision, expected_hash=old.artifact_hash)
            workflow_drafts.mark_review_snapshot(draft_id, revision=old.artifact_revision, artifact_hash_value=old.artifact_hash,
                review_generation=reviewing.review_generation, review_json={"decision": "block", "summary": "New blocking finding", "findings": [], "artifact_revision": old.artifact_revision, "artifact_hash": old.artifact_hash})
        return old
    monkeypatch.setattr(service, "get", superseding_review)
    with pytest.raises(WorkflowDraftConflict):
        publish(CLASS_ID, row.draft_id, row.artifact_revision, row.artifact_hash)
    assert list_course_materials(wiki, CLASS_ID) == []
    assert kind == "material" or wiki.load_course_network(CLASS_ID).revision == 1
    assert workflow_drafts.get(row.draft_id).status == "draft"
