"""Smoke test for SSE chat stream endpoints."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from tests.conftest import CLASS_ID


def _parse_sse(body: str) -> list[dict]:
    events = []
    for block in body.split("\n\n"):
        for line in block.split("\n"):
            if line.startswith("data:"):
                events.append(json.loads(line[5:].strip()))
    return events


def test_ingest_chat_stream(client: TestClient):
    start = client.post(f"/api/classes/{CLASS_ID}/ingest/sessions")
    session_id = start.json()["session_id"]

    res = client.post(
        f"/api/classes/{CLASS_ID}/ingest/sessions/{session_id}/chat/stream",
        json={"message": "We covered acids today."},
    )
    assert res.status_code == 200
    assert "text/event-stream" in res.headers.get("content-type", "")

    events = _parse_sse(res.text)
    assert any(e.get("type") == "reasoning_delta" for e in events)
    final = [e for e in events if e.get("type") == "final"]
    assert len(final) == 1
    assert final[0]["reply"]
    assert final[0]["artifact_markdown"]


def test_plan_chat_stream(client: TestClient):
    start = client.post(f"/api/classes/{CLASS_ID}/plan/sessions")
    session_id = start.json()["session_id"]

    res = client.post(
        f"/api/classes/{CLASS_ID}/plan/sessions/{session_id}/chat/stream",
        json={"message": "Plan a lesson on ions."},
    )
    assert res.status_code == 200
    events = _parse_sse(res.text)
    assert any(e.get("type") == "tool_call" for e in events)
    assert any(e.get("type") == "final" for e in events)


def test_plan_chat_stream_fckw_redox_uses_memory_pathfinder(client: TestClient):
    start = client.post(f"/api/classes/{CLASS_ID}/plan/sessions")
    session_id = start.json()["session_id"]

    res = client.post(
        f"/api/classes/{CLASS_ID}/plan/sessions/{session_id}/chat/stream",
        json={
            "message": (
                "Plan the next 45-minute lesson for Chemie 9b. Topic: redox "
                "reactions applied to CFC/FCKW compounds. Build on our "
                "existing redox lessons in the wiki."
            )
        },
    )
    assert res.status_code == 200
    events = _parse_sse(res.text)
    tool_names = [e.get("name") for e in events if e.get("type") == "tool_call"]
    assert "search_memory" in tool_names
    assert "read_lesson_range" in tool_names
    final = [e for e in events if e.get("type") == "final"][-1]
    assert "2026-05-25" in final["artifact_markdown"]
