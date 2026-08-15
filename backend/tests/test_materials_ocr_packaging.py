"""Offline packaging: Mistral cookbook-style placeholder replace."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.materials_ocr import (
    build_mistral_ocr_process_kwargs,
    run_openai_vision_ocr_fallback,
)
from app.services.materials_ocr_packaging import (
    package_mistral_ocr_response,
    parse_page_range,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "materials"
OCR_JSON = FIXTURES / "mistral_ocr_pages_9_10_min.json"


def test_parse_page_range_human_1_based_to_0_based() -> None:
    assert parse_page_range("9-11", total_pages=22) == [8, 9, 10]
    assert parse_page_range("1,3,5-6", total_pages=10) == [0, 2, 4, 5]


def test_parse_page_range_rejects_out_of_bounds() -> None:
    with pytest.raises(ValueError, match="out of range"):
        parse_page_range("20-25", total_pages=22)


def test_package_replaces_placeholders_by_mistral_id(tmp_path: Path) -> None:
    response = json.loads(OCR_JSON.read_text(encoding="utf-8"))
    result = package_mistral_ocr_response(
        response,
        original_page_numbers=[9, 10],
        out_dir=tmp_path,
    )

    md = result.document_md_path.read_text(encoding="utf-8")
    # Cookbook: ![img-0.jpeg](img-0.jpeg) → ![img-0.jpeg](assets/img-0.jpeg)
    assert "![img-0.jpeg](assets/img-0.jpeg)" in md
    assert "![img-1.jpeg](assets/img-1.jpeg)" in md
    assert "![img-2.jpeg](assets/img-2.jpeg)" in md
    assert "(img-0.jpeg)" not in md.replace("assets/img-0.jpeg", "")
    assert (tmp_path / "assets" / "img-0.jpeg").is_file()
    assert (tmp_path / "assets" / "img-1.jpeg").is_file()
    assert (tmp_path / "assets" / "img-2.jpeg").is_file()

    # Note attached to the same image object as the placeholder (by id).
    assert "Agent image note (VLM — may be wrong):" in md
    assert "Kids greet on Brook Lane." in md
    # img-1 has empty annotation payload → still gets a note after its image.
    idx0 = md.index("![img-0.jpeg](assets/img-0.jpeg)")
    idx1 = md.index("![img-1.jpeg](assets/img-1.jpeg)")
    note0 = md[idx0:idx1]
    assert "Kids greet on Brook Lane." in note0
    assert "> **Type:** comic" in note0
    assert "(empty / not provided)" in md[idx1 : idx1 + 200]

    important = json.loads(result.important_images_path.read_text(encoding="utf-8"))
    assert len(important) == 3  # all annotated cutouts; no VLM "importance" filter

    no_notes = package_mistral_ocr_response(
        response,
        original_page_numbers=[9, 10],
        out_dir=tmp_path / "no_notes",
        inject_vlm_image_notes=False,
    )
    assert "Agent image note" not in no_notes.document_md_path.read_text(
        encoding="utf-8"
    )


def test_package_writes_html_tables_by_id(tmp_path: Path) -> None:
    response = {
        "pages": [
            {
                "markdown": "Intro\n\n[tbl-0.html](tbl-0.html)\n\nOutro",
                "images": [],
                "tables": [
                    {
                        "id": "tbl-0.html",
                        "content": "<table><tr><td>HCN</td></tr></table>",
                    }
                ],
            }
        ]
    }
    result = package_mistral_ocr_response(
        response,
        original_page_numbers=[16],
        out_dir=tmp_path,
    )
    md = result.document_md_path.read_text(encoding="utf-8")
    assert "[tbl-0.html](assets/tbl-0.html)" in md
    assert (tmp_path / "assets" / "tbl-0.html").read_text(encoding="utf-8").startswith(
        "<table>"
    )


def test_package_table_crop_sidecar_and_summary_provenance(tmp_path: Path) -> None:
    from pypdf import PdfWriter

    pdf_path = tmp_path / "source.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with pdf_path.open("wb") as f:
        writer.write(f)

    response = {
        "model": "mistral-ocr-latest",
        "usage_info": {"pages_processed": 1},
        "document_annotation": {
            "document_kind": "chemistry_textbook_chapter",
            "subject": "Chemie",
            "chapter_or_topic": "Aufbau von Molekülen",
            "language": "Deutsch",
            "teacher_summary_de": "Elektronenpaarbindung und Valenzstrichformeln.",
        },
        "pages": [
            {
                "markdown": "Intro\n\n[tbl-0.html](tbl-0.html)\n\nOutro",
                "dimensions": {"width": 100, "height": 100, "dpi": 72},
                "images": [],
                "tables": [
                    {
                        "id": "tbl-0.html",
                        "content": "<table><tr><td>HCN</td></tr></table>",
                    }
                ],
                "blocks": [
                    {
                        "type": "table",
                        "id": "tbl-0.html",
                        "top_left_x": 10,
                        "top_left_y": 10,
                        "bottom_right_x": 80,
                        "bottom_right_y": 60,
                    }
                ],
            }
        ],
    }
    result = package_mistral_ocr_response(
        response,
        original_page_numbers=[5],
        out_dir=tmp_path / "pkg",
        source_pdf=pdf_path,
        arm="textbook",
        material_id="mat_test",
        session_id="sess_1",
    )
    md = result.document_md_path.read_text(encoding="utf-8")
    assert "[tbl-0.html](assets/tbl-0.html)" in md
    assert "![tbl-0.html — PDF crop (prefer for drawings)](assets/tbl-0.jpg)" in md
    crop = tmp_path / "pkg" / "assets" / "tbl-0.jpg"
    assert crop.is_file() and crop.stat().st_size > 64

    assert result.summary_md_path is not None
    summary = result.summary_md_path.read_text(encoding="utf-8")
    assert "Aufbau von Molekülen" in summary
    assert "Elektronenpaarbindung" in summary
    assert "Tables: 1" in summary

    assert result.provenance_path is not None
    prov_text = result.provenance_path.read_text(encoding="utf-8")
    assert "image_base64" not in prov_text
    prov = json.loads(prov_text)
    assert prov["material_id"] == "mat_test"
    assert prov["arm"] == "textbook"
    assert prov["source"]["sha256"]
    assert prov["pages"][0]["table_count"] == 1


def test_package_writes_page_structure_when_blocks_present(tmp_path: Path) -> None:
    response = json.loads(OCR_JSON.read_text(encoding="utf-8"))
    response["pages"][0]["blocks"] = [{"type": "title", "content": "Unit 1"}]
    response["pages"][0]["confidence_scores"] = {"page": 0.97}
    result = package_mistral_ocr_response(
        response,
        original_page_numbers=[9, 10],
        out_dir=tmp_path,
    )
    assert result.page_structure_path is not None
    structure = json.loads(result.page_structure_path.read_text(encoding="utf-8"))
    assert structure[0]["page"] == 9
    assert structure[0]["blocks"][0]["type"] == "title"


def test_sota_ocr_process_kwargs_include_ocr4_flags() -> None:
    kwargs = build_mistral_ocr_process_kwargs(
        document_url="data:application/pdf;base64,AA==",
        model="mistral-ocr-latest",
        arm="textbook",
    )
    assert kwargs["include_image_base64"] is True
    assert kwargs["table_format"] == "html"
    assert "bbox_annotation_format" in kwargs


def test_openai_vision_fallback_is_skeleton_only(tmp_path: Path) -> None:
    with pytest.raises(NotImplementedError, match="skeleton"):
        run_openai_vision_ocr_fallback(
            tmp_path / "missing.pdf",
            out_dir=tmp_path / "out",
        )
