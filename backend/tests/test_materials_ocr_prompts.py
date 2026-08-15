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


def _write_physics_11_wiki(root: Path) -> WikiStore:
    class_dir = root / "wiki" / "classes" / PHYS_CLASS_ID
    class_dir.mkdir(parents=True)
    (class_dir / "class_config.md").write_text(
        "# Physik 11a — 2026/27\n\nsubject: physik\n",
        encoding="utf-8",
    )
    (class_dir / "curriculum_profile.md").write_text(
        "---\n"
        "state: BY\n"
        "school_type: Gymnasium\n"
        "branch: NTG\n"
        "grade: 11\n"
        "subject: physik\n"
        "---\n"
        "# Curriculum Profile — Physik 11a\n",
        encoding="utf-8",
    )
    profile = (SEED_WIKI / "wiki" / "teacher_profile.md").read_text(encoding="utf-8")
    (root / "wiki" / "teacher_profile.md").write_text(profile, encoding="utf-8")
    return WikiStore(root=root)


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
    assert "Lewis" in prompt or "orbital" in prompt.lower()
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
    assert "circuit" in prompt.lower() or "free-body" in prompt.lower()
    assert "molecular orbital" not in prompt.lower()
    assert "Venn" not in prompt
    assert "Aufbau von Molekülen" not in prompt
    assert "9–10" not in prompt
    assert "KLASSENKONTEXT" not in prompt


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
