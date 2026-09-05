from datetime import UTC, datetime

import pytest

from app.course_network.models import (
    CanvasPosition,
    CourseNetworkDocument,
    CurriculumReference,
    CurriculumRouteRef,
    LearningBlock,
    MaterialMapping,
    MaterialSectionReference,
    NetworkEdge,
    canonical_network_json,
)

FIXED_TIME = datetime(2026, 8, 18, 12, 30, tzinfo=UTC)
ROUTE = CurriculumRouteRef(subject=" Chemie ", grade=8, branch="ntg")


def _node(node_id: str = "c8-energy", **changes) -> LearningBlock:
    return LearningBlock(id=node_id, title="Energie", **changes)


def _document(**changes) -> CourseNetworkDocument:
    values = {
        "class_id": "chemie_8a_2026_27",
        "route": ROUTE,
        "updated_at": FIXED_TIME,
    }
    values.update(changes)
    return CourseNetworkDocument(**values)


def test_route_ref_normalizes_the_supported_chemie_ntg_routes():
    assert ROUTE.model_dump() == {"subject": "chemie", "grade": 8, "branch": "NTG"}


def test_network_document_rejects_duplicate_node_ids():
    with pytest.raises(ValueError, match="duplicate node id"):
        _document(nodes=[_node(), _node()])


@pytest.mark.parametrize(
    "edge, message",
    [
        (
            NetworkEdge(
                id="edge-energy-rate",
                source_id="c8-energy",
                target_id="c8-rate",
                relation="builds_on",
            ),
            "unknown node",
        ),
        (
            NetworkEdge(
                id="edge-energy-energy",
                source_id="c8-energy",
                target_id="c8-energy",
                relation="builds_on",
            ),
            "self-edge",
        ),
    ],
)
def test_network_document_rejects_invalid_edge_endpoints(edge, message):
    with pytest.raises(ValueError, match=message):
        _document(nodes=[_node()], edges=[edge])


def test_network_document_rejects_duplicate_semantic_edges():
    edge = NetworkEdge(
        id="edge-energy-rate",
        source_id="c8-energy",
        target_id="c8-rate",
        relation="builds_on",
    )
    duplicate = edge.model_copy(update={"id": "edge-energy-rate-again"})

    with pytest.raises(ValueError, match="duplicate semantic edge"):
        _document(nodes=[_node(), _node("c8-rate")], edges=[edge, duplicate])


def test_related_relationship_rejects_reversed_duplicate():
    first = NetworkEdge(id="related-1", source_id="c8-energy", target_id="c8-rate", relation="related_to")
    reverse = NetworkEdge(id="related-2", source_id="c8-rate", target_id="c8-energy", relation="related_to")
    with pytest.raises(ValueError, match="duplicate semantic edge"):
        _document(nodes=[_node(), _node("c8-rate")], edges=[first, reverse])


def test_network_document_rejects_duplicate_material_mappings():
    mapping = MaterialMapping(
        id="map-textbook-energy",
        material_id="textbook",
        section_id="energy",
        node_id="c8-energy",
        relation="explains",
        origin="agent",
    )

    with pytest.raises(ValueError, match="duplicate material mapping"):
        _document(
            nodes=[_node()],
            material_mappings=[mapping, mapping.model_copy(update={"id": "map-2"})],
        )


def test_material_origin_node_requires_material_reference():
    with pytest.raises(ValueError, match="material-origin"):
        _node(origin="material")


def test_canonical_document_rejects_proposed_nodes_but_draft_seed_allows_them():
    proposed = _node(status="proposed")

    with pytest.raises(ValueError, match="proposed"):
        _document(nodes=[proposed])

    draft = CourseNetworkDocument.for_draft_seed(
        class_id="chemie_8a_2026_27",
        route=ROUTE,
        updated_at=FIXED_TIME,
        nodes=[proposed],
    )

    assert draft.nodes == [proposed]
    with pytest.raises(ValueError, match="proposed"):
        canonical_network_json(draft)


def test_network_document_rejects_unknown_positions_and_invalid_page_ranges():
    with pytest.raises(ValueError, match="unknown node"):
        _document(nodes=[_node()], positions={"c8-rate": CanvasPosition(x=1, y=2)})

    with pytest.raises(ValueError, match="page_end"):
        MaterialSectionReference(
            material_id="textbook", section_id="energy", page_start=12, page_end=11
        )


@pytest.mark.parametrize("coordinate", [float("nan"), float("inf"), float("-inf")])
def test_canvas_position_rejects_non_finite_coordinates(coordinate):
    with pytest.raises(ValueError, match="finite"):
        CanvasPosition(x=coordinate, y=0)


def test_canonical_network_json_is_deterministic_and_retains_unicode():
    document = _document(
        nodes=[
            LearningBlock(
                id="c8-energy",
                title="Aktivierungsenergie",
                curriculum_refs=[
                    CurriculumReference(source_id="lehrplanplus", section_id="lb3")
                ],
            )
        ],
    )

    expected = canonical_network_json(document)

    assert expected == canonical_network_json(document)
    assert "Aktivierungsenergie" in expected
    assert '"schema_version": 1' in expected
