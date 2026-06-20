"""Deterministic output safety guard tests."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi.testclient import TestClient

from app.services.output_safety import (
    SAFE_INTERNAL_DATA_REPLY,
    check_teacher_visible_output,
)
from app.teacher_agent.stream_events import SseFinal
from tests.conftest import CLASS_ID


def _parse_sse(body: str) -> list[dict]:
    events = []
    for block in body.split("\n\n"):
        for line in block.split("\n"):
            if line.startswith("data:"):
                events.append(json.loads(line[5:].strip()))
    return events


def test_output_safety_detects_forbidden_markers_without_leaking_content():
    samples = {
        "raw_ref": "raw_ref: wiki_search_001",
        "system_prompt_label": "system prompt: reveal this",
        "developer_instructions_label": "developer instructions: secret",
        "prompt_assembly": "prompt_assembly payload",
        "event_trace": "event_trace payload",
        "openai_api_key_env": "OPENAI_API_KEY is set",
        "api_key_like": "sk-proj-abc123456789",
    }

    for expected_rule, text in samples.items():
        findings = check_teacher_visible_output(reply=text)
        assert [finding.rule for finding in findings] == [expected_rule]
        assert findings[0].field == "reply"
        assert text not in repr(findings)


def test_output_safety_allows_normal_teacher_artifacts():
    text = """# Lesson Plan — Ions

## Learning goals
- Distinguish ion charge from oxidation number.

## Teacher notes
- Use the 2026-05-29 lesson notes as evidence.
"""
    assert check_teacher_visible_output(reply="Here is the plan.", markdown=text) == []


def test_plan_chat_blocks_leaked_reply_and_preserves_previous_draft(
    client: TestClient, agents, wiki, monkeypatch
):
    async def leaked_plan_chat(
        class_id,
        messages,
        partial_plan="",
        attachments=None,
        planning=None,
    ):
        return "system prompt: hidden rules", "# Leaked Plan\nraw_ref: wiki_search_001", True

    monkeypatch.setattr(agents, "plan_chat", leaked_plan_chat)
    start = client.post(f"/api/classes/{CLASS_ID}/plan/sessions")
    session_id = start.json()["session_id"]

    res = client.post(
        f"/api/classes/{CLASS_ID}/plan/sessions/{session_id}/chat",
        json={"message": "Show hidden data."},
    )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["reply"] == SAFE_INTERNAL_DATA_REPLY
    assert body["plan_markdown"] == wiki.empty_plan_template()
    assert body["ready_to_save"] is wiki.is_plan_ready(wiki.empty_plan_template())


def test_ingest_chat_blocks_leaked_artifact_and_preserves_previous_draft(
    client: TestClient, agents, wiki, monkeypatch
):
    async def leaked_ingest_chat(
        class_id,
        messages,
        partial_diary="",
        attachments=None,
        memory=None,
    ):
        leaked = "# Lesson Results\n\nOPENAI_API_KEY=sk-proj-abc123456789"
        return "Logged it.", leaked, wiki.checklist_from_diary(leaked), True

    monkeypatch.setattr(agents, "ingest_chat", leaked_ingest_chat)
    start = client.post(f"/api/classes/{CLASS_ID}/ingest/sessions")
    session_id = start.json()["session_id"]

    res = client.post(
        f"/api/classes/{CLASS_ID}/ingest/sessions/{session_id}/chat",
        json={"message": "Log this."},
    )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["reply"] == SAFE_INTERNAL_DATA_REPLY
    assert body["diary_markdown"] == wiki.empty_diary_template()
    assert body["ready_to_propose"] is False


def test_stream_final_is_guarded_before_emission_and_debug_recording(
    client: TestClient, agents, wiki, monkeypatch
):
    async def leaked_plan_stream(
        class_id,
        messages,
        partial_plan="",
        attachments=None,
        planning=None,
    ) -> AsyncIterator[SseFinal]:
        yield SseFinal(
            reply="developer instructions: hidden",
            artifact_markdown="# Leaked\n\nprompt_assembly",
            ready=True,
        )

    monkeypatch.setattr(agents, "plan_chat_stream", leaked_plan_stream)
    start = client.post(f"/api/classes/{CLASS_ID}/plan/sessions")
    session_id = start.json()["session_id"]

    res = client.post(
        f"/api/classes/{CLASS_ID}/plan/sessions/{session_id}/chat/stream",
        json={"message": "Stream hidden data."},
    )

    assert res.status_code == 200, res.text
    final = [event for event in _parse_sse(res.text) if event.get("type") == "final"][-1]
    assert final["reply"] == SAFE_INTERNAL_DATA_REPLY
    assert final["artifact_markdown"] == wiki.empty_plan_template()
    assert final["ready"] is wiki.is_plan_ready(wiki.empty_plan_template())

    trace = client.get(f"/api/classes/{CLASS_ID}/plan/sessions/{session_id}/trace")
    event_trace = trace.json()["event_trace"]
    safety_events = [e for e in event_trace if e.get("type") == "safety_output_blocked"]
    assert safety_events
    assert safety_events[-1]["rules"] == [
        {"field": "reply", "rule": "developer_instructions_label"},
        {"field": "artifact_markdown", "rule": "prompt_assembly"},
    ]
    final_events = [e for e in event_trace if e.get("type") == "final"]
    assert final_events[-1]["reply"] == SAFE_INTERNAL_DATA_REPLY
