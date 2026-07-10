"""Optional LLM-as-judge metric for executive-verification behavior."""

from __future__ import annotations

import os

from deepeval.metrics import BaseMetric, GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams

from app.config import get_settings
from tests.evals.goldens.executive_verification import ExecutiveVerificationGolden


def _judge_model() -> str:
    explicit = os.getenv("DEEPEVAL_MODEL")
    if explicit:
        return explicit
    try:
        return get_settings().openai_strong_model
    except Exception:  # noqa: BLE001 - eval fallback only
        return "gpt-5.5"


def _criteria_for(golden: ExecutiveVerificationGolden) -> str:
    expected = ", ".join(golden.expected_decisions)
    return (
        "You are judging a KlassenPilot teacher-copilot conversation. "
        "KlassenPilot should act as an executive assistant: complete useful "
        "foreground work, verify class-state facts against the committed wiki, "
        "and surface only decisions that affect durable class memory or important "
        "planning assumptions.\n\n"
        f"Scenario: {golden.golden_id}\n"
        f"Expected decision sequence: {expected}\n"
        f"Rationale: {golden.rationale}\n\n"
        "Pass only if the assistant behavior satisfies all applicable points:\n"
        "- It does not claim durable memory was saved during chat.\n"
        "- It does not silently accept conflicting class/date/student facts as canonical.\n"
        "- It asks a concise clarification when readiness should be blocked.\n"
        "- It avoids unnecessary clarification when the input is valid enough to proceed.\n"
        "- It keeps the teacher as decision-maker for durable class-state changes.\n"
        "- It continues useful foreground drafting unless the input is clearly for the wrong context.\n"
        "- It sounds practical and non-accusatory."
    )


class ExecutiveVerificationJudgeMetric(BaseMetric):
    """LLM judge for the teacher-facing quality of executive verification."""

    def __init__(self, golden: ExecutiveVerificationGolden, threshold: float = 0.8):
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
        if os.getenv("RUN_LLM_EXECUTIVE_VERIFICATION_JUDGE") != "1":
            return None
        return GEval(
            name=f"ExecutiveVerificationJudge[{self.golden.golden_id}]",
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
                    "(set RUN_LLM_EXECUTIVE_VERIFICATION_JUDGE=1 to enable)."
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
        return f"ExecutiveVerificationJudge[{self.golden.golden_id}]"
