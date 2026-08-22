"""Dedicated HTTP boundary for reviewed class course-network adoption."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_course_network_service
from app.schemas.api import (
    AdoptCourseNetworkDraftRequest,
    CourseNetworkAdoptionResponse,
    CourseNetworkDraftResponse,
    CourseNetworkResponse,
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
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    raise exc


@router.get("/classes/{class_id}/course/network", response_model=CourseNetworkResponse)
def get_course_network(
    class_id: str, service: CourseNetworkServiceDep
) -> CourseNetworkResponse:
    try:
        return CourseNetworkResponse(
            class_id=class_id, network=service.get_network(class_id)
        )
    except (CourseNetworkConflict, WorkflowDraftConflict, KeyError, ValueError) as exc:
        _raise_service_error(exc)


@router.post(
    "/classes/{class_id}/course/network/drafts",
    response_model=CourseNetworkDraftResponse,
    status_code=201,
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
