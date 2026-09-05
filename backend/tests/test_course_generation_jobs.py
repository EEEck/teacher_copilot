import asyncio
import importlib
import importlib.util
import json

import pytest

from app.course_network.edit_service import CourseNetworkEditService
from app.course_network.generation import CourseGenerationError, CourseGenerationRequest, CourseGenerationResult
from app.services.workflow_drafts import WorkflowDraftConflict
from tests.conftest import CLASS_ID
from tests.test_course_network_edits import adopted


def jobs():
    assert importlib.util.find_spec("app.course_network.generation_jobs") is not None, "Durable generation job support is missing"
    return importlib.import_module("app.course_network.generation_jobs")


@pytest.fixture
def service(wiki, workflow_drafts):
    adopted(wiki)
    return CourseNetworkEditService(wiki=wiki, workflow_drafts=workflow_drafts)


def request(text="Clarify the learning goal"):
    return CourseGenerationRequest(purpose="correction", teacher_request=text)


def result(current):
    return CourseGenerationResult.model_validate({"changes": {
        "class_id": CLASS_ID, "base_revision": current.revision, "summary": "Clarify",
        "operations": [{"op": "update_node", "node_id": current.nodes[0].id, "changes": {"learning_goal": "An explicit learning goal"}}],
    }})


def edit_rows(service):
    return [row for row in service.drafts.list_active_for_class(CLASS_ID, mode="course_network") if row.intent == "edit" and row.workspace_id == service.workspace_id]


def test_reservation_is_durable_before_model_await_and_identical_requests_share_result(service):
    module = jobs()
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        calls = 0
        async def generator(wiki, class_id, body, current):
            nonlocal calls
            calls += 1
            row = module.status(service, CLASS_ID)
            assert row.turn_in_progress
            assert row.intent == "generate"
            assert json.loads(row.artifact_markdown)["request"] == body.model_dump(mode="json")
            assert json.loads(row.artifact_markdown)["network_revision"] == current.revision
            assert edit_rows(service) == []
            entered.set()
            await release.wait()
            return result(current)
        first = asyncio.create_task(module.start_or_resume_generation(service, CLASS_ID, request(), generator))
        await entered.wait()
        second = asyncio.create_task(module.start_or_resume_generation(service, CLASS_ID, request(), generator))
        await asyncio.sleep(0)
        assert calls == 1
        with pytest.raises(WorkflowDraftConflict):
            await module.start_or_resume_generation(service, CLASS_ID, request("Different correction"), generator)
        release.set()
        one, two = await asyncio.gather(first, second)
        assert one.draft_id == two.draft_id
        assert len(edit_rows(service)) == 1
        assert module.status(service, CLASS_ID) is None
        replay = await module.start_or_resume_generation(service, CLASS_ID, request(), generator)
        assert replay.draft_id == one.draft_id
        assert calls == 1
        assert service._current(CLASS_ID).revision == 1
    asyncio.run(scenario())


def test_cancelling_http_waiter_keeps_background_generation_running(service):
    module = jobs()
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        async def generator(wiki, class_id, body, current):
            entered.set()
            await release.wait()
            return result(current)
        waiter = asyncio.create_task(module.start_or_resume_generation(service, CLASS_ID, request(), generator))
        await entered.wait()
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        assert module.status(service, CLASS_ID).turn_in_progress
        release.set()
        row = await module.start_or_resume_generation(service, CLASS_ID, request(), generator)
        assert row.intent == "edit"
        assert len(edit_rows(service)) == 1
    asyncio.run(scenario())


def test_failure_preserves_safe_retry_and_never_appears_as_an_edit(service):
    module = jobs()
    async def failing(*args):
        raise CourseGenerationError("Could not generate a usable map proposal. Try again. Your course map has not changed.")
    with pytest.raises(CourseGenerationError):
        asyncio.run(module.start_or_resume_generation(service, CLASS_ID, request("Saved teacher wording"), failing))
    failed = module.status(service, CLASS_ID)
    assert failed.runtime_json["stage"] == "failed"
    assert not failed.turn_in_progress
    assert edit_rows(service) == []
    async def retry(wiki, class_id, body, current):
        assert body.teacher_request == "Saved teacher wording"
        return result(current)
    row = asyncio.run(module.retry_generation(service, CLASS_ID, retry))
    assert row.intent == "edit"
    assert module.status(service, CLASS_ID) is None


def test_restart_status_marks_orphan_interrupted_and_retry_uses_saved_payload(service):
    module = jobs()
    from app.services.workflow_drafts import WorkflowDraftIdentity
    current = service._current(CLASS_ID)
    opened = service.drafts.open_structured_draft(
        WorkflowDraftIdentity(workspace_id=service.workspace_id, class_id=CLASS_ID, mode="course_network", intent="generate", target_kind="generation"),
        default_status="draft", artifact=module._input(request("Resume this wording"), current),
        runtime_json={"stage": "generating"},
    ).row
    service.drafts.save_from_session(draft_id=opened.draft_id, status="draft", artifact_markdown=opened.artifact_markdown, runtime_json=opened.runtime_json, messages_json=[], backend_session_id=opened.backend_session_id, turn_in_progress=True, latest_turn_complete=False)
    recovered = module.status(service, CLASS_ID)
    assert recovered.runtime_json["stage"] == "failed"
    assert "interrupted" in recovered.runtime_json["error"].lower()
    assert not recovered.turn_in_progress
    assert edit_rows(service) == []
    async def generator(wiki, class_id, body, current):
        assert body.teacher_request == "Resume this wording"
        return result(current)
    assert asyncio.run(module.retry_generation(service, CLASS_ID, generator)).intent == "edit"


def test_changed_network_does_not_publish_generation_from_an_old_snapshot(service):
    module = jobs()
    async def generator(wiki, class_id, body, current):
        changed = current.model_copy(deep=True)
        changed.revision += 1
        wiki.write_course_network(class_id, changed)
        return result(current)
    with pytest.raises(WorkflowDraftConflict):
        asyncio.run(module.start_or_resume_generation(service, CLASS_ID, request(), generator))
    assert edit_rows(service) == []
    assert module.status(service, CLASS_ID).runtime_json["stage"] == "failed"


def test_generation_reservations_are_workspace_scoped(service):
    module = jobs()
    other = CourseNetworkEditService(wiki=service.wiki, workflow_drafts=service.drafts, workspace_id="other")
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        async def blocked(wiki, class_id, body, current):
            entered.set()
            await release.wait()
            return result(current)
        task = asyncio.create_task(module.start_or_resume_generation(service, CLASS_ID, request(), blocked))
        await entered.wait()
        assert module.status(other, CLASS_ID) is None
        async def fast(wiki, class_id, body, current):
            return result(current)
        other_row = await module.start_or_resume_generation(other, CLASS_ID, request("Other teacher"), fast)
        assert other_row.workspace_id == "other"
        release.set()
        own_row = await task
        assert own_row.draft_id != other_row.draft_id
    asyncio.run(scenario())


def test_retry_reuses_saved_model_result_after_edit_open_failure(service, monkeypatch):
    module = jobs()
    calls = 0
    async def generator(wiki, class_id, body, current):
        nonlocal calls
        calls += 1
        return result(current)
    original_open = service.open
    def open_then_fail(*args):
        original_open(*args)
        raise OSError("injected crash after edit insert")
    monkeypatch.setattr(service, "open", open_then_fail)
    with pytest.raises(OSError):
        asyncio.run(module.start_or_resume_generation(service, CLASS_ID, request(), generator))
    assert len(edit_rows(service)) == 1
    assert module.status(service, CLASS_ID).runtime_json["result"]
    monkeypatch.setattr(service, "open", original_open)
    recovered = asyncio.run(module.retry_generation(service, CLASS_ID, generator))
    assert recovered.draft_id == edit_rows(service)[0].draft_id
    assert calls == 1
    assert module.status(service, CLASS_ID) is None


def test_retry_finishes_job_receipt_after_edit_was_already_saved(service, monkeypatch):
    module = jobs()
    async def generator(wiki, class_id, body, current):
        return result(current)
    original_save = module._save
    failed_once = False
    def fail_receipt(*args, **kwargs):
        nonlocal failed_once
        if kwargs.get("terminal") and not failed_once:
            failed_once = True
            raise OSError("injected completion receipt failure")
        return original_save(*args, **kwargs)
    monkeypatch.setattr(module, "_save", fail_receipt)
    with pytest.raises(OSError):
        asyncio.run(module.start_or_resume_generation(service, CLASS_ID, request(), generator))
    assert len(edit_rows(service)) == 1
    recovered = asyncio.run(module.retry_generation(service, CLASS_ID, generator))
    assert recovered.draft_id == edit_rows(service)[0].draft_id
    assert module.status(service, CLASS_ID) is None


def test_failure_status_never_exposes_provider_exception_details(service):
    module = jobs()
    async def generator(*args):
        raise RuntimeError("PRIVATE_PROVIDER_KEY_AND_PROMPT")
    with pytest.raises(RuntimeError):
        asyncio.run(module.start_or_resume_generation(service, CLASS_ID, request(), generator))
    row = module.status(service, CLASS_ID)
    assert "PRIVATE_PROVIDER" not in json.dumps(row.runtime_json)
    assert row.runtime_json["stage"] == "failed"
    assert edit_rows(service) == []


def test_discard_refuses_running_jobs_and_discarded_jobs_cannot_be_resurrected(service):
    module = jobs()
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        async def generator(wiki, class_id, body, current):
            entered.set()
            await release.wait()
            return result(current)
        task = asyncio.create_task(module.start_or_resume_generation(service, CLASS_ID, request(), generator))
        await entered.wait()
        job = module.status(service, CLASS_ID)
        with pytest.raises(WorkflowDraftConflict):
            module.discard_generation(service, CLASS_ID, job.draft_id, job.artifact_revision, job.artifact_hash)
        # Defend against a stale generic-discard caller as well as the UI guard.
        service.drafts.discard(job.draft_id)
        release.set()
        with pytest.raises(WorkflowDraftConflict):
            await task
        assert service.drafts.get(job.draft_id).status == "discarded"
        assert edit_rows(service) == []
    asyncio.run(scenario())


def test_failed_generation_discard_requires_exact_job_and_snapshot(service):
    module = jobs()
    async def failing(*args):
        raise CourseGenerationError("Retry")
    with pytest.raises(CourseGenerationError):
        asyncio.run(module.start_or_resume_generation(service, CLASS_ID, request(), failing))
    job = module.status(service, CLASS_ID)
    with pytest.raises(WorkflowDraftConflict):
        module.discard_generation(service, CLASS_ID, job.draft_id, job.artifact_revision, "stale")
    with pytest.raises(KeyError):
        module.discard_generation(service, CLASS_ID, "other-job", job.artifact_revision, job.artifact_hash)
    discarded = module.discard_generation(service, CLASS_ID, job.draft_id, job.artifact_revision, job.artifact_hash)
    assert discarded.status == "discarded"
    assert module.status(service, CLASS_ID) is None


@pytest.mark.parametrize("mutation", ["archive", "document"])
def test_material_input_changes_during_generation_cannot_create_a_proposal(service, mutation):
    from app.course_materials.import_service import CourseMaterialImportService
    from app.course_materials.store import material_root, set_course_material_archived
    from tests.test_course_material_import import Reviewer, extracted
    module = jobs()
    imports = CourseMaterialImportService(wiki=service.wiki, workflow_drafts=service.drafts, reviewer=Reviewer())
    row = extracted(imports, service.wiki)
    asyncio.run(imports.review(CLASS_ID, row.draft_id))
    material = imports.approve(CLASS_ID, row.draft_id, row.artifact_revision, row.artifact_hash)
    body = CourseGenerationRequest(purpose="material_enrichment", material_id=material.material_id)
    async def generator(wiki, class_id, body, current):
        job = module.status(service, CLASS_ID)
        assert json.loads(job.artifact_markdown)["material_snapshot"]["document_hashes"]
        if mutation == "archive":
            set_course_material_archived(wiki, class_id, material.material_id, True)
        else:
            path = material_root(wiki, material) / "document.agent.md"
            path.write_text(path.read_text(encoding="utf-8") + "\nChanged evidence", encoding="utf-8")
        return result(current)
    with pytest.raises(WorkflowDraftConflict):
        asyncio.run(module.start_or_resume_generation(service, CLASS_ID, body, generator))
    assert edit_rows(service) == []
    assert module.status(service, CLASS_ID).runtime_json["stage"] == "failed"
    async def must_not_retry(*args):
        pytest.fail("A changed source must require a new explicit request")
    with pytest.raises((WorkflowDraftConflict, ValueError)):
        asyncio.run(module.retry_generation(service, CLASS_ID, must_not_retry))
