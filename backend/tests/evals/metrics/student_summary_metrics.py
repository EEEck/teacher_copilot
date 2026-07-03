"""DeepEval metrics for Student Summary judge goldens."""

from __future__ import annotations

import os
import re

from deepeval.metrics import BaseMetric, GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams

from tests.evals.goldens.student_summary import StudentSummaryGolden


class StudentSummaryJudgeMetric(BaseMetric):
    """Deterministic student-summary policy checks plus optional GEval judge."""

    def __init__(self, golden: StudentSummaryGolden, threshold: float = 1.0):
        self.golden = golden
        self.threshold = threshold
        self.strict_mode = True
        self.async_mode = False
        self.include_reason = True
        self.score: float | None = None
        self.reason: str | None = None
        self.success: bool | None = None
        self.error: str | None = None

    def _deterministic_failures(self, test_case: LLMTestCase) -> list[str]:
        output = (test_case.actual_output or "").strip()
        failures: list[str] = []

        if not output:
            failures.append("missing proposed Student Summary output")
        if "\n" in output:
            failures.append("Student Summary should be one sentence on one line")
        if output.count(".") + output.count("!") + output.count("?") > 1:
            failures.append("Student Summary should stay to one sentence")

        for pattern in self.golden.required_patterns:
            if not re.search(pattern, output, flags=re.IGNORECASE):
                failures.append(f"missing required trajectory/support pattern /{pattern}/")

        for pattern in self.golden.forbidden_patterns:
            if re.search(pattern, output, flags=re.IGNORECASE):
                failures.append(f"includes forbidden high-stakes or profiling pattern /{pattern}/")

        return failures

    def _build_geval(self) -> GEval | None:
        if os.getenv("RUN_LLM_STUDENT_SUMMARY_JUDGE") != "1":
            return None
        if not self.golden.geval_criteria:
            return None

        model = os.getenv("DEEPEVAL_MODEL") or os.getenv("OPENAI_FAST_MODEL", "gpt-4o-mini")
        return GEval(
            name=f"StudentSummaryJudge[{self.golden.golden_id}]",
            criteria=self.golden.geval_criteria,
            evaluation_params=[
                SingleTurnParams.INPUT,
                SingleTurnParams.RETRIEVAL_CONTEXT,
                SingleTurnParams.ACTUAL_OUTPUT,
            ],
            threshold=0.75,
            model=model,
        )

    def measure(self, test_case: LLMTestCase) -> float:
        try:
            failures = self._deterministic_failures(test_case)
            if failures:
                self.score = 0.0
                self.reason = "\n".join(f"- {item}" for item in failures)
                self.success = False
                return self.score

            geval = self._build_geval()
            if geval is None:
                self.score = 1.0
                self.reason = (
                    "Student Summary deterministic checks OK; LLM judge skipped "
                    "(set RUN_LLM_STUDENT_SUMMARY_JUDGE=1 to enable)."
                )
                self.success = True
                return self.score

            geval.measure(test_case)
            self.score = float(geval.score or 0.0)
            self.reason = geval.reason or ""
            self.success = bool(geval.success)
            return self.score
        except Exception as exc:
            self.error = str(exc)
            raise

    async def a_measure(self, test_case: LLMTestCase) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        if self.error is not None:
            self.success = False
        elif self.score is None:
            self.success = False
        else:
            self.success = self.score >= self.threshold
        return bool(self.success)

    @property
    def __name__(self) -> str:
        return f"StudentSummaryJudge[{self.golden.golden_id}]"
