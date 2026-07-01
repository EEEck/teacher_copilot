"""DeepEval metrics for deterministic Memory Sweep checks."""

from __future__ import annotations

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

from tests.evals.goldens.memory_sweep import MemorySweepGolden


class MemorySweepMetric(BaseMetric):
    """Score Memory Sweep grouping and deterministic write boundaries."""

    def __init__(self, golden: MemorySweepGolden, threshold: float = 1.0):
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
            failures: list[str] = []

            grouped_targets: dict[str, list[str]] = metadata.get("grouped_targets") or {}
            for queue, expected_targets in self.golden.expected_queue_targets.items():
                actual = grouped_targets.get(queue, [])
                for target in expected_targets:
                    if target not in actual:
                        failures.append(
                            f"queue {queue!r} missing target {target!r}; saw {actual!r}"
                        )

            applied_paths: list[str] = metadata.get("applied_paths") or []
            for path in self.golden.expected_applied_paths:
                if path not in applied_paths:
                    failures.append(f"applied paths missing {path!r}; saw {applied_paths!r}")

            skipped: list[str] = metadata.get("skipped") or []
            for expected in self.golden.expected_skipped:
                if expected not in skipped:
                    failures.append(f"skipped missing {expected!r}; saw {skipped!r}")

            before_texts: dict[str, str] = metadata.get("before_texts") or {}
            after_texts: dict[str, str] = metadata.get("after_texts") or {}
            for path, markers in self.golden.changed_markers.items():
                after = after_texts.get(path, "")
                before = before_texts.get(path, "")
                if before == after:
                    failures.append(f"expected {path!r} to change")
                for marker in markers:
                    if marker not in after:
                        failures.append(f"{path!r} missing changed marker {marker!r}")

            for path in self.golden.unchanged_paths:
                if before_texts.get(path, "") != after_texts.get(path, ""):
                    failures.append(f"expected {path!r} to remain unchanged")

            remaining_ids: list[str] = metadata.get("remaining_candidate_ids") or []
            for candidate_id in self.golden.absent_after_review:
                if candidate_id in remaining_ids:
                    failures.append(f"candidate {candidate_id!r} reappeared after review")

            passed = not failures
            self.score = 1.0 if passed else 0.0
            self.reason = (
                "\n".join(f"- {item}" for item in failures)
                if failures
                else "Memory Sweep contract OK."
            )
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
        return f"MemorySweep[{self.golden.golden_id}]"
