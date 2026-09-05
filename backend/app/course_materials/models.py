from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.course_network.models import _validate_slug


class CourseMaterialSection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str = Field(min_length=1, max_length=300)
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    summary: str = Field(default="", max_length=1200)

    _id = field_validator("id")(_validate_slug)

    @model_validator(mode="after")
    def ordered_pages(self):
        if self.page_end < self.page_start:
            raise ValueError("page_end precedes page_start")
        return self


class SectionDraft(CourseMaterialSection):
    content: str = Field(min_length=1, max_length=60000)
    included: bool = True

    @field_validator("content")
    @classmethod
    def no_section_markers(cls, text):
        if "course-section:" in text or "/course-section" in text:
            raise ValueError("Section markers are reserved")
        return text


class CourseMaterialManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    class_id: str
    material_id: str
    title: str = Field(min_length=1, max_length=300)
    arm: Literal["textbook", "personal"]
    source_hash: str
    source_filename: str
    sections: list[CourseMaterialSection]
    approved_at: datetime | None = None

    _class = field_validator("class_id")(_validate_slug)
    _material = field_validator("material_id")(_validate_slug)

    @model_validator(mode="after")
    def unique_sections(self):
        ids = [s.id for s in self.sections]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError("Material must have unique nonempty sections")
        return self


class MaterialImportArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    class_id: str
    material_id: str
    title: str = Field(min_length=1, max_length=300)
    arm: Literal["textbook", "personal"]
    source_filename: str
    source_hash: str = ""
    sections: list[SectionDraft] = Field(default_factory=list)

    def manifest(self, approved_at=None):
        return CourseMaterialManifest(
            **self.model_dump(exclude={"sections"}),
            approved_at=approved_at,
            sections=[
                CourseMaterialSection(**s.model_dump(exclude={"content", "included"}))
                for s in self.sections
                if s.included
            ],
        )
