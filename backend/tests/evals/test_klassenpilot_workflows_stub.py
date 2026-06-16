"""DeepEval end-to-end workflow goldens with deterministic agent stubs."""

from __future__ import annotations

import pytest
from deepeval import assert_test
from deepeval.dataset import Golden

from tests.evals.goldens.workflow_scenarios import WORKFLOW_SCENARIO_GOLDENS
from tests.evals.harness import run_workflow_scenario
from tests.evals.metrics.workflow_metrics import (
    WorkflowScenarioMetric,
    build_workflow_test_case,
)


@pytest.mark.parametrize(
    "golden",
    WORKFLOW_SCENARIO_GOLDENS,
    ids=[g.golden_id for g in WORKFLOW_SCENARIO_GOLDENS],
)
def test_workflow_scenario_golden_stub(eval_client, golden):
    result = run_workflow_scenario(
        eval_client,
        workflow=golden.workflow,
        class_id=golden.class_id,
        messages=golden.messages,
    )
    test_case = build_workflow_test_case(result)
    deepeval_golden = Golden(
        input=test_case.input,
        metadata={
            "golden_id": golden.golden_id,
            "workflow": golden.workflow,
            "mode": "stub",
        },
    )
    assert_test(
        test_case=test_case,
        metrics=[WorkflowScenarioMetric(golden=golden)],
        golden=deepeval_golden,
        run_async=False,
    )
