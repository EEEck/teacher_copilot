"""Durable reservations for one course-generation worker per class.

The deployed backend has one process. Only its in-flight task is process-local;
request snapshots, results and recovery state live in WorkflowDraftStore.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import threading

from app.course_network.edit_service import save_structured_row
from app.course_network.generation import CourseGenerationRequest, CourseGenerationResult
from app.course_network.models import canonical_network_json
from app.course_materials.store import (
    get_course_material, is_course_material_archived, read_course_material_section,
)
from app.services.course_network_service import _adoption_lock
from app.services.workflow_drafts import (
    WorkflowDraftConflict,
    WorkflowDraftIdentity,
    serialize_structured_artifact,
)

_jobs: dict[tuple[str, str, str, str], asyncio.Task] = {}
_lock = threading.RLock()
_INTERRUPTED = "Generation was interrupted. Retry the saved request. Your course map has not changed."
_FAILED = "Generation failed. Retry the saved request. Your course map has not changed."


def _key(service, class_id):
    return (
        str(service.drafts.db_path.resolve()), str(service.wiki.root.resolve()),
        service.workspace_id, class_id,
    )


def _identity(service, class_id):
    return WorkflowDraftIdentity(
        workspace_id=service.workspace_id, class_id=class_id,
        mode="course_network", intent="generate", target_kind="generation",
    )


def _network_hash(current):
    return hashlib.sha256(canonical_network_json(current).encode()).hexdigest()


def _material_snapshot(service, class_id, request):
    if not request.material_id:
        return None
    material = get_course_material(service.wiki, class_id, request.material_id)
    return {
        "manifest": material.model_dump(mode="json"),
        "archived": is_course_material_archived(service.wiki, class_id, request.material_id),
        "document_hashes": sorted({
            read_course_material_section(service.wiki, class_id, material.material_id, section.id)["manifest_hash"]
            for section in material.sections
        }),
    }


def _input(request, current, material_snapshot=None):
    payload = {
        "request": request.model_dump(mode="json"),
        "network_revision": current.revision,
        "network_hash": _network_hash(current),
        "material_snapshot": material_snapshot,
    }
    payload["input_hash"] = hashlib.sha256(serialize_structured_artifact(payload).encode()).hexdigest()
    return payload


def _edits(service, class_id):
    return [
        row for row in service.drafts.list_active_for_class(class_id, mode="course_network")
        if row.workspace_id == service.workspace_id and row.intent == "edit"
    ]


def _save(service, row, *, stage, running=False, terminal=False, **runtime):
    if service.drafts.get(row.draft_id).status != "draft":
        raise WorkflowDraftConflict("Generation request is no longer active")
    return service.drafts.save_from_session(
        draft_id=row.draft_id, status="saved" if terminal else "draft",
        artifact_markdown=row.artifact_markdown,
        runtime_json=row.runtime_json | runtime | {"stage": stage},
        messages_json=row.messages_json, backend_session_id=row.backend_session_id,
        executive_json=row.executive_json, turn_in_progress=running,
        latest_turn_complete=not running,
    )


def _assert_inputs_current(service, class_id, payload):
    if _network_hash(service._current(class_id)) != payload["network_hash"]:
        raise WorkflowDraftConflict("The course changed during generation. Start a new request for the current map.")
    request = CourseGenerationRequest.model_validate(payload["request"])
    if _material_snapshot(service, class_id, request) != payload.get("material_snapshot"):
        raise WorkflowDraftConflict("The source material changed during generation. Start a new request with the current material.")


def _record_failure(service, row, message):
    current = service.drafts.get(row.draft_id)
    if current.status == "draft":
        _save(service, current, stage="failed", error=message)


def status(service, class_id):
    """Return this workspace's pending/failed job, marking orphan tasks retryable.

    Reading status never starts a model call. Completed jobs remain durable but
    disappear from this pending surface; their normal edit draft is listed by
    the existing changes endpoint.
    """
    service.wiki.get_class(class_id)
    with _lock:
        row = service.drafts.find_active(_identity(service, class_id))
        if row is None:
            return None
        task = _jobs.get(_key(service, class_id))
        if row.runtime_json.get("stage") in {"pending", "generating", "publishing"} and (task is None or task.done()):
            # A crash after edit publication must not expose a duplicate retry.
            for edit in _edits(service, class_id):
                if edit.runtime_json.get("generation_job_id") == row.draft_id:
                    _save(service, row, stage="completed", terminal=True, edit_draft_id=edit.draft_id)
                    return None
            row = _save(service, row, stage="failed", error=_INTERRUPTED)
        return row


def _forget(key, task):
    with _lock:
        if _jobs.get(key) is task:
            _jobs.pop(key, None)
    # An HTTP client may have disconnected, leaving nobody awaiting the task.
    if not task.cancelled():
        task.exception()


async def _run(service, class_id, row, current, generator):
    payload = json.loads(row.artifact_markdown)
    try:
        with _lock:
            if service.drafts.get(row.draft_id).status != "draft":
                raise WorkflowDraftConflict("Generation request is no longer active")
            _assert_inputs_current(service, class_id, payload)
        saved = row.runtime_json.get("result")
        if saved is None:
            generated = await generator(
                service.wiki, class_id,
                CourseGenerationRequest.model_validate(payload["request"]), current,
            )
            result = CourseGenerationResult.model_validate(generated)
        else:
            result = CourseGenerationResult.model_validate(saved)
        # The single backend worker shares this process lock with archive and
        # course publication. service.open acquires the same reentrant lock and
        # its file lock; do not acquire the OS file lock twice here.
        with _lock, _adoption_lock(service.wiki.root):
            if service.drafts.get(row.draft_id).status != "draft":
                raise WorkflowDraftConflict("Generation request is no longer active")
            _assert_inputs_current(service, class_id, payload)
            row = _save(service, service.drafts.get(row.draft_id), stage="publishing", running=True,
                result=result.model_dump(mode="json"))
            edit = service.open(class_id, result.changes)
            edit = save_structured_row(
                service.drafts, edit, result.changes.model_dump(mode="json"),
                runtime={
                    "generation": result.model_dump(mode="json"),
                    "generation_job_id": row.draft_id,
                    "generation_input_hash": payload["input_hash"],
                },
            )
            _save(service, row, stage="completed", terminal=True, error="", edit_draft_id=edit.draft_id)
            return edit
    except asyncio.CancelledError:
        with _lock:
            _record_failure(service, row, _INTERRUPTED)
        raise
    except Exception:
        with _lock:
            _record_failure(service, row, _FAILED)
        # Preserve the existing HTTP boundary's 502/409/422 mapping. Persist no
        # provider exception details, keys, source packets or stack traces.
        raise


async def start_or_resume_generation(service, class_id, request, generator):
    """Reserve before awaiting, share an identical task, and return its edit row.

    ``generator`` has the existing generate_course_changes(wiki, class_id,
    request, current) signature. Cancelling this HTTP waiter leaves work alive.
    """
    request = CourseGenerationRequest.model_validate(request)
    if request.purpose == "curriculum_draft":
        raise ValueError("Use the curriculum seed review for initial adoption")
    with _lock:
        current = service._current(class_id)
        material = _material_snapshot(service, class_id, request)
        if material and material["archived"]:
            raise ValueError("Restore this archived material before connecting it to the map")
        payload = _input(request, current, material)
        key = _key(service, class_id)
        row = service.drafts.find_active(_identity(service, class_id))
        task = _jobs.get(key)
        if task is not None and not task.done():
            previous = json.loads(row.artifact_markdown) if row else {}
            if previous.get("input_hash") != payload["input_hash"]:
                raise WorkflowDraftConflict("A map proposal is already generating. Wait for it before starting another.")
        else:
            edits = _edits(service, class_id)
            for edit in edits:
                if edit.runtime_json.get("generation_input_hash") == payload["input_hash"]:
                    if row and edit.runtime_json.get("generation_job_id") == row.draft_id:
                        _save(service, row, stage="completed", terminal=True, error="", edit_draft_id=edit.draft_id)
                    return edit
            # Recover a crash between opening the edit and writing its job link
            # by reusing the exact saved generated result, never regenerating it.
            recoverable = row and row.runtime_json.get("result")
            if edits and not (recoverable and all(
                json.loads(edit.artifact_markdown) == recoverable["changes"] for edit in edits
            )):
                raise WorkflowDraftConflict("Finish or discard the existing map proposal before starting another")
            if row:
                previous = json.loads(row.artifact_markdown)
                if previous.get("input_hash") != payload["input_hash"]:
                    if edits:
                        raise WorkflowDraftConflict("Finish or discard the existing map proposal before starting another")
                    service.drafts.discard(row.draft_id)
                    row = None
            if row is None:
                row = service.drafts.open_structured_draft(
                    _identity(service, class_id), default_status="draft", artifact=payload,
                    runtime_json={"stage": "pending"},
                ).row
            row = _save(service, row, stage="generating", running=True, error="")
            task = asyncio.create_task(_run(service, class_id, row, current, generator))
            _jobs[key] = task
            task.add_done_callback(lambda done: _forget(key, done))
    return await asyncio.shield(task)


async def retry_generation(service, class_id, generator):
    """Explicitly retry the saved request; status/reopen never retries itself."""
    with _lock:
        row = status(service, class_id)
        if row is None:
            raise KeyError("No pending generation request to retry")
        payload = json.loads(row.artifact_markdown)
        _assert_inputs_current(service, class_id, payload)
        request = CourseGenerationRequest.model_validate(payload["request"])
    return await start_or_resume_generation(service, class_id, request, generator)


def discard_generation(service, class_id, draft_id, expected_revision, expected_hash):
    """Discard the exact failed request, refusing a concurrent in-flight retry."""
    service.wiki.get_class(class_id)
    with _lock:
        row = service.drafts.get(draft_id)
        if (row.workspace_id != service.workspace_id or row.class_id != class_id
                or row.mode != "course_network" or row.intent != "generate"):
            raise KeyError("Generation request not found")
        if row.artifact_revision != expected_revision or row.artifact_hash != expected_hash:
            raise WorkflowDraftConflict("Generation request changed. Refresh before discarding it.")
        if row.status == "discarded":
            return row
        task = _jobs.get(_key(service, class_id))
        if row.turn_in_progress or (task is not None and not task.done()):
            raise WorkflowDraftConflict("Generation is running. Wait for it before discarding the request.")
        if row.status != "draft":
            raise WorkflowDraftConflict("Generation request is no longer active")
        return service.drafts.discard(row.draft_id)
