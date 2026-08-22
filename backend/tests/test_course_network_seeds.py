from app.course_network.seeds import load_seed_for_class, load_seed_for_route
from app.services.class_provisioning import ClassSpec, create_class

GRADE_8_REQUIRED_NODES = {
    "mass-conservation",
    "reaction-equations",
    "energy-profiles",
    "activation-energy",
    "catalysis",
    "avogadro-hypothesis",
    "amount-of-substance",
    "molar-mass-and-molar-volume",
    "stoichiometry",
}


def test_grade_8_route_seed_is_reviewed_and_grounded_in_registered_sections(wiki):
    document = load_seed_for_route(wiki, "chemie", 8, "NTG")
    source = wiki.load_trusted_sources()["by-lehrplanplus-chemie-8-ntg"]
    registered_references = {
        (source.source_id, section.id) for section in source.sections
    }

    assert document.route.model_dump() == {
        "subject": "chemie",
        "grade": 8,
        "branch": "NTG",
    }
    assert len(document.nodes) >= 12
    assert GRADE_8_REQUIRED_NODES <= {node.id for node in document.nodes}
    assert all(node.curriculum_refs for node in document.nodes)
    assert all(
        (reference.source_id, reference.section_id) in registered_references
        for node in document.nodes
        for reference in node.curriculum_refs
    )
    assert {edge.relation for edge in document.edges} <= {"builds_on", "related_to"}


def test_seed_loaded_for_a_class_rebinds_the_route_exact_proposed_draft(wiki):
    summary = create_class(
        wiki,
        ClassSpec(
            label="Chemie 8a â€” 2026/27",
            subject="chemie",
            grade=8,
            section="a",
            school_year="2026_27",
        ),
    )

    document = load_seed_for_class(wiki, summary.id)

    assert document.class_id == summary.id
    assert document.revision == 1
    assert document.route.grade == 8
    assert {node.status for node in document.nodes} == {"proposed"}


def test_grade_9_route_uses_the_same_seed_schema(wiki):
    document = load_seed_for_route(wiki, "chemie", 9, "ntg")

    assert document.route.model_dump() == {
        "subject": "chemie",
        "grade": 9,
        "branch": "NTG",
    }
    assert document.nodes
    assert {node.status for node in document.nodes} == {"proposed"}
