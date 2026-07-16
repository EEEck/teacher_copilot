"""M2: GET /api/workflow/active — what the backend is running right now.

Replaces the frontend's sessionStorage pending-turn markers as the source of
truth for the Running-tasks box and completion toasts. Deterministic; no agent.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.memory_sweep_reviews import MemorySweepReviewStore
from app.services.workflow_drafts import WorkflowDraftIdentity, WorkflowDraftStore

CLASS_A = "chemie_9b_2026_27"
CLASS_B = "physik_10a_2026_27"


def _open_draft(
    store: WorkflowDraftStore,
    *,
    class_id: str,
    mode: str,
    intent: str = "free_entry",
    lesson_date: str = "",
    lesson_title: str = "",
    session_id: str,
):
    return store.open_draft(
        WorkflowDraftIdentity(
            workspace_id="local",
            class_id=class_id,
            mode=mode,
            intent=intent,
            lesson_date=lesson_date,
            lesson_title=lesson_title,
        ),
        default_status="chatting",
        artifact_markdown="# Draft",
        backend_session_id=session_id,
    ).row


def _set_turn_running(store: WorkflowDraftStore, row, running: bool) -> None:
    store.save_from_session(
        draft_id=row.draft_id,
        status="chatting",
        artifact_markdown=row.artifact_markdown,
        runtime_json={},
        messages_json=[],
        backend_session_id=row.backend_session_id,
        turn_in_progress=running,
        latest_turn_complete=not running,
    )


def test_lists_in_progress_draft_turns_across_classes(
    client: TestClient, workflow_drafts: WorkflowDraftStore
):
    running_a = _open_draft(
        workflow_drafts,
        class_id=CLASS_A,
        mode="ingest",
        intent="log_new_results",
        lesson_date="2026-10-05",
        lesson_title="Alkane naming",
        session_id="sess-a",
    )
    running_b = _open_draft(
        workflow_drafts, class_id=CLASS_B, mode="plan", session_id="sess-b"
    )
    idle = _open_draft(
        workflow_drafts, class_id=CLASS_A, mode="discuss", session_id="sess-idle"
    )
    _set_turn_running(workflow_drafts, running_a, True)
    _set_turn_running(workflow_drafts, running_b, True)
    _set_turn_running(workflow_drafts, idle, False)

    res = client.get("/api/workflow/active")
    assert res.status_code == 200, res.text
    items = res.json()["items"]

    by_draft = {i["draft_id"]: i for i in items}
    assert running_a.draft_id in by_draft
    assert running_b.draft_id in by_draft
    # Idle-but-active drafts are resumable work, not running work.
    assert idle.draft_id not in by_draft

    a = by_draft[running_a.draft_id]
    assert a["kind"] == "draft_turn"
    assert a["class_id"] == CLASS_A
    assert a["mode"] == "ingest"
    assert a["session_id"] == "sess-a"
    assert a["lesson_date"] == "2026-10-05"
    assert a["lesson_title"] == "Alkane naming"
    # Cross-class: a second class's running turn is visible too.
    assert by_draft[running_b.draft_id]["class_id"] == CLASS_B


def test_excludes_terminal_drafts(
    client: TestClient, workflow_drafts: WorkflowDraftStore
):
    row = _open_draft(
        workflow_drafts, class_id=CLASS_A, mode="plan", session_id="sess-term"
    )
    # A saved draft whose turn flag was never cleared must not look "running".
    workflow_drafts.save_from_session(
        draft_id=row.draft_id,
        status="chatting",
        artifact_markdown="# Draft",
        runtime_json={},
        messages_json=[],
        backend_session_id="sess-term",
        turn_in_progress=True,
        latest_turn_complete=False,
    )
    workflow_drafts.mark_saved(row.draft_id)

    items = client.get("/api/workflow/active").json()["items"]
    assert all(i["draft_id"] != row.draft_id for i in items)


def test_lists_generating_memory_sweeps(
    client: TestClient, memory_sweep_reviews: MemorySweepReviewStore
):
    generating = memory_sweep_reviews.create_generating(
        class_id=CLASS_A, source_fingerprint="fp-1", source={}
    )
    done = memory_sweep_reviews.create_generating(
        class_id=CLASS_B, source_fingerprint="fp-2", source={}
    )
    memory_sweep_reviews.mark_failed(done.review_id, error="boom")

    items = client.get("/api/workflow/active").json()["items"]
    sweeps = [i for i in items if i["kind"] == "memory_sweep"]

    assert [s["review_id"] for s in sweeps] == [generating.review_id]
    assert sweeps[0]["class_id"] == CLASS_A


def test_empty_when_nothing_running(client: TestClient):
    assert client.get("/api/workflow/active").json()["items"] == []
