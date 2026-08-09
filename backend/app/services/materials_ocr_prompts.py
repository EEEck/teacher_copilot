"""Annotation prompts / schemas for class materials OCR.

Mistral:
- ``document_annotation_prompt`` steers document-level JSON only.
- Bbox notes are steered by schema ``Field(description=...)``.

Keep the bbox schema small: agent-friendly figure notes, not lesson-planning
policy. Importance / HITL come later.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MaterialArm = Literal["textbook", "personal"]
SubjectId = Literal["chemie", "general"]


def build_document_annotation_prompt(
    *,
    subject: SubjectId = "chemie",
    arm: MaterialArm = "textbook",
    locale: str = "de-DE",
    grade_hint: str = "Gymnasium, etwa Jahrgangsstufe 9–10 (NTG)",
) -> str:
    """Short domain prompt for Mistral ``document_annotation_prompt``."""
    if subject == "chemie" and arm == "textbook":
        return (
            f"Dies ist ein Ausschnitt aus einem deutschen {grade_hint} "
            "Chemie-Schulbuch (Lehrwerk), keine Rechnung und kein Sprachbuch. "
            f"Sprache der Texte: überwiegend Deutsch ({locale}); Formeln können "
            "lateinische Elementsymbole nutzen.\n"
            "Typische Abbildungen: Molekülorbital-/Energieniveau-Diagramme "
            "(bindend/antibindend), Bindungsenergie-Abstand-Kurven, "
            "Valenzstrichformeln, Molekülmodelle (Kugel-Stab/Kalotten), "
            "Apparaturen, Tabellen — oft mit farbigen Orbital-Wolken, die "
            "KEINE Venn-Diagramme sind.\n"
            "Extrahiere nur, was im Dokument steht. Keine erfundenen Orte, "
            "Sprachwissenschaft oder fremde Fächer. Fehlende Felder leer lassen."
        )
    if subject == "chemie" and arm == "personal":
        return (
            "Dies sind von einer Lehrkraft erstellte oder fotografierte "
            f"Chemie-Materialien ({grade_hint}), z. B. Arbeitsblatt, Tafelbild "
            "oder Notizen — kein Belletristik-/Sprachbuch.\n"
            "Erwarte Handschrift, Skizzen, Reaktionsgleichungen und "
            "Orbital-/Strukturzeichnungen. Nur sichtbaren Inhalt extrahieren; "
            "bei Unsicherheit Felder leer lassen."
        )
    if arm == "textbook":
        return (
            f"School textbook excerpt ({locale}). Extract only what appears in "
            "the document; leave fields empty if unsure. Do not invent topics."
        )
    return (
        f"Teacher-created classroom material ({locale}). Extract only visible "
        "content; leave fields empty if unsure."
    )


class MaterialsDocumentAnnotation(BaseModel):
    """Compact document-level annotation (≤8 pages recommended by Mistral)."""

    document_kind: str = Field(
        description=(
            "One of: chemistry_textbook_chapter, chemistry_worksheet, "
            "chemistry_notes, other_school_material."
        )
    )
    subject: str = Field(
        description="Subject label, e.g. Chemie. Empty if unclear."
    )
    chapter_or_topic: str = Field(
        description=(
            "Chapter/topic title if visible (e.g. Aufbau von Molekülen). "
            "Empty if none."
        )
    )
    language: str = Field(
        description="Primary language code or name, e.g. Deutsch / de."
    )
    teacher_summary_de: str = Field(
        description=(
            "2–4 German sentences: what this excerpt teaches. Only facts "
            "supported by the pages. Empty if unsure."
        )
    )


def build_teaching_image_note_model(
    *,
    subject: SubjectId = "chemie",
    arm: MaterialArm = "textbook",
    grade_hint: str | None = None,
) -> type[BaseModel]:
    """Simple bbox schema (close to Mistral's cookbook Image example)."""
    prompt_kwargs: dict = {"subject": subject, "arm": arm}
    if grade_hint:
        prompt_kwargs["grade_hint"] = grade_hint
    background = build_document_annotation_prompt(**prompt_kwargs)

    class FigureNote(BaseModel):
        image_type: str = Field(
            description=(
                "Short type label, e.g. orbital_diagram, energy_curve, "
                "molecule_model, structure_formula, apparatus, photo, "
                "comic, chart, decorative, other."
            )
        )
        short_description: str = Field(
            description=(
                f"DOCUMENT CONTEXT: {background}\n"
                "1–2 short sentences (DE or EN) describing what is literally "
                "visible in this figure cutout. Max ~40 words."
            )
        )
        visible_text: list[str] = Field(
            description=(
                "Labels/text drawn inside the figure, quoted as seen. "
                "Empty list if none are legible."
            )
        )

    FigureNote.__name__ = "FigureNote"
    FigureNote.__qualname__ = "FigureNote"
    return FigureNote
