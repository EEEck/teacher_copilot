"""Opt-in live Mistral OCR against the ESL textbook page slice.

Requires ``MISTRAL_API_KEY`` in ``backend/.env`` and::

    set RUN_LIVE_MISTRAL_OCR=1
    .\\.venv\\Scripts\\python -m pytest tests\\test_materials_ocr_live.py -q
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.config import get_settings
from app.services.materials_ocr import mistral_ocr_configured, run_mistral_ocr_on_pdf

RUN_LIVE = os.getenv("RUN_LIVE_MISTRAL_OCR") == "1"
FIXTURE_PDF = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "materials"
    / "esl_textbook_sample_pages_9_to_11.pdf"
)


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.skipif(
    not RUN_LIVE,
    reason="live Mistral OCR is opt-in (set RUN_LIVE_MISTRAL_OCR=1)",
)
def test_live_mistral_ocr_packages_esl_page_slice(tmp_path: Path) -> None:
    if not mistral_ocr_configured():
        pytest.skip("MISTRAL_API_KEY not configured in backend/.env")
    if not FIXTURE_PDF.is_file():
        pytest.skip(f"missing fixture PDF: {FIXTURE_PDF}")

    # Fixture file is already pages 9–11 of the full book.
    result = run_mistral_ocr_on_pdf(
        FIXTURE_PDF,
        out_dir=tmp_path / "mistral_ocr",
        original_page_numbers=[9, 10, 11],
        subject="general",
        arm="textbook",
    )

    md = result.document_md_path.read_text(encoding="utf-8")
    assert "## PDF page 9" in md
    assert "## PDF page 10" in md
    assert "## PDF page 11" in md
    assert "base64," not in md
    assert result.asset_count >= 1
    assert result.manifest_path.is_file()
    assert result.important_images_path.is_file()
    assert (tmp_path / "mistral_ocr" / "raw_response.json").is_file()
    # OCR 4 should return typed blocks and/or confidence on pages.
    raw = (tmp_path / "mistral_ocr" / "raw_response.json").read_text(encoding="utf-8")
    assert '"blocks"' in raw or "confidence" in raw.lower()
    if result.page_structure_path is not None:
        assert result.page_structure_path.is_file()
