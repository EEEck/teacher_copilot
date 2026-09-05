"""Pure, class-scoped graph changes. Publication remains a reviewed action."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.course_network.models import (
    CourseNetworkDocument,
    CurriculumReference,
    LearningBlock,
    MaterialMapping,
    MaterialSectionReference,
    NetworkEdge,
)
from app.course_network.validation import _has_builds_on_cycle


class LearningBlockPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = None
    description: str | None = None
    learning_goal: str | None = None
    curriculum_refs: list[CurriculumReference] | None = None
    material_refs: list[MaterialSectionReference] | None = None


class AddNode(BaseModel):
    op: Literal["add_node"]
    node: LearningBlock


class UpdateNode(BaseModel):
    op: Literal["update_node"]
    node_id: str
    changes: LearningBlockPatch


class RetireNode(BaseModel):
    op: Literal["retire_node"]
    node_id: str


class AddEdge(BaseModel):
    op: Literal["add_edge"]
    edge: NetworkEdge


class RemoveEdge(BaseModel):
    op: Literal["remove_edge"]
    edge_id: str


GraphOperation = Annotated[
    AddNode | UpdateNode | RetireNode | AddEdge | RemoveEdge, Field(discriminator="op")
]


class NetworkChangeSet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    class_id: str
    base_revision: int = Field(ge=1)
    summary: str
    operations: list[GraphOperation] = Field(default_factory=list)
    material_id: str | None = None
    replacement_mappings: list[MaterialMapping] | None = None

    @model_validator(mode="after")
    def mapping_scope(self):
        if self.replacement_mappings is not None:
            if not self.material_id:
                raise ValueError("mapping replacement requires a material_id")
            if any(
                m.material_id != self.material_id for m in self.replacement_mappings
            ):
                raise ValueError("mapping replacement crosses material scope")
        if not self.operations and self.replacement_mappings is None:
            raise ValueError("empty change set")
        return self


def apply_change_set(
    current: CourseNetworkDocument, changes: NetworkChangeSet, *, draft: bool = False
) -> CourseNetworkDocument:
    if (
        current.class_id != changes.class_id
        or current.revision != changes.base_revision
    ):
        raise ValueError("course network class or base revision mismatch")
    payload = current.model_dump(mode="json")
    nodes = {node["id"]: node for node in payload["nodes"]}
    edges = {edge["id"]: edge for edge in payload["edges"]}
    for operation in changes.operations:
        if isinstance(operation, AddNode):
            if operation.node.id in nodes:
                raise ValueError("node ID already exists")
            node = operation.node.model_dump(mode="json")
            node["status"] = "proposed" if draft else "adopted"
            nodes[node["id"]] = node
        elif isinstance(operation, (UpdateNode, RetireNode)):
            if (
                operation.node_id not in nodes
                or nodes[operation.node_id]["status"] == "retired"
            ):
                raise ValueError("unknown or retired node")
            if isinstance(operation, UpdateNode):
                nodes[operation.node_id].update(
                    operation.changes.model_dump(exclude_none=True, mode="json")
                )
            else:
                nodes[operation.node_id]["status"] = "retired"
                edges = {
                    key: e
                    for key, e in edges.items()
                    if operation.node_id not in (e["source_id"], e["target_id"])
                }
                payload["material_mappings"] = [
                    m
                    for m in payload["material_mappings"]
                    if m["node_id"] != operation.node_id
                ]
                payload["positions"].pop(operation.node_id, None)
        elif isinstance(operation, AddEdge):
            if operation.edge.id in edges:
                raise ValueError("edge ID already exists")
            edges[operation.edge.id] = operation.edge.model_dump(mode="json")
        elif isinstance(operation, RemoveEdge):
            if operation.edge_id not in edges:
                raise ValueError("unknown edge")
            del edges[operation.edge_id]
    if changes.replacement_mappings is not None:
        payload["material_mappings"] = [
            m
            for m in payload["material_mappings"]
            if m["material_id"] != changes.material_id
        ]
        payload["material_mappings"].extend(
            m.model_dump(mode="json") for m in changes.replacement_mappings
        )
    active = {key for key, n in nodes.items() if n["status"] != "retired"}
    if any(
        e["source_id"] not in active or e["target_id"] not in active
        for e in edges.values()
    ):
        raise ValueError("edge references an unknown or retired node")
    if any(m["node_id"] not in active for m in payload["material_mappings"]):
        raise ValueError("mapping references an unknown or retired node")
    payload.update(
        nodes=list(nodes.values()),
        edges=list(edges.values()),
        revision=current.revision if draft else current.revision + 1,
        updated_at=datetime.now(UTC),
    )
    result = (
        CourseNetworkDocument.for_draft_seed(**payload)
        if draft
        else CourseNetworkDocument.model_validate(payload)
    )
    if _has_builds_on_cycle(result):
        raise ValueError("builds_on cycle")
    return result
