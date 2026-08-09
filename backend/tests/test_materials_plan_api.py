"""Plan materials upload (mocked OCR) + promote-on-save."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services.materials_ocr_packaging import MaterialsOcrPackage, package_mistral_ocr_response

CLASS_ID = "chemie_9b_2026_27"
FIXTURE_PDF = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "materials"
    / "esl_textbook_sample_pages_9_to_11.pdf"
)


def _fake_ocr(pdf_path: Path, *, out_dir: Path, **kwargs) -> MaterialsOcrPackage:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    source = out_dir / "source.pdf"
    source.write_bytes(Path(pdf_path).read_bytes())
    response = {
        "model": "mock-ocr",
        "document_annotation": {
            "document_kind": "chemistry_textbook_chapter",
            "subject": "Chemie",
            "chapter_or_topic": "Aufbau von Molekülen",
            "language": "Deutsch",
            "teacher_summary_de": "Elektronenpaarbindung und Valenzstrichformeln.",
        },
        "pages": [
            {
                "markdown": "# Moleküle\n\nElektronenpaarbindung.\n",
                "images": [],
                "tables": [],
            }
        ],
    }
    return package_mistral_ocr_response(
        response,
        original_page_numbers=[5],
        out_dir=out_dir,
        source_pdf=source,
        arm=kwargs.get("arm"),
        material_id=kwargs.get("material_id"),
        session_id=kwargs.get("session_id"),
    )


@pytest.fixture()
def mock_ocr(monkeypatch, tmp_path):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    monkeypatch.setattr(
        "app.services.materials_scratch.run_mistral_ocr_on_pdf",
        _fake_ocr,
    )
    monkeypatch.setattr(
        "app.services.materials_scratch.scratch_root",
        lambda settings=None: scratch,
    )
    return scratch


def test_upload_material_to_scratch_inventory(
    client: TestClient, mock_ocr
):
    start = client.post(f"/api/classes/{CLASS_ID}/plan/sessions")
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    with FIXTURE_PDF.open("rb") as f:
        res = client.post(
            f"/api/classes/{CLASS_ID}/plan/sessions/{session_id}/materials",
            files={"file": ("chapter.pdf", f, "application/pdf")},
            data={"arm": "textbook"},
        )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["material_id"].startswith("mat_")
    assert body["arm"] == "textbook"
    assert "Molekül" in body["title"] or "Molekül" in body["summary"]
    assert body["page_count"] == 1

    draft = client.get(
        f"/api/classes/{CLASS_ID}/plan/sessions/{session_id}/draft"
    ).json()
    assert len(draft["materials"]) == 1
    assert draft["materials"][0]["material_id"] == body["material_id"]

    root = mock_ocr / session_id / body["material_id"]
    assert (root / "document.agent.md").is_file()
    assert (root / "summary.md").is_file()
    assert (root / "provenance.json").is_file()
    prov = (root / "provenance.json").read_text(encoding="utf-8")
    assert "image_base64" not in prov


def test_save_promotes_materials_to_wiki(
    client: TestClient, mock_ocr, wiki
):
    start = client.post(f"/api/classes/{CLASS_ID}/plan/sessions")
    session_id = start.json()["session_id"]
    with FIXTURE_PDF.open("rb") as f:
        upload = client.post(
            f"/api/classes/{CLASS_ID}/plan/sessions/{session_id}/materials",
            files={"file": ("chapter.pdf", f, "application/pdf")},
            data={"arm": "textbook"},
        )
    assert upload.status_code == 200
    material_id = upload.json()["material_id"]

    plan_md = """# Lesson Package -- Molecular bonding

## Teacher Lesson Plan
Use Elektronenpaarbindung from the uploaded chapter.

## Student Materials
Practice Valenzstrichformeln.

## Observation and Update Capture
Note which Lewis forms need review.
"""
    save = client.post(
        f"/api/classes/{CLASS_ID}/plan/save",
        json={
            "session_id": session_id,
            "lesson_date": "2026-09-15",
            "plan_markdown": plan_md,
        },
    )
    assert save.status_code == 200, save.text
    assert material_id in save.json().get("material_ids", [])

    dest = (
        wiki.root
        / "wiki"
        / "classes"
        / CLASS_ID
        / "materials"
        / "textbooks"
        / material_id
    )
    assert (dest / "document.agent.md").is_file()
    assert (dest / "summary.md").is_file()
    assert (dest / "source.pdf").is_file() or (dest / "upload.pdf").is_file()
    materials_json = (
        wiki.root
        / "wiki"
        / "classes"
        / CLASS_ID
        / "lessons"
        / "2026-09-15"
        / "materials.json"
    )
    assert materials_json.is_file()
    assert material_id in json.loads(materials_json.read_text(encoding="utf-8"))[
        "material_ids"
    ]

    # Idempotent second save with same material_id.
    save2 = client.post(
        f"/api/classes/{CLASS_ID}/plan/save",
        json={
            "session_id": session_id,
            "lesson_date": "2026-09-15",
            "plan_markdown": plan_md,
        },
    )
    assert save2.status_code == 200, save2.text
    assert (dest / "document.agent.md").is_file()


def test_materials_search_and_toc(tmp_path):
    from app.teacher_agent.wiki.materials import (
        build_materials_context_trace,
        list_materials_for_plan,
        read_class_material,
        search_class_materials,
    )
    from app.services.materials_scratch import SessionMaterialEntry

    root = tmp_path / "mat_1"
    root.mkdir()
    (root / "summary.md").write_text(
        "# Material summary\n\n## Summary\n\nElektronenpaarbindung basics.\n",
        encoding="utf-8",
    )
    (root / "document.agent.md").write_text(
        "# OCR\n\n## PDF page 5\n\nValenzstrichformeln for H2O.\n",
        encoding="utf-8",
    )
    entry = SessionMaterialEntry(
        material_id="mat_1",
        arm="textbook",
        title="Aufbau von Molekülen",
        summary="Elektronenpaarbindung basics.",
        page_numbers=[5],
        scratch_path=str(root),
        page_count=1,
    )
    materials = list_materials_for_plan(
        tmp_path, "chemie_x", inventory=[entry]
    )
    assert len(materials) == 1
    toc = build_materials_context_trace(materials)
    assert "mat_1" in toc["text"]
    assert len(toc["text"]) < 2000
    hits = search_class_materials(materials, "Valenzstrichformeln")
    assert hits
    payload = read_class_material(materials, "mat_1", "summary")
    assert "Elektronenpaarbindung" in payload["content"]
