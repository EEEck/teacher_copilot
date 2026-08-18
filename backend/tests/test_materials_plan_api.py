"""Plan materials upload (mocked OCR) + promote-on-save."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services.materials_ocr_packaging import MaterialsOcrPackage, package_mistral_ocr_response
from app.schemas.api import ChatMessage
from app.teacher_agent.prompt_assembly import build_plan_chat_prompt_assembly
from app.teacher_agent.wiki.materials import build_materials_context_trace

CLASS_ID = "chemie_9b_2026_27"
FIXTURE_PDF = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "materials"
    / "esl_textbook_sample_pages_9_to_11.pdf"
)


def _fake_ocr(
    pdf_path: Path,
    *,
    out_dir: Path,
    subject: str = "Chemie",
    topic: str = "Aufbau von Molekülen",
    summary: str = "Elektronenpaarbindung und Valenzstrichformeln.",
    **kwargs,
) -> MaterialsOcrPackage:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    source = out_dir / "source.pdf"
    source.write_bytes(Path(pdf_path).read_bytes())
    response = {
        "model": "mock-ocr",
        "document_annotation": {
            "document_kind": "textbook_chapter",
            "subject": subject,
            "chapter_or_topic": topic,
            "language": "Deutsch" if subject == "Chemie" else "English",
            "teacher_summary_de": summary,
        },
        "pages": [
            {
                "markdown": f"# {topic}\n\n{summary}\n",
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


def test_promote_skips_debug_ocr_artifacts(tmp_path):
    from app.services.materials_scratch import (
        SessionMaterialEntry,
        promote_scratch_material,
    )

    scratch = tmp_path / "scratch" / "mat_debug"
    scratch.mkdir(parents=True)
    (scratch / "document.agent.md").write_text("# ok\n", encoding="utf-8")
    (scratch / "summary.md").write_text("# summary\n", encoding="utf-8")
    (scratch / "source.pdf").write_bytes(b"%PDF")
    (scratch / "raw_response.json").write_text("{}\n", encoding="utf-8")
    (scratch / "document_annotation.json").write_text("{}\n", encoding="utf-8")
    entry = SessionMaterialEntry(
        material_id="mat_debug",
        arm="textbook",
        title="t",
        summary="s",
        scratch_path=str(scratch),
    )
    dest = (
        tmp_path
        / "wiki"
        / "wiki"
        / "classes"
        / "c1"
        / "materials"
        / "textbooks"
        / "mat_debug"
    )
    promote_scratch_material(wiki_root=tmp_path / "wiki", class_id="c1", entry=entry)
    assert (dest / "document.agent.md").is_file()
    assert (dest / "summary.md").is_file()
    assert not (dest / "raw_response.json").exists()
    assert not (dest / "document_annotation.json").exists()
    assert (scratch / "raw_response.json").is_file()


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


def test_serve_material_asset_from_scratch(client: TestClient, tmp_path, monkeypatch):
    from app.services.materials_scratch import attach_prebuilt_package, scratch_root

    scratch = tmp_path / "scratch"
    scratch.mkdir()
    monkeypatch.setattr(
        "app.services.materials_scratch.scratch_root",
        lambda settings=None: scratch,
    )
    start = client.post(f"/api/classes/{CLASS_ID}/plan/sessions")
    session_id = start.json()["session_id"]
    package = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "materials"
        / "mini_bonding_package"
    )
    # Seed via service on the overridden plan client path: upload-like attach
    from app.api import deps
    from app.main import app

    plan_svc = app.dependency_overrides[deps.get_plan_service]()
    summary = plan_svc.attach_prebuilt_material(
        CLASS_ID, session_id, package_dir=package, arm="textbook"
    )
    material_id = summary.material_id
    res = client.get(
        f"/api/classes/{CLASS_ID}/plan/sessions/{session_id}"
        f"/materials/{material_id}/assets/img-0.jpeg"
    )
    assert res.status_code == 200, res.text
    assert res.content[:2] == b"\xff\xd8"
    bad = client.get(
        f"/api/classes/{CLASS_ID}/plan/sessions/{session_id}"
        f"/materials/{material_id}/assets/../summary.md"
    )
    assert bad.status_code in {400, 404}


def test_materials_use_procedure_authorizes_classroom_asset_embeds():
    text = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "teacher_agent"
        / "skills"
        / "materials_use_procedure.md"
    ).read_text(encoding="utf-8")
    assert "classroom use" in text.lower()
    assert "assets/img-" in text
    assert "not" in text.lower() and "instructions" in text.lower()
    assert "every" in text.lower() and "listed material" in text.lower()


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


def _upload_pdf(client: TestClient, session_id: str, name: str = "chapter.pdf"):
    with FIXTURE_PDF.open("rb") as f:
        return client.post(
            f"/api/classes/{CLASS_ID}/plan/sessions/{session_id}/materials",
            files={"file": (name, f, "application/pdf")},
            data={"arm": "textbook"},
        )


def test_two_on_subject_pdfs_both_injected_then_delete_one(
    client: TestClient, mock_ocr, wiki, monkeypatch
):
    topics = iter(
        [
            ("Lewis structures", "Valenzstrichformeln for H2O."),
            ("Molekülorbitale", "MO diagrams for diatomic molecules."),
        ]
    )

    def fake(pdf_path, *, out_dir, **kwargs):
        topic, summary = next(topics)
        return _fake_ocr(
            pdf_path,
            out_dir=out_dir,
            topic=topic,
            summary=summary,
            **kwargs,
        )

    monkeypatch.setattr("app.services.materials_scratch.run_mistral_ocr_on_pdf", fake)

    start = client.post(f"/api/classes/{CLASS_ID}/plan/sessions")
    session_id = start.json()["session_id"]
    first = _upload_pdf(client, session_id, "bonding.pdf")
    second = _upload_pdf(client, session_id, "mo.pdf")
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    id_a = first.json()["material_id"]
    id_b = second.json()["material_id"]
    assert id_a != id_b

    draft = client.get(
        f"/api/classes/{CLASS_ID}/plan/sessions/{session_id}/draft"
    ).json()
    ids = {item["material_id"] for item in draft["materials"]}
    assert ids == {id_a, id_b}
    assert draft["class_core"]

    from app.api import deps
    from app.main import app

    plan_svc = app.dependency_overrides[deps.get_plan_service]()
    session = plan_svc.get_session(session_id)
    assembly = build_plan_chat_prompt_assembly(
        wiki,
        CLASS_ID,
        messages=[ChatMessage(role="user", content="Summarize this PDF.")],
        current_plan="",
        runtime=session.runtime,
    )
    toc = assembly["nested"]["class_materials"]["text"]
    assert id_a in toc
    assert id_b in toc
    assert "as a set" in toc.lower() or "every material" in toc.lower()

    deleted = client.delete(
        f"/api/classes/{CLASS_ID}/plan/sessions/{session_id}/materials/{id_a}"
    )
    assert deleted.status_code == 200, deleted.text
    remaining = {item["material_id"] for item in deleted.json()["materials"]}
    assert remaining == {id_b}
    assert not (mock_ocr / session_id / id_a).exists()
    assert (mock_ocr / session_id / id_b).is_dir()

    session = plan_svc.get_session(session_id)
    after = build_plan_chat_prompt_assembly(
        wiki,
        CLASS_ID,
        messages=[ChatMessage(role="user", content="Summarize this PDF.")],
        current_plan="",
        runtime=session.runtime,
    )["nested"]["class_materials"]["text"]
    assert id_a not in after
    assert id_b in after


def test_materials_toc_keeps_both_ids_under_tight_char_cap():
    from app.teacher_agent.wiki.materials import ClassMaterialRecord, MaterialSection

    records = [
        ClassMaterialRecord(
            material_id="mat_aaa",
            arm="textbook",
            title="First chapter",
            summary="x" * 800,
            page_numbers=[1, 2, 3],
            root=Path("."),
            source="scratch",
            wiki_path="",
            sections=(MaterialSection(id="summary", title="Summary", body=""),),
        ),
        ClassMaterialRecord(
            material_id="mat_bbb",
            arm="textbook",
            title="Second chapter",
            summary="y" * 800,
            page_numbers=[4, 5],
            root=Path("."),
            source="scratch",
            wiki_path="",
            sections=(MaterialSection(id="summary", title="Summary", body=""),),
        ),
    ]
    toc = build_materials_context_trace(records, index_chars=400)
    assert "mat_aaa" in toc["text"]
    assert "mat_bbb" in toc["text"]
    assert "First chapter" in toc["text"]
    assert "Second chapter" in toc["text"]


def test_esl_pdf_rejected_on_chemie_class(client: TestClient, mock_ocr, monkeypatch):
    def fake_esl(pdf_path, *, out_dir, **kwargs):
        return _fake_ocr(
            pdf_path,
            out_dir=out_dir,
            subject="English",
            topic="It's fun at home",
            summary="Family and home vocabulary.",
            **kwargs,
        )

    monkeypatch.setattr(
        "app.services.materials_scratch.run_mistral_ocr_on_pdf", fake_esl
    )
    start = client.post(f"/api/classes/{CLASS_ID}/plan/sessions")
    session_id = start.json()["session_id"]
    res = _upload_pdf(client, session_id, "esl_textbook_sample_pages_9_to_11.pdf")
    assert res.status_code == 422, res.text
    message = res.json()["error"]["message"]
    assert "English" in message or "ESL" in message
    draft = client.get(
        f"/api/classes/{CLASS_ID}/plan/sessions/{session_id}/draft"
    ).json()
    assert draft["materials"] == []
    scratch_session = mock_ocr / session_id
    if scratch_session.exists():
        leftover = list(scratch_session.iterdir())
        assert leftover == []


def test_patch_context_excludes_planning_brief(client: TestClient, wiki):
    start = client.post(f"/api/classes/{CLASS_ID}/plan/sessions")
    session_id = start.json()["session_id"]
    draft = client.get(
        f"/api/classes/{CLASS_ID}/plan/sessions/{session_id}/draft"
    ).json()
    keys = {item["key"] for item in draft["class_core"]}
    assert "planning_brief" in keys
    patched = client.patch(
        f"/api/classes/{CLASS_ID}/plan/sessions/{session_id}/context",
        json={"excluded_core_keys": ["planning_brief"]},
    )
    assert patched.status_code == 200, patched.text
    items = {item["key"]: item for item in patched.json()["class_core"]}
    assert items["planning_brief"]["included"] is False

    from app.api import deps
    from app.main import app

    plan_svc = app.dependency_overrides[deps.get_plan_service]()
    session = plan_svc.get_session(session_id)
    assembly = build_plan_chat_prompt_assembly(
        wiki,
        CLASS_ID,
        messages=[ChatMessage(role="user", content="Plan next lesson.")],
        current_plan="",
        runtime=session.runtime,
    )
    core_text = assembly["nested"]["active_class_core"]["text"]
    assert "Active class core" in core_text
    assert "## Planning brief" not in core_text
    included = [
        section
        for section in assembly["nested"]["active_class_core"]["sections"]
        if section.get("key") == "planning_brief"
    ]
    assert included
    assert included[0]["included"] is False
