import asyncio

import pytest

from app.course_network.generation import (
    CourseGenerationRequest,
    generate_course_changes,
)
from app.course_network.seeds import load_seed_for_class
from tests.conftest import CLASS_ID


def test_generation_preserves_scope_and_uses_actual_source_packet(wiki):
    seed = load_seed_for_class(wiki, CLASS_ID)

    async def model(packet):
        assert "course_network" in packet
        assert "c9_" in packet
        return {
            "changes": {
                "class_id": CLASS_ID,
                "base_revision": 1,
                "summary": "Clarify",
                "operations": [
                    {
                        "op": "update_node",
                        "node_id": seed.nodes[0].id,
                        "changes": {"title": "Reviewed concept"},
                    }
                ],
            },
            "rationales": [],
            "coverage_notes": ["Partial scope"],
            "warnings": [],
        }

    result = asyncio.run(
        generate_course_changes(
            wiki,
            CLASS_ID,
            CourseGenerationRequest(
                purpose="curriculum_draft", teacher_request="Clarify the seed"
            ),
            seed,
            model_runner=model,
        )
    )
    assert result.changes.operations[0].node_id == seed.nodes[0].id
    assert wiki.load_course_network(CLASS_ID) is None


def test_generation_cannot_return_another_class_or_unknown_node(wiki):
    seed = load_seed_for_class(wiki, CLASS_ID)

    async def model(packet):
        return {
            "changes": {
                "class_id": "other",
                "base_revision": 1,
                "summary": "Wrong",
                "operations": [
                    {
                        "op": "update_node",
                        "node_id": "unknown",
                        "changes": {"title": "No"},
                    }
                ],
            },
            "rationales": [],
            "coverage_notes": [],
            "warnings": [],
        }

    with pytest.raises(ValueError):
        asyncio.run(
            generate_course_changes(
                wiki,
                CLASS_ID,
                CourseGenerationRequest(purpose="correction", teacher_request="Update"),
                seed,
                model_runner=model,
            )
        )
