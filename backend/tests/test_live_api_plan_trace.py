"""Opt-in live API integration test for the FCKW/redox planning workflow.

This test is intentionally skipped by default because it calls the running API
and may trigger real OpenAI usage. Enable it when developing agent behavior:

    $env:RUN_LIVE_API_TESTS="1"
    $env:LIVE_API_BASE_URL="http://localhost:8010"
    python -m pytest tests/test_live_api_plan_trace.py

Optional soft quality gate (extra OpenAI call):

    $env:RUN_LLM_PLAN_JUDGE="1"
"""

from __future__ import annotations

import json
import os
import urllib.request

import pytest

from tests.eval.fckw_prompts import CLASS_ID, FCKW_PROMPTS
from tests.eval.plan_judge import score_lesson_plan_with_llm_judge
from tests.eval.plan_trace_scorer import merge_results, score_fckw_scenario

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

    trace_before = _json_request("GET", f"{plan_base}/sessions/{session_id}/trace")
    events_per_turn: list[list[dict]] = []
    traces_after: list[dict] = []
    final_artifact = ""

    for prompt in FCKW_PROMPTS:
        events_per_turn.append(
            _stream_request(f"{plan_base}/sessions/{session_id}/chat/stream", {"message": prompt})
        )
        trace = _json_request("GET", f"{plan_base}/sessions/{session_id}/trace")
        traces_after.append(trace)
        final_artifact = trace.get("artifact_markdown") or final_artifact

    contract = score_fckw_scenario(
        trace_before_turn_1=trace_before,
        traces_after_turns=traces_after,
        events_per_turn=events_per_turn,
        final_artifact=final_artifact,
        require_raw_evidence=True,
    )
    judge = score_lesson_plan_with_llm_judge(final_artifact)
    result = merge_results(contract, judge)
    result.assert_ok()
