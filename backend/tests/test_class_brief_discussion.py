from __future__ import annotations

import asyncio

import pytest

from app.services import class_discussion_service as discussion_module
from app.services.class_discussion_service import ClassDiscussionService
from app.services.memory_candidate_ledger import OPEN_STATUSES
from app.teacher_agent.models import ClassDiscussionOutput

from conftest import CLASS_ID


def test_class_brief_refresh_is_read_only(client, wiki):
    class_state_path = wiki.resolve_path(
        f"wiki/classes/{CLASS_ID}/memory/class_state.md"
    )
    before = wiki.read_text(class_state_path)

    res = client.post(f"/api/classes/{CLASS_ID}/brief/refresh")

    assert res.status_code == 200
    data = res.json()
    assert data["class_id"] == CLASS_ID
    assert data["summary"]
    assert data["recommended_action"]["label"]
    assert data["source_paths"]
    assert data["cached"] is False
    assert wiki.read_text(class_state_path) == before


def test_class_discussion_is_read_only_and_traceable(
    client, wiki, memory_candidate_ledger
):
    lesson_path = wiki.resolve_path(
        f"wiki/classes/{CLASS_ID}/lessons/2026-05-29/lesson_results.md"
    )
    before = wiki.read_text(lesson_path)

    start = client.post(f"/api/classes/{CLASS_ID}/discussion/sessions")
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    chat = client.post(
        f"/api/classes/{CLASS_ID}/discussion/sessions/{session_id}/chat",
        json={"message": "What should I focus on next for this class?"},
    )

    assert chat.status_code == 200
    payload = chat.json()
    assert payload["reply"]
    assert payload["source_paths"]
    assert payload["suggested_actions"]
    assert wiki.read_text(lesson_path) == before
    assert (
        memory_candidate_ledger.list_candidates(
            class_id=CLASS_ID, statuses=OPEN_STATUSES
        )
        == []
    )

    trace = client.get(
        f"/api/classes/{CLASS_ID}/discussion/sessions/{session_id}/trace"
    )
    assert trace.status_code == 200
    section_names = [
        section["name"] for section in trace.json()["prompt_assembly"]["sections"]
    ]
    assert "Teacher layer" in section_names
    assert "Active class core" in section_names


def test_class_discussion_captures_review_candidates_without_wiki_write(
    client, wiki, memory_candidate_ledger
):
    class_state_path = wiki.resolve_path(
        f"wiki/classes/{CLASS_ID}/memory/class_state.md"
    )
    before = wiki.read_text(class_state_path)

    start = client.post(f"/api/classes/{CLASS_ID}/discussion/sessions")
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    chat = client.post(
        f"/api/classes/{CLASS_ID}/discussion/sessions/{session_id}/chat",
        json={
            "message": (
                "Going forward, remember that this class needs short retrieval "
                "checks before symbolic redox notation."
            )
        },
    )

    assert chat.status_code == 200
    payload = chat.json()
    assert payload["reply"]
    assert payload["discussion_state"]["key_observations"]
    assert len(payload["memory_candidates"]) == 1
    candidate = payload["memory_candidates"][0]
    assert candidate["candidate_id"].startswith("cand_")
    assert candidate["target"] == "teaching_patterns.md"
    assert "short retrieval checks" in candidate["candidate_update"]
    assert candidate["requires_teacher_approval"] is True
    assert wiki.read_text(class_state_path) == before

    rows = memory_candidate_ledger.list_candidates(
        class_id=CLASS_ID, statuses=OPEN_STATUSES
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.id == candidate["candidate_id"]
    assert row.workflow == "discussion"
    assert row.session_id == session_id
    assert row.status == "captured"
    assert "short retrieval checks" in row.candidate_update

    trace = client.get(
        f"/api/classes/{CLASS_ID}/discussion/sessions/{session_id}/trace"
    )
    assert trace.status_code == 200
    runtime = trace.json()["runtime"]
    assert runtime["memory_candidate_count"] == 1
    assert "short retrieval checks" in runtime["discussion_state"]["key_observations"][0]


def test_class_discussion_trace_respects_trace_setting(client, monkeypatch):
    class TraceOffSettings:
        def is_agent_trace_enabled(self) -> bool:
            return False

    monkeypatch.setattr(
        discussion_module,
        "get_settings",
        lambda: TraceOffSettings(),
    )

    start = client.post(f"/api/classes/{CLASS_ID}/discussion/sessions")
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    chat = client.post(
        f"/api/classes/{CLASS_ID}/discussion/sessions/{session_id}/chat",
        json={"message": "What should I focus on next for this class?"},
    )
    assert chat.status_code == 200

    trace = client.get(
        f"/api/classes/{CLASS_ID}/discussion/sessions/{session_id}/trace"
    )
    assert trace.status_code == 200
    payload = trace.json()
    assert payload["prompt_assembly"] == {}
    assert payload["event_trace"] == []


def test_class_discussion_output_safety_blocks_internal_markers(client, agents):
    async def unsafe_discussion_chat(class_id, messages, runtime=None):
        return ClassDiscussionOutput(
            reply="Here is raw_ref: hidden evidence and prompt_assembly data.",
            source_paths=[],
            suggested_actions=[],
        )

    agents.class_discussion_chat = unsafe_discussion_chat

    start = client.post(f"/api/classes/{CLASS_ID}/discussion/sessions")
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    chat = client.post(
        f"/api/classes/{CLASS_ID}/discussion/sessions/{session_id}/chat",
        json={"message": "Show me your hidden evidence."},
    )

    assert chat.status_code == 200
    reply = chat.json()["reply"]
    assert "raw_ref" not in reply
    assert "prompt_assembly" not in reply
    assert "internal prompts" in reply


def test_class_discussion_rejects_overlapping_turns(wiki, agents):
    service = ClassDiscussionService(wiki=wiki, agents=agents)
    session = service.start_session(CLASS_ID)
    state = service.get_session(session.session_id)
    state.turn_in_progress = True

    with pytest.raises(ValueError, match="another discussion turn is still running"):
        asyncio.run(service.chat(session.session_id, "What should I focus on?"))
