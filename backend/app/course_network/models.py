"""Class-owned, canonical course-network model contract."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")

RelationType = Literal["builds_on", "related_to"]
NodeOrigin = Literal["curriculum", "teacher", "material"]
NodeStatus = Literal["proposed", "adopted", "retired"]
MappingRelation = Literal["explains", "practices", "assesses", "extends"]
MappingOrigin = Literal["agent", "teacher"]


def _validate_slug(value: str) -> str:
    if not _SLUG_RE.fullmatch(value):
        raise ValueError("must be a non-empty stable slug-like id")
    return value


class CurriculumRouteRef(BaseModel):
    """The reviewed Chemie 8/9 NTG route owned by the network contract."""

    subject: str
    grade: int
    branch: str

    @field_validator("subject")
    @classmethod
    def normalize_subject(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized != "chemie":
            raise ValueError("only the chemie subject is supported")
        return normalized

    @field_validator("grade")
    @classmethod
    def validate_grade(cls, value: int) -> int:
        if value not in {8, 9}:
            raise ValueError("only Chemie grades 8 and 9 are supported")
        return value

    @field_validator("branch")
    @classmethod
    def normalize_branch(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized != "NTG":
            raise ValueError("only the NTG branch is supported")
        return normalized


class CurriculumReference(BaseModel):
    source_id: str
    section_id: str

    _validate_source_id = field_validator("source_id")(_validate_slug)
    _validate_section_id = field_validator("section_id")(_validate_slug)


class MaterialSectionReference(BaseModel):
    material_id: str
    section_id: str
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)

    _validate_material_id = field_validator("material_id")(_validate_slug)
    _validate_section_id = field_validator("section_id")(_validate_slug)

    @model_validator(mode="after")
    def page_bounds_are_ordered(self) -> MaterialSectionReference:
        if (
            self.page_start is not None
            and self.page_end is not None
            and self.page_end < self.page_start
        ):
            raise ValueError("page_end must be greater than or equal to page_start")
        return self


class CanvasPosition(BaseModel):
    x: float
    y: float


class LearningBlock(BaseModel):
    """One teacher-facing Lernbaustein in a class course network."""

    id: str
    title: str
    description: str = ""
    learning_goal: str = ""
    curriculum_refs: list[CurriculumReference] = Field(default_factory=list)
    material_refs: list[MaterialSectionReference] = Field(default_factory=list)
    origin: NodeOrigin = "teacher"
    status: NodeStatus = "adopted"

    _validate_id = field_validator("id")(_validate_slug)

    @field_validator("title")
    @classmethod
    def title_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("title must not be blank")
        return value

    @model_validator(mode="after")
    def material_nodes_keep_material_provenance(self) -> LearningBlock:
        if self.origin == "material" and not self.material_refs:
            raise ValueError(
                "material-origin nodes require at least one material reference"
            )
        return self


class NetworkEdge(BaseModel):
    id: str
    source_id: str
    target_id: str
    relation: RelationType
    curriculum_refs: list[CurriculumReference] = Field(default_factory=list)
    material_refs: list[MaterialSectionReference] = Field(default_factory=list)
    origin: NodeOrigin = "teacher"

    _validate_id = field_validator("id")(_validate_slug)
    _validate_source_id = field_validator("source_id")(_validate_slug)
    _validate_target_id = field_validator("target_id")(_validate_slug)


class MaterialMapping(BaseModel):
    id: str
    material_id: str
    section_id: str
    node_id: str
    relation: MappingRelation
    confidence: float | None = Field(default=None, ge=0, le=1)
    teacher_note: str = ""
    origin: MappingOrigin

    _validate_id = field_validator("id")(_validate_slug)
    _validate_material_id = field_validator("material_id")(_validate_slug)
    _validate_section_id = field_validator("section_id")(_validate_slug)
    _validate_node_id = field_validator("node_id")(_validate_slug)


class CourseNetworkDocument(BaseModel):
    """Canonical course-network data for one class.

    ``for_draft_seed`` is the sole construction path that permits proposed
    nodes. Ordinary construction represents a canonical document and rejects
    them before any durable write can occur.
    """

    schema_version: Literal[1] = 1
    class_id: str
    route: CurriculumRouteRef
    revision: int = Field(default=1, ge=1)
    nodes: list[LearningBlock] = Field(default_factory=list)
    edges: list[NetworkEdge] = Field(default_factory=list)
    material_mappings: list[MaterialMapping] = Field(default_factory=list)
    positions: dict[str, CanvasPosition] = Field(default_factory=dict)
    updated_at: datetime

    _validate_class_id = field_validator("class_id")(_validate_slug)

    @classmethod
    def for_draft_seed(cls, **values) -> CourseNetworkDocument:
        """Build a reviewed seed draft, which may contain proposed nodes."""
        return cls.model_validate(values, context={"allow_proposed_nodes": True})

    def validate_for_canonical_write(self) -> CourseNetworkDocument:
        """Return this document after applying canonical-write validation."""
        return type(self).model_validate(self.model_dump())

    @model_validator(mode="after")
    def validate_graph(self, info: ValidationInfo) -> CourseNetworkDocument:
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("duplicate node id")
        node_id_set = set(node_ids)

        edge_ids = [edge.id for edge in self.edges]
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("duplicate edge id")
        semantic_edges: set[tuple[str, str, RelationType]] = set()
        for edge in self.edges:
            if edge.source_id not in node_id_set or edge.target_id not in node_id_set:
                raise ValueError("edge references an unknown node")
            if edge.source_id == edge.target_id:
                raise ValueError("self-edge is not allowed")
            semantic_edge = (edge.source_id, edge.target_id, edge.relation)
            if semantic_edge in semantic_edges:
                raise ValueError("duplicate semantic edge")
            semantic_edges.add(semantic_edge)

        mapping_ids = [mapping.id for mapping in self.material_mappings]
        if len(mapping_ids) != len(set(mapping_ids)):
            raise ValueError("duplicate material mapping id")
        mapping_tuples: set[tuple[str, str, str, MappingRelation]] = set()
        for mapping in self.material_mappings:
            if mapping.node_id not in node_id_set:
                raise ValueError("material mapping references an unknown node")
            mapping_tuple = (
                mapping.material_id,
                mapping.section_id,
                mapping.node_id,
                mapping.relation,
            )
            if mapping_tuple in mapping_tuples:
                raise ValueError("duplicate material mapping")
            mapping_tuples.add(mapping_tuple)

        if any(position_id not in node_id_set for position_id in self.positions):
            raise ValueError("position references an unknown node")

        allow_proposed = bool((info.context or {}).get("allow_proposed_nodes"))
        if not allow_proposed and any(node.status == "proposed" for node in self.nodes):
            raise ValueError("canonical documents cannot contain proposed nodes")
        return self


def canonical_network_json(document: CourseNetworkDocument) -> str:
    """Serialize one canonical network with stable ordering and Unicode intact."""
    canonical_document = document.validate_for_canonical_write()
    return json.dumps(
        canonical_document.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
