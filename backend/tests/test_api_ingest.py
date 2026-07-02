"""Smoke test for the ingest (update-memory) flow: start -> chat -> propose -> commit.

Runs fully offline against the stub agent + a tmp copy of the seed wiki.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.schemas.api import ApprovedWikiUpdate, CommitIngestRequest
from app.services.ingest_service import IngestService
from app.teacher_agent.wiki_store import WikiStore
from tests.conftest import CLASS_ID, COMPLETE_DIARY, READY_PLAN
from tests.conftest import StubAgentRunner


def test_ingest_full_flow(client: TestClient):
    base = f"/api/classes/{CLASS_ID}/ingest"

    start = client.post(f"{base}/sessions")
    assert start.status_code == 200, start.text
    start_body = start.json()
    session_id = start_body["session_id"]
    assert start_body["memory_state"]["phase"] == "identify_target"
    assert start_body["memory_state"]["target"]["target_confirmed"] is False

    chat = client.post(
        f"{base}/sessions/{session_id}/chat",
        json={"message": "We covered Topic A today."},
    )
    assert chat.status_code == 200, chat.text
    chat_body = chat.json()
    assert chat_body["reply"]
    assert chat_body["diary_markdown"]
    assert chat_body["ready_to_propose"] is True
    assert chat_body["last_change_summary"] == "Updated lesson results."
    assert chat_body["memory_state"]["target"]["lesson_date"] == "2026-10-01"
    assert chat_body["memory_state"]["target"]["target_confirmed"] is True
    assert chat_body["memory_candidates"]
    assert chat_body["memory_candidates"][0]["target"] == "teaching_patterns.md"

    propose = client.post(f"{base}/sessions/{session_id}/propose")
    assert propose.status_code == 200, propose.text
    propose_body = propose.json()
    assert propose_body["memory_state"]["intent"] == "log_new_results"
    assert propose_body["memory_candidates"]
    proposals = propose_body["wiki_proposals"]
    assert len(proposals) > 0

    approved = [
        {"wiki_path": p["wiki_path"], "content": p["proposed_content"], "approved": True}
        for p in proposals
    ]
    commit = client.post(
        f"/api/classes/{CLASS_ID}/ingest/commit",
        json={
            "session_id": session_id,
            "diary_markdown": chat_body["diary_markdown"],
            "approved_updates": approved,
        },
    )
    assert commit.status_code == 200, commit.text
    commit_body = commit.json()
    assert commit_body["applied_wiki_paths"]
    assert commit_body["log_entry_id"]
    proposal = commit_body["class_memory_proposal"]
    assert proposal["class_id"] == CLASS_ID
    assert "class_state" in proposal["pages"]
    assert "teaching_patterns" in proposal["pages"]
    assert "Peer checking helps reduce balancing errors." in proposal["pages"]["teaching_patterns"]
    assert f"wiki/classes/{CLASS_ID}/memory/class_state.md" not in commit_body["applied_wiki_paths"]

    class_state = client.get(
        f"/api/classes/{CLASS_ID}/wiki/file",
        params={"path": f"wiki/classes/{CLASS_ID}/memory/class_state.md"},
    )
    assert class_state.status_code == 404

    apply_compact = client.post(
        f"/api/classes/{CLASS_ID}/memory/compact/apply",
        json={
            "pages": {
                "class_state": proposal["pages"]["class_state"],
                "teaching_patterns": proposal["pages"]["teaching_patterns"],
            },
            "source_paths": proposal["source_paths"],
        },
    )
    assert apply_compact.status_code == 200, apply_compact.text
    apply_body = apply_compact.json()
    assert f"wiki/classes/{CLASS_ID}/memory/class_state.md" in apply_body["applied_wiki_paths"]
    assert f"wiki/classes/{CLASS_ID}/memory/teaching_patterns.md" in apply_body["applied_wiki_paths"]

    class_state = client.get(
        f"/api/classes/{CLASS_ID}/wiki/file",
        params={"path": f"wiki/classes/{CLASS_ID}/memory/class_state.md"},
    )
    assert class_state.status_code == 200
    assert "Current unit: redox" in class_state.json()["markdown"]


def test_compact_memory_apply_rejects_non_compact_memory_pages(client: TestClient):
    res = client.post(
        f"/api/classes/{CLASS_ID}/memory/compact/apply",
        json={"pages": {"canonical_wiki": "# Unsafe"}, "source_paths": []},
    )
    assert res.status_code == 400
    assert "Unsupported compact memory page" in res.json()["error"]["message"]


def test_ingest_start_accepts_empty_body(client: TestClient):
    base = f"/api/classes/{CLASS_ID}/ingest"

    start = client.post(f"{base}/sessions", json=None)
    assert start.status_code == 200, start.text
    body = start.json()
    assert body["memory_state"]["phase"] == "identify_target"
    assert body["memory_state"]["target"]["target_confirmed"] is False


def test_ingest_start_hint_loads_existing_lesson_results(client: TestClient):
    base = f"/api/classes/{CLASS_ID}/ingest"

    start = client.post(
        f"{base}/sessions",
        json={
            "lesson_date": "2026-05-29",
            "intent": "correct_existing_results",
            "target_kind": "taught_lesson",
            "source": "timeline_hint",
        },
    )
    assert start.status_code == 200, start.text
    body = start.json()
    session_id = body["session_id"]
    memory = body["memory_state"]

    assert memory["phase"] == "collect_results"
    assert memory["intent"] == "correct_existing_results"
    assert memory["target"]["lesson_date"] == "2026-05-29"
    assert memory["target"]["target_kind"] == "taught_lesson"
    assert memory["target"]["target_confirmed"] is True
    assert memory["target"]["source"] == "timeline_hint"
    assert memory["target"]["plan_loaded"] is True
    assert memory["target"]["existing_results_loaded"] is True

    draft = client.get(f"{base}/sessions/{session_id}/draft")
    assert draft.status_code == 200, draft.text
    draft_body = draft.json()
    assert "Lesson Results" in draft_body["diary_markdown"]
    assert "2026-05-29" in draft_body["diary_markdown"]
    assert "Anions and Oxidation State Review" in draft_body["diary_markdown"]
    assert draft_body["memory_state"]["target"]["lesson_date"] == "2026-05-29"


def test_ingest_start_hint_loads_known_planned_lesson(client: TestClient):
    ingest_base = f"/api/classes/{CLASS_ID}/ingest"
    plan_base = f"/api/classes/{CLASS_ID}/plan"
    lesson_date = "2027-01-16"

    plan_start = client.post(f"{plan_base}/sessions")
    assert plan_start.status_code == 200, plan_start.text
    save = client.post(
        f"{plan_base}/save",
        json={
            "session_id": plan_start.json()["session_id"],
            "lesson_date": lesson_date,
            "plan_markdown": READY_PLAN,
        },
    )
    assert save.status_code == 200, save.text

    start = client.post(
        f"{ingest_base}/sessions",
        json={
            "lesson_date": lesson_date,
            "intent": "update_missing_results",
            "target_kind": "planned_lesson",
            "source": "timeline_hint",
        },
    )
    assert start.status_code == 200, start.text
    body = start.json()
    memory = body["memory_state"]

    assert memory["phase"] == "collect_results"
    assert memory["intent"] == "update_missing_results"
    assert memory["target"]["lesson_date"] == lesson_date
    assert memory["target"]["target_kind"] == "planned_lesson"
    assert memory["target"]["target_confirmed"] is True
    assert memory["target"]["confidence"] == "high"
    assert memory["target"]["plan_loaded"] is True
    assert memory["target"]["existing_results_loaded"] is False

    draft = client.get(f"{ingest_base}/sessions/{body['session_id']}/draft")
    assert draft.status_code == 200, draft.text
    assert lesson_date in draft.json()["diary_markdown"]
    assert "Stub Plan" in draft.json()["diary_markdown"]


def test_ingest_unknown_start_hint_needs_confirmation(client: TestClient):
    base = f"/api/classes/{CLASS_ID}/ingest"

    start = client.post(
        f"{base}/sessions",
        json={
            "lesson_date": "2027-01-15",
            "lesson_title": "Untracked lesson",
            "intent": "update_missing_results",
            "target_kind": "planned_lesson",
            "source": "timeline_hint",
        },
    )
    assert start.status_code == 200, start.text
    memory = start.json()["memory_state"]

    assert memory["phase"] == "identify_target"
    assert memory["intent"] == "update_missing_results"
    assert memory["target"]["lesson_date"] == "2027-01-15"
    assert memory["target"]["lesson_title"] == "Untracked lesson"
    assert memory["target"]["target_kind"] == "planned_lesson"
    assert memory["target"]["target_confirmed"] is False
    assert memory["target"]["confidence"] == "low"
    assert memory["target"]["needs_confirmation"] is True
    assert memory["target"]["plan_loaded"] is False
    assert memory["target"]["existing_results_loaded"] is False
    assert memory["session_state"]["open_questions"]


def test_ingest_start_hint_rejects_invalid_enum_values(client: TestClient):
    base = f"/api/classes/{CLASS_ID}/ingest"

    start = client.post(
        f"{base}/sessions",
        json={
            "lesson_date": "2026-05-29",
            "intent": "rewrite_everything",
            "target_kind": "lessonish",
            "source": "timeline_hint",
        },
    )
    assert start.status_code == 422
    assert start.json()["error"]["type"] == "validation_error"


def test_ingest_commit_skips_unapproved_wiki_paths(client: TestClient):
    """Phase 5 trust: unchecked proposals must not be written via the HTTP commit path."""
    base = f"/api/classes/{CLASS_ID}/ingest"
    wiki_base = f"/api/classes/{CLASS_ID}/wiki/file"

    start = client.post(f"{base}/sessions")
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    patch = client.patch(
        f"{base}/sessions/{session_id}/draft",
        json={"diary_markdown": COMPLETE_DIARY},
    )
    assert patch.status_code == 200

    propose = client.post(f"{base}/sessions/{session_id}/propose")
    assert propose.status_code == 200
    proposals = propose.json()["wiki_proposals"]
    lesson_prop = next(p for p in proposals if "lesson_results.md" in p["wiki_path"])
    student_prop = next(p for p in proposals if "students/S-014.md" in p["wiki_path"])

    before = client.get(wiki_base, params={"path": student_prop["wiki_path"]})
    assert before.status_code == 200
    before_md = before.json()["markdown"]

    commit = client.post(
        f"/api/classes/{CLASS_ID}/ingest/commit",
        json={
            "session_id": session_id,
            "diary_markdown": COMPLETE_DIARY,
            "approved_updates": [
                {
                    "wiki_path": lesson_prop["wiki_path"],
                    "content": lesson_prop["proposed_content"],
                    "approved": True,
                },
                {
                    "wiki_path": student_prop["wiki_path"],
                    "content": student_prop["proposed_content"],
                    "approved": False,
                },
            ],
        },
    )
    assert commit.status_code == 200, commit.text
    applied = commit.json()["applied_wiki_paths"]
    assert student_prop["wiki_path"] not in applied
    assert any("lesson_results.md" in p for p in applied)

    after = client.get(wiki_base, params={"path": student_prop["wiki_path"]})
    assert after.status_code == 200
    assert after.json()["markdown"] == before_md
    assert "## 2026-10-01" not in after.json()["markdown"]


def test_ingest_commit_writes_teacher_edited_content(client: TestClient):
    """Commit payload content (not just propose output) is what gets written."""
    base = f"/api/classes/{CLASS_ID}/ingest"
    wiki_base = f"/api/classes/{CLASS_ID}/wiki/file"
    marker = "TEACHER_EDIT_VIA_API"

    start = client.post(f"{base}/sessions")
    session_id = start.json()["session_id"]
    client.patch(
        f"{base}/sessions/{session_id}/draft",
        json={"diary_markdown": COMPLETE_DIARY},
    )
    propose = client.post(f"{base}/sessions/{session_id}/propose")
    lesson_prop = next(
        p for p in propose.json()["wiki_proposals"] if "lesson_results.md" in p["wiki_path"]
    )
    edited = lesson_prop["proposed_content"].replace("Topic A", f"Topic A ({marker})")

    commit = client.post(
        f"/api/classes/{CLASS_ID}/ingest/commit",
        json={
            "session_id": session_id,
            "diary_markdown": COMPLETE_DIARY,
            "approved_updates": [
                {
                    "wiki_path": lesson_prop["wiki_path"],
                    "content": edited,
                    "approved": True,
                },
            ],
        },
    )
    assert commit.status_code == 200, commit.text

    file_res = client.get(wiki_base, params={"path": lesson_prop["wiki_path"]})
    assert file_res.status_code == 200
    assert marker in file_res.json()["markdown"]


def test_ingest_commit_requires_lesson_results_approved(client: TestClient):
    base = f"/api/classes/{CLASS_ID}/ingest"

    start = client.post(f"{base}/sessions")
    session_id = start.json()["session_id"]
    client.patch(
        f"{base}/sessions/{session_id}/draft",
        json={"diary_markdown": COMPLETE_DIARY},
    )
    propose = client.post(f"{base}/sessions/{session_id}/propose")
    timeline_prop = next(
        p for p in propose.json()["wiki_proposals"] if p["wiki_path"].endswith("timeline.md")
    )

    commit = client.post(
        f"/api/classes/{CLASS_ID}/ingest/commit",
        json={
            "session_id": session_id,
            "diary_markdown": COMPLETE_DIARY,
            "approved_updates": [
                {
                    "wiki_path": timeline_prop["wiki_path"],
                    "content": timeline_prop["proposed_content"],
                    "approved": True,
                },
            ],
        },
    )
    assert commit.status_code == 400
    assert "lesson_results" in commit.json()["error"]["message"]


def test_ingest_chat_unknown_session_returns_typed_404(client: TestClient):
    res = client.post(
        f"/api/classes/{CLASS_ID}/ingest/sessions/does-not-exist/chat",
        json={"message": "hi"},
    )
    assert res.status_code == 404
    body = res.json()
    assert body["error"]["type"] == "http_error"
    assert "Unknown session" in body["error"]["message"]


def test_validation_error_returns_typed_envelope(client: TestClient):
    start = client.post(f"/api/classes/{CLASS_ID}/ingest/sessions")
    session_id = start.json()["session_id"]
    # Missing required `message` field -> 422 via the validation handler.
    res = client.post(
        f"/api/classes/{CLASS_ID}/ingest/sessions/{session_id}/chat",
        json={},
    )
    assert res.status_code == 422
    assert res.json()["error"]["type"] == "validation_error"


@pytest.mark.anyio
async def test_ingest_commit_rejects_unfinished_streamed_turn(
    wiki: WikiStore,
    agents: StubAgentRunner,
):
    ingest = IngestService(wiki=wiki, agents=agents)
    session = await ingest.start_session(CLASS_ID)
    stream = ingest.chat_stream(session.session_id, "sorry, I forgot one more thing")

    first_line = await anext(stream)
    assert first_line.startswith("data:")
    await stream.aclose()

    _, proposals = wiki.compile_from_diary(CLASS_ID, COMPLETE_DIARY)
    approved = [
        ApprovedWikiUpdate(
            wiki_path=p.wiki_path,
            content=p.proposed_content,
            approved=True,
        )
        for p in proposals
    ]

    with pytest.raises(ValueError, match="latest chat turn"):
        ingest.commit(
            CommitIngestRequest(
                session_id=session.session_id,
                diary_markdown=COMPLETE_DIARY,
                approved_updates=approved,
            )
        )


@pytest.mark.anyio
async def test_ingest_allows_retry_after_unfinished_streamed_turn(
    wiki: WikiStore,
    agents: StubAgentRunner,
):
    ingest = IngestService(wiki=wiki, agents=agents)
    session = await ingest.start_session(CLASS_ID)
    stream = ingest.chat_stream(session.session_id, "sorry, I forgot one more thing")

    first_line = await anext(stream)
    assert first_line.startswith("data:")
    await stream.aclose()

    retry_events = [
        line
        async for line in ingest.chat_stream(
            session.session_id, "sorry, I forgot one more thing"
        )
    ]

    assert any('"type":"final"' in line for line in retry_events)
    _, proposals = wiki.compile_from_diary(CLASS_ID, COMPLETE_DIARY)
    approved = [
        ApprovedWikiUpdate(
            wiki_path=p.wiki_path,
            content=p.proposed_content,
            approved=True,
        )
        for p in proposals
    ]
    response = ingest.commit(
        CommitIngestRequest(
            session_id=session.session_id,
            diary_markdown=COMPLETE_DIARY,
            approved_updates=approved,
        )
    )
    assert response.applied_wiki_paths
