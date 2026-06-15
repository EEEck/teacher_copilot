"""DeepEval workflow startup goldens for Chemie 9b."""

from __future__ import annotations

import pytest
from deepeval import assert_test
from deepeval.dataset import Golden
from deepeval.test_case import LLMTestCase

from tests.evals.goldens.chemie_9b_startup import WORKFLOW_GOLDENS
from tests.evals.harness import fetch_startup_trace
from tests.evals.metrics.context_metrics import IngestStartupContextMetric, PlanStartupContextMetric


@pytest.mark.parametrize("golden", WORKFLOW_GOLDENS, ids=[g.golden_id for g in WORKFLOW_GOLDENS])
def test_workflow_startup_golden(eval_client, golden):
    trace = fetch_startup_trace(eval_client, workflow=golden.workflow, class_id=golden.class_id)
    test_case = LLMTestCase(
        input=f"workflow:{golden.workflow}",
        actual_output="",
        metadata={"trace": trace},
    )
    deepeval_golden = Golden(
        input=test_case.input,
        metadata={
            "golden_id": golden.golden_id,
            "workflow": golden.workflow,
            "class_id": golden.class_id,
        },
    )
    metrics = (
        [PlanStartupContextMetric()]
        if golden.workflow == "plan"
        else [IngestStartupContextMetric()]
    )
    assert_test(
        test_case=test_case,
        metrics=metrics,
        golden=deepeval_golden,
        run_async=False,
    )
