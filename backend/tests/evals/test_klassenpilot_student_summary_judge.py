"""DeepEval student-summary golden with deterministic checks and optional LLM judge."""

from __future__ import annotations

import pytest
from deepeval import assert_test
from deepeval.dataset import Golden
from deepeval.test_case import LLMTestCase

from tests.evals.goldens.student_summary import STUDENT_SUMMARY_GOLDENS
from tests.evals.metrics.student_summary_metrics import StudentSummaryJudgeMetric


@pytest.mark.parametrize(
    "golden",
    STUDENT_SUMMARY_GOLDENS,
    ids=[golden.golden_id for golden in STUDENT_SUMMARY_GOLDENS],
)
def test_student_summary_judge_golden(golden):
    test_case = LLMTestCase(
        input=golden.prompt,
        actual_output=golden.proposed_summary,
        retrieval_context=[golden.student_page_markdown],
        metadata={
            "golden_id": golden.golden_id,
            "class_id": golden.class_id,
            "student_id": golden.student_id,
        },
    )
    deepeval_golden = Golden(
        input=test_case.input,
        expected_output=golden.proposed_summary,
        context=[golden.student_page_markdown],
        metadata={
            "golden_id": golden.golden_id,
            "class_id": golden.class_id,
            "student_id": golden.student_id,
        },
    )

    assert_test(
        test_case=test_case,
        metrics=[StudentSummaryJudgeMetric(golden=golden)],
        golden=deepeval_golden,
        run_async=False,
    )
