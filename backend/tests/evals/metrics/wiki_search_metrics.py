"""DeepEval metrics for deterministic wiki-search component checks."""

from __future__ import annotations

import json
from typing import Any

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

from tests.evals.goldens.wiki_search import WikiSearchGolden


class WikiSearchMetric(BaseMetric):
    """Score source-bounded deterministic wiki search results."""

    def __init__(self, golden: WikiSearchGolden, threshold: float = 1.0):
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
            hits = metadata.get("hits") or []
            rendered = json.dumps(hits, ensure_ascii=False)
            paths = "\n".join(str(hit.get("path", "")) for hit in hits if isinstance(hit, dict))
            failures: list[str] = []

            if not hits:
                failures.append("search returned no hits")

            for marker in self.golden.required_path_markers:
                if marker not in paths:
                    failures.append(f"search paths missing marker {marker!r}")
            for marker in self.golden.required_text_markers:
                if marker.lower() not in rendered.lower():
                    failures.append(f"search hits missing text marker {marker!r}")
            for marker in self.golden.forbidden_path_markers:
                if marker in paths:
                    failures.append(f"search paths include forbidden marker {marker!r}")

            passed = not failures
            self.score = 1.0 if passed else 0.0
            self.reason = "\n".join(f"- {item}" for item in failures) if failures else "Wiki search OK."
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
        return f"WikiSearch[{self.golden.golden_id}]"
