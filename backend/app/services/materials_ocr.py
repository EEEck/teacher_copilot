"""Mistral OCR 4 materials extraction (primary; no Docling/LlamaParse).

Thin wrapper around Mistral Document AI:
- OCR 4: blocks, page confidence, header/footer, HTML tables, image cutouts
- bbox annotations via schema Field descriptions (+ short domain prompt)
- optional document_annotation for chapter/topic metadata
- packaging: OCR markdown + local assets + figure notes as returned

Fallback: OpenAI vision skeleton only (``implement later``).
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from app.config import Settings, get_settings
from app.services.materials_ocr_packaging import (
    MaterialsOcrPackage,
    package_mistral_ocr_response,
    parse_page_range,
)
from app.services.materials_ocr_prompts import (
    MaterialArm,
    MaterialsDocumentAnnotation,
    SubjectId,
    build_document_annotation_prompt,
    build_teaching_image_note_model,
)

logger = logging.getLogger(__name__)

# Soft size tip: above this, prefer Files API over inlining a data URL.
_DATA_URL_SOFT_MAX_BYTES = 4 * 1024 * 1024


def _as_dict(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, list):
        return [_as_dict(x) for x in obj]
    if isinstance(obj, tuple):
        return [_as_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _as_dict(v) for k, v in obj.items()}
    if hasattr(obj, "model_dump"):
        return _as_dict(obj.model_dump())
    if hasattr(obj, "__dict__"):
        return {
            k: _as_dict(v) for k, v in obj.__dict__.items() if not k.startswith("_")
        }
    return str(obj)


def _mistral_response_format(model_cls: type[BaseModel]) -> dict[str, Any]:
    try:
        from mistralai.extra import response_format_from_pydantic_model

        return response_format_from_pydantic_model(model_cls)
    except Exception:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": model_cls.__name__,
                "schema": model_cls.model_json_schema(),
                "strict": True,
            },
        }


def _get_mistral_client(api_key: str):
    try:
        from mistralai import Mistral
    except Exception:  # pragma: no cover
        from mistralai.client import Mistral  # type: ignore

    return Mistral(api_key=api_key)


def mistral_ocr_configured(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return bool(settings.mistral_api_key.get_secret_value().strip())


def pdf_as_data_url(pdf_path: Path) -> str:
    pdf_b64 = base64.b64encode(pdf_path.read_bytes()).decode("utf-8")
    return f"data:application/pdf;base64,{pdf_b64}"


def build_mistral_ocr_process_kwargs(
    *,
    document_url: str,
    model: str,
    include_bbox_annotations: bool = True,
    include_document_annotation: bool = True,
    subject: SubjectId = "chemie",
    arm: MaterialArm = "textbook",
    grade_hint: str | None = None,
) -> dict[str, Any]:
    """OCR 4 process kwargs (testable without a live call).

    Subject/arm context is injected into:
    - ``document_annotation_prompt`` (document-level schema only), and
    - bbox schema Field descriptions (what actually steers figure notes).
    """
    prompt_kwargs: dict[str, Any] = {"subject": subject, "arm": arm}
    if grade_hint:
        prompt_kwargs["grade_hint"] = grade_hint
    kwargs: dict[str, Any] = {
        "model": model,
        "document": {
            "type": "document_url",
            "document_url": document_url,
        },
        # OCR 4 layout primitives for reading-order / citation grounding.
        "include_blocks": True,
        "extract_header": True,
        "extract_footer": True,
        "confidence_scores_granularity": "page",
        # Tables + figures.
        "table_format": "html",
        "include_image_base64": True,
        "image_min_size": 100,
        "image_limit": 40,
    }
    if include_bbox_annotations:
        note_model = build_teaching_image_note_model(
            subject=subject, arm=arm, grade_hint=grade_hint
        )
        kwargs["bbox_annotation_format"] = _mistral_response_format(note_model)
    if include_document_annotation:
        kwargs["document_annotation_format"] = _mistral_response_format(
            MaterialsDocumentAnnotation
        )
        kwargs["document_annotation_prompt"] = build_document_annotation_prompt(
            **prompt_kwargs
        )
    return kwargs


def _resolve_document_url(client: Any, pdf_path: Path) -> tuple[str, str | None]:
    """Return (document_url, uploaded_file_id_or_None).

    Prefer Files upload + signed URL (production pattern). Fall back to a data
    URL for small local spikes if upload is unavailable.
    """
    size = pdf_path.stat().st_size
    try:
        with pdf_path.open("rb") as fh:
            uploaded = client.files.upload(
                file={
                    "file_name": pdf_path.name,
                    "content": fh,
                },
                purpose="ocr",
            )
        file_id = getattr(uploaded, "id", None) or (uploaded or {}).get("id")
        if not file_id:
            raise RuntimeError("Mistral files.upload returned no file id")
        signed = client.files.get_signed_url(file_id=file_id)
        url = getattr(signed, "url", None) or (signed or {}).get("url")
        if not url:
            raise RuntimeError("Mistral get_signed_url returned no url")
        return str(url), str(file_id)
    except Exception as exc:
        if size > _DATA_URL_SOFT_MAX_BYTES:
            raise RuntimeError(
                "Mistral Files upload failed for a large PDF; refusing data-URL "
                f"fallback ({size} bytes). Original error: {exc}"
            ) from exc
        logger.warning(
            "Mistral Files upload unavailable (%s); using data-URL for %s (%s bytes)",
            exc,
            pdf_path.name,
            size,
        )
        return pdf_as_data_url(pdf_path), None


def _delete_uploaded_file(client: Any, file_id: str | None) -> None:
    if not file_id:
        return
    try:
        client.files.delete(file_id=file_id)
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to delete Mistral OCR upload %s: %s", file_id, exc)


def _write_raw_response_debug(raw: dict[str, Any], raw_path: Path) -> None:
    raw_for_disk = _as_dict(raw)
    for page in raw_for_disk.get("pages") or []:
        if not isinstance(page, dict):
            continue
        for img in page.get("images") or []:
            if isinstance(img, dict) and "image_base64" in img:
                img["image_base64"] = (
                    f"<omitted {len(str(img['image_base64']))} chars>"
                )
    raw_path.write_text(
        json.dumps(raw_for_disk, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run_mistral_ocr_on_pdf(
    pdf_path: Path,
    *,
    out_dir: Path,
    original_page_numbers: list[int] | None = None,
    page_range: str | None = None,
    settings: Settings | None = None,
    include_bbox_annotations: bool = True,
    include_document_annotation: bool = True,
    subject: SubjectId = "chemie",
    arm: MaterialArm = "textbook",
    grade_hint: str | None = None,
    inject_vlm_image_notes: bool = True,
    material_id: str | None = None,
    session_id: str | None = None,
    copy_source_pdf: bool = True,
) -> MaterialsOcrPackage:
    """OCR a PDF with Mistral OCR 4 and write the materials package under ``out_dir``."""
    settings = settings or get_settings()
    api_key = settings.mistral_api_key.get_secret_value().strip()
    if not api_key:
        raise RuntimeError("MISTRAL_API_KEY is not configured")

    pdf_path = Path(pdf_path)
    if not pdf_path.is_file():
        raise FileNotFoundError(pdf_path)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    send_pdf = pdf_path
    if page_range:
        from pypdf import PdfReader, PdfWriter

        reader = PdfReader(str(pdf_path))
        indexes = parse_page_range(page_range, len(reader.pages))
        writer = PdfWriter()
        for idx in indexes:
            writer.add_page(reader.pages[idx])
        send_pdf = out_dir / "source.pdf"
        with send_pdf.open("wb") as f:
            writer.write(f)
        if original_page_numbers is None:
            original_page_numbers = [i + 1 for i in indexes]
    elif copy_source_pdf:
        dest = out_dir / "source.pdf"
        if pdf_path.resolve() != dest.resolve():
            dest.write_bytes(pdf_path.read_bytes())
        send_pdf = dest

    client = _get_mistral_client(api_key)
    document_url, uploaded_file_id = _resolve_document_url(client, send_pdf)
    try:
        kwargs = build_mistral_ocr_process_kwargs(
            document_url=document_url,
            model=settings.mistral_ocr_model,
            include_bbox_annotations=include_bbox_annotations,
            include_document_annotation=include_document_annotation,
            subject=subject,
            arm=arm,
            grade_hint=grade_hint,
        )
        response = client.ocr.process(**kwargs)
    finally:
        _delete_uploaded_file(client, uploaded_file_id)

    raw = _as_dict(response)
    _write_raw_response_debug(raw, out_dir / "raw_response.json")
    doc_ann = raw.get("document_annotation")
    if doc_ann is not None:
        (out_dir / "document_annotation.json").write_text(
            json.dumps(
                json.loads(doc_ann) if isinstance(doc_ann, str) else doc_ann,
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    pages = raw.get("pages") or []
    if original_page_numbers is None:
        original_page_numbers = list(range(1, len(pages) + 1))
    if len(original_page_numbers) != len(pages):
        raise RuntimeError(
            f"OCR returned {len(pages)} pages but expected "
            f"{len(original_page_numbers)} ({original_page_numbers})"
        )

    return package_mistral_ocr_response(
        raw,
        original_page_numbers=original_page_numbers,
        out_dir=out_dir,
        inject_vlm_image_notes=inject_vlm_image_notes,
        source_pdf=send_pdf,
        arm=arm,
        material_id=material_id,
        session_id=session_id,
    )


def run_openai_vision_ocr_fallback(
    pdf_path: Path,
    *,
    out_dir: Path,
    original_page_numbers: list[int] | None = None,
    page_range: str | None = None,
    settings: Settings | None = None,
) -> MaterialsOcrPackage:
    """Skeleton fallback: render pages → OpenAI vision model → package trio.

    Implement later with the OpenAI SDK (page images + structured markdown).
    Not wired as an automatic backup — call explicitly only when experimenting.
    """
    # IMPLEMENT LATER: OpenAI vision OCR fallback
    # 1) Rasterize PDF pages (pypdfium2 / pdf2image) for page_range
    # 2) Call OpenAI Responses/Chat with image inputs (settings.openai_api_key +
    #    a vision-capable model, e.g. settings.openai_strong_model)
    # 3) Ask for per-page markdown + image placeholders (no Docling/LlamaParse)
    # 4) Normalize into the same MaterialsOcrPackage shape as Mistral packaging
    _ = (pdf_path, out_dir, original_page_numbers, page_range, settings)
    raise NotImplementedError(
        "OpenAI vision OCR fallback is a skeleton only — implement later"
    )


def run_materials_ocr_on_pdf(
    pdf_path: Path,
    *,
    out_dir: Path,
    original_page_numbers: list[int] | None = None,
    page_range: str | None = None,
    settings: Settings | None = None,
    include_bbox_annotations: bool = True,
    engine: Literal["mistral", "openai_vision"] = "mistral",
) -> MaterialsOcrPackage:
    """Public entry: Mistral OCR 4 by default; optional explicit OpenAI skeleton."""
    if engine == "openai_vision":
        return run_openai_vision_ocr_fallback(
            pdf_path,
            out_dir=out_dir,
            original_page_numbers=original_page_numbers,
            page_range=page_range,
            settings=settings,
        )
    return run_mistral_ocr_on_pdf(
        pdf_path,
        out_dir=out_dir,
        original_page_numbers=original_page_numbers,
        page_range=page_range,
        settings=settings,
        include_bbox_annotations=include_bbox_annotations,
    )
