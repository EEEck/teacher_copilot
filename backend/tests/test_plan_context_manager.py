"""Tests for the lesson-planning runtime context manager (Phase 1).

Covers: structured-state round-trip + persistence, configurable verbatim-window
trimming, slim/deduped class slice under budget, evidence raw-store progressive
exposure, and memory candidates surfaced at save without any durable writes.
All offline against the stub agent + a tmp copy of the seed wiki.
"""

from __future__ import annotations

import json
import inspect
from pathlib import Path

from fastapi.testclient import TestClient

from app.api import deps
from app.main import app
from app.services.ingest_service import IngestService
from app.services.memory_candidate_ledger import (
    MemoryCandidateLedger,
    rows_from_runtime_candidates,
)
from app.services.plan_service import PlanService
from app.schemas.api import ChatMessage
from app.teacher_agent.agents import (
    AgentRunner,
    _strip_plan_debug_sections,
    _trim_to_last_user_turns,
)
from app.context_limits import get_context_limits
from app.teacher_agent.memory_capture import MemoryCandidate
from app.teacher_agent.prompt_assembly import build_ingest_user_input_assembly
from app.teacher_agent.planning_state import (
    EvidenceBrief,
    LessonPlanningState,
    LessonPlanningStatePatch,
    PlanRuntime,
    SessionState,
    SessionStatePatch,
    StatePatch,
    apply_plan_phase_auto_advance,
    merge_turn_into_runtime,
    render_briefs,
    render_session_state,
    teacher_signals_plan_finalize,
)
from app.teacher_agent.tools import _capture, lookup_raw_evidence
from app.teacher_agent.wiki import memory as wiki_memory
from app.teacher_agent.wiki_store import WikiStore
from tests.conftest import CLASS_ID, StubAgentRunner


def _parse_sse(body: str) -> list[dict]:
    events = []
    for block in body.split("\n\n"):
        for line in block.split("\n"):
            if line.startswith("data:"):
                events.append(json.loads(line[5:].strip()))
    return events


# --- state round-trip + persistence (API level) ----------------------------


def test_plan_chat_surfaces_phase_and_state(client: TestClient):
    base = f"/api/classes/{CLASS_ID}/plan"
    session_id = client.post(f"{base}/sessions").json()["session_id"]

    res = client.post(
        f"{base}/sessions/{session_id}/chat",
        json={"message": "Plan a 45 min lesson on redox."},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["phase"] == "lesson_refinement"
    assert body["session_state"]["phase"] == "lesson_refinement"
    assert body["lesson_planning_state"]["duration_minutes"] == 45
    assert body["memory_candidates"], "expected at least one memory candidate"


def test_memory_candidates_dedupe_across_turns(client: TestClient):
    base = f"/api/classes/{CLASS_ID}/plan"
    session_id = client.post(f"{base}/sessions").json()["session_id"]

    first = client.post(
        f"{base}/sessions/{session_id}/chat", json={"message": "Plan redox lesson."}
    ).json()
    second = client.post(
        f"{base}/sessions/{session_id}/chat", json={"message": "Refine it please."}
    ).json()

    # Stub proposes the same candidate each turn; it must not accumulate dupes.
    assert len(first["memory_candidates"]) == 1
    assert len(second["memory_candidates"]) == 1


def test_merge_turn_into_runtime_replaces_state_and_dedupes():
    rt = PlanRuntime()
    cand = MemoryCandidate(target="copilot.md", candidate_update="Draft early.")
    merge_turn_into_runtime(
        rt,
        session_state=SessionState(phase="lesson_refinement"),
        lesson_planning_state=LessonPlanningState(lesson_topic="Redox"),
        new_evidence_briefs=[EvidenceBrief(raw_ref="wiki_search_001", brief=["x"])],
        memory_candidates=[cand],
        last_change_summary="changed",
        plan_changed=True,
    )
    # Same candidate + a brief with the same raw_ref next turn → no growth.
    merge_turn_into_runtime(
        rt,
        session_state=SessionState(phase="finalize"),
        lesson_planning_state=LessonPlanningState(lesson_topic="Redox 2"),
        new_evidence_briefs=[EvidenceBrief(raw_ref="wiki_search_001", brief=["y"])],
        memory_candidates=[cand],
        last_change_summary="changed again",
        plan_changed=True,
    )
    assert rt.session_state.phase == "finalize"
    assert rt.lesson_planning_state.lesson_topic == "Redox 2"
    assert len(rt.memory_candidates) == 1
    assert len([b for b in rt.evidence_briefs if b.raw_ref == "wiki_search_001"]) == 1
    assert rt.plan_version == 2


def test_state_patch_updates_backend_owned_runtime():
    rt = PlanRuntime()
    merge_turn_into_runtime(
        rt,
        state_patch=StatePatch(
            session_state=SessionStatePatch(
                phase="lesson_refinement",
                decisions=["Use a structured recap."],
                open_questions=["Which CFC example?"],
            ),
            lesson_planning_state=LessonPlanningStatePatch(
                lesson_topic="FCKW redox",
                duration_minutes=45,
                constraints=["No real CFCs in the lab."],
            ),
        ),
        session_state=SessionState(),
        lesson_planning_state=LessonPlanningState(),
        new_evidence_briefs=[],
        memory_candidates=[],
        last_change_summary="patched",
        plan_changed=False,
    )

    assert rt.session_state.phase == "lesson_refinement"
    assert rt.session_state.decisions == ["Use a structured recap."]
    assert rt.session_state.open_questions == ["Which CFC example?"]
    assert rt.lesson_planning_state.lesson_topic == "FCKW redox"
    assert rt.lesson_planning_state.duration_minutes == 45
    assert rt.lesson_planning_state.constraints == ["No real CFCs in the lab."]


def test_state_patch_dedupes_lists_and_rejects_invalid_phase():
    rt = PlanRuntime()
    merge_turn_into_runtime(
        rt,
        state_patch=StatePatch(
            session_state=SessionStatePatch(
                phase="lesson_refinement", decisions=["Use recap."]
            ),
            lesson_planning_state=LessonPlanningStatePatch(
                accepted_plan_elements=["Exit ticket"]
            ),
        ),
        session_state=SessionState(),
        lesson_planning_state=LessonPlanningState(),
        new_evidence_briefs=[],
        memory_candidates=[],
        last_change_summary="",
        plan_changed=False,
    )
    merge_turn_into_runtime(
        rt,
        state_patch=StatePatch(
            session_state=SessionStatePatch(
                phase="not_a_phase", decisions=["Use recap.", "Add practice."]
            ),
            lesson_planning_state=LessonPlanningStatePatch(
                accepted_plan_elements=["Exit ticket", "Differentiated homework"]
            ),
        ),
        session_state=SessionState(),
        lesson_planning_state=LessonPlanningState(),
        new_evidence_briefs=[],
        memory_candidates=[],
        last_change_summary="",
        plan_changed=False,
    )

    assert rt.session_state.phase == "lesson_refinement"
    assert rt.session_state.decisions == ["Use recap.", "Add practice."]
    assert rt.lesson_planning_state.accepted_plan_elements == [
        "Exit ticket",
        "Differentiated homework",
    ]


def test_durable_preference_state_patch_promotes_memory_candidate():
    rt = PlanRuntime()
    teacher_message = (
        "From now on, please use MBB-style communication for plan summaries. "
        "This is a general communication preference, not just for this lesson."
    )
    merge_turn_into_runtime(
        rt,
        state_patch=StatePatch(
            session_state=SessionStatePatch(
                decisions=[
                    "Use MBB-style communication for future lesson-planning summaries."
                ],
            ),
            lesson_planning_state=LessonPlanningStatePatch(
                teacher_preferences_for_this_lesson=[
                    "Use MBB-style communication for future planning summaries."
                ],
            ),
        ),
        session_state=SessionState(),
        lesson_planning_state=LessonPlanningState(),
        new_evidence_briefs=[],
        memory_candidates=[],
        last_change_summary="Captured communication preference.",
        plan_changed=False,
        teacher_message=teacher_message,
    )

    assert len(rt.memory_candidates) == 1
    candidate = rt.memory_candidates[0]
    assert candidate.target == "teacher_profile.md"
    assert candidate.section == "Communication"
    assert candidate.source == "teacher_explicit"
    assert candidate.basis == "explicit"
    assert candidate.confidence == "high"
    assert "MBB-style communication" in candidate.candidate_update

    rows = rows_from_runtime_candidates(
        rt.memory_candidates,
        class_id=CLASS_ID,
        subject="chemie",
        workflow="plan",
        session_id="session-1",
        turn_index=2,
    )
    assert len(rows) == 1
    assert rows[0].class_id is None
    assert rows[0].channel == "teacher_behavior"
    assert rows[0].target == "teacher_profile.md"


def test_lesson_scoped_preference_state_patch_does_not_promote_memory_candidate():
    rt = PlanRuntime()
    merge_turn_into_runtime(
        rt,
        state_patch=StatePatch(
            lesson_planning_state=LessonPlanningStatePatch(
                teacher_preferences_for_this_lesson=[
                    "Use a quieter individual worksheet phase today."
                ],
            ),
        ),
        session_state=SessionState(),
        lesson_planning_state=LessonPlanningState(),
        new_evidence_briefs=[],
        memory_candidates=[],
        last_change_summary="Captured lesson preference.",
        plan_changed=False,
        teacher_message="For today's redox lesson, use a quieter worksheet phase.",
    )

    assert rt.memory_candidates == []


def test_existing_explicit_user_candidate_prevents_state_repair_duplicate():
    rt = PlanRuntime()
    existing = MemoryCandidate(
        target="user.md",
        section="Communication",
        candidate_update=(
            "Use MBB-style communication in all lesson-planning summaries: "
            "recommendation, reasons, next steps."
        ),
        source="teacher_explicit",
        basis="explicit",
        confidence="high",
    )
    merge_turn_into_runtime(
        rt,
        state_patch=StatePatch(),
        session_state=SessionState(),
        lesson_planning_state=LessonPlanningState(),
        new_evidence_briefs=[],
        memory_candidates=[existing],
        last_change_summary="Captured preference.",
        plan_changed=False,
    )
    merge_turn_into_runtime(
        rt,
        state_patch=StatePatch(
            lesson_planning_state=LessonPlanningStatePatch(
                teacher_preferences_for_this_lesson=[
                    "Use MBB-style communication for future planning summaries."
                ],
            ),
        ),
        session_state=SessionState(),
        lesson_planning_state=LessonPlanningState(),
        new_evidence_briefs=[],
        memory_candidates=[],
        last_change_summary="Retained preference in state.",
        plan_changed=False,
        teacher_message=(
            "From now on, for all lesson-planning summaries, use MBB-style "
            "communication. This is a general communication preference."
        ),
    )

    assert rt.memory_candidates == [existing]


def test_plan_chat_repairs_state_only_preference_to_api_and_ledger(
    tmp_path: Path,
    wiki: WikiStore,
):
    class StateOnlyPreferenceRunner(StubAgentRunner):
        def _emit_plan_state(
            self,
            planning: PlanRuntime,
            messages: list[ChatMessage],
            plan_md: str,
            partial_plan: str,
            *,
            phase: str = "lesson_refinement",
        ) -> None:
            latest = messages[-1].content if messages else ""
            merge_turn_into_runtime(
                planning,
                state_patch=StatePatch(
                    session_state=SessionStatePatch(
                        phase=phase,
                        teacher_goal=latest[:80],
                        decisions=[
                            "Use MBB-style communication for future lesson-planning summaries."
                        ],
                    ),
                    lesson_planning_state=LessonPlanningStatePatch(
                        lesson_topic="FCKW redox",
                        duration_minutes=45,
                        teacher_preferences_for_this_lesson=[
                            "Use MBB-style communication for future planning summaries."
                        ],
                    ),
                ),
                session_state=SessionState(),
                lesson_planning_state=LessonPlanningState(),
                new_evidence_briefs=[],
                memory_candidates=[],
                last_change_summary="Captured communication preference in state.",
                plan_changed=plan_md.strip() != (partial_plan or "").strip(),
                teacher_message=latest,
            )
            planning.session_state.phase = phase

    before = {path: wiki.read_text(path) for path in _profile_paths(wiki)}
    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    agents = StateOnlyPreferenceRunner(wiki)
    ingest = IngestService(
        wiki=wiki,
        agents=agents,
        memory_candidate_ledger=ledger,
    )
    plan = PlanService(
        wiki=wiki,
        agents=agents,
        memory_candidate_ledger=ledger,
    )

    app.dependency_overrides[deps.get_wiki] = lambda: wiki
    app.dependency_overrides[deps.get_agents] = lambda: agents
    app.dependency_overrides[deps.get_memory_candidate_ledger] = lambda: ledger
    app.dependency_overrides[deps.get_ingest_service] = lambda: ingest
    app.dependency_overrides[deps.get_plan_service] = lambda: plan
    try:
        with TestClient(app, raise_server_exceptions=False) as local_client:
            base = f"/api/classes/{CLASS_ID}/plan"
            session_id = local_client.post(f"{base}/sessions").json()["session_id"]
            chat = local_client.post(
                f"{base}/sessions/{session_id}/chat",
                json={
                    "message": (
                        "Please plan FCKW redox. From now on, for all "
                        "lesson-planning summaries, use MBB-style communication. "
                        "This is a general communication preference, not just this lesson."
                    )
                },
            )
            stream_session_id = local_client.post(f"{base}/sessions").json()[
                "session_id"
            ]
            stream = local_client.post(
                f"{base}/sessions/{stream_session_id}/chat/stream",
                json={
                    "message": (
                        "Please plan FCKW redox. From now on, for all "
                        "lesson-planning summaries, use MBB-style communication. "
                        "This is a general communication preference, not just this lesson."
                    )
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert chat.status_code == 200, chat.text
    body = chat.json()
    assert len(body["memory_candidates"]) == 1
    candidate = body["memory_candidates"][0]
    assert candidate["target"] == "teacher_profile.md"
    assert candidate["section"] == "Communication"
    assert candidate["basis"] == "explicit"
    assert candidate["confidence"] == "high"
    assert "MBB-style communication" in candidate["candidate_update"]

    assert stream.status_code == 200, stream.text
    stream_final = [event for event in _parse_sse(stream.text) if event["type"] == "final"][
        -1
    ]
    stream_candidate = stream_final["memory_candidates"][0]
    assert stream_candidate["target"] == "teacher_profile.md"
    assert stream_candidate["section"] == "Communication"
    assert "MBB-style communication" in stream_candidate["candidate_update"]

    rows = ledger.list_candidates(class_id=CLASS_ID)
    assert len(rows) == 2
    assert {row.session_id for row in rows} == {session_id, stream_session_id}
    assert all(row.class_id is None for row in rows)
    assert all(row.channel == "teacher_behavior" for row in rows)
    assert all(row.target == "teacher_profile.md" for row in rows)
    assert {path: wiki.read_text(path) for path in _profile_paths(wiki)} == before


def test_plan_finalize_signal_requires_acceptance_or_direct_save_intent():
    assert teacher_signals_plan_finalize(
        "I am very happy with it. Maybe as a last refinement, add active recall."
    )
    assert teacher_signals_plan_finalize("Looks good, ready to save.")
    assert not teacher_signals_plan_finalize("Can we revise the warmup?")
    assert not teacher_signals_plan_finalize("I am not happy with this yet.")


def test_plan_auto_advance_finalizes_ready_plan_after_last_refinement():
    rt = PlanRuntime()
    rt.session_state.phase = "lesson_refinement"
    rt.session_state.open_questions = ["Which exact opener?"]
    rt.lesson_planning_state.needs_revision = ["Tighten the opening."]

    apply_plan_phase_auto_advance(
        rt,
        teacher_message=(
            "I am very happy with it. Maybe as a last refinement, "
            "add only a 2 min recap."
        ),
        plan_ready=True,
    )

    assert rt.session_state.phase == "finalize"
    assert rt.session_state.open_questions == []
    assert rt.lesson_planning_state.needs_revision == []
    assert rt.session_state.agent_next_step == (
        "Present the finalized lesson plan for teacher review."
    )


def test_merge_turn_auto_advance_finalizes_ready_plan():
    rt = PlanRuntime()
    merge_turn_into_runtime(
        rt,
        state_patch=StatePatch(
            session_state=SessionStatePatch(phase="lesson_refinement")
        ),
        session_state=SessionState(),
        lesson_planning_state=LessonPlanningState(),
        new_evidence_briefs=[],
        memory_candidates=[],
        last_change_summary="Final tweak applied.",
        plan_changed=True,
        teacher_message=(
            "I am very happy with it. Maybe as a last refinement, "
            "add active recall."
        ),
        plan_ready=True,
    )

    assert rt.session_state.phase == "finalize"
    assert rt.lesson_planning_state.needs_revision == []


# --- verbatim-window trimming ----------------------------------------------


def _msg(role: str, content: str) -> ChatMessage:
    return ChatMessage(role=role, content=content)


def test_trim_to_last_user_turns_keeps_window():
    msgs = []
    for i in range(6):
        msgs.append(_msg("user", f"u{i}"))
        msgs.append(_msg("assistant", f"a{i}"))
    trimmed = _trim_to_last_user_turns(msgs, 2)
    users = [m.content for m in trimmed if m.role == "user"]
    assert users == ["u4", "u5"]
    # Starts on the earliest kept user turn.
    assert trimmed[0].content == "u4"


def test_trim_to_last_user_turns_handles_short_history():
    msgs = [_msg("user", "only")]
    assert _trim_to_last_user_turns(msgs, 8) == msgs


def test_ingest_user_input_trims_to_last_user_turns():
    msgs = []
    for i in range(10):
        msgs.append(_msg("user", f"old-or-new-user-{i}"))
        msgs.append(_msg("assistant", f"assistant-{i}"))
    out = build_ingest_user_input_assembly(
        msgs,
        "# Lesson Results\n\nDraft",
        history_turns=3,
    )

    assert "old-or-new-user-0" not in out["text"]
    assert "old-or-new-user-6" not in out["text"]
    assert "old-or-new-user-7" in out["text"]
    assert "old-or-new-user-9" in out["text"]
    assert out["sections"][-1]["source"] == "last 3 user turns"


def test_strip_plan_debug_sections_removes_evidence_briefs():
    plan = """# Lesson Plan

## Learning goals
- Goal

## Evidence briefs
- None yet.

## Homework
- Practice
"""
    cleaned = _strip_plan_debug_sections(plan)
    assert "## Evidence briefs" not in cleaned
    assert "## Learning goals" in cleaned
    assert "## Homework" in cleaned


def test_runner_readiness_does_not_parse_assistant_reply_text():
    source = "\n".join(
        [
            inspect.getsource(AgentRunner.plan_chat),
            inspect.getsource(AgentRunner.plan_chat_stream),
            inspect.getsource(AgentRunner.ingest_chat),
            inspect.getsource(AgentRunner.ingest_chat_stream),
        ]
    ).lower()
    assert "ready to save" not in source
    assert "reply.lower" not in source


# --- slim/deduped class slice under budget ----------------------------------


def test_build_plan_context_slim_dedup_and_budget(wiki: WikiStore):
    slim = wiki.build_plan_context_slim(CLASS_ID)
    # Compact: well under the blunt 14k clip the old pack tripped.
    assert len(slim) < 9000
    # Misconceptions header appears once (no 4x duplication).
    assert slim.count("## Top misconceptions") == 1
    assert "## Taught so far" in slim
    assert "Reaction Writing Basics" in slim


def test_build_plan_context_slim_clamps_oversized_pages(wiki: WikiStore):
    paths = wiki.memory_paths(CLASS_ID)
    big = "# Planning Brief\n\n" + ("- a very long planning note line\n" * 400)
    wiki.write_text(paths["planning_brief"], big)
    slim = wiki.build_plan_context_slim(CLASS_ID)
    budget = wiki_memory.memory_budget("planning_brief")
    # The injected planning-brief section is clamped, so the whole slice stays
    # bounded rather than dumping the oversized page.
    assert len(slim) < budget + 6000
    assert "trimmed to size budget" in slim


# --- evidence progressive exposure ------------------------------------------


def test_capture_and_lookup_raw_evidence_round_trip():
    rt = PlanRuntime()
    payload = '[{"path":"wiki/.../lesson_results.md"}]'
    tagged = _capture(rt, "wiki_search", payload)
    assert tagged.startswith("raw_ref: wiki_search_001")
    assert payload in tagged
    assert lookup_raw_evidence(rt, "wiki_search_001") == payload


def test_lookup_raw_evidence_unknown_ref():
    rt = PlanRuntime()
    out = lookup_raw_evidence(rt, "missing_999")
    assert out.startswith("Error: unknown raw_ref")


def test_briefs_render_without_raw_payload():
    rt = PlanRuntime()
    raw = "SECRET-RAW-PAYLOAD-CONTENT"
    ref = rt.next_raw_ref("wiki_search")
    rt.raw_store[ref] = raw
    rt.evidence_briefs.append(
        EvidenceBrief(
            type="wiki_search",
            purpose="prior redox",
            brief=["Redox covered 2026-05-25."],
            raw_ref=ref,
        )
    )
    rendered = render_briefs(rt.evidence_briefs)
    assert ref in rendered  # raw_ref is referenced
    assert raw not in rendered  # but raw payload is NOT injected


def test_render_session_state_includes_decisions():
    s = SessionState(phase="lesson_refinement", decisions=["Use Einstieg structure."])
    out = render_session_state(s)
    assert "lesson_refinement" in out
    assert "Use Einstieg structure." in out


# --- save surfaces candidates, writes nothing durable -----------------------


def _profile_paths(wiki: WikiStore) -> list[Path]:
    mem = wiki.memory_paths(CLASS_ID)
    return [mem["copilot_profile"], wiki_memory.user_profile_path(wiki)]


def test_save_surfaces_candidates_without_durable_writes(
    client: TestClient, wiki: WikiStore
):
    before = {p: wiki.read_text(p) for p in _profile_paths(wiki)}

    base = f"/api/classes/{CLASS_ID}/plan"
    session_id = client.post(f"{base}/sessions").json()["session_id"]
    chat = client.post(
        f"{base}/sessions/{session_id}/chat",
        json={"message": "Plan a redox lesson."},
    ).json()
    save = client.post(
        f"{base}/save",
        json={
            "session_id": session_id,
            "lesson_date": "2026-10-06",
            "plan_markdown": chat["plan_markdown"],
        },
    )
    assert save.status_code == 200, save.text
    assert save.json()["memory_candidates"], "candidates should surface at save"

    after = {p: wiki.read_text(p) for p in _profile_paths(wiki)}
    assert before == after, "planning save must not write durable memory"


def test_save_surfaces_backend_disciplined_fast_lane_candidate(
    client: TestClient,
):
    base = f"/api/classes/{CLASS_ID}/plan"
    session_id = client.post(f"{base}/sessions").json()["session_id"]
    chat = client.post(
        f"{base}/sessions/{session_id}/chat",
        json={
            "message": (
                "From now on, always draft early, then refine the markdown "
                "directly."
            )
        },
    ).json()
    save = client.post(
        f"{base}/save",
        json={
            "session_id": session_id,
            "lesson_date": "2026-10-06",
            "plan_markdown": chat["plan_markdown"],
        },
    )

    assert save.status_code == 200, save.text
    candidates = save.json()["memory_candidates"]
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["target"] == "copilot.md"
    assert candidate["source"] == "teacher_explicit"
    assert candidate["speech_act"] == "conduct_request"
    assert candidate["fast_lane"] is True
    assert candidate["candidate_id"]
    assert candidate["evidence"].startswith("Direct teacher quote:")


# --- robustness: state guard + soft caps ------------------------------------


def _merge(rt: PlanRuntime, session_state, lesson_state, *, candidates=None):
    merge_turn_into_runtime(
        rt,
        session_state=session_state,
        lesson_planning_state=lesson_state,
        new_evidence_briefs=[],
        memory_candidates=candidates or [],
        last_change_summary="",
        plan_changed=False,
    )


def test_empty_turn_does_not_wipe_persisted_state():
    rt = PlanRuntime()
    _merge(
        rt,
        SessionState(phase="lesson_refinement", decisions=["Use a demo Einstieg."]),
        LessonPlanningState(lesson_topic="Redox", duration_minutes=45),
    )
    # A later turn echoes the phase but drops the accumulator fields.
    _merge(rt, SessionState(phase="lesson_refinement"), LessonPlanningState())

    assert rt.session_state.decisions == ["Use a demo Einstieg."]
    assert rt.session_state.phase == "lesson_refinement"
    assert rt.lesson_planning_state.lesson_topic == "Redox"
    assert rt.lesson_planning_state.duration_minutes == 45


def test_state_updates_still_apply():
    rt = PlanRuntime()
    _merge(rt, SessionState(decisions=["A"]), LessonPlanningState(lesson_topic="Redox"))
    _merge(
        rt,
        SessionState(decisions=["A", "B"]),
        LessonPlanningState(lesson_topic="Säuren"),
    )
    assert rt.session_state.decisions == ["A", "B"]
    assert rt.lesson_planning_state.lesson_topic == "Säuren"


def test_memory_candidates_capped():
    cap = get_context_limits().candidates_cap
    rt = PlanRuntime()
    cands = [
        MemoryCandidate(target="class_state.md", candidate_update=f"fact {i}")
        for i in range(cap + 15)
    ]
    _merge(rt, SessionState(), LessonPlanningState(), candidates=cands)
    assert len(rt.memory_candidates) == cap


def test_raw_store_capped():
    cap = get_context_limits().raw_store_cap
    rt = PlanRuntime()
    refs = [rt.add_raw("wiki_search", f"payload {i}") for i in range(cap + 10)]
    assert len(rt.raw_store) == cap
    # Oldest pruned, newest retained.
    assert refs[-1] in rt.raw_store
    assert refs[0] not in rt.raw_store
