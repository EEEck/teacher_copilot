"""Live judge eval: how well does the model classify the capture speech act?

Opt-in (uses API credits). The deterministic stub
(test_klassenpilot_memory_capture_stub.py) verifies the backend discipline
function; this eval measures the thing the discipline function depends on —
the model's own speech-act judgment — by running each golden message through
a real chat turn and checking the end-to-end fast-lane outcome.

Run:
    $env:RUN_LIVE_AGENT_EVALS="1"; pytest tests/evals/test_klassenpilot_memory_capture_live.py
"""

from __future__ import annotations

import os

import pytest

from app.teacher_agent.memory_capture import (
    MemoryCandidate,
    canonical_memory_target,
    discipline_memory_candidates,
)
from tests.evals.goldens.memory_capture import MEMORY_CAPTURE_GOLDENS
from tests.evals.harness import run_chat_scenario, run_chat_turn, start_session

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_AGENT_EVALS") != "1",
    reason="live agent capture evals are opt-in (set RUN_LIVE_AGENT_EVALS=1)",
)

_LIVE_GOLDENS = [g for g in MEMORY_CAPTURE_GOLDENS if g.workflow]

_CANDIDATE_FIELDS = set(MemoryCandidate.model_fields)


def _runtime_candidates(trace: dict) -> list[MemoryCandidate]:
    raw = (trace.get("runtime") or {}).get("memory_candidates") or []
    out: list[MemoryCandidate] = []
    for item in raw:
        if isinstance(item, dict):
            out.append(
                MemoryCandidate(**{k: v for k, v in item.items() if k in _CANDIDATE_FIELDS})
            )
    return out


@pytest.mark.parametrize(
    "golden",
    _LIVE_GOLDENS,
    ids=[g.golden_id for g in _LIVE_GOLDENS],
)
def test_memory_capture_speech_act_live(live_eval_client, golden):
    if golden.prior_message:
        result = run_chat_scenario(
            live_eval_client,
            workflow=golden.workflow,
            class_id="chemie_9b_2026_27",
            prior_messages=(golden.prior_message,),
            message=golden.teacher_message,
        )
    else:
        session_id = start_session(
            live_eval_client, workflow=golden.workflow, class_id="chemie_9b_2026_27"
        )
        result = run_chat_turn(
            live_eval_client,
            workflow=golden.workflow,
            class_id="chemie_9b_2026_27",
            session_id=session_id,
            message=golden.teacher_message,
        )

    emitted = _runtime_candidates(result.trace)
    target = canonical_memory_target(golden.target)
    target_candidates = [
        c for c in emitted if canonical_memory_target(c.target) == target
    ]
    speech_acts = sorted({(c.speech_act or "∅") for c in target_candidates})

    # Separate the two failure modes so the eval measures JUDGMENT cleanly:
    # - emission gap: the model emitted no candidate for a target it should
    #   have captured. Mem V3 PR4 targets this by making capture an explicit
    #   remember(...) tool call (whose staged candidates land in
    #   runtime.memory_candidates, read above). When the tool fires, this xfail
    #   no longer triggers and the run proceeds to the judgment assertion; a
    #   still-empty emission is reported as xfail, not a red judgment regression.
    if golden.expected_fast_lane and not target_candidates:
        pytest.xfail(
            f"capture emission gap: model emitted no {target} candidate for "
            f"{golden.teacher_message!r} (remember tool did not fire)"
        )

    # Judgment: run what the model DID emit through the same backend discipline
    # the production path uses, then check the fast-lane outcome. A candidate
    # emitted but classified wrong is a real regression and hard-fails.
    disciplined = discipline_memory_candidates(
        target_candidates, teacher_message=golden.teacher_message
    )
    got_fast_lane = any(c.fast_lane for c in disciplined)

    assert got_fast_lane is golden.expected_fast_lane, (
        f"{golden.golden_id}: model emitted speech_act(s)={speech_acts} for "
        f"{target}; fast_lane={got_fast_lane}, expected "
        f"{golden.expected_fast_lane}. Message: {golden.teacher_message!r}"
    )
