import asyncio
import json

import pytest

from app.course_materials import import_service
from app.course_network.review import CourseNetworkReviewJudgement
from app.services.workflow_drafts import WorkflowDraftConflict
from tests.conftest import CLASS_ID
from tests.test_course_material_import import extracted


@pytest.mark.parametrize("decision", ["accept", "revise", "block"])
def test_correction_guidance_keeps_existing_packet_and_exact_review_gate(
    wiki, workflow_drafts, monkeypatch, decision
):
    captured = {}

    def agent_stub(**kwargs):
        captured["instructions"] = kwargs["instructions"]
        assert kwargs["tools"] == []
        return object()

    async def reviewer_stub(agent, packet, timeout):
        captured["packet"] = json.loads(packet)
        return CourseNetworkReviewJudgement(decision=decision, summary="Stub review")

    monkeypatch.setattr(import_service, "Agent", agent_stub)
    monkeypatch.setattr(import_service, "run_course_review", reviewer_stub)
    service = import_service.CourseMaterialImportService(
        wiki=wiki, workflow_drafts=workflow_drafts
    )
    row = extracted(service, wiki)
    original = (service.package_dir(row) / "document.agent.md").read_text(
        encoding="utf-8"
    )
    artifact = json.loads(row.artifact_markdown)
    artifact["title"] = "Teacher organizational title"
    artifact["sections"][0]["content"] = "Corrected activation barrier."
    row = service.update(
        CLASS_ID, row.draft_id, artifact, row.artifact_revision, row.artifact_hash
    )
    asyncio.run(service.review(CLASS_ID, row.draft_id))

    assert captured["packet"] == {
        "proposed_extraction": artifact,
        "original_ocr": original,
    }
    instructions = captured["instructions"]
    for required in (
        "OCR is fallible",
        "organizational titles",
        "Differences from OCR alone",
        "typo or formula corrections",
        "source-verified",
        "severity='note'",
        "inspect the PDF",
        "materially wrong or unsupported chemical claims",
        "unselected pages",
    ):
        assert required in instructions

    if decision == "accept":
        assert service.approve(
            CLASS_ID, row.draft_id, row.artifact_revision, row.artifact_hash
        )
    else:
        with pytest.raises(WorkflowDraftConflict):
            service.approve(
                CLASS_ID, row.draft_id, row.artifact_revision, row.artifact_hash
            )
