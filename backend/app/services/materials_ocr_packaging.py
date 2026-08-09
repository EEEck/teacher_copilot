"""Assemble Mistral OCR pages into local markdown + assets.

Follows Mistral's cookbook pattern: replace ``![id](id)`` / ``[tbl](tbl)`` by id.
Adds: VLM figure notes, HTML tables + PDF table crops, summary.md, provenance.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MaterialsOcrPackage:
    document_md_path: Path
    manifest_path: Path
    important_images_path: Path
    asset_count: int
    important_count: int
    page_structure_path: Path | None = None
    summary_md_path: Path | None = None
    provenance_path: Path | None = None


def parse_page_range(page_range: str, total_pages: int) -> list[int]:
    """Return 0-based page indexes from a human 1-based range like '9-10'."""
    out: list[int] = []
    for part in page_range.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            start, end = map(int, part.split("-", 1))
            out.extend(range(start - 1, end))
        else:
            out.append(int(part) - 1)

    bad = [p + 1 for p in out if p < 0 or p >= total_pages]
    if bad:
        raise ValueError(f"Page(s) out of range: {bad}; PDF has {total_pages} pages")
    return out


def _parse_annotation(raw: Any) -> dict[str, Any]:
    empty = {"image_type": "", "short_description": "", "visible_text": []}
    if raw is None:
        return empty
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return empty
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {
                "image_type": "",
                "short_description": raw[:200],
                "visible_text": [],
            }
    if not isinstance(raw, dict):
        return empty

    visible = raw.get("visible_text") or []
    if isinstance(visible, str):
        visible = [visible] if visible else []

    description = str(raw.get("short_description") or raw.get("caption") or "")
    image_type = str(raw.get("image_type") or raw.get("pedagogical_role") or "")
    return {
        "image_type": image_type,
        "short_description": description,
        "visible_text": [str(x) for x in visible],
    }


def _decode_image_bytes(image_base64: str | None) -> bytes | None:
    if not isinstance(image_base64, str) or not image_base64:
        return None
    if image_base64.startswith("<omitted") or image_base64.startswith("<redacted"):
        return None
    val = image_base64
    if val.startswith("data:"):
        _, val = val.split(",", 1)
    try:
        raw = base64.b64decode(val, validate=False)
    except Exception:
        return None
    return raw if len(raw) >= 64 else None


def _agent_image_note(annotation: dict[str, Any]) -> str:
    description = (annotation.get("short_description") or "").strip()
    image_type = (annotation.get("image_type") or "").strip()
    visible = [
        str(x).strip()
        for x in (annotation.get("visible_text") or [])
        if str(x).strip()
    ]
    lines = [
        "> **Agent image note (VLM — may be wrong):** "
        + (description or "(empty / not provided)")
    ]
    if image_type:
        lines.append(f"> **Type:** {image_type}")
    if visible:
        lines.append(f"> **Visible text:** {'; '.join(visible)}")
    return "\n".join(lines)


def _replace_image_placeholder(
    markdown: str,
    *,
    image_id: str,
    local_link: str,
    note: str | None = None,
) -> str:
    placeholder = f"![{image_id}]({image_id})"
    replacement = f"![{image_id}]({local_link})"
    if note:
        replacement = replacement + "\n\n" + note
    if placeholder not in markdown:
        return markdown
    return markdown.replace(placeholder, replacement, 1)


def _replace_table_placeholder(
    markdown: str,
    *,
    table_id: str,
    local_link: str,
    crop_link: str | None = None,
) -> str:
    placeholder = f"[{table_id}]({table_id})"
    if placeholder not in markdown:
        return markdown
    replacement = f"[{table_id}]({local_link})"
    if crop_link:
        replacement += (
            f"\n\n![{table_id} — PDF crop (prefer for drawings)]({crop_link})"
        )
    return markdown.replace(placeholder, replacement, 1)


def _find_table_bbox(
    page: dict[str, Any], table_id: str
) -> tuple[int, int, int, int] | None:
    want = {table_id, Path(table_id).name, Path(table_id).stem}
    for block in page.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        if (block.get("type") or "").lower() != "table":
            continue
        bid = str(block.get("table_id") or block.get("id") or "")
        if bid not in want and Path(bid).name not in want:
            continue
        try:
            return (
                int(block["top_left_x"]),
                int(block["top_left_y"]),
                int(block["bottom_right_x"]),
                int(block["bottom_right_y"]),
            )
        except (KeyError, TypeError, ValueError):
            return None
    return None


def _ocr_page_dimensions(page: dict[str, Any]) -> tuple[int, int, int] | None:
    dims = page.get("dimensions") or {}
    width, height = dims.get("width"), dims.get("height")
    if not width or not height:
        return None
    return int(width), int(height), int(dims.get("dpi") or 200)


def crop_pdf_page_region_jpeg(
    pdf_path: Path,
    *,
    pdf_page_index: int,
    bbox: tuple[int, int, int, int],
    ocr_width: int,
    ocr_height: int,
    dpi: int = 200,
) -> bytes | None:
    try:
        import pypdfium2 as pdfium
        from PIL import Image
    except ImportError:
        return None

    pdf_path = Path(pdf_path)
    if not pdf_path.is_file():
        return None
    left, top, right, bottom = bbox
    if right <= left or bottom <= top:
        return None

    doc = pdfium.PdfDocument(str(pdf_path))
    try:
        if pdf_page_index < 0 or pdf_page_index >= len(doc):
            return None
        page = doc[pdf_page_index]
        scale = max(dpi, 72) / 72.0
        pil = page.render(scale=scale).to_pil().convert("RGB")
    finally:
        doc.close()

    if pil.size != (ocr_width, ocr_height):
        pil = pil.resize((ocr_width, ocr_height), Image.Resampling.LANCZOS)

    left = max(0, min(left, ocr_width - 1))
    top = max(0, min(top, ocr_height - 1))
    right = max(left + 1, min(right, ocr_width))
    bottom = max(top + 1, min(bottom, ocr_height))
    crop = pil.crop((left, top, right, bottom))
    buf = BytesIO()
    crop.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _parse_document_annotation(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return {}
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {"teacher_summary_de": raw[:500]}
    return raw if isinstance(raw, dict) else {}


def write_summary_md(
    *,
    out_dir: Path,
    original_page_numbers: list[int],
    document_annotation: dict[str, Any],
    manifest: list[dict[str, Any]],
) -> Path:
    chapter = str(document_annotation.get("chapter_or_topic") or "").strip()
    subject = str(document_annotation.get("subject") or "").strip()
    summary = str(document_annotation.get("teacher_summary_de") or "").strip()
    kind = str(document_annotation.get("document_kind") or "").strip()
    figures = [r for r in manifest if r.get("kind") != "table"]
    tables = [r for r in manifest if r.get("kind") == "table"]

    lines = [
        "# Material summary",
        "",
        f"- Pages: {original_page_numbers[0]}–{original_page_numbers[-1]}"
        if original_page_numbers
        else "- Pages: (unknown)",
        f"- Subject: {subject or '(unknown)'}",
        f"- Kind: {kind or '(unknown)'}",
        f"- Chapter/topic: {chapter or '(unknown)'}",
        f"- Figures: {len(figures)}",
        f"- Tables: {len(tables)}",
        "",
        "## Summary",
        "",
        summary or "(no document annotation summary)",
        "",
        "## Agent use",
        "",
        "- Prefer `summary.md` for orientation; read `document.agent.md` on demand.",
        "- PDF `source.pdf` is reference only (not the search corpus).",
        "- Table HTML may flatten drawings; prefer `assets/tbl-*.jpg` crops when present.",
        "",
    ]
    path = out_dir / "summary.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_provenance_json(
    *,
    out_dir: Path,
    source_pdf: Path | None,
    response: dict[str, Any],
    original_page_numbers: list[int],
    arm: str | None = None,
    material_id: str | None = None,
    session_id: str | None = None,
) -> Path:
    source_meta: dict[str, Any] = {}
    if source_pdf and Path(source_pdf).is_file():
        data = Path(source_pdf).read_bytes()
        source_meta = {
            "filename": Path(source_pdf).name,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    pages_meta = []
    for page, page_num in zip(response.get("pages") or [], original_page_numbers):
        if not isinstance(page, dict):
            continue
        conf = page.get("confidence_scores") or {}
        pages_meta.append(
            {
                "page": page_num,
                "image_count": len(page.get("images") or []),
                "table_count": len(page.get("tables") or []),
                "block_count": len(page.get("blocks") or []),
                "average_page_confidence": conf.get("average_page_confidence_score"),
            }
        )
    payload = {
        "material_id": material_id,
        "session_id": session_id,
        "arm": arm,
        "source": source_meta,
        "model": response.get("model"),
        "usage_info": response.get("usage_info"),
        "original_page_numbers": original_page_numbers,
        "pages": pages_meta,
    }
    path = out_dir / "provenance.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def package_mistral_ocr_response(
    response: dict[str, Any],
    *,
    original_page_numbers: list[int],
    out_dir: Path,
    inject_vlm_image_notes: bool = True,
    source_pdf: Path | None = None,
    arm: str | None = None,
    material_id: str | None = None,
    session_id: str | None = None,
) -> MaterialsOcrPackage:
    """Write document.agent.md + assets + summary + provenance under ``out_dir``."""
    pages = response.get("pages") or []
    if len(pages) != len(original_page_numbers):
        raise ValueError(
            f"page count mismatch: OCR has {len(pages)} pages, "
            f"original_page_numbers has {len(original_page_numbers)}"
        )

    assets_dir = out_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    source_pdf = Path(source_pdf) if source_pdf else None

    manifest: list[dict[str, Any]] = []
    important: list[dict[str, Any]] = []
    markdown_pages: list[str] = []
    page_structure: list[dict[str, Any]] = []

    for page_index, (page, original_page_num) in enumerate(
        zip(pages, original_page_numbers, strict=True)
    ):
        md = str(page.get("markdown") or "")

        structure_row: dict[str, Any] = {"page": original_page_num}
        for key in ("blocks", "confidence_scores", "header", "footer"):
            val = page.get(key)
            if val not in (None, "", []):
                structure_row[key] = val
        if len(structure_row) > 1:
            page_structure.append(structure_row)

        for img in page.get("images") or []:
            if not isinstance(img, dict):
                continue
            image_id = str(img.get("id") or "").strip()
            if not image_id:
                continue

            img_bytes = _decode_image_bytes(
                img.get("image_base64")
                if isinstance(img.get("image_base64"), str)
                else None
            )
            asset_path = assets_dir / image_id
            if img_bytes:
                asset_path.write_bytes(img_bytes)
            local_link = f"assets/{image_id}"

            annotation = _parse_annotation(img.get("image_annotation"))
            row = {
                "page": original_page_num,
                "source_image_id": image_id,
                "file": image_id,
                "markdown_link": local_link,
                "annotation": annotation,
            }
            manifest.append(row)
            if img.get("image_annotation") is not None:
                important.append(row)

            note = None
            if inject_vlm_image_notes and img.get("image_annotation") is not None:
                note = _agent_image_note(annotation)
            md = _replace_image_placeholder(
                md,
                image_id=image_id,
                local_link=local_link,
                note=note,
            )

        for table in page.get("tables") or []:
            if not isinstance(table, dict):
                continue
            table_id = str(table.get("id") or "").strip()
            html = str(table.get("content") or "").strip()
            if not table_id or not html:
                continue
            (assets_dir / table_id).write_text(html + "\n", encoding="utf-8")
            local_link = f"assets/{table_id}"
            crop_link: str | None = None
            crop_name: str | None = None
            bbox = _find_table_bbox(page, table_id)
            dims = _ocr_page_dimensions(page)
            if source_pdf and bbox and dims:
                ocr_w, ocr_h, dpi = dims
                jpeg = crop_pdf_page_region_jpeg(
                    source_pdf,
                    pdf_page_index=page_index,
                    bbox=bbox,
                    ocr_width=ocr_w,
                    ocr_height=ocr_h,
                    dpi=dpi,
                )
                if jpeg:
                    crop_name = f"{Path(table_id).stem}.jpg"
                    (assets_dir / crop_name).write_bytes(jpeg)
                    crop_link = f"assets/{crop_name}"
            md = _replace_table_placeholder(
                md,
                table_id=table_id,
                local_link=local_link,
                crop_link=crop_link,
            )
            manifest.append(
                {
                    "page": original_page_num,
                    "source_image_id": table_id,
                    "file": table_id,
                    "markdown_link": local_link,
                    "crop_file": crop_name,
                    "kind": "table",
                }
            )

        markdown_pages.append(
            f"---\n\n## PDF page {original_page_num}\n\n{md}".strip()
        )

    document_md_path = out_dir / "document.agent.md"
    document_md_path.write_text(
        "# OCR Markdown for agent ingestion\n\n"
        + "\n\n".join(markdown_pages)
        + "\n",
        encoding="utf-8",
    )

    manifest_path = assets_dir / "manifest.json"
    important_images_path = out_dir / "important_images.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    important_images_path.write_text(
        json.dumps(important, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    page_structure_path: Path | None = None
    if page_structure:
        page_structure_path = out_dir / "page_structure.json"
        page_structure_path.write_text(
            json.dumps(page_structure, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    doc_ann = _parse_document_annotation(response.get("document_annotation"))
    summary_md_path = write_summary_md(
        out_dir=out_dir,
        original_page_numbers=original_page_numbers,
        document_annotation=doc_ann,
        manifest=manifest,
    )
    provenance_path = write_provenance_json(
        out_dir=out_dir,
        source_pdf=source_pdf,
        response=response,
        original_page_numbers=original_page_numbers,
        arm=arm,
        material_id=material_id,
        session_id=session_id,
    )

    return MaterialsOcrPackage(
        document_md_path=document_md_path,
        manifest_path=manifest_path,
        important_images_path=important_images_path,
        asset_count=len(manifest),
        important_count=len(important),
        page_structure_path=page_structure_path,
        summary_md_path=summary_md_path,
        provenance_path=provenance_path,
    )
