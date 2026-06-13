"""Tier-1 FCKW plan trace contract tests (offline, deterministic)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.conftest import CLASS_ID
from tests.eval.fckw_prompts import FCKW_PROMPTS
from tests.eval.plan_trace_scorer import (
    load_trace_json,
    score_fckw_scenario,
    score_startup_context,
    tool_names_from_events,
)
from tests.test_api_stream import _parse_sse

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "fckw_plan"


def _parse_turn_events(client: TestClient, session_id: str, message: str) -> list[dict]:
    res = client.post(
        f"/api/classes/{CLASS_ID}/plan/sessions/{session_id}/chat/stream",
        json={"message": message},
    )
    assert res.status_code == 200, res.text
    return _parse_sse(res.text)


def test_fckw_startup_context_before_first_message(client: TestClient):
    start = client.post(f"/api/classes/{CLASS_ID}/plan/sessions")
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]

    trace = client.get(f"/api/classes/{CLASS_ID}/plan/sessions/{session_id}/trace")
    assert trace.status_code == 200, trace.text
    result = score_startup_context(trace.json())
    assert result.passed, result.failures


def test_fckw_startup_context_fixture_trace():
    fixture = _FIXTURE_DIR / "trace_before_turn1.json"
    if not fixture.exists():
        pytest.skip("fixture trace not generated yet")
    result = score_startup_context(load_trace_json(fixture))
    assert result.passed, result.failures


def test_fckw_three_turn_stub_scenario_contract(client: TestClient):
    start = client.post(f"/api/classes/{CLASS_ID}/plan/sessions")
    session_id = start.json()["session_id"]
    trace0 = client.get(f"/api/classes/{CLASS_ID}/plan/sessions/{session_id}/trace").json()

    events_per_turn: list[list[dict]] = []
    traces_after: list[dict] = []
    final_artifact = ""

    for prompt in FCKW_PROMPTS:
        events_per_turn.append(_parse_turn_events(client, session_id, prompt))
        trace = client.get(f"/api/classes/{CLASS_ID}/plan/sessions/{session_id}/trace").json()
        traces_after.append(trace)
        final_artifact = trace.get("artifact_markdown") or final_artifact

    result = score_fckw_scenario(
        trace_before_turn_1=trace0,
        traces_after_turns=traces_after,
        events_per_turn=events_per_turn,
        final_artifact=final_artifact,
    )
    assert result.passed, result.failures


def test_stub_turn1_uses_memory_pathfinder_tools(client: TestClient):
    start = client.post(f"/api/classes/{CLASS_ID}/plan/sessions")
    session_id = start.json()["session_id"]
    events = _parse_turn_events(client, session_id, FCKW_PROMPTS[0])
    names = tool_names_from_events(events)
    assert "search_memory" in names
    assert "read_lesson_range" in names
