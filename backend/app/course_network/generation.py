"""Bounded proposal generation; this module never publishes course memory."""

from __future__ import annotations

import asyncio
from typing import Literal

from agents import Agent, Runner
from pydantic import BaseModel, ConfigDict, Field

from app.config import get_settings
from app.course_materials.store import get_course_material, read_course_material_section
from app.course_network.operations import NetworkChangeSet, apply_change_set
from app.course_network.validation import (
    route_authorized_curriculum_sections,
    validate_course_network_draft,
)
from app.services.workflow_drafts import serialize_structured_artifact
from app.teacher_agent.skills.loader import load_skill


class CourseGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purpose: Literal["curriculum_draft", "material_enrichment", "correction"]
    teacher_request: str = Field(default="", max_length=6000)
    material_id: str | None = None


class ChangeRationale(BaseModel):
    item_id: str
    reason: str


class CourseGenerationResult(BaseModel):
    changes: NetworkChangeSet
    rationales: list[ChangeRationale] = Field(default_factory=list)
    coverage_notes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


async def generate_course_changes(
    wiki, class_id, request, current, *, model_runner=None
):
    settings = get_settings()
    if current.class_id != class_id:
        raise ValueError("Course class mismatch")
    material = None
    if request.material_id:
        manifest = get_course_material(wiki, class_id, request.material_id)
        material = {
            "manifest": manifest.model_dump(mode="json"),
            "sections": [
                read_course_material_section(wiki, class_id, manifest.material_id, s.id)
                for s in manifest.sections
            ],
        }
    if request.purpose == "material_enrichment" and material is None:
        raise ValueError("Choose an approved course material")
    sources = route_authorized_curriculum_sections(wiki, class_id, current.route)
    packet = serialize_structured_artifact(
        {
            "request": request.model_dump(),
            "course_network": current.model_dump(mode="json"),
            "curriculum": [
                {
                    "source_id": sid,
                    "section_id": secid,
                    "title": section.title,
                    "content": section.body[:6000],
                }
                for (sid, secid), (_, section) in sources.items()
            ],
            "approved_material": material,
        }
    )
    if len(packet) > 180000:
        raise ValueError(
            "This material is too large for one proposal; import a smaller chapter"
        )
    if model_runner:
        raw = await model_runner(packet)
    else:
        from app.teacher_agent.agent import chat_model_settings

        model = settings.resolved_utility_model()
        agent = Agent(
            name="Course concept map proposal",
            model=model,
            model_settings=chat_model_settings(
                settings.resolved_utility_effort(), model=model
            ),
            instructions=load_skill("course_network"),
            tools=[],
            output_type=CourseGenerationResult,
        )
        result = await asyncio.wait_for(
            Runner.run(agent, packet, max_turns=1),
            timeout=settings.agent_timeout_seconds,
        )
        raw = result.final_output
    result = CourseGenerationResult.model_validate(raw)
    if result.changes.class_id != class_id:
        raise ValueError("Generated changes cross class scope")
    if result.changes.material_id and result.changes.material_id != request.material_id:
        raise ValueError("Generated mapping changes cross material scope")
    draft = request.purpose == "curriculum_draft"
    preview = apply_change_set(current, result.changes, draft=draft)
    added = sum(op.op == "add_node" for op in result.changes.operations)
    if (not draft and added > settings.course_enrichment_max_nodes) or (
        draft and len(preview.nodes) > settings.course_generation_max_nodes
    ):
        raise ValueError("Generated proposal exceeds the course map node limit")
    findings = validate_course_network_draft(wiki, preview, expected_class_id=class_id)
    if findings:
        raise ValueError("; ".join(f.message for f in findings))
    refs = {(m.material_id, m.section_id) for m in preview.material_mappings}
    for item in [*preview.nodes, *preview.edges]:
        refs.update((ref.material_id, ref.section_id) for ref in item.material_refs)
    for material_id, section_id in refs:
        read_course_material_section(wiki, class_id, material_id, section_id)
    return result
