"""Class-scoped course library, extraction review and graph change actions."""

from __future__ import annotations

import asyncio
import hashlib
import json
from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.api.course_network_routes import (
    _GENERATION_UNAVAILABLE_RESPONSE,
    _raise_service_error,
)
from app.api.errors import ErrorEnvelope
from app.api.deps import get_request_identity, get_wiki, get_workflow_draft_store
from app.course_materials.import_service import CourseMaterialImportService
from app.course_materials.models import MaterialImportArtifact
from app.course_materials.store import (
    list_material_library,
    saved_material_root,
    set_course_material_archived,
    read_course_material_section,
    resolve_course_asset,
    source_page_map,
)
from app.course_network.edit_service import (
    CourseNetworkEditService,
    save_structured_row,
)
from app.course_network.generation import (
    CourseGenerationRequest,
    generate_course_changes,
)
from app.course_network.operations import NetworkChangeSet
from app.course_network.generation_jobs import start_or_resume_generation, status as generation_status, retry_generation, discard_generation
from app.services.materials_ocr_packaging import parse_page_range
from app.services.workflow_drafts import WorkflowDraftConflict

router = APIRouter(
    tags=["course-materials"],
    responses={
        404: {
            "model": ErrorEnvelope,
            "description": "Class, draft, or approved material not found",
        },
        409: {
            "model": ErrorEnvelope,
            "description": "Stale review, inactive draft, or publication conflict",
        },
        422: {
            "model": ErrorEnvelope,
            "description": "Invalid source, page selection, extraction, or graph change",
        },
    },
)
_jobs: dict[tuple[str, str], asyncio.Task] = {}


def import_service(
    wiki=Depends(get_wiki),
    drafts=Depends(get_workflow_draft_store),
    identity=Depends(get_request_identity),
):
    return CourseMaterialImportService(
        wiki=wiki, workflow_drafts=drafts, workspace_id=identity.workspace_id
    )


def edit_service(service=Depends(import_service)):
    return CourseNetworkEditService(
        wiki=service.wiki,
        workflow_drafts=service.drafts,
        workspace_id=service.workspace_id,
        material_resolver=lambda c, m, s: read_course_material_section(
            service.wiki, c, m, s
        ),
    )


def envelope(row):
    return {
        "draft_id": row.draft_id,
        "class_id": row.class_id,
        "status": row.status,
        "artifact_revision": row.artifact_revision,
        "artifact_hash": row.artifact_hash,
        "artifact": json.loads(row.artifact_markdown),
        "runtime": row.runtime_json,
        "review": row.active_review_json or None,
        "running": row.turn_in_progress,
    }


class Snapshot(BaseModel):
    expected_revision: int
    expected_hash: str


class MaterialEdit(Snapshot):
    artifact: MaterialImportArtifact


class GraphEdit(Snapshot):
    changes: NetworkChangeSet


class MaterialArchive(BaseModel):
    archived: bool


@router.get("/classes/{class_id}/course/materials")
def materials(class_id: str, service=Depends(import_service)):
    try:
        return {"materials": list_material_library(service.wiki, class_id)}
    except (KeyError, ValueError) as exc:
        _raise_service_error(exc)


@router.post("/classes/{class_id}/course/materials/{material_id}/review-import")
def review_saved_material(class_id: str, material_id: str, service=Depends(import_service)):
    try:
        return envelope(service.from_saved_material(class_id, material_id))
    except Exception as exc:
        _raise_service_error(exc)


@router.patch("/classes/{class_id}/course/materials/{material_id}/archive")
def archive_material(class_id: str, material_id: str, body: MaterialArchive, service=Depends(import_service)):
    try:
        return set_course_material_archived(service.wiki, class_id, material_id, body.archived)
    except Exception as exc:
        _raise_service_error(exc)


@router.get("/classes/{class_id}/course/material-imports/{draft_id}/source")
def import_source(class_id: str, draft_id: str, request: Request, original_page: int | None = None, service=Depends(import_service)):
    try:
        row = service.get(class_id, draft_id)
        path = service.package_dir(row).parent / "upload.pdf"
        if not path.is_file():
            path = service.package_dir(row) / "source.pdf"
        if not path.is_file():
            raise KeyError("Import source PDF not found")
        if original_page is not None:
            return _source_redirect(request, path, original_page)
        return FileResponse(path, media_type="application/pdf")
    except Exception as exc:
        _raise_service_error(exc)


@router.get("/classes/{class_id}/course/material-imports")
def imports(class_id: str, service=Depends(import_service)):
    try:
        service.wiki.get_class(class_id)
        rows = service.drafts.list_active_for_class(class_id, mode="course_material")
        return {
            "drafts": [
                import_status(class_id, row.draft_id, service)
                for row in rows
                if row.workspace_id == service.workspace_id
            ]
        }
    except (KeyError, ValueError) as exc:
        _raise_service_error(exc)


async def _extract(service, class_id, draft_id, contents, pages):
    try:
        await asyncio.to_thread(service.extract, class_id, draft_id, contents, pages)
    except Exception:
        row = service.get(class_id, draft_id)
        save_structured_row(
            service.drafts,
            row,
            json.loads(row.artifact_markdown),
            runtime=row.runtime_json
            | {
                "stage": "failed",
                "error": "Extraction failed. Check the PDF and page selection, then retry.",
            },
        )
    finally:
        _jobs.pop((str(service.wiki.root), draft_id), None)


def start_extraction(service, row, contents, pages):
    key = (str(service.wiki.root), row.draft_id)
    if key in _jobs:
        raise HTTPException(409, "Extraction is already running")
    row = service.drafts.save_from_session(
        draft_id=row.draft_id,
        status="draft",
        artifact_markdown=row.artifact_markdown,
        runtime_json=row.runtime_json | {"stage": "extracting", "page_range": pages},
        messages_json=row.messages_json,
        backend_session_id=row.backend_session_id,
        turn_in_progress=True,
        latest_turn_complete=False,
    )
    task = asyncio.create_task(
        _extract(service, row.class_id, row.draft_id, contents, pages)
    )
    _jobs[key] = task
    return envelope(row)


@router.post("/classes/{class_id}/course/material-imports", status_code=202)
async def upload(
    class_id: str,
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form()] = "",
    arm: Annotated[str, Form()] = "personal",
    pages: Annotated[str, Form()] = "",
    service=Depends(import_service),
):
    try:
        service.wiki.get_class(class_id)
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise ValueError("Upload a PDF file")
        contents = await file.read(40 * 1024 * 1024 + 1)
        if not contents.startswith(b"%PDF-") or len(contents) > 40 * 1024 * 1024:
            raise ValueError("Upload a PDF up to 40 MB")
        try:
            reader = PdfReader(BytesIO(contents))
            if reader.is_encrypted:
                raise ValueError("Encrypted PDFs are not supported")
            selected = sorted(p + 1 for p in parse_page_range(pages, len(reader.pages))) if pages else list(range(1, len(reader.pages) + 1))
        except PdfReadError as exc:
            raise ValueError("This PDF cannot be read. Upload a valid PDF file.") from exc
        if not selected or len(set(selected)) != len(selected) or len(selected) > 30:
            raise ValueError("Select between 1 and 30 distinct PDF pages")
        source_hash = hashlib.sha256(contents).hexdigest()
        for material in list_material_library(service.wiki, class_id):
            root, _ = saved_material_root(service.wiki, class_id, material["material_id"])
            source = root / "source.pdf"
            provenance = root / "provenance.json"
            if source.is_file() and provenance.is_file():
                original_pages = json.loads(provenance.read_text(encoding="utf-8")).get("original_page_numbers", [])
                if sorted(original_pages) == selected and hashlib.sha256(source.read_bytes()).hexdigest() == source_hash:
                    raise WorkflowDraftConflict(f"These PDF pages are already saved as {material['title']}. Open the material in the library; restore it first if archived.")
        for active in service.drafts.list_active_for_class(class_id, mode="course_material"):
            if active.workspace_id == service.workspace_id and active.runtime_json.get("upload_hash") == source_hash and active.runtime_json.get("selected_pages") == selected:
                raise WorkflowDraftConflict("These PDF pages already have an import. Resume or discard it below.")
        row = service.create(class_id, title=title, arm=arm, filename=file.filename)
        row = save_structured_row(service.drafts, row, json.loads(row.artifact_markdown), runtime=row.runtime_json | {"upload_hash": source_hash, "selected_pages": selected})
        source = service.package_dir(row).parent / "upload.pdf"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(contents)
        return start_extraction(service, row, contents, pages or None)
    except Exception as exc:
        _raise_service_error(exc)


@router.get("/classes/{class_id}/course/material-imports/{draft_id}")
def import_status(class_id: str, draft_id: str, service=Depends(import_service)):
    try:
        row = service.get(class_id, draft_id)
        result = envelope(row)
        if row.turn_in_progress and (str(service.wiki.root), draft_id) not in _jobs:
            row = save_structured_row(
                service.drafts,
                row,
                json.loads(row.artifact_markdown),
                runtime=row.runtime_json
                | {
                    "stage": "failed",
                    "error": "Extraction was interrupted. Retry the saved upload.",
                },
            )
            result = envelope(row)
        return result
    except (KeyError, ValueError) as exc:
        _raise_service_error(exc)


@router.post(
    "/classes/{class_id}/course/material-imports/{draft_id}/retry", status_code=202
)
async def retry_import(class_id: str, draft_id: str, service=Depends(import_service)):
    try:
        row = service.get(class_id, draft_id)
        if row.runtime_json.get("stage") not in {"extracting", "failed"}:
            raise HTTPException(409, "Extraction has already completed")
        source = service.package_dir(row).parent / "upload.pdf"
        if not source.exists():
            raise ValueError("Upload this PDF again; no saved source is available")
        return start_extraction(
            service, row, source.read_bytes(), row.runtime_json.get("page_range")
        )
    except (KeyError, ValueError) as exc:
        _raise_service_error(exc)


@router.put("/classes/{class_id}/course/material-imports/{draft_id}")
def update_import(
    class_id: str, draft_id: str, body: MaterialEdit, service=Depends(import_service)
):
    try:
        return envelope(
            service.update(
                class_id,
                draft_id,
                body.artifact.model_dump(),
                body.expected_revision,
                body.expected_hash,
            )
        )
    except Exception as exc:
        _raise_service_error(exc)


@router.post("/classes/{class_id}/course/material-imports/{draft_id}/review")
async def review_import(class_id: str, draft_id: str, service=Depends(import_service)):
    try:
        await service.review(class_id, draft_id)
        return envelope(service.get(class_id, draft_id))
    except Exception as exc:
        _raise_service_error(exc)


@router.post("/classes/{class_id}/course/material-imports/{draft_id}/approve")
def approve_import(
    class_id: str, draft_id: str, body: Snapshot, service=Depends(import_service)
):
    try:
        service.approve(class_id, draft_id, body.expected_revision, body.expected_hash)
        return envelope(service.get(class_id, draft_id))
    except Exception as exc:
        _raise_service_error(exc)


@router.get("/classes/{class_id}/course/materials/{material_id}/sections/{section_id}")
def section(
    class_id: str, material_id: str, section_id: str, service=Depends(import_service)
):
    try:
        return read_course_material_section(
            service.wiki, class_id, material_id, section_id
        )
    except (KeyError, ValueError) as exc:
        _raise_service_error(exc)


@router.get("/classes/{class_id}/course/materials/{material_id}/files/{asset:path}")
def asset(class_id: str, material_id: str, asset: str, request: Request, original_page: int | None = None, service=Depends(import_service)):
    try:
        path = resolve_course_asset(service.wiki, class_id, material_id, asset)
        if original_page is not None:
            if asset != "source.pdf":
                raise ValueError("Page selection is only available for the source PDF")
            return _source_redirect(request, path, original_page)
        return FileResponse(path)
    except (KeyError, ValueError) as exc:
        _raise_service_error(exc)


def _source_redirect(request, source, original_page):
    physical_page = source_page_map(source).get(original_page)
    if physical_page is None:
        raise ValueError("This original page is not available in the source PDF")
    return RedirectResponse(f"{request.url.path}#page={physical_page}")


@router.post(
    "/classes/{class_id}/course/changes/generate",
    responses={502: _GENERATION_UNAVAILABLE_RESPONSE},
)
async def generate_changes(
    class_id: str, body: CourseGenerationRequest, service=Depends(edit_service)
):
    try:
        row = await start_or_resume_generation(service, class_id, body, generate_course_changes)
        return envelope(row)
    except Exception as exc:
        _raise_service_error(exc)


@router.get("/classes/{class_id}/course/changes")
def list_changes(class_id: str, service=Depends(edit_service)):
    try:
        service.wiki.get_class(class_id)
        job = generation_status(service, class_id)
        return {
            "generation": envelope(job) if job else None,
            "drafts": [
                envelope(row)
                for row in service.drafts.list_active_for_class(
                    class_id, mode="course_network"
                )
                if row.intent == "edit" and row.workspace_id == service.workspace_id
            ]
        }
    except Exception as exc:
        _raise_service_error(exc)


@router.post("/classes/{class_id}/course/changes/retry-generation", responses={502: _GENERATION_UNAVAILABLE_RESPONSE})
async def retry_changes_generation(class_id: str, service=Depends(edit_service)):
    try:
        return envelope(await retry_generation(service, class_id, generate_course_changes))
    except Exception as exc:
        _raise_service_error(exc)


@router.post("/classes/{class_id}/course/changes/{draft_id}/discard-generation")
def discard_changes_generation(class_id: str, draft_id: str, body: Snapshot, service=Depends(edit_service)):
    try:
        return envelope(discard_generation(service, class_id, draft_id, body.expected_revision, body.expected_hash))
    except Exception as exc:
        _raise_service_error(exc)


@router.get("/classes/{class_id}/course/changes/{draft_id}")
def get_changes(class_id: str, draft_id: str, service=Depends(edit_service)):
    try:
        return envelope(service.get(class_id, draft_id))
    except Exception as exc:
        _raise_service_error(exc)


@router.put("/classes/{class_id}/course/changes/{draft_id}")
def update_changes(
    class_id: str, draft_id: str, body: GraphEdit, service=Depends(edit_service)
):
    try:
        return envelope(
            service.update(
                class_id,
                draft_id,
                body.changes,
                body.expected_revision,
                body.expected_hash,
            )
        )
    except Exception as exc:
        _raise_service_error(exc)


@router.post("/classes/{class_id}/course/changes/{draft_id}/review")
async def review_changes(class_id: str, draft_id: str, service=Depends(edit_service)):
    try:
        await service.review(class_id, draft_id)
        return envelope(service.get(class_id, draft_id))
    except Exception as exc:
        _raise_service_error(exc)


@router.post("/classes/{class_id}/course/changes/{draft_id}/commit")
def commit_changes(
    class_id: str, draft_id: str, body: Snapshot, service=Depends(edit_service)
):
    try:
        return service.commit(
            class_id, draft_id, body.expected_revision, body.expected_hash
        )
    except Exception as exc:
        _raise_service_error(exc)
