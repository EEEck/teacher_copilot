"""Smoke test for the ingest (update-memory) flow: start -> chat -> propose -> commit.

Runs fully offline against the stub agent + a tmp copy of the seed wiki.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import CLASS_ID, COMPLETE_DIARY


def test_ingest_full_flow(client: TestClient):
    base = f"/api/classes/{CLASS_ID}/ingest"

    start = client.post(f"{base}/sessions")
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]

    chat = client.post(
        f"{base}/sessions/{session_id}/chat",
        json={"message": "We covered Topic A today."},
    )
    assert chat.status_code == 200, chat.text
    chat_body = chat.json()
    assert chat_body["reply"]
    assert chat_body["diary_markdown"]
    assert chat_body["ready_to_propose"] is True

    propose = client.post(f"{base}/sessions/{session_id}/propose")
    assert propose.status_code == 200, propose.text
    proposals = propose.json()["wiki_proposals"]
    assert len(proposals) > 0

    approved = [
        {"wiki_path": p["wiki_path"], "content": p["proposed_content"], "approved": True}
        for p in proposals
    ]
    commit = client.post(
        f"/api/classes/{CLASS_ID}/ingest/commit",
        json={
            "session_id": session_id,
            "diary_markdown": chat_body["diary_markdown"],
            "approved_updates": approved,
        },
    )
    assert commit.status_code == 200, commit.text
    commit_body = commit.json()
    assert commit_body["applied_wiki_paths"]
    assert commit_body["log_entry_id"]


def test_ingest_commit_skips_unapproved_wiki_paths(client: TestClient):
    """Phase 5 trust: unchecked proposals must not be written via the HTTP commit path."""
    base = f"/api/classes/{CLASS_ID}/ingest"
    wiki_base = f"/api/classes/{CLASS_ID}/wiki/file"

    start = client.post(f"{base}/sessions")
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    patch = client.patch(
        f"{base}/sessions/{session_id}/draft",
        json={"diary_markdown": COMPLETE_DIARY},
    )
    assert patch.status_code == 200

    propose = client.post(f"{base}/sessions/{session_id}/propose")
    assert propose.status_code == 200
    proposals = propose.json()["wiki_proposals"]
    lesson_prop = next(p for p in proposals if "lesson_results.md" in p["wiki_path"])
    student_prop = next(p for p in proposals if "students/S-014.md" in p["wiki_path"])

    before = client.get(wiki_base, params={"path": student_prop["wiki_path"]})
    assert before.status_code == 200
    before_md = before.json()["markdown"]

    commit = client.post(
        f"/api/classes/{CLASS_ID}/ingest/commit",
        json={
            "session_id": session_id,
            "diary_markdown": COMPLETE_DIARY,
            "approved_updates": [
                {
                    "wiki_path": lesson_prop["wiki_path"],
                    "content": lesson_prop["proposed_content"],
                    "approved": True,
                },
                {
                    "wiki_path": student_prop["wiki_path"],
                    "content": student_prop["proposed_content"],
                    "approved": False,
                },
            ],
        },
    )
    assert commit.status_code == 200, commit.text
    applied = commit.json()["applied_wiki_paths"]
    assert student_prop["wiki_path"] not in applied
    assert any("lesson_results.md" in p for p in applied)

    after = client.get(wiki_base, params={"path": student_prop["wiki_path"]})
    assert after.status_code == 200
    assert after.json()["markdown"] == before_md
    assert "## 2026-10-01" not in after.json()["markdown"]


def test_ingest_commit_requires_lesson_results_approved(client: TestClient):
    base = f"/api/classes/{CLASS_ID}/ingest"

    start = client.post(f"{base}/sessions")
    session_id = start.json()["session_id"]
    client.patch(
        f"{base}/sessions/{session_id}/draft",
        json={"diary_markdown": COMPLETE_DIARY},
    )
    propose = client.post(f"{base}/sessions/{session_id}/propose")
    timeline_prop = next(
        p for p in propose.json()["wiki_proposals"] if p["wiki_path"].endswith("timeline.md")
    )

    commit = client.post(
        f"/api/classes/{CLASS_ID}/ingest/commit",
        json={
            "session_id": session_id,
            "diary_markdown": COMPLETE_DIARY,
            "approved_updates": [
                {
                    "wiki_path": timeline_prop["wiki_path"],
                    "content": timeline_prop["proposed_content"],
                    "approved": True,
                },
            ],
        },
    )
    assert commit.status_code == 400
    assert "lesson_results" in commit.json()["error"]["message"]


def test_ingest_chat_unknown_session_returns_typed_404(client: TestClient):
    res = client.post(
        f"/api/classes/{CLASS_ID}/ingest/sessions/does-not-exist/chat",
        json={"message": "hi"},
    )
    assert res.status_code == 404
    body = res.json()
    assert body["error"]["type"] == "http_error"
    assert "Unknown session" in body["error"]["message"]


def test_validation_error_returns_typed_envelope(client: TestClient):
    start = client.post(f"/api/classes/{CLASS_ID}/ingest/sessions")
    session_id = start.json()["session_id"]
    # Missing required `message` field -> 422 via the validation handler.
    res = client.post(
        f"/api/classes/{CLASS_ID}/ingest/sessions/{session_id}/chat",
        json={},
    )
    assert res.status_code == 422
    assert res.json()["error"]["type"] == "validation_error"
