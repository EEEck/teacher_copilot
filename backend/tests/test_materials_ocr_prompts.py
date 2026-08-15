"""OCR annotation prompts are assembled from class wiki context, not chemie defaults."""

from __future__ import annotations

from pathlib import Path

from app.services.materials_ocr import build_mistral_ocr_process_kwargs
from app.services.materials_ocr_prompts import (
    build_document_annotation_prompt,
    materials_ocr_context_from_wiki,
)
from app.teacher_agent.wiki_store import WikiStore
from tests.wiki_fixtures import CLASS_ID, SEED_WIKI

PHYS_CLASS_ID = "physik_11a_2026_27"


def _write_class_wiki(
    root: Path,
    *,
    class_id: str,
    heading: str,
    subject: str,
    grade: str,
    branch: str = "NTG",
) -> WikiStore:
    class_dir = root / "wiki" / "classes" / class_id
    class_dir.mkdir(parents=True)
    (class_dir / "class_config.md").write_text(
        f"# {heading}\n\nsubject: {subject}\n",
        encoding="utf-8",
    )
    (class_dir / "curriculum_profile.md").write_text(
        "---\n"
        "state: BY\n"
        "school_type: Gymnasium\n"
        f"branch: {branch}\n"
        f"grade: {grade}\n"
        f"subject: {subject}\n"
        "---\n"
        f"# Curriculum Profile — {heading}\n",
        encoding="utf-8",
    )
    profile = (SEED_WIKI / "wiki" / "teacher_profile.md").read_text(encoding="utf-8")
    wiki_dir = root / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    (wiki_dir / "teacher_profile.md").write_text(profile, encoding="utf-8")
    return WikiStore(root=root)


def _write_physics_11_wiki(root: Path) -> WikiStore:
    return _write_class_wiki(
        root,
        class_id=PHYS_CLASS_ID,
        heading="Physik 11a — 2026/27",
        subject="physik",
        grade="11",
    )


def test_chemie_9b_seed_wiki_textbook_prompt_uses_curriculum_profile() -> None:
    wiki = WikiStore(root=SEED_WIKI)
    ctx = materials_ocr_context_from_wiki(wiki, CLASS_ID, "textbook")
    prompt = build_document_annotation_prompt(ctx)

    assert "CLASS CONTEXT" in prompt
    assert "Chemie" in prompt
    assert "Bavaria" in prompt
    assert "Gymnasium" in prompt
    assert "NTG" in prompt
    assert "Grade 9" in prompt
    assert "Chemie 9b" in prompt
    assert "English" in prompt
    assert "textbook" in prompt.lower()
    assert "reaction equation" in prompt.lower() or "apparatus" in prompt.lower()
    assert "orbital" not in prompt.lower()
    assert "Venn" not in prompt
    assert "language book" not in prompt.lower()
    assert "9–10" not in prompt
    assert "KLASSENKONTEXT" not in prompt


def test_chemie_9b_personal_prompt_expects_mixed_media() -> None:
    wiki = WikiStore(root=SEED_WIKI)
    ctx = materials_ocr_context_from_wiki(wiki, CLASS_ID, "personal")
    prompt = build_document_annotation_prompt(ctx)

    assert "MATERIAL KIND (personal)" in prompt
    assert "handwriting" in prompt.lower()
    assert "board" in prompt.lower() or "slide" in prompt.lower() or "PDF" in prompt
    assert "Grade 9" in prompt


def test_physics_11_mock_class_prompt(tmp_path: Path) -> None:
    wiki = _write_physics_11_wiki(tmp_path)
    ctx = materials_ocr_context_from_wiki(wiki, PHYS_CLASS_ID, "textbook")
    prompt = build_document_annotation_prompt(ctx)

    assert "Physik" in prompt
    assert "Grade 11" in prompt
    assert "Physik 11a" in prompt
    assert "Bavaria" in prompt
    assert "Gymnasium" in prompt
    assert "circuit" in prompt.lower() or "energy graph" in prompt.lower()
    assert "orbital" not in prompt.lower()
    assert "Venn" not in prompt
    assert "language book" not in prompt.lower()
    assert "Aufbau von Molekülen" not in prompt
    assert "9–10" not in prompt
    assert "KLASSENKONTEXT" not in prompt


def test_latin_uses_generic_overlay_not_stem_library(tmp_path: Path) -> None:
    wiki = _write_class_wiki(
        tmp_path,
        class_id="latein_8a_2026_27",
        heading="Latein 8a — 2026/27",
        subject="latein",
        grade="8",
        branch="SG",
    )
    prompt = build_document_annotation_prompt(
        materials_ocr_context_from_wiki(wiki, "latein_8a_2026_27", "textbook")
    )
    assert "SUBJECT OVERLAY (generic)" in prompt
    assert "diagrams, photos, tables" in prompt.lower() or "inserted images" in prompt.lower()
    assert "reaction equation" not in prompt.lower()
    assert "circuit" not in prompt.lower()
    assert "Latein" in prompt or "latein" in prompt.lower()


def test_biologie_uses_stem_overlay(tmp_path: Path) -> None:
    wiki = _write_class_wiki(
        tmp_path,
        class_id="bio_10a_2026_27",
        heading="Biologie 10a — 2026/27",
        subject="biologie",
        grade="10",
    )
    prompt = build_document_annotation_prompt(
        materials_ocr_context_from_wiki(wiki, "bio_10a_2026_27", "textbook")
    )
    assert "SUBJECT OVERLAY (biologie)" in prompt
    assert "cell" in prompt.lower() or "organism" in prompt.lower()
    assert "SUBJECT OVERLAY (generic)" not in prompt
    assert "SUBJECT OVERLAY (chemie)" not in prompt


def test_mathe_uses_stem_overlay(tmp_path: Path) -> None:
    wiki = _write_class_wiki(
        tmp_path,
        class_id="mathe_7b_2026_27",
        heading="Mathematik 7b — 2026/27",
        subject="mathematik",
        grade="7",
    )
    prompt = build_document_annotation_prompt(
        materials_ocr_context_from_wiki(wiki, "mathe_7b_2026_27", "textbook")
    )
    assert "SUBJECT OVERLAY (mathe)" in prompt
    assert "geometric" in prompt.lower() or "formula" in prompt.lower()
    assert "SUBJECT OVERLAY (generic)" not in prompt
    assert "reaction equation" not in prompt.lower()


def test_ocr_process_kwargs_inject_assembled_wiki_prompt() -> None:
    wiki = WikiStore(root=SEED_WIKI)
    ctx = materials_ocr_context_from_wiki(wiki, CLASS_ID, "textbook")
    expected = build_document_annotation_prompt(ctx)
    kwargs = build_mistral_ocr_process_kwargs(
        document_url="data:application/pdf;base64,AA==",
        model="mistral-ocr-latest",
        ocr_context=ctx,
    )
    assert kwargs["document_annotation_prompt"] == expected
