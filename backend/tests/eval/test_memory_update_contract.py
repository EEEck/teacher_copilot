"""Tier-1 Update Memory trace contract tests (offline, deterministic)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.eval.ingest_trace_scorer import score_ingest_startup_context
from tests.eval.memory_update_prompts import CLASS_ID, MEMORY_UPDATE_PROMPTS
from tests.test_api_stream import _parse_sse


def _parse_turn_events(client: TestClient, session_id: str, message: str) -> list[dict]:
    res = client.post(
        f"/api/classes/{CLASS_ID}/ingest/sessions/{session_id}/chat/stream",
        json={"message": message},
    )
    assert res.status_code == 200, res.text
    return _parse_sse(res.text)


def _tool_names(events: list[dict]) -> list[str]:
    return [str(e.get("name", "")) for e in events if e.get("type") == "tool_call"]


def test_update_memory_trace_before_first_message(client: TestClient):
    start = client.post(f"/api/classes/{CLASS_ID}/ingest/sessions")
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]

    trace = client.get(f"/api/classes/{CLASS_ID}/ingest/sessions/{session_id}/trace")
    assert trace.status_code == 200, trace.text
    result = score_ingest_startup_context(trace.json())
    assert result.passed, result.failures


def test_update_memory_three_turn_stub_scenario_contract(client: TestClient):
    start = client.post(f"/api/classes/{CLASS_ID}/ingest/sessions")
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]

    events_per_turn: list[list[dict]] = []
    traces_after: list[dict] = []
    final_artifact = ""
    expected_phases = ["collect_results", "collect_results", "review_draft"]

    for turn_idx, prompt in enumerate(MEMORY_UPDATE_PROMPTS, start=1):
        events = _parse_turn_events(client, session_id, prompt)
        events_per_turn.append(events)
        trace = client.get(
            f"/api/classes/{CLASS_ID}/ingest/sessions/{session_id}/trace"
        )
        assert trace.status_code == 200, trace.text
        traces_after.append(trace.json())
        final_artifact = traces_after[-1].get("artifact_markdown") or final_artifact
        assert traces_after[-1]["runtime"]["phase"] == expected_phases[turn_idx - 1]

    all_tools = [name for events in events_per_turn for name in _tool_names(events)]
    assert "read_memory_target" in all_tools

    final_trace = traces_after[-1]
    runtime = final_trace["runtime"]
    assert runtime["phase"] == "review_draft"
    assert runtime["target"]["lesson_date"] == "2026-05-29"
    assert runtime["target"]["target_confirmed"] is True
    assert runtime["target"]["intent"] == "correct_existing_results"
    assert runtime["lesson_result_state"]["draft_confidence"] == "high"
    assert final_trace["raw_evidence"]

    assert "S-004 did well" in final_artifact
    assert "poor lesson organization" in final_artifact
    assert "metal displacement" in final_artifact
    assert "Joonho" not in final_artifact
    assert "Alex" not in final_artifact
    assert "Rita" not in final_artifact
    assert "S-001" in final_artifact

    event_types = [e["type"] for e in final_trace["event_trace"]]
    assert "prompt_assembly" in event_types
    assert "reasoning_delta" not in event_types


def test_update_memory_trace_disabled_by_default_in_production(
    client: TestClient, monkeypatch
):
    from app.config import get_settings

    monkeypatch.setenv("APP_ENV", "production")
    # The development worktree intentionally enables traces in backend/.env.
    # Set an explicit production override so this test verifies the production
    # gate rather than inheriting local developer diagnostics.
    monkeypatch.setenv("AGENT_TRACE_ENABLED", "false")
    monkeypatch.delenv("PLAN_TRACE_ENABLED", raising=False)
    get_settings.cache_clear()
    try:
        start = client.post(f"/api/classes/{CLASS_ID}/ingest/sessions")
        session_id = start.json()["session_id"]

        trace = client.get(
            f"/api/classes/{CLASS_ID}/ingest/sessions/{session_id}/trace"
        )
        assert trace.status_code == 404
        assert trace.json()["error"]["message"] == "Memory trace endpoint is disabled"
    finally:
        get_settings.cache_clear()
