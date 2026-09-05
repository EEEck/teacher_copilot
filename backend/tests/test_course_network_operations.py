from datetime import UTC, datetime

import pytest

from app.course_network.models import CourseNetworkDocument, LearningBlock, NetworkEdge
from app.course_network.operations import NetworkChangeSet, apply_change_set


def network():
    return CourseNetworkDocument(
        class_id="chemie_8a",
        route={"subject": "chemie", "grade": 8, "branch": "NTG"},
        updated_at=datetime.now(UTC),
        nodes=[
            LearningBlock(id="energy", title="Energy"),
            LearningBlock(id="catalysis", title="Catalysis"),
        ],
        edges=[
            NetworkEdge(
                id="catalysis-energy",
                source_id="catalysis",
                target_id="energy",
                relation="builds_on",
            )
        ],
    )


def test_retirement_preserves_history_without_mutating_input():
    before = network()
    changes = NetworkChangeSet(
        class_id=before.class_id,
        base_revision=1,
        summary="Retire",
        operations=[{"op": "retire_node", "node_id": "energy"}],
    )
    after = apply_change_set(before, changes)
    assert after.revision == 2
    assert after.nodes[0].status == "retired"
    assert not after.edges
    assert before.nodes[0].status == "adopted"
    assert len(before.edges) == 1


@pytest.mark.parametrize("values", [{"base_revision": 2}, {"class_id": "other"}])
def test_change_set_rejects_stale_or_wrong_class(values):
    proposal = dict(
        class_id="chemie_8a",
        base_revision=1,
        summary="Edit",
        operations=[
            {
                "op": "update_node",
                "node_id": "energy",
                "changes": {"title": "Energy transfer"},
            }
        ],
    )
    proposal.update(values)
    with pytest.raises(ValueError):
        apply_change_set(network(), NetworkChangeSet(**proposal))


def test_new_prerequisite_cycle_is_rejected():
    changes = NetworkChangeSet(
        class_id="chemie_8a",
        base_revision=1,
        summary="Cycle",
        operations=[
            {
                "op": "add_edge",
                "edge": {
                    "id": "reverse",
                    "source_id": "energy",
                    "target_id": "catalysis",
                    "relation": "builds_on",
                },
            }
        ],
    )
    with pytest.raises(ValueError, match="cycle"):
        apply_change_set(network(), changes)


def test_unknown_mapping_node_and_unscoped_replacement_are_rejected():
    mapping = {
        "id": "map1",
        "material_id": "mat1",
        "section_id": "s1",
        "node_id": "missing",
        "relation": "explains",
        "origin": "agent",
    }
    with pytest.raises(ValueError):
        apply_change_set(
            network(),
            NetworkChangeSet(
                class_id="chemie_8a",
                base_revision=1,
                summary="Map",
                material_id="mat1",
                replacement_mappings=[mapping],
            ),
        )
    with pytest.raises(ValueError):
        NetworkChangeSet(
            class_id="chemie_8a",
            base_revision=1,
            summary="Map",
            replacement_mappings=[mapping],
        )


def test_existing_nodes_cannot_be_renamed_or_restored_by_arbitrary_patch():
    with pytest.raises(ValueError):
        NetworkChangeSet(
            class_id="chemie_8a",
            base_revision=1,
            summary="Rename",
            operations=[
                {"op": "update_node", "node_id": "energy", "changes": {"id": "new-id"}}
            ],
        )
