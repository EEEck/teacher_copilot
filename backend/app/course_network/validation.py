"""Deterministic, no-provider checks for proposed course-network artifacts."""

from __future__ import annotations

from dataclasses import dataclass

from app.course_network.models import CourseNetworkDocument, CurriculumRouteRef


@dataclass(frozen=True)
class CourseNetworkValidationFinding:
    code: str
    message: str
    path: str = ""


def _expected_route(wiki, class_id: str) -> CurriculumRouteRef:
    class_config = wiki.get_class(class_id)
    curriculum = wiki.get_curriculum_profile(class_id)
    return CurriculumRouteRef(
        subject=(curriculum.subject or class_config.subject),
        grade=int(curriculum.grade),
        branch=curriculum.branch,
    )


def _registered_curriculum_refs(wiki) -> set[tuple[str, str]]:
    registered: set[tuple[str, str]] = set()
    for source in wiki.load_trusted_sources().values():
        registered.update((source.source_id, section.id) for section in source.sections)
    return registered


def _has_builds_on_cycle(document: CourseNetworkDocument) -> bool:
    adjacency: dict[str, list[str]] = {node.id: [] for node in document.nodes}
    for edge in document.edges:
        if edge.relation == "builds_on":
            adjacency[edge.source_id].append(edge.target_id)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> bool:
        if node_id in visiting:
            return True
        if node_id in visited:
            return False
        visiting.add(node_id)
        if any(visit(target) for target in adjacency[node_id]):
            return True
        visiting.remove(node_id)
        visited.add(node_id)
        return False

    return any(visit(node_id) for node_id in adjacency)


def validate_course_network_draft(
    wiki, document: CourseNetworkDocument
) -> list[CourseNetworkValidationFinding]:
    """Return the stable findings that must block an LLM review or adoption."""
    findings: list[CourseNetworkValidationFinding] = []
    if document.route != _expected_route(wiki, document.class_id):
        findings.append(
            CourseNetworkValidationFinding(
                "route_mismatch",
                "Draft route does not match the class curriculum route.",
                "route",
            )
        )
    if _has_builds_on_cycle(document):
        findings.append(
            CourseNetworkValidationFinding(
                "builds_on_cycle",
                "The builds_on relationships must be acyclic.",
                "edges",
            )
        )

    registered = _registered_curriculum_refs(wiki)
    for collection_name, items in (
        ("nodes", document.nodes),
        ("edges", document.edges),
    ):
        for item in items:
            if item.origin == "curriculum" and not item.curriculum_refs:
                findings.append(
                    CourseNetworkValidationFinding(
                        "missing_curriculum_provenance",
                        "Curriculum-origin items require a curriculum reference.",
                        f"{collection_name}.{item.id}",
                    )
                )
            for reference in item.curriculum_refs:
                if (reference.source_id, reference.section_id) not in registered:
                    findings.append(
                        CourseNetworkValidationFinding(
                            "unknown_curriculum_reference",
                            "Curriculum reference is not registered for this wiki.",
                            f"{collection_name}.{item.id}",
                        )
                    )
    return findings
