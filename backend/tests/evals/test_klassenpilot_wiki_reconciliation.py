"""Wiki-vs-input reconciliation eval.

Two layers, matching the design (docs/mem_v3/input_reconciliation.md):

- Deterministic (always-on): roster membership is a FACT, so the detection step
  is a pure function. These tests verify each golden's non_roster_ids against
  the real roster — proving detection needs no model, and guarding the goldens.
- Live judge (opt-in, RUN_LIVE_AGENT_EVALS): run each scenario through a real
  ingest turn and check the reply. The clarify wiring is a tracked follow-up, so
  clarify cases xfail (documented target) rather than hard-fail; the "don't
  spuriously flag / don't fabricate" checks hard-fail (real regressions).
"""

from __future__ import annotations

import os

import pytest

from tests.evals.goldens.wiki_input_reconciliation import (
    CHEMIE_9B_CLASS_ID,
    WIKI_RECONCILIATION_GOLDENS,
    non_roster_ids,
    student_ids_in,
)
from tests.evals.harness import actual_output_text, run_chat_scenario


def _roster(eval_wiki) -> set[str]:
    students_index = eval_wiki.read_text(
        eval_wiki.roll_up_paths(CHEMIE_9B_CLASS_ID)["students"]
    )
    return set(student_ids_in(students_index))


# --- deterministic: detection is a pure function of message + roster ----------


def test_goldens_cover_the_three_paths():
    ids = {g.golden_id for g in WIKI_RECONCILIATION_GOLDENS}
    assert "non_roster_observation_is_flagged" in ids  # flag
    assert "valid_observation_is_accepted" in ids  # accept
    assert "explicit_new_student_is_accepted" in ids  # confirmed change


@pytest.mark.parametrize(
    "golden",
    WIKI_RECONCILIATION_GOLDENS,
    ids=[g.golden_id for g in WIKI_RECONCILIATION_GOLDENS],
)
def test_non_roster_detection_is_deterministic(eval_wiki, golden):
    """The whole detection step is code, not model judgment."""
    roster = _roster(eval_wiki)
    assert "S-014" in roster and "S-099" not in roster  # sanity on the fixture
    detected = tuple(non_roster_ids(golden.teacher_message, roster))
    assert detected == golden.non_roster_ids, (
        f"{golden.golden_id}: detected {detected}, golden says {golden.non_roster_ids}"
    )


# --- live judge: target behavior, opt-in --------------------------------------

_LIVE = os.getenv("RUN_LIVE_AGENT_EVALS") == "1"


@pytest.mark.skipif(not _LIVE, reason="live agent evals are opt-in (RUN_LIVE_AGENT_EVALS=1)")
@pytest.mark.parametrize(
    "golden",
    WIKI_RECONCILIATION_GOLDENS,
    ids=[g.golden_id for g in WIKI_RECONCILIATION_GOLDENS],
)
def test_wiki_reconciliation_reply_behavior_live(live_eval_client, golden):
    result = run_chat_scenario(
        live_eval_client,
        workflow=golden.workflow,
        class_id=CHEMIE_9B_CLASS_ID,
        prior_messages=(golden.prior_message,) if golden.prior_message else (),
        message=golden.teacher_message,
    )
    reply = actual_output_text(result).lower()

    # Real regressions hard-fail regardless of feature status: the agent must
    # not spuriously flag a valid id or mislabel an explicit new student.
    for forbidden in golden.forbidden_reply_signals:
        assert forbidden.lower() not in reply, (
            f"{golden.golden_id}: reply contains forbidden signal {forbidden!r}"
        )

    if not golden.expect_clarify:
        return

    surfaced_ids = all(sid.lower() in reply for sid in golden.non_roster_ids)
    surfaced_signal = any(sig.lower() in reply for sig in golden.expected_reply_signals)
    if not (surfaced_ids and surfaced_signal):
        pytest.xfail(
            f"reconciliation not yet wired: reply did not clarify the non-roster "
            f"id(s) {golden.non_roster_ids} for {golden.golden_id!r}"
        )
