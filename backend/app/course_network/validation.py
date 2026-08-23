"""Deterministic, no-provider checks for proposed course-network artifacts."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.course_network.models import CourseNetworkDocument, CurriculumRouteRef


@dataclass(frozen=True)
class CourseNetworkValidationFinding:
    code: str
    message: str
    path: str = ""


def expected_course_network_route(wiki, class_id: str) -> CurriculumRouteRef:
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


def _grade(value: str) -> int | None:
    match = re.search(r"\d+", value or "")
    return int(match.group(0)) if match else None


def route_authorized_curriculum_sections(
    wiki, expected_class_id: str, expected_route: CurriculumRouteRef
) -> dict[tuple[str, str], tuple[object, object]]:
    """Return the genuine trusted-source sections authorized for one route."""
    authorized: dict[tuple[str, str], tuple[object, object]] = {}
    for source in wiki.list_trusted_sources(expected_class_id, scope="active"):
        if source.subject and source.subject.strip().lower() != expected_route.subject:
            continue
        if source.branch and source.branch.strip().upper() != expected_route.branch:
            continue
        if (
            source_grade := _grade(source.grade)
        ) is not None and source_grade != expected_route.grade:
            continue
        authorized.update(
            {
                (source.source_id, section.id): (source, section)
                for section in source.sections
            }
        )
    return authorized


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
    wiki, document: CourseNetworkDocument, *, expected_class_id: str
) -> list[CourseNetworkValidationFinding]:
    """Return the stable findings that must block an LLM review or adoption."""
    findings: list[CourseNetworkValidationFinding] = []
    expected_route = expected_course_network_route(wiki, expected_class_id)
    if document.class_id != expected_class_id:
        findings.append(
            CourseNetworkValidationFinding(
                "class_mismatch",
                "Draft class_id does not match the requested class.",
                "class_id",
            )
        )
    if document.route != expected_route:
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
    authorized = route_authorized_curriculum_sections(
        wiki, expected_class_id, expected_route
    )
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
                elif (reference.source_id, reference.section_id) not in authorized:
                    findings.append(
                        CourseNetworkValidationFinding(
                            "unauthorized_curriculum_reference",
                            "Curriculum reference is not authorized for this class route.",
                            f"{collection_name}.{item.id}",
                        )
                    )
    return findings
