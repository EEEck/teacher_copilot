"""Structured, single-source lesson-package contract.

The package is deliberately independent of the chat/runtime layer: it can be
validated and rendered deterministically, while ``plan_markdown`` remains the
backward-compatible transport and persistence format.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LearningGoal(BaseModel):
    statement: str
    knowledge: str | None = None
    practice: str | None = None
    meaning: str | None = None


class AnticipatedStudentIdea(BaseModel):
    idea: str
    why_it_may_appear: str
    teacher_move: str


class RepresentationChoice(BaseModel):
    representation: str
    purpose: str
    transition_to_or_from: str | None = None


class SourceRef(BaseModel):
    source_id: str
    section_id: str = ""
    label: str = ""


class DocumentSection(BaseModel):
    title: str
    items: list[str] = Field(default_factory=list)


class ArtifactSection(BaseModel):
    audience: Literal["teacher", "student", "observation"]
    title: str
    sections: list[DocumentSection] = Field(default_factory=list)


class LessonShared(BaseModel):
    subject: str
    grade: int
    branch: str | None = None
    artifact_language: str = "en"
    duration_minutes: int
    phenomenon_or_context: str
    central_question: str
    big_idea: str
    learning_goals: list[LearningGoal] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    core_evidence_task: str
    anticipated_student_ideas: list[AnticipatedStudentIdea] = Field(default_factory=list)
    representations: list[RepresentationChoice] = Field(default_factory=list)
    differentiation_invariants: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    look_fors: list[str] = Field(default_factory=list)
    vocabulary: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    exit_ticket: list[str] = Field(default_factory=list)
    is_practical: bool = False


class LessonArtifact(BaseModel):
    title: str
    shared: LessonShared
    sections: list[ArtifactSection] = Field(default_factory=list)
    consulted_sources: list[SourceRef] = Field(default_factory=list)


def validate_lesson_artifact(
    artifact: LessonArtifact,
    *,
    allowed_source_ids: set[str] | None = None,
) -> list[str]:
    """Return deterministic, teacher-safe package-contract failures."""
    errors: list[str] = []
    shared = artifact.shared
    audiences = [section.audience for section in artifact.sections]
    if sorted(audiences) != ["observation", "student", "teacher"]:
        errors.append(
            "Artifact must contain exactly one teacher, student, and observation section."
        )
    if shared.artifact_language != "en":
        errors.append("Artifact language must be en for the current build.")
    if not 15 <= shared.duration_minutes <= 120:
        errors.append("Lesson duration must be between 15 and 120 minutes.")
    if not shared.learning_goals:
        errors.append("Artifact requires at least one learning goal.")
    if not shared.core_evidence_task.strip():
        errors.append("Artifact requires one shared core evidence task.")
    if not shared.exit_ticket:
        errors.append("Artifact requires an exit ticket.")
    if shared.is_practical and not shared.safety_notes:
        errors.append("Practical lessons require at least one safety note.")
    if allowed_source_ids is not None:
        for source in artifact.consulted_sources:
            if source.source_id not in allowed_source_ids:
                errors.append(f"Unknown trusted source: {source.source_id}.")
    for section in artifact.sections:
        if section.audience != "student":
            continue
        student_text = " ".join(
            item for document in section.sections for item in document.items
        ).lower()
        if "teacher-only" in student_text or "for the teacher" in student_text:
            errors.append("Student materials must not include teacher-only notes.")
            break
    return errors
