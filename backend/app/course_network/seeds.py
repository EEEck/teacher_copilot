"""Reviewed, route-specific draft seeds for class course networks."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.course_network.models import CourseNetworkDocument, CurriculumRouteRef


def _seed_path(wiki, route: CurriculumRouteRef) -> Path:
    return (
        wiki.root
        / "wiki"
        / "subjects"
        / route.subject
        / "teaching_frameworks"
        / f"{route.grade:02d}"
        / "course_network_seed.json"
    )


def _load_seed_document(wiki, route: CurriculumRouteRef) -> CourseNetworkDocument:
    path = _seed_path(wiki, route)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(
            f"No reviewed course-network seed for "
            f"{route.subject} {route.grade} {route.branch}."
        ) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid course-network seed at {path}.") from exc

    try:
        document = CourseNetworkDocument.for_draft_seed(**payload)
    except ValidationError as exc:
        raise ValueError(f"Invalid course-network seed at {path}: {exc}") from exc
    if document.route != route:
        raise ValueError(f"Course-network seed route does not match {path}.")
    if document.revision != 1:
        raise ValueError(f"Course-network seed revision must be 1 at {path}.")
    if any(node.status != "proposed" for node in document.nodes):
        raise ValueError(f"Course-network seed nodes must be proposed at {path}.")
    return document


def load_seed_for_route(
    wiki, subject: str, grade: int, branch: str
) -> CourseNetworkDocument:
    """Load the reviewed draft seed for one exact curriculum route."""
    route = CurriculumRouteRef(subject=subject, grade=grade, branch=branch)
    return _load_seed_document(wiki, route)


def load_seed_for_class(wiki, class_id: str) -> CourseNetworkDocument:
    """Load a class's route seed and bind the proposed draft to that class."""
    class_config = wiki.get_class(class_id)
    curriculum = wiki.get_curriculum_profile(class_id)
    configured_subject = (class_config.subject or "").strip().lower()
    curriculum_subject = (curriculum.subject or configured_subject).strip().lower()
    if curriculum_subject != configured_subject:
        raise ValueError(
            "Curriculum profile subject does not match the class subject: "
            f"{curriculum_subject or '<none>'} != {configured_subject or '<none>'}."
        )
    try:
        route = CurriculumRouteRef(
            subject=configured_subject,
            grade=int(curriculum.grade),
            branch=curriculum.branch,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Class {class_id} has no usable curriculum route.") from exc

    document = _load_seed_document(wiki, route)
    payload = document.model_dump(mode="json")
    payload["class_id"] = class_id
    payload["revision"] = 1
    return CourseNetworkDocument.for_draft_seed(**payload)
