"""DeepEval metrics for complete workflow scenarios."""

from __future__ import annotations

import os
import re
from typing import Any

from deepeval.metrics import BaseMetric, GEval
from deepeval.test_case import LLMTestCase, SingleTurnParams

from tests.eval.plan_trace_scorer import score_trace_hygiene
from tests.evals.goldens.workflow_scenarios import WorkflowScenarioGolden
from tests.evals.harness import (
    WorkflowScenarioResult,
    actual_output_text,
    build_retrieval_context,
    tool_names_from_events,
)


def _scenario_from_metadata(metadata: dict[str, Any]) -> WorkflowScenarioResult:
    raw = metadata.get("scenario_result")
    if isinstance(raw, WorkflowScenarioResult):
        return raw
    raise ValueError("LLMTestCase metadata missing scenario_result")


def _runtime_phase(trace: dict[str, Any], workflow: str) -> str:
    runtime = trace.get("runtime") or {}
    if workflow == "plan":
        session_state = runtime.get("session_state") or {}
        return str(session_state.get("phase") or runtime.get("phase") or "")
    return str(runtime.get("phase") or "")


def _all_tool_names(result: WorkflowScenarioResult) -> list[str]:
    names: list[str] = []
    for turn in result.turns:
        names.extend(tool_names_from_events(turn.events))
    return names


def _artifact_pattern_failures(
    text: str,
    *,
    required: tuple[str, ...],
    forbidden: tuple[str, ...],
) -> list[str]:
    failures: list[str] = []
    for pattern in required:
        if not re.search(pattern, text or "", flags=re.IGNORECASE):
            failures.append(f"final artifact missing pattern /{pattern}/")
    for pattern in forbidden:
        if re.search(pattern, text or "", flags=re.IGNORECASE):
            failures.append(f"final artifact includes forbidden pattern /{pattern}/")
    return failures


class WorkflowScenarioMetric(BaseMetric):
    """Deterministic: final phase/readiness/tools/artifact for an E2E scenario."""

    def __init__(self, golden: WorkflowScenarioGolden, threshold: float = 1.0):
        self.golden = golden
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
            metadata = test_case.metadata or getattr(test_case, "additional_metadata", None) or {}
            result = _scenario_from_metadata(metadata)
            final_turn = result.final_turn
            failures: list[str] = []

            if len(result.turns) != len(self.golden.messages):
                failures.append(
                    f"expected {len(self.golden.messages)} turns, got {len(result.turns)}"
                )

            phase = _runtime_phase(final_turn.trace, self.golden.workflow)
            if phase != self.golden.expected_final_phase:
                failures.append(
                    f"expected final phase {self.golden.expected_final_phase!r}, got {phase!r}"
                )

            ready = bool(final_turn.final.get("ready"))
            if ready != self.golden.expected_ready:
                failures.append(f"expected final ready={self.golden.expected_ready}, got {ready}")

            names = _all_tool_names(result)
            hits = {name for name in names if name in self.golden.tools_any_of}
            if len(hits) < self.golden.tools_any_of_min:
                failures.append(
                    f"expected at least {self.golden.tools_any_of_min} tool types from "
                    f"{list(self.golden.tools_any_of)!r}, saw {names!r}"
                )

            hygiene = score_trace_hygiene(
                final_turn.trace,
                require_raw_evidence=self.golden.require_raw_evidence,
            )
            failures.extend(hygiene.failures)

            output = actual_output_text(final_turn)
            failures.extend(
                _artifact_pattern_failures(
                    output,
                    required=self.golden.artifact_patterns,
                    forbidden=self.golden.forbidden_artifact_patterns,
                )
            )

            passed = not failures
            self.score = 1.0 if passed else 0.0
            self.reason = "\n".join(f"- {item}" for item in failures) if failures else "Workflow OK."
            self.success = passed
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
        return f"WorkflowScenario[{self.golden.golden_id}]"


class WorkflowGroundedGEval(BaseMetric):
    """LLM-as-judge: final artifact quality against request and retrieved evidence."""

    def __init__(self, golden: WorkflowScenarioGolden, threshold: float = 0.7):
        self.golden = golden
        self.threshold = threshold
        self.strict_mode = False
        self.async_mode = True
        self.include_reason = True
        self.score: float | None = None
        self.reason: str | None = None
        self.success: bool | None = None
        self.error: str | None = None

    def measure(self, test_case: LLMTestCase) -> float:
        try:
            if not self.golden.geval_criteria or os.getenv("RUN_LLM_CHAT_JUDGE", "1") != "1":
                self.score = 1.0
                self.reason = "LLM judge skipped (RUN_LLM_CHAT_JUDGE!=1 or no criteria)."
                self.success = True
                return self.score
            model = os.getenv("DEEPEVAL_MODEL") or os.getenv("OPENAI_FAST_MODEL", "gpt-4o-mini")
            metric = GEval(
                name=f"WorkflowGrounded[{self.golden.golden_id}]",
                criteria=self.golden.geval_criteria,
                evaluation_params=[
                    SingleTurnParams.INPUT,
                    SingleTurnParams.RETRIEVAL_CONTEXT,
                    SingleTurnParams.ACTUAL_OUTPUT,
                ],
                threshold=self.threshold,
                model=model,
            )
            metric.measure(test_case)
            self.score = float(metric.score or 0.0)
            self.reason = metric.reason or ""
            self.success = bool(metric.success)
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
        return f"WorkflowGrounded[{self.golden.golden_id}]"


def build_workflow_test_case(result: WorkflowScenarioResult) -> LLMTestCase:
    final = result.final_turn
    return LLMTestCase(
        input="\n\n---\n\n".join(result.messages),
        actual_output=actual_output_text(final),
        retrieval_context=build_retrieval_context(final),
        metadata={"scenario_result": result},
    )
