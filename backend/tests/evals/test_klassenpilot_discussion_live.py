"""Opt-in LLM-as-judge eval for task anchoring in Discuss."""

from __future__ import annotations

import os

import pytest
from deepeval import assert_test
from deepeval.dataset import Golden

from tests.evals.goldens.discussion import (
    DISCUSSION_GOLDENS,
    DISCUSSION_SCENARIO_PRIORS,
)
from tests.evals.harness import run_chat_scenario
from tests.evals.metrics.chat_metrics import build_chat_test_case, chat_metrics_for_golden


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_AGENT_EVALS") != "1",
    reason="live Discuss eval is opt-in (set RUN_LIVE_AGENT_EVALS=1)",
)


@pytest.mark.parametrize("golden", DISCUSSION_GOLDENS, ids=[g.golden_id for g in DISCUSSION_GOLDENS])
def test_discussion_golden_live(live_eval_client, golden):
    result = run_chat_scenario(
        live_eval_client,
        workflow=golden.workflow,
        class_id=golden.class_id,
        prior_messages=DISCUSSION_SCENARIO_PRIORS[golden.golden_id],
        message=golden.message,
    )

    assert_test(
        test_case=build_chat_test_case(result),
        metrics=chat_metrics_for_golden(golden, include_llm_judge=True),
        golden=Golden(input=golden.message, metadata={"golden_id": golden.golden_id, "mode": "live"}),
        run_async=False,
    )
