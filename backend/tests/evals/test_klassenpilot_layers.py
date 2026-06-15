"""DeepEval layer-isolation goldens."""

from __future__ import annotations

import pytest
from deepeval import assert_test
from deepeval.dataset import Golden
from deepeval.test_case import LLMTestCase

from tests.evals.goldens.layer_isolation import LAYER_GOLDENS
from tests.evals.harness import fetch_layer_traces
from tests.evals.metrics.context_metrics import LayerContextMetric


@pytest.mark.parametrize("expectation", LAYER_GOLDENS, ids=[g.golden_id for g in LAYER_GOLDENS])
def test_layer_context_golden(eval_wiki, expectation):
    traces = fetch_layer_traces(eval_wiki, expectation.class_id)
    test_case = LLMTestCase(
        input=f"layer:{expectation.layer_scope.value}",
        actual_output="",
        metadata=traces,
    )
    golden = Golden(
        input=test_case.input,
        metadata={
            "golden_id": expectation.golden_id,
            "class_id": expectation.class_id,
            "layer_scope": expectation.layer_scope.value,
        },
    )
    assert_test(
        test_case=test_case,
        metrics=[LayerContextMetric(expectation=expectation)],
        golden=golden,
        run_async=False,
    )
