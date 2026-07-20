"""Smoke test for the lesson-plan flow: start -> chat -> save.

This is the flow that produced the original ``API 500: 'title'`` bug; the test
pins that a chat turn renders prompts and returns a draft without error.
Runs fully offline against the stub agent + a tmp copy of the seed wiki.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import CLASS_ID


def test_new_plan_session_starts_with_an_empty_artifact(client: TestClient):
    base = f"/api/classes/{CLASS_ID}/plan"
    session_id = client.post(f"{base}/sessions").json()["session_id"]

    draft = client.get(f"{base}/sessions/{session_id}/draft")

    assert draft.status_code == 200, draft.text
    assert draft.json()["plan_markdown"] == ""


def test_plan_full_flow(client: TestClient):
    base = f"/api/classes/{CLASS_ID}/plan"

    start = client.post(f"{base}/sessions")
    assert start.status_code == 200, start.text
    start_body = start.json()
    session_id = start_body["session_id"]
    assert start_body["opening_message"] == ""

    chat = client.post(
        f"{base}/sessions/{session_id}/chat",
        json={"message": "Plan a 45 min lesson on stoichiometry."},
    )
    assert chat.status_code == 200, chat.text
    chat_body = chat.json()
    assert chat_body["reply"]
    assert chat_body["plan_markdown"]
    assert "lesson_artifact" not in chat_body
    assert chat_body["ready_to_save"] is True

    save = client.post(
        f"{base}/save",
        json={
            "session_id": session_id,
            "lesson_date": "2026-10-05",
            "plan_markdown": chat_body["plan_markdown"],
        },
    )
    assert save.status_code == 200, save.text
    save_body = save.json()
    assert save_body["plan_path"]
    assert save_body["lesson_date"] == "2026-10-05"
    assert save_body["session_state"]
    assert save_body["lesson_planning_state"]
    assert save_body["memory_candidates"]
    assert save_body["memory_candidates"][0]["candidate_id"]


def test_plan_chat_unknown_session_returns_typed_404(client: TestClient):
    res = client.post(
        f"/api/classes/{CLASS_ID}/plan/sessions/nope/chat",
        json={"message": "hi"},
    )
    assert res.status_code == 404
    body = res.json()
    assert body["error"]["type"] == "http_error"
    assert "Unknown session" in body["error"]["message"]


def test_blocking_executive_finding_prevents_plan_readiness(client: TestClient):
    base = f"/api/classes/{CLASS_ID}/plan"
    session_id = client.post(f"{base}/sessions").json()["session_id"]

    chat = client.post(
        f"{base}/sessions/{session_id}/chat",
        json={"message": "Plan this for student S-999."},
    )

    assert chat.status_code == 200, chat.text
    assert chat.json()["ready_to_save"] is False
    assert chat.json()["executive_state"]["status"] == "needs_decision"
    assert chat.json()["executive_state"]["open_findings"][0]["category"] == "identity"


def test_advisory_executive_finding_does_not_block_plan(client: TestClient):
    base = f"/api/classes/{CLASS_ID}/plan"
    session_id = client.post(f"{base}/sessions").json()["session_id"]

    chat = client.post(
        f"{base}/sessions/{session_id}/chat",
        json={"message": "Start the new organic chemistry unit after redox."},
    )

    assert chat.status_code == 200, chat.text
    assert chat.json()["ready_to_save"] is True
    assert chat.json()["executive_state"]["status"] == "advisory"


def test_plan_chat_returns_deterministic_verification_report(client: TestClient):
    base = f"/api/classes/{CLASS_ID}/plan"
    session_id = client.post(f"{base}/sessions").json()["session_id"]

    chat = client.post(
        f"{base}/sessions/{session_id}/chat",
        json={"message": "Plan the next lesson."},
    )

    assert chat.status_code == 200, chat.text
    report = chat.json()["executive_state"]["verification_reports"]["plan"]
    assert report["pack_id"] == "plan"
    assert {row["row_id"] for row in report["rows"]} == {
        "markdown_package",
        "source_provenance",
        "duration",
    }
    draft = client.get(f"{base}/sessions/{session_id}/draft")
    assert draft.status_code == 200
    assert draft.json()["executive_state"]["verification_reports"]["plan"]["pack_id"] == "plan"


def test_blocking_finding_keeps_ready_flag_false_without_status_downgrade(
    client: TestClient,
):
    base = f"/api/classes/{CLASS_ID}/plan"
    session_id = client.post(f"{base}/sessions").json()["session_id"]
    first = client.post(
        f"{base}/sessions/{session_id}/chat",
        json={"message": "Plan the next lesson."},
    )
    assert first.json()["ready_to_save"] is True

    second = client.post(
        f"{base}/sessions/{session_id}/chat",
        json={"message": "Add a note for student S-999."},
    )
    assert second.json()["ready_to_save"] is False

    trace = client.get(f"{base}/sessions/{session_id}/trace")
    assert trace.status_code == 200
    # Main's draft UX only upgrades to ready; it does not downgrade status when
    # executive findings later clear ready_to_save on the turn response.
    assert trace.json()["status"] == "ready_to_save"


def test_plan_save_rejects_invalid_lesson_date(client: TestClient):
    base = f"/api/classes/{CLASS_ID}/plan"
    start = client.post(f"{base}/sessions")
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]

    save = client.post(
        f"{base}/save",
        json={
            "session_id": session_id,
            "lesson_date": "../bad",
            "plan_markdown": "# Lesson Plan\n\n## Learning goals\n\n## Lesson flow\n\n## Warmup\n",
        },
    )

    assert save.status_code == 422
    assert "lesson_date must be YYYY-MM-DD" in save.text


def test_plan_save_manual_unknown_student_returns_409_without_write(client: TestClient):
    base = f"/api/classes/{CLASS_ID}/plan"
    session_id = client.post(f"{base}/sessions").json()["session_id"]
    chat = client.post(
        f"{base}/sessions/{session_id}/chat",
        json={"message": "Plan the next lesson."},
    )
    edited = chat.json()["plan_markdown"] + "\nStudent note: S-999 needs support.\n"

    save = client.post(
        f"{base}/save",
        json={
            "session_id": session_id,
            "lesson_date": "2026-10-05",
            "plan_markdown": edited,
        },
    )

    assert save.status_code == 409, save.text
    body = save.json()
    assert body["code"] == "write_verification_blocked"
    assert body["action"] == "plan_save"
    assert "S-999" in body["message"]

    saved = client.get(
        f"/api/classes/{CLASS_ID}/wiki/file",
        params={
            "path": f"wiki/classes/{CLASS_ID}/lessons/2026-10-05/lesson_plan.md"
        },
    )
    assert saved.status_code == 404


def test_plan_save_accepts_markdown_only_audience_sections_with_exit_ticket(
    client: TestClient,
):
    """A valid Markdown-first package must not be rejected after a clear check."""
    base = f"/api/classes/{CLASS_ID}/plan"
    session_id = client.post(f"{base}/sessions").json()["session_id"]
    markdown = """# Lesson Plan — Carbon Bonding

## Teacher

Use a particle-model drawing before introducing formal notation. Start with a
short bridge from electron transfer to electron sharing, then model methane.

## Student

Draw methane, ethane, ethene, and ethyne. Count the bonds around each carbon
and explain to a partner how sharing differs from transfer.

## Observation

Listen for students who confuse ion charge with bond order. Collect one shared
piece of evidence during the molecule-drawing task before students leave.

### Exit ticket

In two sentences, explain why carbon can form four bonds and how electron
sharing differs from redox electron transfer.
"""

    save = client.post(
        f"{base}/save",
        json={
            "session_id": session_id,
            "lesson_date": "2026-10-06",
            "plan_markdown": markdown,
        },
    )

    assert save.status_code == 200, save.text
    assert save.json()["lesson_date"] == "2026-10-06"


def test_plan_save_accepts_teacher_authored_markdown_without_heading_contract(
    client: TestClient,
):
    """A teacher can save a deliberate format variation after a clear safety check."""
    base = f"/api/classes/{CLASS_ID}/plan"
    session_id = client.post(f"{base}/sessions").json()["session_id"]
    markdown = """Carbon bonding lesson — teacher working format

Begin with a five-minute redox recall, then have pairs sketch methane, ethane,
ethene, and ethyne. Ask every pair to compare electron transfer in redox with
electron sharing in covalent bonds. Keep hybridization as a brief geometry
intuition only. Collect each student's written answer to decide whether the
next lesson needs another visual model before structural-formula practice.
"""

    save = client.post(
        f"{base}/save",
        json={
            "session_id": session_id,
            "lesson_date": "2026-10-07",
            "plan_markdown": markdown,
        },
    )

    assert save.status_code == 200, save.text
    assert save.json()["lesson_date"] == "2026-10-07"


def test_plan_save_rejects_empty_markdown_before_verification(client: TestClient):
    base = f"/api/classes/{CLASS_ID}/plan"
    session_id = client.post(f"{base}/sessions").json()["session_id"]

    save = client.post(
        f"{base}/save",
        json={
            "session_id": session_id,
            "lesson_date": "2026-10-08",
            "plan_markdown": " \n\t ",
        },
    )

    assert save.status_code == 422
    assert "plan_markdown must not be empty" in save.text


def test_profile_proposal_normalizes_human_label_targets(
    client: TestClient, agents
):
    from app.teacher_agent.models import ProfileCandidateOut, ProfileProposalOutput

    async def propose_profile_updates(*args, **kwargs):
        return ProfileProposalOutput(
            copilot_candidates=[
                ProfileCandidateOut(
                    target="Planning Patterns",
                    section="Avoid",
                    content="Avoid rote memorization as the main strategy.",
                    basis="explicit",
                    confidence="high",
                    evidence="Teacher corrected the planning style.",
                )
            ],
            warnings=[],
        )

    agents.propose_profile_updates = propose_profile_updates

    res = client.post(
        f"/api/classes/{CLASS_ID}/memory/profile/propose",
        json={
            "final_lesson_markdown": "# Lesson Plan\n",
            "session_state": {},
            "lesson_planning_state": {},
            "memory_candidates": [],
        },
    )

    assert res.status_code == 200, res.text
    candidate = res.json()["candidates"][0]
    assert candidate["target"] == "copilot_profile.md"
    assert candidate["section"] == "Avoid"
