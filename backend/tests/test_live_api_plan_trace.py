"""Opt-in live API integration test for the FCKW/redox planning workflow.

This test is intentionally skipped by default because it calls the running API
and may trigger real OpenAI usage. Enable it when developing agent behavior:

    $env:RUN_LIVE_API_TESTS="1"
    $env:LIVE_API_BASE_URL="http://localhost:8010"
    python -m pytest tests/test_live_api_plan_trace.py
"""

from __future__ import annotations

import json
import os
import urllib.request

import pytest

CLASS_ID = "chemie_9b_2026_27"

PROMPT = """Plan the next 45-minute lesson for Chemie 9b. Topic: redox reactions applied to CFC/FCKW compounds (Chlorfluorkohlenwasserstoffe). Include about 10 minutes on environmental impact (ozone layer, Montreal Protocol, alternatives). Build on our existing redox lessons in the wiki. Exam-oriented Gymnasium level.
Structure the lesson flow: 5 min redox recap, 15 min FCKW structure and redox half-reactions, 10 min environmental impact with one example (e.g. CFC-11), 10 min practice, 5 min exit ticket. Note the misconception: oxidation number vs charge.
Add differentiated practice and homework (2 questions). Teacher notes: no real CFCs in the lab; demo alternatives only."""

REVIEW_PROMPT = """Can we also add a 5 min review session of the last 4 lectures? I would like to consider what the class confused the last few sessions and incorporate key findings to make the introduction of FCKW simpler for them to digest."""

FINAL_REFINEMENT_PROMPT = """I am very happy with it. Maybe as a last refinement, let's add only a 2 min recap together with students actively recalling the key learning."""


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_API_TESTS") != "1",
    reason="live API integration tests are opt-in",
)


def _json_request(method: str, url: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as res:
        return json.loads(res.read().decode("utf-8"))


def _stream_request(url: str, payload: dict) -> list[dict]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
    )
    with urllib.request.urlopen(req, timeout=240) as res:
        text = res.read().decode("utf-8")
    events: list[dict] = []
    for block in text.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data:"):
                events.append(json.loads(line[5:].strip()))
    return events


def test_live_fckw_plan_uses_wiki_tools_and_trace():
    base = os.getenv("LIVE_API_BASE_URL", "http://localhost:8010").rstrip("/")
    plan_base = f"{base}/api/classes/{CLASS_ID}/plan"
    session = _json_request("POST", f"{plan_base}/sessions", {})
    session_id = session["session_id"]

    turn1_events = _stream_request(
        f"{plan_base}/sessions/{session_id}/chat/stream", {"message": PROMPT}
    )
    trace1 = _json_request("GET", f"{plan_base}/sessions/{session_id}/trace")
    assert trace1["runtime"]["session_state"]["phase"] == "lesson_refinement"

    turn2_events = _stream_request(
        f"{plan_base}/sessions/{session_id}/chat/stream",
        {"message": REVIEW_PROMPT},
    )
    trace2 = _json_request("GET", f"{plan_base}/sessions/{session_id}/trace")
    assert trace2["runtime"]["session_state"]["phase"] == "lesson_refinement"

    turn3_events = _stream_request(
        f"{plan_base}/sessions/{session_id}/chat/stream",
        {"message": FINAL_REFINEMENT_PROMPT},
    )
    events = turn1_events + turn2_events + turn3_events
    tool_names = [e.get("name") for e in events if e.get("type") == "tool_call"]
    final = [e for e in turn3_events if e.get("type") == "final"][-1]
    plan = final["artifact_markdown"]

    assert "search_memory" in tool_names
    assert any(name in tool_names for name in ("read_lesson", "read_lesson_range"))
    assert "45 min" in plan or "45-minute" in plan
    assert "CFC" in plan or "FCKW" in plan
    assert "oxidation number" in plan
    assert "charge" in plan
    assert "Montreal Protocol" in plan
    assert "no real CFCs" in plan
    assert "2 min" in plan or "2-minute" in plan
    assert "recall" in plan.lower()

    trace = _json_request("GET", f"{plan_base}/sessions/{session_id}/trace")
    event_types = [e["type"] for e in trace["event_trace"]]

    assert trace["prompt_stack"]["class_slice"]
    assert trace["prompt_stack"]["current_lessonplan_md"]
    assert trace["runtime"]["session_state"]["phase"] == "finalize"
    assert trace["runtime"]["lesson_planning_state"]["duration_minutes"] == 45
    assert "tool_call" in event_types
    assert "tool_result" in event_types
    assert "reasoning_delta" not in event_types
    assert trace["raw_evidence"]
