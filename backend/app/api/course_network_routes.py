"""Dedicated HTTP boundary for reviewed class course-network adoption."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_course_network_service
from app.api.errors import ErrorEnvelope
from app.schemas.api import (
    AdoptCourseNetworkDraftRequest,
    CourseNetworkAdoptionResponse,
    CourseNetworkDraftResponse,
    CourseNetworkResponse,
    CourseNetworkSourceProvenance,
    CourseNetworkSourceSectionResponse,
)
from app.services.course_network_service import (
    CourseNetworkConflict,
    CourseNetworkService,
)
from app.services.workflow_drafts import WorkflowDraftConflict

router = APIRouter(tags=["course-network"])
CourseNetworkServiceDep = Annotated[
    CourseNetworkService, Depends(get_course_network_service)
]
_NOT_FOUND_RESPONSE = {
    "model": ErrorEnvelope,
    "description": "Class, course-network draft, or authorized evidence was not found.",
}
_CONFLICT_RESPONSE = {
    "model": ErrorEnvelope,
    "description": (
        "Draft is terminal, adoption is in progress, or review/artifact snapshot "
        "is stale."
    ),
}
_VALIDATION_RESPONSE = {
    "model": ErrorEnvelope,
    "description": "Request or structured draft validation failed.",
}


def _network_from_draft(row):
    try:
        from app.course_network.models import CourseNetworkDocument

        return CourseNetworkDocument.for_draft_seed(**json.loads(row.artifact_markdown))
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail="invalid_course_network_draft"
        ) from exc


def _review_from_draft(row):
    if not row.active_review_json:
        return None
    try:
        from app.course_network.review import CourseNetworkReviewResult

        return CourseNetworkReviewResult.model_validate(row.active_review_json)
    except ValueError:
        return None


def _draft_response(row) -> CourseNetworkDraftResponse:
    return CourseNetworkDraftResponse(
        draft_id=row.draft_id,
        class_id=row.class_id,
        status=row.status,
        artifact_markdown=row.artifact_markdown,
        artifact_revision=row.artifact_revision,
        artifact_hash=row.artifact_hash,
        backend_session_id=row.backend_session_id,
        network=_network_from_draft(row).model_dump(mode="json"),
        review=_review_from_draft(row),
    )


def _raise_service_error(exc: Exception) -> None:
    if isinstance(exc, (CourseNetworkConflict, WorkflowDraftConflict)):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, KeyError):
        detail = exc.args[0] if exc.args else "not_found"
        raise HTTPException(status_code=404, detail=str(detail)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    raise exc


@router.get(
    "/classes/{class_id}/course/network",
    response_model=CourseNetworkResponse,
    responses={404: _NOT_FOUND_RESPONSE, 422: _VALIDATION_RESPONSE},
)
def get_course_network(
    class_id: str, service: CourseNetworkServiceDep
) -> CourseNetworkResponse:
    try:
        return CourseNetworkResponse(
            class_id=class_id, network=service.get_network(class_id)
        )
    except (CourseNetworkConflict, WorkflowDraftConflict, KeyError, ValueError) as exc:
        _raise_service_error(exc)


@router.get(
    "/classes/{class_id}/course/network/sources/{source_id}/sections/{section_id}",
    response_model=CourseNetworkSourceSectionResponse,
    responses={404: _NOT_FOUND_RESPONSE, 422: _VALIDATION_RESPONSE},
)
def get_course_network_source_section(
    class_id: str,
    source_id: str,
    section_id: str,
    service: CourseNetworkServiceDep,
) -> CourseNetworkSourceSectionResponse:
    try:
        payload = service.get_source_section(class_id, source_id, section_id)
        return CourseNetworkSourceSectionResponse(
            source_id=str(payload["source_id"]),
            source_title=str(payload["title"]),
            section_id=str(payload["section_id"]),
            section_title=str(payload["section_title"]),
            content=str(payload["content"]),
            provenance=CourseNetworkSourceProvenance(
                authority=str(payload["authority"]),
                jurisdiction=str(payload["jurisdiction"]),
                canonical_url=str(payload["canonical_url"]),
                retrieved_at=str(payload["retrieved_at"]),
                version_label=str(payload["version_label"]),
                content_hash=str(payload["content_hash"]),
            ),
        )
    except (CourseNetworkConflict, WorkflowDraftConflict, KeyError, ValueError) as exc:
        _raise_service_error(exc)


@router.post(
    "/classes/{class_id}/course/network/drafts",
    response_model=CourseNetworkDraftResponse,
    status_code=201,
    responses={
        404: _NOT_FOUND_RESPONSE,
        409: {
            "model": ErrorEnvelope,
            "description": "A network was already adopted for this class",
        },
        422: _VALIDATION_RESPONSE,
    },
)
def open_course_network_seed_draft(
    class_id: str, service: CourseNetworkServiceDep
) -> CourseNetworkDraftResponse:
    try:
        return _draft_response(service.open_seed_draft(class_id))
    except (CourseNetworkConflict, WorkflowDraftConflict, KeyError, ValueError) as exc:
        _raise_service_error(exc)


@router.get(
    "/classes/{class_id}/course/network/drafts/{draft_id}",
    response_model=CourseNetworkDraftResponse,
    responses={404: _NOT_FOUND_RESPONSE, 422: _VALIDATION_RESPONSE},
)
def get_course_network_draft(
    class_id: str, draft_id: str, service: CourseNetworkServiceDep
) -> CourseNetworkDraftResponse:
    try:
        return _draft_response(service.get_draft(class_id, draft_id))
    except (CourseNetworkConflict, WorkflowDraftConflict, KeyError, ValueError) as exc:
        _raise_service_error(exc)


@router.post(
    "/classes/{class_id}/course/network/drafts/{draft_id}/review",
    response_model=CourseNetworkDraftResponse,
    responses={
        404: _NOT_FOUND_RESPONSE,
        409: _CONFLICT_RESPONSE,
        422: _VALIDATION_RESPONSE,
    },
)
async def review_course_network_seed(
    class_id: str, draft_id: str, service: CourseNetworkServiceDep
) -> CourseNetworkDraftResponse:
    try:
        await service.review_seed(class_id, draft_id)
        return _draft_response(service.get_draft(class_id, draft_id))
    except (CourseNetworkConflict, WorkflowDraftConflict, KeyError, ValueError) as exc:
        _raise_service_error(exc)


@router.post(
    "/classes/{class_id}/course/network/drafts/{draft_id}/adopt",
    response_model=CourseNetworkAdoptionResponse,
    responses={
        404: _NOT_FOUND_RESPONSE,
        409: {
            "model": ErrorEnvelope,
            "description": "Stale review, non-accepted review, or duplicate adoption",
        },
        422: _VALIDATION_RESPONSE,
    },
)
def adopt_course_network_seed(
    class_id: str,
    draft_id: str,
    body: AdoptCourseNetworkDraftRequest,
    service: CourseNetworkServiceDep,
) -> CourseNetworkAdoptionResponse:
    try:
        adopted = service.adopt_seed(
            class_id, draft_id, body.expected_revision, body.expected_hash
        )
        return CourseNetworkAdoptionResponse(
            class_id=class_id,
            draft_id=adopted.draft.draft_id,
            log_entry_id=adopted.log_entry_id,
            network=adopted.network,
        )
    except (CourseNetworkConflict, WorkflowDraftConflict, KeyError, ValueError) as exc:
        _raise_service_error(exc)
