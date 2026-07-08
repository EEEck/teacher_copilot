from __future__ import annotations

import json
from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.schemas.api import ChatAttachment, ChatMessage
from app.teacher_agent.stream_events import SseFinal, SseReasoningDelta
from app.teacher_agent.wiki_store import WikiStore
from tests.conftest import CLASS_ID, StubAgentRunner

FCKW_INITIAL_MESSAGE = (
    "What was covered no problem on those two items: Review common anions and their "
    "charges. Separate ion charge from oxidation number. I could not fully cover "
    "the following due to student confusin and interruption: Connect chloride, "
    "oxide, and phosphate back to the redox sequence. Student participation "
    "student were engaged"
)
FCKW_REORGANIZE_MESSAGE = (
    "I want to add more information about student participation: Matt was also "
    "doing well and helped other students with reguards to interruption that was "
    "mainly due to my poor lesson organization can you organize the lesson results "
    "in a mbb style so it is easier to review"
)
FCKW_FORGOTTEN_MESSAGE = (
    "sorry i forgot to add that i plan to have a carefully review student "
    "particpation and focus more on encurougaing student to particapte"
)

FCKW_DIARY = """# Lesson Results - 2026-07-02 - Lesson Plan - Redox reactions and FCKWs (CFCs)

## What was covered
- Reviewed common anions and their charges.
- Revisited the difference between ion charge and oxidation number.
- Tried to connect chloride, oxide, and phosphate back to the redox sequence, but this could not be fully completed because of student confusion and interruptions.

## Student participation
- Students were engaged overall.
- Confusion built up during the lesson, and support was not signaled early enough.
- Participation dropped during the phosphate discussion.
- S-042 was also doing well and helped other students.

## What went well
- Students understood the common anions quickly.
- The explanation of the common anions was clear.
- S-042 supported other students well.

## What didn't go well
- The lesson went into a rabbit hole with phosphates.
- This confused students too much and disrupted the flow of the lesson.
- The interruptions were made worse by my lesson organization.

## Student observations
- S-033 understood the phosphate redox states best and did very well.
- S-014 interrupted often and was not following along.
- S-027 participated well, but not everything was correct.
- S-042 helped other students and was doing well.

## Homework & follow-ups
- Homework focused mainly on common anions.
- Revisit the link between chloride, oxide, phosphate, and the redox sequence in a later lesson.
- Check the distinction between ion charge and oxidation number again if needed.
"""

FCKW_AMENDED_DIARY = (
    FCKW_DIARY.rstrip()
    + "\n- Carefully review student participation and focus more on encouraging students to participate.\n"
)


def _install_fckw_ingest_stub(
    monkeypatch: pytest.MonkeyPatch,
    agents: StubAgentRunner,
    wiki: WikiStore,
) -> None:
    async def ingest_chat_stream(
        class_id: str,
        messages: list[ChatMessage],
        partial_diary: str = "",
        attachments: list[ChatAttachment] | None = None,
        memory=None,
    ) -> AsyncIterator:
        yield SseReasoningDelta(text="Reviewing class memory...")
        latest = messages[-1].content.lower() if messages else ""
        diary = FCKW_AMENDED_DIARY if "forgot" in latest else FCKW_DIARY
        yield SseFinal(
            reply="Updated the FCKW lesson results.",
            artifact_markdown=diary,
            ready=True,
            completeness=wiki.checklist_from_diary(diary),
            last_change_summary="Updated lesson results.",
            memory_state={},
        )

    monkeypatch.setattr(agents, "ingest_chat_stream", ingest_chat_stream)


def _approved_updates(proposals: list[dict]) -> list[dict]:
    return [
        {
            "wiki_path": proposal["wiki_path"],
            "content": proposal["proposed_content"],
            "approved": True,
        }
        for proposal in proposals
    ]


def _final_diary_from_stream_response(response) -> str:
    events = []
    for block in response.text.split("\n\n"):
        for line in block.split("\n"):
            if line.startswith("data:"):
                events.append(json.loads(line[5:].strip()))
    final = [event for event in events if event.get("type") == "final"][-1]
    return final["artifact_markdown"]


def test_forgotten_note_after_first_commit_amends_lesson_without_duplicate_rollups(
    client: TestClient,
    agents: StubAgentRunner,
    wiki: WikiStore,
    monkeypatch: pytest.MonkeyPatch,
):
    _install_fckw_ingest_stub(monkeypatch, agents, wiki)

    start = client.post(f"/api/classes/{CLASS_ID}/ingest/sessions")
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]

    first = client.post(
        f"/api/classes/{CLASS_ID}/ingest/sessions/{session_id}/chat/stream",
        json={"message": FCKW_INITIAL_MESSAGE},
    )
    assert first.status_code == 200, first.text
    first_diary = _final_diary_from_stream_response(first)

    second = client.post(
        f"/api/classes/{CLASS_ID}/ingest/sessions/{session_id}/chat/stream",
        json={
            "message": FCKW_REORGANIZE_MESSAGE,
            "diary_markdown": first_diary,
        },
    )
    assert second.status_code == 200, second.text
    review_diary = _final_diary_from_stream_response(second)

    propose = client.post(f"/api/classes/{CLASS_ID}/ingest/sessions/{session_id}/propose")
    assert propose.status_code == 200, propose.text
    commit = client.post(
        f"/api/classes/{CLASS_ID}/ingest/commit",
        json={
            "session_id": session_id,
            "diary_markdown": review_diary,
            "approved_updates": _approved_updates(propose.json()["wiki_proposals"]),
        },
    )
    assert commit.status_code == 200, commit.text

    forgotten = client.post(
        f"/api/classes/{CLASS_ID}/ingest/sessions/{session_id}/chat/stream",
        json={
            "message": FCKW_FORGOTTEN_MESSAGE,
            "diary_markdown": review_diary,
        },
    )
    assert forgotten.status_code == 200, forgotten.text
    amended_diary = _final_diary_from_stream_response(forgotten)
    assert "encouraging students to participate" in amended_diary

    repropose = client.post(f"/api/classes/{CLASS_ID}/ingest/sessions/{session_id}/propose")
    assert repropose.status_code == 200, repropose.text
    recommit = client.post(
        f"/api/classes/{CLASS_ID}/ingest/commit",
        json={
            "session_id": session_id,
            "diary_markdown": amended_diary,
            "approved_updates": _approved_updates(repropose.json()["wiki_proposals"]),
        },
    )
    assert recommit.status_code == 200, recommit.text

    lesson_results = wiki.read_text(
        wiki.lesson_dir(CLASS_ID, "2026-07-02") / "lesson_results.md"
    )
    misconceptions = wiki.read_text(wiki.roll_up_paths(CLASS_ID)["misconceptions"])
    open_loops = wiki.read_text(wiki.roll_up_paths(CLASS_ID)["open_loops"])

    assert "encouraging students to participate" in lesson_results
    assert misconceptions.count("## 2026-07-02") == 1
    assert open_loops.count("## 2026-07-02") == 1
