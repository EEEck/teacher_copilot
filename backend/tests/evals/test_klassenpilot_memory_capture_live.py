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
from tests.evals.goldens.memory_capture import (
    MEMORY_CAPTURE_GOLDENS,
    expected_fast_lane_for_target,
)
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


def _candidate_debug(candidate: MemoryCandidate) -> str:
    parts = [
        f"target={canonical_memory_target(candidate.target)}",
        f"speech_act={candidate.speech_act or 'none'}",
        f"fast_lane={candidate.fast_lane}",
    ]
    reason = (candidate.routing_reason or "").strip()
    if reason:
        parts.append(f"routing_reason={reason!r}")
    update = (candidate.candidate_update or "").strip()
    if update:
        parts.append(f"content={update!r}")
    return "{" + ", ".join(parts) + "}"


def _expected_targets(golden) -> tuple[str, ...]:
    targets = golden.expected_targets or (golden.target,)
    return tuple(canonical_memory_target(target) for target in targets)


def _candidate_targets(emitted: list[MemoryCandidate]) -> list[str]:
    return sorted({canonical_memory_target(candidate.target) for candidate in emitted})


def _missing_expected_target_message(
    *,
    golden_id: str,
    expected_target: str | None = None,
    expected_targets: tuple[str, ...] = (),
    emitted: list[MemoryCandidate],
    teacher_message: str,
) -> str:
    expected = tuple(
        canonical_memory_target(target)
        for target in (expected_targets or ((expected_target or ""),))
        if target
    )
    if not emitted:
        return (
            f"{golden_id}: capture emission gap: model emitted no candidates "
            f"for expected {list(expected)}. Message: {teacher_message!r}"
        )
    emitted_targets = _candidate_targets(emitted)
    missing = [target for target in expected if target not in emitted_targets]
    details = "; ".join(_candidate_debug(c) for c in emitted)
    return (
        f"{golden_id}: wrong target: missing expected target(s): "
        f"{', '.join(missing) or '(none)'}; expected {list(expected)}, "
        f"got {emitted_targets}. Emitted candidates: {details}. "
        f"Message: {teacher_message!r}"
    )


def _forbidden_target_message(
    *,
    golden_id: str,
    forbidden_targets: tuple[str, ...],
    emitted: list[MemoryCandidate],
    teacher_message: str,
) -> str:
    forbidden = {canonical_memory_target(target) for target in forbidden_targets}
    offenders = [
        candidate
        for candidate in emitted
        if canonical_memory_target(candidate.target) in forbidden
    ]
    details = "; ".join(_candidate_debug(c) for c in offenders)
    return (
        f"{golden_id}: forbidden target emitted: {sorted(forbidden)}. "
        f"Offending candidates: {details}. Message: {teacher_message!r}"
    )


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
    expected_targets = _expected_targets(golden)
    forbidden_targets = tuple(canonical_memory_target(t) for t in golden.forbidden_targets)
    emitted_targets = _candidate_targets(emitted)

    if golden.expect_no_durable_candidates:
        assert not emitted, (
            f"{golden.golden_id}: expected no durable capture for a one-off or "
            f"unknown-scope request; emitted "
            f"{'; '.join(_candidate_debug(candidate) for candidate in emitted)}"
        )

    # Separate the two failure modes so the eval measures JUDGMENT cleanly:
    # - emission gap: the model emitted no candidate for a target it should
    #   have captured. Mem V3 PR4 targets this by making capture an explicit
    #   remember(...) tool call (whose staged candidates land in
    #   runtime.memory_candidates, read above). When the tool fires, this xfail
    #   no longer triggers and the run proceeds to the judgment assertion; a
    #   still-empty emission is reported as xfail, not a red judgment regression.
    if forbidden_targets and any(target in forbidden_targets for target in emitted_targets):
        pytest.fail(
            _forbidden_target_message(
                golden_id=golden.golden_id,
                forbidden_targets=forbidden_targets,
                emitted=emitted,
                teacher_message=golden.teacher_message,
            )
        )

    missing_targets = [
        target for target in expected_targets if target not in emitted_targets
    ]
    if golden.expected_fast_lane and missing_targets:
        if emitted:
            pytest.fail(
                _missing_expected_target_message(
                    golden_id=golden.golden_id,
                    expected_targets=expected_targets,
                    emitted=emitted,
                    teacher_message=golden.teacher_message,
                )
            )
        pytest.xfail(
            _missing_expected_target_message(
                golden_id=golden.golden_id,
                expected_targets=expected_targets,
                emitted=emitted,
                teacher_message=golden.teacher_message,
            )
        )

    if golden.expected_min_candidates and len(emitted) < golden.expected_min_candidates:
        pytest.fail(
            f"{golden.golden_id}: emitted {len(emitted)} candidate(s), expected "
            f"at least {golden.expected_min_candidates}. Emitted: "
            f"{'; '.join(_candidate_debug(c) for c in emitted)}"
        )

    # Judgment: run what the model DID emit through the same backend discipline
    # the production path uses, then check the fast-lane outcome. A candidate
    # emitted but classified wrong is a real regression and hard-fails.
    for target in expected_targets:
        target_candidates = [
            c for c in emitted if canonical_memory_target(c.target) == target
        ]
        speech_acts = sorted({(c.speech_act or "none") for c in target_candidates})
        disciplined = discipline_memory_candidates(
            target_candidates, teacher_message=golden.teacher_message
        )
        got_fast_lane = any(c.fast_lane for c in disciplined)

        expected_fast_lane = expected_fast_lane_for_target(golden, target)
        assert got_fast_lane is expected_fast_lane, (
            f"{golden.golden_id}: model emitted speech_act(s)={speech_acts} for "
            f"{target}; fast_lane={got_fast_lane}, expected {expected_fast_lane}. "
            f"Emitted targets={emitted_targets}. "
            f"Message: {golden.teacher_message!r}"
        )
