"""Smoke test for SSE chat stream endpoints."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.config import get_settings
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
    assert final[0]["last_change_summary"] == "Updated lesson results."
    assert final[0]["memory_state"]["target"]["lesson_date"] == "2026-10-01"


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
                "reactions applied to CFC/FCKW compounds "
                "(Chlorfluorkohlenwasserstoffe). Include about 10 minutes on "
                "environmental impact (ozone layer, Montreal Protocol, "
                "alternatives). Build on our existing redox lessons in the wiki. "
                "Exam-oriented Gymnasium level. Structure the lesson flow: "
                "5 min redox recap, 15 min FCKW structure and redox half-reactions, "
                "10 min environmental impact with one example (e.g. CFC-11), "
                "10 min practice, 5 min exit ticket. Note the misconception: "
                "oxidation number vs charge. Add differentiated practice and "
                "homework (2 questions). Teacher notes: no real CFCs in the lab; "
                "demo alternatives only."
            )
        },
    )
    assert res.status_code == 200
    events = _parse_sse(res.text)
    tool_names = [e.get("name") for e in events if e.get("type") == "tool_call"]
    assert "search_memory" in tool_names
    assert "read_lesson_range" in tool_names
    final = [e for e in events if e.get("type") == "final"][-1]
    assert final["artifact_markdown"]
    assert "2026-05-25" in final["artifact_markdown"]
    assert "Homework" in final["artifact_markdown"]

    trace = client.get(f"/api/classes/{CLASS_ID}/plan/sessions/{session_id}/trace")
    assert trace.status_code == 200, trace.text
    body = trace.json()
    assert body["prompt_stack"]["teacher_context"]
    assert body["prompt_stack"]["active_class_core"]
    assert body["prompt_assembly"]["stage"] == "plan_chat"
    section_names = [s["name"] for s in body["prompt_assembly"]["sections"]]
    assert section_names.count("Teacher layer") == 1
    assert section_names.count("Active class core") == 1
    assert body["prompt_assembly"]["nested"]["teacher_context"]["sections"]
    assert body["prompt_assembly"]["nested"]["active_class_core"]["sections"]
    assert "Class Copilot Profile" in body["prompt_stack"]["active_class_core"]
    assert body["prompt_stack"]["current_lessonplan_md"]
    assert body["runtime"]["session_state"]["phase"] == "lesson_refinement"
    assert body["runtime"]["lesson_planning_state"]["duration_minutes"] == 45
    assert "wiki_search_001" in body["raw_evidence"]
    event_types = [e["type"] for e in body["event_trace"]]
    assert "reasoning_delta" not in event_types
    assert event_types.count("prompt_assembly") >= 2
    assert "tool_call" in event_types
    assert "tool_result" in event_types
    assert "final" in event_types


def test_plan_trace_disabled_by_default_in_production(
    client: TestClient, monkeypatch
):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("PLAN_TRACE_ENABLED", raising=False)
    get_settings.cache_clear()
    try:
        start = client.post(f"/api/classes/{CLASS_ID}/plan/sessions")
        session_id = start.json()["session_id"]

        trace = client.get(
            f"/api/classes/{CLASS_ID}/plan/sessions/{session_id}/trace"
        )
        assert trace.status_code == 404
        assert trace.json()["error"]["message"] == "Plan trace endpoint is disabled"
    finally:
        get_settings.cache_clear()
