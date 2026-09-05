import asyncio
import json

import pytest

from app.course_materials import store
from app.course_materials.import_service import CourseMaterialImportService
from app.services.materials_scratch import wiki_material_dir
from app.services.workflow_drafts import WorkflowDraftConflict
from tests.conftest import CLASS_ID
from tests.test_course_material_import import Reviewer, extracted


def saved_package(wiki):
    root = wiki_material_dir(wiki.root, CLASS_ID, "personal", "mat_saved")
    root.mkdir(parents=True)
    (root / "source.pdf").write_bytes(b"saved-source")
    (root / "document.agent.md").write_text("## PDF page 3\n# Reactions\nAtoms rearrange.", encoding="utf-8")
    (root / "summary.md").write_text("# Teacher reactions chapter", encoding="utf-8")
    (root / "provenance.json").write_text(json.dumps({"original_page_numbers": [3]}), encoding="utf-8")
    return root


def test_saved_plan_material_requires_section_approval_and_preserves_source(wiki, workflow_drafts):
    root = saved_package(wiki)
    service = CourseMaterialImportService(wiki=wiki, workflow_drafts=workflow_drafts, reviewer=Reviewer())
    assert store.list_course_materials(wiki, CLASS_ID) == []
    items = store.list_material_library(wiki, CLASS_ID)
    assert [(m["material_id"], m["library_status"]) for m in items] == [("mat_saved", "saved")]
    row = service.from_saved_material(CLASS_ID, "mat_saved")
    again = service.from_saved_material(CLASS_ID, "mat_saved")
    assert again.draft_id == row.draft_id
    data = json.loads(row.artifact_markdown)
    data["sections"][0]["content"] = "Atoms rearrange; atoms are conserved."
    row = service.update(CLASS_ID, row.draft_id, data, row.artifact_revision, row.artifact_hash)
    with pytest.raises(WorkflowDraftConflict):
        service.approve(CLASS_ID, row.draft_id, row.artifact_revision, row.artifact_hash)
    asyncio.run(service.review(CLASS_ID, row.draft_id))
    material = service.approve(CLASS_ID, row.draft_id, row.artifact_revision, row.artifact_hash)
    assert material.material_id == "mat_saved"
    assert (root / "source.pdf").read_bytes() == b"saved-source"
    assert "Atoms rearrange." in (root / "document.agent.md").read_text(encoding="utf-8")
    assert "atoms are conserved" in store.read_course_material_section(wiki, CLASS_ID, "mat_saved", material.sections[0].id)["content"]
    assert service.approve(CLASS_ID, row.draft_id, row.artifact_revision, row.artifact_hash).material_id == "mat_saved"


def test_archive_excludes_automatic_library_but_preserves_historical_evidence(wiki, workflow_drafts):
    service = CourseMaterialImportService(wiki=wiki, workflow_drafts=workflow_drafts, reviewer=Reviewer())
    row = extracted(service, wiki)
    asyncio.run(service.review(CLASS_ID, row.draft_id))
    material = service.approve(CLASS_ID, row.draft_id, row.artifact_revision, row.artifact_hash)
    before = store.read_course_material_section(wiki, CLASS_ID, material.material_id, material.sections[0].id)
    store.set_course_material_archived(wiki, CLASS_ID, material.material_id, True)
    assert store.list_course_materials(wiki, CLASS_ID) == []
    assert store.list_material_library(wiki, CLASS_ID)[0]["archived"] is True
    assert store.read_course_material_section(wiki, CLASS_ID, material.material_id, material.sections[0].id) == before
    assert store.resolve_course_asset(wiki, CLASS_ID, material.material_id, "source.pdf").read_bytes() == b"test-source"
    store.set_course_material_archived(wiki, CLASS_ID, material.material_id, False)
    assert len(store.list_course_materials(wiki, CLASS_ID)) == 1


def test_saved_normalization_rejects_source_changed_during_review(wiki, workflow_drafts):
    root = saved_package(wiki)
    service = CourseMaterialImportService(wiki=wiki, workflow_drafts=workflow_drafts, reviewer=Reviewer())
    row = service.from_saved_material(CLASS_ID, "mat_saved")
    asyncio.run(service.review(CLASS_ID, row.draft_id))
    (root / "source.pdf").write_bytes(b"different-source")
    with pytest.raises(WorkflowDraftConflict):
        service.approve(CLASS_ID, row.draft_id, row.artifact_revision, row.artifact_hash)
    assert not (root / "material.json").exists()


def test_library_api_normalizes_saved_material_and_archives_without_deleting(client, wiki):
    root = saved_package(wiki)
    base = f"/api/classes/{CLASS_ID}/course/materials"
    assert client.get(base).json()["materials"][0]["library_status"] == "saved"
    response = client.post(base + "/mat_saved/review-import")
    assert response.status_code == 200, response.text
    row = response.json()
    assert row["artifact"]["material_id"] == "mat_saved"
    assert client.patch(base + "/mat_saved/archive", json={"archived": True}).status_code == 200
    assert client.get(base).json()["materials"][0]["archived"] is True
    assert client.get(base + "/mat_saved/files/source.pdf").content == b"saved-source"
    assert (root / "document.agent.md").exists()


def test_duplicate_pdf_page_selection_does_not_start_another_import(client, wiki):
    from io import BytesIO
    from pypdf import PdfWriter
    root = saved_package(wiki)
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    buffer = BytesIO()
    writer.write(buffer)
    contents = buffer.getvalue()
    (root / "source.pdf").write_bytes(contents)
    (root / "provenance.json").write_text(json.dumps({"original_page_numbers": [1]}), encoding="utf-8")
    response = client.post(f"/api/classes/{CLASS_ID}/course/material-imports", files={"file": ("again.pdf", contents, "application/pdf")}, data={"pages": "1"})
    assert response.status_code == 409, response.text
    assert "already" in response.text.lower()
    assert client.get(f"/api/classes/{CLASS_ID}/course/material-imports").json()["drafts"] == []
