"""DeepEval chat goldens — live OpenAI Agents SDK (opt-in, uses API credits)."""

from __future__ import annotations

import os

import pytest
from deepeval import assert_test
from deepeval.dataset import Golden

from tests.evals.goldens.chat_plan import CHAT_GOLDENS, CHAT_SCENARIO_PRIORS
from tests.evals.harness import run_chat_scenario, start_session, run_chat_turn
from tests.evals.metrics.chat_metrics import build_chat_test_case, chat_metrics_for_golden

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_AGENT_EVALS") != "1",
    reason="live agent chat evals are opt-in (set RUN_LIVE_AGENT_EVALS=1)",
)


@pytest.mark.parametrize("golden", CHAT_GOLDENS, ids=[g.golden_id for g in CHAT_GOLDENS])
def test_chat_golden_live(live_eval_client, golden):
    priors = CHAT_SCENARIO_PRIORS.get(golden.golden_id, ())
    if priors:
        result = run_chat_scenario(
            live_eval_client,
            workflow=golden.workflow,
            class_id=golden.class_id,
            prior_messages=priors,
            message=golden.message,
            attachments=golden.attachments,
        )
    else:
        session_id = start_session(live_eval_client, workflow=golden.workflow, class_id=golden.class_id)
        result = run_chat_turn(
            live_eval_client,
            workflow=golden.workflow,
            class_id=golden.class_id,
            session_id=session_id,
            message=golden.message,
            attachments=golden.attachments,
        )

    test_case = build_chat_test_case(result)
    deepeval_golden = Golden(
        input=golden.message,
        metadata={"golden_id": golden.golden_id, "mode": "live"},
    )
    assert_test(
        test_case=test_case,
        metrics=chat_metrics_for_golden(golden, include_llm_judge=True),
        golden=deepeval_golden,
        run_async=False,
    )
