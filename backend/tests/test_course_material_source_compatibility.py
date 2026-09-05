import asyncio
import json
import shutil
from io import BytesIO

import pytest
from pypdf import PdfWriter

from app.course_materials import store
from app.course_materials.import_service import CourseMaterialImportService
from app.services.materials_scratch import (
    SessionMaterialEntry,
    promote_scratch_material,
)
from tests.conftest import CLASS_ID
from tests.test_course_material_import import Reviewer
from tests.test_course_material_lifecycle import saved_package


def pdf(pages):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=100, height=100)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def approve_saved(wiki, workflow_drafts):
    service = CourseMaterialImportService(
        wiki=wiki, workflow_drafts=workflow_drafts, reviewer=Reviewer()
    )
    row = service.from_saved_material(CLASS_ID, "mat_saved")
    asyncio.run(service.review(CLASS_ID, row.draft_id))
    material = service.approve(
        CLASS_ID, row.draft_id, row.artifact_revision, row.artifact_hash
    )
    return service, row, material


def test_normalization_keeps_legacy_section_aliases_outside_automatic_sections(
    wiki, workflow_drafts
):
    saved_package(wiki)
    _, _, material = approve_saved(wiki, workflow_drafts)
    records = wiki.list_class_materials(CLASS_ID, inventory=[])
    assert {s.id for s in records[0].sections} == {s.id for s in material.sections}
    assert (
        wiki.read_class_material(records, "mat_saved", section_id="reactions")[
            "content"
        ]
        == "Atoms rearrange."
    )
    store.set_course_material_archived(wiki, CLASS_ID, "mat_saved", True)
    assert (
        wiki.read_class_material(records, "mat_saved", section_id="reactions")[
            "content"
        ]
        == "Atoms rearrange."
    )


def test_saved_library_and_review_use_chapter_metadata(wiki, workflow_drafts):
    root = saved_package(wiki)
    (root / "summary.md").write_text(
        "# Material summary\n\n- Chapter/topic: Chemical reactions\n", encoding="utf-8"
    )
    assert (
        store.list_material_library(wiki, CLASS_ID)[0]["title"] == "Chemical reactions"
    )
    service = CourseMaterialImportService(wiki=wiki, workflow_drafts=workflow_drafts)
    assert (
        json.loads(
            service.from_saved_material(CLASS_ID, "mat_saved").artifact_markdown
        )["title"]
        == "Chemical reactions"
    )


def test_normalized_automatic_summary_and_search_use_approved_content(
    wiki, workflow_drafts
):
    from app.teacher_agent.wiki.materials import (
        build_materials_context_trace,
        search_class_materials,
    )

    root = saved_package(wiki)
    (root / "document.agent.md").write_text(
        "## PDF page 3\n# Reactions\nAtoms are destroyed.", encoding="utf-8"
    )
    original_summary = "# Material summary\n\n## Summary\nAtoms are destroyed."
    (root / "summary.md").write_text(original_summary, encoding="utf-8")
    service = CourseMaterialImportService(
        wiki=wiki, workflow_drafts=workflow_drafts, reviewer=Reviewer()
    )
    row = service.from_saved_material(CLASS_ID, "mat_saved")
    artifact = json.loads(row.artifact_markdown)
    artifact["sections"][0]["content"] = "Atoms are conserved."
    row = service.update(
        CLASS_ID, row.draft_id, artifact, row.artifact_revision, row.artifact_hash
    )
    asyncio.run(service.review(CLASS_ID, row.draft_id))
    service.approve(CLASS_ID, row.draft_id, row.artifact_revision, row.artifact_hash)
    records = wiki.list_class_materials(CLASS_ID, inventory=[])
    assert "conserved" in records[0].summary
    assert "destroyed" not in records[0].summary
    assert "conserved" in wiki.read_class_material(records, "mat_saved")["content"]
    assert "destroyed" not in build_materials_context_trace(records)["text"]
    assert search_class_materials(records, "destroyed") == []
    assert search_class_materials(records, "conserved")
    assert (
        "destroyed"
        in wiki.read_class_material(records, "mat_saved", section_id="reactions")[
            "content"
        ]
    )
    assert (root / "summary.md").read_text(encoding="utf-8") == original_summary


def test_approved_full_pdf_uses_original_order_after_reordered_extraction(
    client, wiki, workflow_drafts
):
    service = CourseMaterialImportService(
        wiki=wiki, workflow_drafts=workflow_drafts, reviewer=Reviewer()
    )
    row = service.create(
        CLASS_ID, title="Chapter", arm="personal", filename="chapter.pdf"
    )
    package = service.package_dir(row)
    package.mkdir(parents=True)
    (package.parent / "upload.pdf").write_bytes(pdf(2))
    (package / "source.pdf").write_bytes(pdf(2))
    (package / "document.agent.md").write_text(
        "## PDF page 2\n# Second\nSecond page.\n## PDF page 1\n# First\nFirst page.",
        encoding="utf-8",
    )
    (package / "provenance.json").write_text(
        json.dumps({"original_page_numbers": [2, 1]}), encoding="utf-8"
    )
    row = service.finish_extraction(CLASS_ID, row.draft_id, source_hash="fixture")
    asyncio.run(service.review(CLASS_ID, row.draft_id))
    material = service.approve(
        CLASS_ID, row.draft_id, row.artifact_revision, row.artifact_hash
    )
    source = store.resolve_course_asset(
        wiki, CLASS_ID, material.material_id, "source.pdf"
    )
    assert store.source_page_map(source) == {1: 1, 2: 2}
    for section in material.sections:
        data = store.read_course_material_section(
            wiki, CLASS_ID, material.material_id, section.id
        )
        assert data["source_page_start"] == section.page_start
    # The pre-approval selected package retains its reordered physical layout.
    assert store.source_page_map(package / "source.pdf") == {2: 1, 1: 2}
    # Standalone approvals predating the explicit metadata used the same full-PDF contract.
    (source.parent / "source-layout.json").unlink()
    assert store.source_page_map(source) == {1: 1, 2: 2}


@pytest.mark.parametrize("physical_count,expected", [(2, [1, 2]), (7, [3, 7])])
def test_original_page_links_preserve_citations_and_resolve_physical_source_pages(
    client, wiki, workflow_drafts, physical_count, expected
):
    root = saved_package(wiki)
    contents = pdf(physical_count)
    (root / "source.pdf").write_bytes(contents)
    (root / "document.agent.md").write_text(
        "## PDF page 3\n# Reactions\nAtoms rearrange.\n## PDF page 7\n# Energy\nEnergy transfers.",
        encoding="utf-8",
    )
    (root / "provenance.json").write_text(
        json.dumps({"original_page_numbers": [3, 7]}), encoding="utf-8"
    )
    service, row, material = approve_saved(wiki, workflow_drafts)
    base = f"/api/classes/{CLASS_ID}/course"
    urls = [
        base + f"/material-imports/{row.draft_id}/source",
        base + "/materials/mat_saved/files/source.pdf",
    ]
    for url in urls:
        assert client.get(url).content == contents
        for original, physical in zip([3, 7], expected):
            response = client.get(
                url, params={"original_page": original}, follow_redirects=False
            )
            assert response.status_code == 307
            assert response.headers["location"] == f"{url}#page={physical}"
        assert client.get(url, params={"original_page": 99}).status_code == 422
    store.set_course_material_archived(wiki, CLASS_ID, "mat_saved", True)
    for section, original, physical in zip(material.sections, [3, 7], expected):
        data = client.get(base + f"/materials/mat_saved/sections/{section.id}").json()
        assert data["page_start"] == data["page_end"] == original
        assert data["source_page_start"] == data["source_page_end"] == physical
    (root / "source.pdf").unlink()
    assert (
        client.get(
            urls[1], params={"original_page": 3}, follow_redirects=False
        ).status_code
        == 404
    )
    (service.package_dir(row) / "source.pdf").unlink()
    assert (
        client.get(
            urls[0], params={"original_page": 3}, follow_redirects=False
        ).status_code
        == 404
    )


def test_full_import_upload_maps_pages_before_extraction(client, wiki, workflow_drafts):
    service = CourseMaterialImportService(wiki=wiki, workflow_drafts=workflow_drafts)
    row = service.create(
        CLASS_ID, title="Chapter", arm="personal", filename="chapter.pdf"
    )
    path = service.package_dir(row).parent / "upload.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pdf(7))
    url = f"/api/classes/{CLASS_ID}/course/material-imports/{row.draft_id}/source"
    response = client.get(url, params={"original_page": 7}, follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == f"{url}#page=7"


def test_malformed_pdf_returns_validation_error_without_creating_draft(client):
    base = f"/api/classes/{CLASS_ID}/course/material-imports"
    response = client.post(
        base, files={"file": ("broken.pdf", b"%PDF-broken", "application/pdf")}
    )
    assert response.status_code == 422
    assert client.get(base).json()["drafts"] == []


def test_repeated_plan_promotion_preserves_reviewed_package_and_archive(
    wiki, workflow_drafts, tmp_path
):
    root = saved_package(wiki)
    scratch = tmp_path / "scratch"
    shutil.copytree(root, scratch)
    entry = SessionMaterialEntry(
        material_id="mat_saved",
        arm="personal",
        title="Reactions",
        summary="",
        scratch_path=str(scratch),
    )
    approve_saved(wiki, workflow_drafts)
    store.set_course_material_archived(wiki, CLASS_ID, "mat_saved", True)
    before = {
        p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()
    }
    promote_scratch_material(wiki_root=wiki.root, class_id=CLASS_ID, entry=entry)
    assert {
        p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()
    } == before
    shutil.rmtree(scratch)
    assert promote_scratch_material(
        wiki_root=wiki.root, class_id=CLASS_ID, entry=entry
    ).promoted
    assert {
        p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()
    } == before


def test_repeated_promotion_rejects_conflicting_source_without_overwriting(
    wiki, tmp_path
):
    root = saved_package(wiki)
    scratch = tmp_path / "scratch"
    shutil.copytree(root, scratch)
    (scratch / "source.pdf").write_bytes(b"different")
    entry = SessionMaterialEntry(
        material_id="mat_saved",
        arm="personal",
        title="Reactions",
        summary="",
        scratch_path=str(scratch),
    )
    with pytest.raises(ValueError, match="already exists"):
        promote_scratch_material(wiki_root=wiki.root, class_id=CLASS_ID, entry=entry)
    assert (root / "source.pdf").read_bytes() == b"saved-source"
