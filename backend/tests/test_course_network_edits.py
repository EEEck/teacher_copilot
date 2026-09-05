import asyncio
import json

import pytest

from app.course_network.edit_service import CourseNetworkEditService
from app.course_network.models import CourseNetworkDocument
from app.course_network.operations import NetworkChangeSet
from app.course_network.review import CourseNetworkReviewJudgement
from app.course_network.seeds import load_seed_for_class
from app.services.workflow_drafts import WorkflowDraftConflict
from tests.conftest import CLASS_ID


class Reviewer:
    async def review(self, packet):
        return CourseNetworkReviewJudgement(decision="accept", summary="Reviewed")


def adopted(wiki):
    payload = load_seed_for_class(wiki, CLASS_ID).model_dump()
    for node in payload["nodes"]:
        node["status"] = "adopted"
    return wiki.write_course_network(
        CLASS_ID, CourseNetworkDocument.model_validate(payload)
    )


def test_edits_require_exact_review_and_retries_do_not_republish(wiki, workflow_drafts):
    before = adopted(wiki)
    service = CourseNetworkEditService(
        wiki=wiki, workflow_drafts=workflow_drafts, reviewer=Reviewer()
    )
    changes = NetworkChangeSet(
        class_id=CLASS_ID,
        base_revision=1,
        summary="Clarify",
        operations=[
            {
                "op": "update_node",
                "node_id": before.nodes[0].id,
                "changes": {"title": "A clearer title"},
            }
        ],
    )
    row = service.open(CLASS_ID, changes)
    with pytest.raises(WorkflowDraftConflict):
        service.commit(CLASS_ID, row.draft_id, row.artifact_revision, row.artifact_hash)
    asyncio.run(service.review(CLASS_ID, row.draft_id))
    after = service.commit(
        CLASS_ID, row.draft_id, row.artifact_revision, row.artifact_hash
    )
    assert after.revision == 2
    assert after.nodes[0].title == "A clearer title"
    retry = service.commit(
        CLASS_ID, row.draft_id, row.artifact_revision, row.artifact_hash
    )
    assert retry.revision == 2


def test_review_invalidated_by_edit_and_other_class_cannot_open(wiki, workflow_drafts):
    before = adopted(wiki)
    service = CourseNetworkEditService(
        wiki=wiki, workflow_drafts=workflow_drafts, reviewer=Reviewer()
    )
    changes = NetworkChangeSet(
        class_id=CLASS_ID,
        base_revision=1,
        summary="Clarify",
        operations=[
            {
                "op": "update_node",
                "node_id": before.nodes[0].id,
                "changes": {"title": "First title"},
            }
        ],
    )
    row = service.open(CLASS_ID, changes)
    asyncio.run(service.review(CLASS_ID, row.draft_id))
    changes.operations[0].changes.title = "Second title"
    service.update(
        CLASS_ID, row.draft_id, changes, row.artifact_revision, row.artifact_hash
    )
    with pytest.raises(WorkflowDraftConflict):
        service.commit(CLASS_ID, row.draft_id, row.artifact_revision, row.artifact_hash)
    with pytest.raises(KeyError):
        service.get("other-class", row.draft_id)
    assert wiki.load_course_network(CLASS_ID).revision == 1


def test_commit_resumes_after_log_written_without_duplicate_audit(
    wiki, workflow_drafts, monkeypatch
):
    before = adopted(wiki)
    service = CourseNetworkEditService(
        wiki=wiki, workflow_drafts=workflow_drafts, reviewer=Reviewer()
    )
    changes = NetworkChangeSet(
        class_id=CLASS_ID,
        base_revision=1,
        summary="Clarify",
        operations=[
            {
                "op": "update_node",
                "node_id": before.nodes[0].id,
                "changes": {"title": "Recovery title"},
            }
        ],
    )
    row = service.open(CLASS_ID, changes)
    asyncio.run(service.review(CLASS_ID, row.draft_id))
    original = workflow_drafts.complete_course_network_adoption

    def fail(*args, **kwargs):
        raise OSError("simulated interruption after graph and audit publication")

    monkeypatch.setattr(workflow_drafts, "complete_course_network_adoption", fail)
    with pytest.raises(OSError):
        service.commit(CLASS_ID, row.draft_id, row.artifact_revision, row.artifact_hash)
    with pytest.raises(WorkflowDraftConflict):
        service.update(
            CLASS_ID, row.draft_id, changes, row.artifact_revision, row.artifact_hash
        )
    monkeypatch.setattr(workflow_drafts, "complete_course_network_adoption", original)
    assert (
        service.commit(
            CLASS_ID, row.draft_id, row.artifact_revision, row.artifact_hash
        ).revision
        == 2
    )
    assert wiki.read_text(wiki.log_path).count(f"(id:course-edit-{row.draft_id})") == 1
