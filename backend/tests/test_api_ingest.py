"""Smoke test for the ingest (update-memory) flow: start -> chat -> propose -> commit.

Runs fully offline against the stub agent + a tmp copy of the seed wiki.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import CLASS_ID


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
