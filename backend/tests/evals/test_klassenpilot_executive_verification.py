"""Executive-verification evals for messy teacher input.

Default tests are deterministic coverage checks for the eval definitions. Live
model/API behavior is opt-in because it uses OpenAI calls.
"""

from __future__ import annotations

import json
import os

import pytest

from tests.evals.goldens.executive_verification import (
    CHEMIE_9B_CLASS_ID,
    EXECUTIVE_VERIFICATION_GOLDENS,
    ExecutiveVerificationGolden,
)
from tests.evals.goldens.wiki_input_reconciliation import student_ids_in


def test_executive_verification_goldens_cover_core_decisions():
    ids = {golden.golden_id for golden in EXECUTIVE_VERIFICATION_GOLDENS}

    assert "memory_date_and_student_mismatch_blocks_then_resolves" in ids
    assert "memory_wrong_subject_context_blocks_artifact" in ids
    assert "memory_valid_messy_input_proceeds" in ids


def test_eval_wiki_supports_organic_mismatch_scenario(eval_wiki):
    roster_text = eval_wiki.read_text(
        eval_wiki.roll_up_paths(CHEMIE_9B_CLASS_ID)["students"]
    )
    roster = set(student_ids_in(roster_text))
    timeline = eval_wiki.get_timeline(CHEMIE_9B_CLASS_ID)
    entries_by_date = {entry.date: entry for entry in timeline.entries}

    assert "S-046" in roster
    assert "S-006" not in roster
    assert "2026-07-09" in entries_by_date
    assert entries_by_date["2026-07-09"].has_plan is True
    assert entries_by_date["2026-07-09"].status == "planned"
    assert "2026-09-28" not in entries_by_date


def test_artifact_text_excludes_the_assistant_reply():
    final = {
        "reply": "Macbeth belongs to English 10c, not Chemie 9b.",
        "artifact_markdown": "Organic chemistry lesson result",
    }

    assert "macbeth" not in _artifact_text(final).lower()
    assert _artifact_text(final) == "Organic chemistry lesson result"


def _parse_sse(body: str) -> list[dict]:
    events: list[dict] = []
    for block in body.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data:"):
                events.append(json.loads(line[5:].strip()))
    return events


def _run_live_ingest_golden(client, golden: ExecutiveVerificationGolden) -> list[dict]:
    start = client.post(
        f"/api/classes/{golden.class_id}/ingest/sessions",
        json=golden.start_body,
    )
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]

    finals: list[dict] = []
    for message in golden.messages:
        stream = client.post(
            f"/api/classes/{golden.class_id}/ingest/sessions/{session_id}/chat/stream",
            json={"message": message},
        )
        assert stream.status_code == 200, stream.text
        events = _parse_sse(stream.text)
        turn_finals = [event for event in events if event.get("type") == "final"]
        assert turn_finals, f"{golden.golden_id}: stream returned no final event"
        finals.append(turn_finals[-1])
    return finals


def _assert_decision(final: dict, expected: str, *, golden_id: str) -> None:
    ready = bool(final.get("ready"))
    status = ((final.get("executive_state") or {}).get("status") or "clear")
    if expected == "block_ready":
        assert ready is False, f"{golden_id}: expected ready=false"
        assert status == "needs_decision", (
            f"{golden_id}: expected needs_decision, got {status!r}"
        )
    elif expected == "proceed":
        assert ready is True, f"{golden_id}: expected ready=true"
        assert status in {"clear", "advisory"}, (
            f"{golden_id}: expected clear/advisory, got {status!r}"
        )
    elif expected == "proceed_with_note":
        assert ready is True, f"{golden_id}: expected ready=true"
        assert status == "advisory", f"{golden_id}: expected advisory"
    else:  # pragma: no cover - guards future golden edits
        raise AssertionError(f"Unknown expectation: {expected}")


def _turn_text(final: dict) -> str:
    return "\n\n".join(
        str(final.get(key) or "")
        for key in ("reply", "artifact_markdown", "plan_markdown")
    )


def _artifact_text(final: dict) -> str:
    return "\n\n".join(
        value
        for key in ("artifact_markdown", "plan_markdown")
        if (value := str(final.get(key) or ""))
    )


_LIVE = os.getenv("RUN_LIVE_AGENT_EVALS") == "1"
_LLM_JUDGE = os.getenv("RUN_LLM_EXECUTIVE_VERIFICATION_JUDGE") == "1"


@pytest.mark.skipif(
    not _LIVE,
    reason="live executive-verification evals are opt-in (RUN_LIVE_AGENT_EVALS=1)",
)
@pytest.mark.parametrize(
    "golden",
    EXECUTIVE_VERIFICATION_GOLDENS,
    ids=[golden.golden_id for golden in EXECUTIVE_VERIFICATION_GOLDENS],
)
def test_executive_verification_live_contract(live_eval_client, golden):
    finals = _run_live_ingest_golden(live_eval_client, golden)

    assert len(finals) == len(golden.expected_decisions)
    for final, expected in zip(finals, golden.expected_decisions, strict=True):
        _assert_decision(final, expected, golden_id=golden.golden_id)

    for final, required_signals in zip(
        finals, golden.required_reply_signals, strict=False
    ):
        reply = str(final.get("reply") or "")
        for signal in required_signals:
            assert signal.lower() in reply.lower(), (
                f"{golden.golden_id}: reply missing required signal {signal!r}"
            )

    combined_reply = "\n".join(str(final.get("reply") or "") for final in finals)
    for forbidden in golden.forbidden_reply_signals:
        assert forbidden.lower() not in combined_reply.lower(), (
            f"{golden.golden_id}: reply contains forbidden signal {forbidden!r}"
        )

    final_text = _artifact_text(finals[-1])
    for pattern in golden.required_artifact_patterns:
        assert pattern.lower() in final_text.lower(), (
            f"{golden.golden_id}: final artifact missing {pattern!r}"
        )
    for pattern in golden.forbidden_artifact_patterns:
        assert pattern.lower() not in final_text.lower(), (
            f"{golden.golden_id}: final artifact contains forbidden {pattern!r}"
        )

    candidate_targets = {
        candidate.get("target")
        for candidate in (finals[-1].get("memory_candidates") or [])
    }
    for target in golden.required_memory_candidate_targets:
        assert target in candidate_targets, (
            f"{golden.golden_id}: missing memory candidate target {target!r}"
        )


@pytest.mark.skipif(
    not (_LIVE and _LLM_JUDGE),
    reason=(
        "LLM executive-verification judge is opt-in "
        "(RUN_LIVE_AGENT_EVALS=1 and RUN_LLM_EXECUTIVE_VERIFICATION_JUDGE=1)"
    ),
)
@pytest.mark.parametrize(
    "golden",
    EXECUTIVE_VERIFICATION_GOLDENS,
    ids=[golden.golden_id for golden in EXECUTIVE_VERIFICATION_GOLDENS],
)
def test_executive_verification_llm_judge_live(live_eval_client, golden):
    from deepeval import assert_test
    from deepeval.dataset import Golden
    from deepeval.test_case import LLMTestCase

    from tests.evals.metrics.executive_verification_metrics import (
        ExecutiveVerificationJudgeMetric,
    )

    finals = _run_live_ingest_golden(live_eval_client, golden)
    actual_output = "\n\n--- turn ---\n\n".join(_turn_text(final) for final in finals)
    expected_context = (
        f"Expected decisions: {golden.expected_decisions}\n"
        f"Required reply signals: {golden.required_reply_signals}\n"
        f"Required artifact patterns: {golden.required_artifact_patterns}\n"
        f"Forbidden artifact patterns: {golden.forbidden_artifact_patterns}\n"
        f"Rationale: {golden.rationale}"
    )
    test_case = LLMTestCase(
        input="\n\n--- message ---\n\n".join(golden.messages),
        actual_output=actual_output,
        retrieval_context=[expected_context],
        metadata={"golden_id": golden.golden_id, "class_id": golden.class_id},
    )
    deepeval_golden = Golden(
        input="\n\n--- message ---\n\n".join(golden.messages),
        context=[expected_context],
        metadata={"golden_id": golden.golden_id, "mode": "live_llm_judge"},
    )

    assert_test(
        test_case=test_case,
        metrics=[ExecutiveVerificationJudgeMetric(golden=golden)],
        golden=deepeval_golden,
        run_async=False,
    )
