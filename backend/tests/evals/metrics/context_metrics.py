"""DeepEval metrics wrapping deterministic trace scorers."""

from __future__ import annotations

import json
from typing import Any

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

from tests.eval.ingest_trace_scorer import score_ingest_startup_context
from tests.eval.plan_trace_scorer import score_startup_context
from tests.evals.contracts.layer_contract import LayerExpectation, score_layer_context


def _reason_from_result(result) -> str:
    if result.passed:
        return "All contract checks passed."
    return "\n".join(f"- {item}" for item in result.failures)


class LayerContextMetric(BaseMetric):
    """Score isolated context layers from pack-builder traces."""

    def __init__(self, expectation: LayerExpectation, threshold: float = 1.0):
        self.expectation = expectation
        self.threshold = threshold
        self.strict_mode = True
        self.async_mode = False
        self.include_reason = True
        self.score: float | None = None
        self.reason: str | None = None
        self.success: bool | None = None
        self.error: str | None = None

    def measure(self, test_case: LLMTestCase) -> float:
        try:
            metadata = (
                test_case.metadata
                or getattr(test_case, "additional_metadata", None)
                or {}
            )
            result = score_layer_context(
                teacher_trace=metadata.get("teacher_trace") or {},
                core_trace=metadata.get("core_trace"),
                subject_trace=metadata.get("subject_trace"),
                expectation=self.expectation,
            )
            self.score = 1.0 if result.passed else 0.0
            self.reason = _reason_from_result(result)
            self.success = result.passed
            return self.score
        except Exception as exc:
            self.error = str(exc)
            raise

    async def a_measure(self, test_case: LLMTestCase) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        if self.error is not None or self.score is None:
            self.success = False
        else:
            self.success = self.score >= self.threshold
        return bool(self.success)

    @property
    def __name__(self) -> str:
        return f"LayerContext[{self.expectation.golden_id}]"


class PlanStartupContextMetric(BaseMetric):
    """Score plan workflow startup trace."""

    def __init__(self, threshold: float = 1.0):
        self.threshold = threshold
        self.strict_mode = True
        self.async_mode = False
        self.include_reason = True
        self.score: float | None = None
        self.reason: str | None = None
        self.success: bool | None = None
        self.error: str | None = None

    def measure(self, test_case: LLMTestCase) -> float:
        try:
            trace = _trace_from_test_case(test_case)
            result = score_startup_context(trace)
            self.score = 1.0 if result.passed else 0.0
            self.reason = _reason_from_result(result)
            self.success = result.passed
            return self.score
        except Exception as exc:
            self.error = str(exc)
            raise

    async def a_measure(self, test_case: LLMTestCase) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        if self.error is not None or self.score is None:
            self.success = False
        else:
            self.success = self.score >= self.threshold
        return bool(self.success)

    @property
    def __name__(self) -> str:
        return "PlanStartupContext"


class IngestStartupContextMetric(BaseMetric):
    """Score ingest workflow startup trace."""

    def __init__(self, threshold: float = 1.0):
        self.threshold = threshold
        self.strict_mode = True
        self.async_mode = False
        self.include_reason = True
        self.score: float | None = None
        self.reason: str | None = None
        self.success: bool | None = None
        self.error: str | None = None

    def measure(self, test_case: LLMTestCase) -> float:
        try:
            trace = _trace_from_test_case(test_case)
            result = score_ingest_startup_context(trace)
            self.score = 1.0 if result.passed else 0.0
            self.reason = _reason_from_result(result)
            self.success = result.passed
            return self.score
        except Exception as exc:
            self.error = str(exc)
            raise

    async def a_measure(self, test_case: LLMTestCase) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        if self.error is not None or self.score is None:
            self.success = False
        else:
            self.success = self.score >= self.threshold
        return bool(self.success)

    @property
    def __name__(self) -> str:
        return "IngestStartupContext"


def _trace_from_test_case(test_case: LLMTestCase) -> dict[str, Any]:
    metadata = (
        test_case.metadata or getattr(test_case, "additional_metadata", None) or {}
    )
    trace = metadata.get("trace")
    if isinstance(trace, dict):
        return trace
    if test_case.actual_output:
        return json.loads(test_case.actual_output)
    raise ValueError("LLMTestCase is missing trace metadata")
