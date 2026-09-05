import asyncio
import json

import pytest

from app.course_materials.import_service import CourseMaterialImportService
from app.course_materials.store import (
    list_course_materials,
    read_course_material_section,
)
from app.course_network.review import CourseNetworkReviewJudgement
from app.services.workflow_drafts import WorkflowDraftConflict
from tests.conftest import CLASS_ID


class Reviewer:
    async def review(self, packet):
        return CourseNetworkReviewJudgement(
            decision="accept", summary="Reviewed extraction"
        )


def test_discarded_import_cannot_publish_an_old_accepted_review(wiki, workflow_drafts):
    service = CourseMaterialImportService(wiki=wiki, workflow_drafts=workflow_drafts, reviewer=Reviewer())
    row = extracted(service, wiki)
    asyncio.run(service.review(CLASS_ID, row.draft_id))
    workflow_drafts.discard(row.draft_id)
    with pytest.raises(WorkflowDraftConflict):
        service.approve(CLASS_ID, row.draft_id, row.artifact_revision, row.artifact_hash)
    assert list_course_materials(wiki, CLASS_ID) == []


def extracted(service, wiki):
    # Supply a provider-independent package; the real service owns the draft and approval.
    row = service.create(
        CLASS_ID, title="Catalysis", arm="textbook", filename="chapter.pdf"
    )
    package = service.package_dir(row)
    package.mkdir(parents=True, exist_ok=True)
    (package / "document.agent.md").write_text(
        "## PDF page 4\n# Activation energy\nThe activation barrier.\n## PDF page 5\n# Catalysis\nAn alternative reaction path.",
        encoding="utf-8",
    )
    (package / "provenance.json").write_text(
        json.dumps({"original_page_numbers": [4, 5]}), encoding="utf-8"
    )
    (package / "source.pdf").write_bytes(b"test-source")
    return service.finish_extraction(CLASS_ID, row.draft_id, source_hash="abc")


def test_material_only_becomes_visible_after_exact_approval(wiki, workflow_drafts):
    service = CourseMaterialImportService(
        wiki=wiki, workflow_drafts=workflow_drafts, reviewer=Reviewer()
    )
    row = extracted(service, wiki)
    assert list_course_materials(wiki, CLASS_ID) == []
    with pytest.raises(WorkflowDraftConflict):
        service.approve(
            CLASS_ID, row.draft_id, row.artifact_revision, row.artifact_hash
        )
    asyncio.run(service.review(CLASS_ID, row.draft_id))
    material = service.approve(
        CLASS_ID, row.draft_id, row.artifact_revision, row.artifact_hash
    )
    assert [m.material_id for m in list_course_materials(wiki, CLASS_ID)] == [
        material.material_id
    ]
    section = read_course_material_section(
        wiki, CLASS_ID, material.material_id, material.sections[1].id
    )
    assert "alternative reaction path" in section["content"]
    assert section["page_start"] == 5
    assert (
        service.approve(
            CLASS_ID, row.draft_id, row.artifact_revision, row.artifact_hash
        ).material_id
        == material.material_id
    )


def test_extraction_edit_invalidates_review_and_other_class_cannot_read(
    wiki, workflow_drafts
):
    service = CourseMaterialImportService(
        wiki=wiki, workflow_drafts=workflow_drafts, reviewer=Reviewer()
    )
    row = extracted(service, wiki)
    asyncio.run(service.review(CLASS_ID, row.draft_id))
    artifact = json.loads(row.artifact_markdown)
    artifact["sections"][0]["title"] = "Updated section"
    updated = service.update(
        CLASS_ID, row.draft_id, artifact, row.artifact_revision, row.artifact_hash
    )
    with pytest.raises(WorkflowDraftConflict):
        service.approve(
            CLASS_ID, row.draft_id, updated.artifact_revision, updated.artifact_hash
        )
    with pytest.raises(KeyError):
        service.get("another-class", row.draft_id)
    assert list_course_materials(wiki, CLASS_ID) == []
