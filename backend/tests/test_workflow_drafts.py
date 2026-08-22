from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor

import anyio
import pytest

from app.course_network.seeds import load_seed_for_class
from app.services.workflow_drafts import (
    WorkflowDraftIdentity,
    serialize_structured_artifact,
)
from app.schemas.api import ApprovedWikiUpdate, CommitIngestRequest, SavePlanRequest
from app.services.ingest_service import IngestService
from app.services.plan_service import PlanService
from app.services.workflow_drafts import WorkflowDraftStore
from tests.conftest import CLASS_ID, COMPLETE_DIARY, READY_PLAN, StubAgentRunner


def test_concurrent_structured_open_resumes_one_active_draft(wiki, monkeypatch):
    db_path = wiki.root / "workflow" / "workflow_drafts.sqlite"
    stores = [WorkflowDraftStore(db_path), WorkflowDraftStore(db_path)]
    stores[0].initialize()
    identity = WorkflowDraftIdentity(
        workspace_id="local",
        class_id=CLASS_ID,
        mode="course_network",
        intent="seed_adoption",
        target_kind="course_network",
    )
    seed = load_seed_for_class(wiki, CLASS_ID).model_dump(mode="json")
    barrier = threading.Barrier(2)

    for store in stores:
        original_find_active = store.find_active

        def synchronized_find_active(identity, *, _find=original_find_active):
            row = _find(identity)
            barrier.wait(timeout=5)
            return row

        monkeypatch.setattr(store, "find_active", synchronized_find_active)

    def open_with(store):
        return store.open_structured_draft(
            identity,
            default_status="draft",
            artifact=seed,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(open_with, stores))

    assert len({result.row.draft_id for result in results}) == 1
    assert sorted(result.created for result in results) == [False, True]
    assert len(stores[0].list_active_for_class(CLASS_ID, mode="course_network")) == 1


def test_structured_artifact_serialization_is_order_stable_and_invalidates_review(wiki):
    store = WorkflowDraftStore(wiki.root / "workflow" / "workflow_drafts.sqlite")
    store.initialize()
    seed = load_seed_for_class(wiki, CLASS_ID)
    artifact = serialize_structured_artifact(seed.model_dump(mode="json"))

    assert artifact == serialize_structured_artifact(
        dict(reversed(list(seed.model_dump(mode="json").items())))
    )
    assert ", \"" not in artifact

    opened = store.open_structured_draft(
        WorkflowDraftIdentity(
            workspace_id="local",
            class_id=CLASS_ID,
            mode="course_network",
            intent="seed_adoption",
            target_kind="course_network",
        ),
        default_status="draft",
        artifact=seed.model_dump(mode="json"),
    ).row
    reviewed = store.mark_review_snapshot(
        opened.draft_id,
        revision=opened.artifact_revision,
        artifact_hash_value=opened.artifact_hash,
        review_json={"decision": "accept", "summary": "Looks sound.", "findings": []},
    )
    changed_payload = json.loads(artifact)
    changed_payload["nodes"][0]["title"] += " (angepasst)"
    changed = store.save_from_session(
        draft_id=opened.draft_id,
        status="draft",
        artifact_markdown=serialize_structured_artifact(changed_payload),
        runtime_json={},
        messages_json=[],
        backend_session_id=opened.backend_session_id,
    )

    assert reviewed.active_review_json["decision"] == "accept"
    assert changed.active_review_revision is None
    assert changed.active_review_hash is None
    assert changed.active_review_json == {}


@pytest.mark.anyio
async def test_general_ingest_session_resumes_same_durable_draft(wiki, agents):
    store = WorkflowDraftStore(wiki.root / "workflow" / "workflow_drafts.sqlite")
    store.initialize()
    first = IngestService(wiki=wiki, agents=agents, workflow_drafts=store)

    started = await first.start_session(CLASS_ID)
    patched = first.update_draft(started.session_id, COMPLETE_DIARY)

    second = IngestService(wiki=wiki, agents=agents, workflow_drafts=store)
    resumed = await second.start_session(CLASS_ID)
    resumed_draft = second.get_draft(resumed.session_id)

    assert resumed.draft_id == started.draft_id
    assert resumed.session_id == started.session_id
    assert resumed.messages == started.messages
    assert resumed_draft.diary_markdown == patched.diary_markdown
    assert resumed_draft.artifact_revision == patched.artifact_revision
    assert resumed_draft.artifact_hash == patched.artifact_hash


@pytest.mark.anyio
async def test_executive_findings_survive_workflow_draft_resume(wiki, agents):
    store = WorkflowDraftStore(wiki.root / "workflow" / "workflow_drafts.sqlite")
    store.initialize()
    plan = PlanService(wiki=wiki, agents=agents, workflow_drafts=store)

    session = await plan.start_session(CLASS_ID)
    await plan.chat(session.session_id, "Add a note for student S-999.")
    live = plan.core.get_session(session.session_id)
    assert [item.finding_id for item in live.executive.open_blocking_findings()] == [
        "student-s999"
    ]

    resumed_service = PlanService(wiki=wiki, agents=agents, workflow_drafts=store)
    resumed = await resumed_service.start_session(CLASS_ID)
    restored = resumed_service.core.get_session(resumed.session_id)

    assert resumed.draft_id == session.draft_id
    assert [
        item.finding_id for item in restored.executive.open_blocking_findings()
    ] == ["student-s999"]


@pytest.mark.anyio
async def test_plan_session_id_rehydrates_for_save_after_service_restart(wiki, agents):
    store = WorkflowDraftStore(wiki.root / "workflow" / "workflow_drafts.sqlite")
    store.initialize()
    first = PlanService(wiki=wiki, agents=agents, workflow_drafts=store)

    started = await first.start_session(CLASS_ID)
    saved_draft = first.update_draft(started.session_id, READY_PLAN)

    restarted = PlanService(wiki=wiki, agents=agents, workflow_drafts=store)
    draft = restarted.get_draft(started.session_id)

    assert draft.plan_markdown == READY_PLAN
    assert restarted.get_session(started.session_id).draft_id == started.draft_id

    response = await restarted.save(
        CLASS_ID,
        SavePlanRequest(
            session_id=started.session_id,
            lesson_date="2026-10-05",
            plan_markdown=READY_PLAN,
            draft_id=started.draft_id,
            expected_artifact_revision=saved_draft.artifact_revision,
            expected_artifact_hash=saved_draft.artifact_hash,
        ),
    )

    assert response.lesson_date == "2026-10-05"


@pytest.mark.anyio
async def test_timeline_ingest_drafts_are_scoped_by_lesson_date(wiki, agents):
    store = WorkflowDraftStore(wiki.root / "workflow" / "workflow_drafts.sqlite")
    store.initialize()
    ingest = IngestService(wiki=wiki, agents=agents, workflow_drafts=store)

    first = await ingest.start_session(
        CLASS_ID,
        hint={
            "lesson_date": "2026-05-29",
            "intent": "correct_existing_results",
            "target_kind": "taught_lesson",
            "source": "timeline_hint",
        },
    )
    second = await ingest.start_session(
        CLASS_ID,
        hint={
            "lesson_date": "2027-01-15",
            "intent": "update_missing_results",
            "target_kind": "planned_lesson",
            "source": "timeline_hint",
        },
    )
    first_again = await ingest.start_session(
        CLASS_ID,
        hint={
            "lesson_date": "2026-05-29",
            "intent": "correct_existing_results",
            "target_kind": "taught_lesson",
            "source": "timeline_hint",
        },
    )

    assert first.draft_id != second.draft_id
    assert first_again.draft_id == first.draft_id


@pytest.mark.anyio
async def test_discarded_ingest_draft_is_not_resumed(wiki, agents):
    store = WorkflowDraftStore(wiki.root / "workflow" / "workflow_drafts.sqlite")
    store.initialize()
    ingest = IngestService(wiki=wiki, agents=agents, workflow_drafts=store)

    first = await ingest.start_session(CLASS_ID)
    ingest.discard_draft(first.draft_id)
    fresh = await ingest.start_session(CLASS_ID)

    assert fresh.draft_id != first.draft_id


@pytest.mark.anyio
async def test_ingest_commit_rejects_stale_review_snapshot(wiki, agents):
    store = WorkflowDraftStore(wiki.root / "workflow" / "workflow_drafts.sqlite")
    store.initialize()
    ingest = IngestService(wiki=wiki, agents=agents, workflow_drafts=store)

    session = await ingest.start_session(CLASS_ID)
    draft = ingest.update_draft(session.session_id, COMPLETE_DIARY)
    proposed = await ingest.propose(session.session_id)
    ingest.update_draft(
        session.session_id,
        COMPLETE_DIARY.replace("Topic A", "Topic A plus a late correction"),
    )
    approved = [
        ApprovedWikiUpdate(
            wiki_path=p.wiki_path,
            content=p.proposed_content,
            approved=True,
        )
        for p in proposed.wiki_proposals
    ]

    with pytest.raises(ValueError, match="draft_changed_since_review_created"):
        await ingest.commit(
            CommitIngestRequest(
                session_id=session.session_id,
                diary_markdown="STALE CLIENT MARKDOWN",
                approved_updates=approved,
                draft_id=session.draft_id,
                expected_artifact_revision=draft.artifact_revision,
                expected_artifact_hash=draft.artifact_hash,
                source_artifact_revision=proposed.artifact_revision,
                source_artifact_hash=proposed.artifact_hash,
            )
        )


@pytest.mark.anyio
async def test_unfinished_streamed_turn_guard_survives_service_restart(wiki, agents):
    store = WorkflowDraftStore(wiki.root / "workflow" / "workflow_drafts.sqlite")
    store.initialize()
    ingest = IngestService(wiki=wiki, agents=agents, workflow_drafts=store)

    session = await ingest.start_session(CLASS_ID)
    store.save_from_session(
        draft_id=session.draft_id,
        status=session.status.value,
        artifact_markdown=COMPLETE_DIARY,
        runtime_json={},
        messages_json=[
            message.model_dump() for message in session.messages
        ] + [{"role": "user", "content": "sorry, I forgot one more thing"}],
        backend_session_id=session.session_id,
        turn_in_progress=False,
        latest_turn_complete=False,
    )

    resumed = IngestService(wiki=wiki, agents=agents, workflow_drafts=store)
    resumed_session = await resumed.start_session(CLASS_ID)

    _, proposals = wiki.compile_from_diary(CLASS_ID, COMPLETE_DIARY)
    approved = [
        ApprovedWikiUpdate(
            wiki_path=p.wiki_path,
            content=p.proposed_content,
            approved=True,
        )
        for p in proposals
    ]
    with pytest.raises(ValueError, match="latest chat turn"):
        await resumed.commit(
            CommitIngestRequest(
                session_id=resumed_session.session_id,
                diary_markdown=COMPLETE_DIARY,
                approved_updates=approved,
            )
        )


@pytest.mark.anyio
async def test_streamed_turn_continues_after_client_stops_consuming(wiki, agents):
    store = WorkflowDraftStore(wiki.root / "workflow" / "workflow_drafts.sqlite")
    store.initialize()
    plan = PlanService(wiki=wiki, agents=agents, workflow_drafts=store)

    session = await plan.start_session(CLASS_ID)
    stream = plan.chat_stream(session.session_id, "review the last 4 lectures")
    first_line = await anext(stream)
    assert first_line.startswith("data:")
    await stream.aclose()

    for _ in range(50):
        row = store.get(session.draft_id)
        if row.latest_turn_complete and not row.turn_in_progress:
            break
        await anyio.sleep(0.01)
    else:
        pytest.fail("streamed turn did not finish after the client stopped consuming")

    row = store.get(session.draft_id)
    assert row.artifact_revision > 0
    assert "Review of recent lessons" in row.artifact_markdown
    assert row.messages_json[-1]["role"] == "assistant"


@pytest.mark.anyio
async def test_inflight_turn_resumes_after_service_restart(wiki, agents):
    store = WorkflowDraftStore(wiki.root / "workflow" / "workflow_drafts.sqlite")
    store.initialize()
    first = PlanService(wiki=wiki, agents=agents, workflow_drafts=store)

    started = await first.start_session(CLASS_ID)
    store.save_from_session(
        draft_id=started.draft_id,
        status=started.status.value,
        artifact_markdown="",
        runtime_json={},
        messages_json=[
            *[message.model_dump() for message in started.messages],
            {"role": "user", "content": "review the last 4 lectures"},
        ],
        backend_session_id=started.session_id,
        pending_turn_json={"attachments": []},
        turn_in_progress=True,
        latest_turn_complete=False,
    )

    resumed = PlanService(wiki=wiki, agents=agents, workflow_drafts=store)
    await resumed.start_session(CLASS_ID)

    for _ in range(50):
        row = store.get(started.draft_id)
        if row.latest_turn_complete and not row.turn_in_progress:
            break
        await anyio.sleep(0.01)
    else:
        pytest.fail("resumed streamed turn did not finish after service restart")

    row = store.get(started.draft_id)
    assert row.messages_json[-1]["role"] == "assistant"
    assert "Review of recent lessons" in row.artifact_markdown


@pytest.mark.anyio
async def test_ingest_commit_uses_backend_draft_when_revision_present(wiki, agents):
    store = WorkflowDraftStore(wiki.root / "workflow" / "workflow_drafts.sqlite")
    store.initialize()
    ingest = IngestService(wiki=wiki, agents=agents, workflow_drafts=store)

    session = await ingest.start_session(CLASS_ID)
    draft = ingest.update_draft(session.session_id, COMPLETE_DIARY)
    proposed = await ingest.propose(session.session_id)
    approved = [
        ApprovedWikiUpdate(
            wiki_path=p.wiki_path,
            content=p.proposed_content,
            approved=True,
        )
        for p in proposed.wiki_proposals
    ]

    response = await ingest.commit(
        CommitIngestRequest(
            session_id=session.session_id,
            diary_markdown="# Lesson Results -- 1999-01-01 -- stale",
            approved_updates=approved,
            draft_id=session.draft_id,
            expected_artifact_revision=draft.artifact_revision,
            expected_artifact_hash=draft.artifact_hash,
            source_artifact_revision=proposed.artifact_revision,
            source_artifact_hash=proposed.artifact_hash,
        )
    )

    assert response.lesson_date == "2026-10-01"


@pytest.mark.anyio
async def test_plan_save_rejects_stale_draft_and_uses_backend_markdown(wiki, agents):
    store = WorkflowDraftStore(wiki.root / "workflow" / "workflow_drafts.sqlite")
    store.initialize()
    plan = PlanService(wiki=wiki, agents=agents, workflow_drafts=store)

    session = await plan.start_session(CLASS_ID)
    draft = plan.update_draft(session.session_id, READY_PLAN)

    stale = SavePlanRequest(
        session_id=session.session_id,
        lesson_date="2026-10-05",
        plan_markdown="# Lesson Plan -- stale",
        draft_id=session.draft_id,
        expected_artifact_revision=draft.artifact_revision,
        expected_artifact_hash=draft.artifact_hash,
    )
    response = await plan.save(CLASS_ID, stale)
    saved = wiki.read_text(wiki.resolve_path(response.plan_path))
    assert "Stub Plan" in saved
    assert "stale" not in saved

    updated = plan.update_draft(session.session_id, READY_PLAN + "\n\nLate edit.\n")
    with pytest.raises(ValueError, match="draft_changed_since_review_created"):
        await plan.save(
            CLASS_ID,
            stale.model_copy(
                update={
                    "expected_artifact_revision": draft.artifact_revision,
                    "expected_artifact_hash": draft.artifact_hash,
                }
            ),
        )
    assert updated.artifact_revision > draft.artifact_revision


def test_discard_workflow_draft_endpoint_starts_fresh(client):
    base = f"/api/classes/{CLASS_ID}/ingest"

    first = client.post(f"{base}/sessions")
    assert first.status_code == 200, first.text
    first_body = first.json()

    discard = client.post(
        f"/api/classes/{CLASS_ID}/workflow-drafts/{first_body['draft_id']}/discard"
    )
    assert discard.status_code == 200, discard.text
    assert discard.json()["status"] == "discarded"

    second = client.post(f"{base}/sessions")
    assert second.status_code == 200, second.text
    assert second.json()["draft_id"] != first_body["draft_id"]


def test_timeline_marks_matching_active_ingest_draft(client, wiki):
    lesson_date = "2027-01-15"
    wiki.write_text(
        wiki.lesson_dir(CLASS_ID, lesson_date) / "lesson_plan.md",
        READY_PLAN,
    )
    started = client.post(
        f"/api/classes/{CLASS_ID}/ingest/sessions",
        json={
            "lesson_date": lesson_date,
            "lesson_title": "Stub Plan",
            "intent": "update_missing_results",
            "target_kind": "planned_lesson",
            "source": "timeline_hint",
        },
    )
    assert started.status_code == 200, started.text
    session_id = started.json()["session_id"]

    # Empty open (assistant greeting only) is not a Draft chip / Edit draft CTA.
    empty_timeline = client.get(f"/api/classes/{CLASS_ID}/timeline")
    assert empty_timeline.status_code == 200, empty_timeline.text
    empty_body = empty_timeline.json()
    empty_entry = next(
        item for item in empty_body["entries"] if item["date"] == lesson_date
    )
    assert empty_entry["memory_draft_id"] is None
    assert empty_body["active_memory_draft"] is None

    chat = client.post(
        f"/api/classes/{CLASS_ID}/ingest/sessions/{session_id}/chat",
        json={"message": "We finished alkanes today."},
    )
    assert chat.status_code == 200, chat.text

    timeline = client.get(f"/api/classes/{CLASS_ID}/timeline")

    assert timeline.status_code == 200, timeline.text
    body = timeline.json()
    entry = next(item for item in body["entries"] if item["date"] == lesson_date)
    assert entry["memory_draft_id"] == started.json()["draft_id"]
    assert body["active_memory_draft"]["draft_id"] == started.json()["draft_id"]
    assert body["active_plan_draft"] is None

    discarded = client.post(
        f"/api/classes/{CLASS_ID}/workflow-drafts/{started.json()['draft_id']}/discard"
    )
    assert discarded.status_code == 200, discarded.text
    refreshed = client.get(f"/api/classes/{CLASS_ID}/timeline")
    refreshed_body = refreshed.json()
    refreshed_entry = next(
        item for item in refreshed_body["entries"] if item["date"] == lesson_date
    )
    assert refreshed_entry["memory_draft_id"] is None
    assert refreshed_body["active_memory_draft"] is None


def test_timeline_plan_draft_chip_needs_teacher_progress(client):
    started = client.post(f"/api/classes/{CLASS_ID}/plan/sessions")
    assert started.status_code == 200, started.text
    session_id = started.json()["session_id"]

    empty = client.get(f"/api/classes/{CLASS_ID}/timeline")
    assert empty.status_code == 200, empty.text
    assert empty.json()["active_plan_draft"] is None

    chat = client.post(
        f"/api/classes/{CLASS_ID}/plan/sessions/{session_id}/chat",
        json={"message": "Plan a short review lesson."},
    )
    assert chat.status_code == 200, chat.text

    touched = client.get(f"/api/classes/{CLASS_ID}/timeline")
    assert touched.status_code == 200, touched.text
    assert touched.json()["active_plan_draft"]["draft_id"] == started.json()["draft_id"]

    discarded = client.post(
        f"/api/classes/{CLASS_ID}/workflow-drafts/{started.json()['draft_id']}/discard"
    )
    assert discarded.status_code == 200, discarded.text
    # Discard + auto-open of a fresh shell must not leave a Draft chip.
    client.post(f"/api/classes/{CLASS_ID}/plan/sessions")
    after = client.get(f"/api/classes/{CLASS_ID}/timeline")
    assert after.status_code == 200, after.text
    assert after.json()["active_plan_draft"] is None


def test_ingest_commit_stale_review_returns_409(client):
    base = f"/api/classes/{CLASS_ID}/ingest"

    start = client.post(f"{base}/sessions")
    assert start.status_code == 200, start.text
    start_body = start.json()
    session_id = start_body["session_id"]

    patch = client.patch(
        f"{base}/sessions/{session_id}/draft",
        json={"diary_markdown": COMPLETE_DIARY},
    )
    assert patch.status_code == 200, patch.text
    draft_body = patch.json()

    propose = client.post(f"{base}/sessions/{session_id}/propose")
    assert propose.status_code == 200, propose.text
    proposed = propose.json()

    stale_patch = client.patch(
        f"{base}/sessions/{session_id}/draft",
        json={
            "diary_markdown": COMPLETE_DIARY.replace(
                "Topic A", "Topic A plus stale conflict"
            )
        },
    )
    assert stale_patch.status_code == 200, stale_patch.text

    approved = [
        {"wiki_path": p["wiki_path"], "content": p["proposed_content"], "approved": True}
        for p in proposed["wiki_proposals"]
    ]
    commit = client.post(
        f"/api/classes/{CLASS_ID}/ingest/commit",
        json={
            "session_id": session_id,
            "diary_markdown": "STALE CLIENT MARKDOWN",
            "approved_updates": approved,
            "draft_id": start_body["draft_id"],
            "expected_artifact_revision": draft_body["artifact_revision"],
            "expected_artifact_hash": draft_body["artifact_hash"],
            "source_artifact_revision": proposed["artifact_revision"],
            "source_artifact_hash": proposed["artifact_hash"],
        },
    )
    assert commit.status_code == 409, commit.text
    assert "draft_changed_since_review_created" in commit.text
