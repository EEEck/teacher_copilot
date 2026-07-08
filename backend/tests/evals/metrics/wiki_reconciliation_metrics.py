"""DeepEval metrics for wiki-vs-input reconciliation behavior."""

from __future__ import annotations

import os

from deepeval.metrics import BaseMetric, GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams

from app.config import get_settings
from tests.evals.goldens.wiki_input_reconciliation import WikiReconciliationGolden


def _judge_model() -> str:
    explicit = os.getenv("DEEPEVAL_MODEL")
    if explicit:
        return explicit
    try:
        return get_settings().openai_strong_model
    except Exception:  # noqa: BLE001 - eval fallback only
        return "gpt-5.5"


def _criteria_for(golden: WikiReconciliationGolden) -> str:
    base = (
        "You are judging a teacher-facing reply from KlassenPilot, a private "
        "teacher copilot that uses the committed class wiki as the source of "
        "truth. Pass only if the reply follows the expected wiki reconciliation "
        "behavior for this scenario. The agent must not silently overwrite, "
        "delete, or add wiki facts when the teacher input conflicts with the "
        "wiki; conflicting input is a proposed change until the teacher confirms "
        "how to resolve it."
    )
    if golden.expect_clarify:
        return (
            f"{base}\n\n"
            "Expected behavior for this scenario:\n"
            "- Identify that the teacher mentioned a student ID that is not on "
            "the current class roster.\n"
            "- Ask the teacher to resolve the discrepancy before recording the "
            "student observation, e.g. typo/correct student/new student.\n"
            "- Do not silently accept the non-roster observation as if it were "
            "already valid.\n"
            "- Do not claim a durable wiki write happened.\n"
            f"Golden rationale: {golden.rationale}"
        )
    if golden.non_roster_ids:
        return (
            f"{base}\n\n"
            "Expected behavior for this scenario:\n"
            "- Treat the teacher's explicit 'new student joined / add them' "
            "instruction as a confirmed-change path, not as a typo.\n"
            "- It is acceptable to say the roster/wiki update still needs the "
            "normal teacher-approved write flow.\n"
            "- Do not second-guess the teacher by calling the new student ID a "
            "likely typo.\n"
            "- Do not claim a durable wiki write happened unless the product "
            "actually performs an approved write in this turn.\n"
            f"Golden rationale: {golden.rationale}"
        )
    return (
        f"{base}\n\n"
        "Expected behavior for this scenario:\n"
        "- Accept the observation as using an enrolled student ID.\n"
        "- Do not ask a roster-conflict clarification.\n"
        "- Do not call the valid student ID a typo or non-roster student.\n"
        "- Do not claim a durable wiki write happened unless the product "
        "actually performs an approved write in this turn.\n"
        f"Golden rationale: {golden.rationale}"
    )


class WikiReconciliationJudgeMetric(BaseMetric):
    """Optional LLM-as-judge for teacher-facing reconciliation behavior."""

    def __init__(self, golden: WikiReconciliationGolden, threshold: float = 0.8):
        self.golden = golden
        self.threshold = threshold
        self.strict_mode = False
        self.async_mode = False
        self.include_reason = True
        self.score: float | None = None
        self.reason: str | None = None
        self.success: bool | None = None
        self.error: str | None = None

    def _build_geval(self) -> GEval | None:
        if os.getenv("RUN_LLM_WIKI_RECONCILIATION_JUDGE") != "1":
            return None
        return GEval(
            name=f"WikiReconciliationJudge[{self.golden.golden_id}]",
            criteria=_criteria_for(self.golden),
            evaluation_params=[
                SingleTurnParams.INPUT,
                SingleTurnParams.RETRIEVAL_CONTEXT,
                SingleTurnParams.ACTUAL_OUTPUT,
            ],
            threshold=self.threshold,
            model=_judge_model(),
        )

    def measure(self, test_case: LLMTestCase) -> float:
        try:
            geval = self._build_geval()
            if geval is None:
                self.score = 1.0
                self.reason = (
                    "LLM judge skipped "
                    "(set RUN_LLM_WIKI_RECONCILIATION_JUDGE=1 to enable)."
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
        return f"WikiReconciliationJudge[{self.golden.golden_id}]"
