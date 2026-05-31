"""Smoke test for the lesson-plan flow: start -> chat -> save.

This is the flow that produced the original ``API 500: 'title'`` bug; the test
pins that a chat turn renders prompts and returns a draft without error.
Runs fully offline against the stub agent + a tmp copy of the seed wiki.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import CLASS_ID


def test_plan_full_flow(client: TestClient):
    base = f"/api/classes/{CLASS_ID}/plan"

    start = client.post(f"{base}/sessions")
    assert start.status_code == 200, start.text
    start_body = start.json()
    session_id = start_body["session_id"]
    assert start_body["opening_message"] == ""

    chat = client.post(
        f"{base}/sessions/{session_id}/chat",
        json={"message": "Plan a 45 min lesson on stoichiometry."},
    )
    assert chat.status_code == 200, chat.text
    chat_body = chat.json()
    assert chat_body["reply"]
    assert chat_body["plan_markdown"]
    assert chat_body["ready_to_save"] is True

    save = client.post(
        f"{base}/save",
        json={
            "session_id": session_id,
            "lesson_date": "2026-10-05",
            "plan_markdown": chat_body["plan_markdown"],
        },
    )
    assert save.status_code == 200, save.text
    save_body = save.json()
    assert save_body["plan_path"]
    assert save_body["lesson_date"] == "2026-10-05"


def test_plan_chat_unknown_session_returns_typed_404(client: TestClient):
    res = client.post(
        f"/api/classes/{CLASS_ID}/plan/sessions/nope/chat",
        json={"message": "hi"},
    )
    assert res.status_code == 404
    body = res.json()
    assert body["error"]["type"] == "http_error"
    assert "Unknown session" in body["error"]["message"]


def test_plan_save_rejects_invalid_lesson_date(client: TestClient):
    base = f"/api/classes/{CLASS_ID}/plan"
    start = client.post(f"{base}/sessions")
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]

    save = client.post(
        f"{base}/save",
        json={
            "session_id": session_id,
            "lesson_date": "../bad",
            "plan_markdown": "# Lesson Plan\n\n## Learning goals\n\n## Lesson flow\n\n## Warmup\n",
        },
    )

    assert save.status_code == 422
    assert "lesson_date must be YYYY-MM-DD" in save.text
