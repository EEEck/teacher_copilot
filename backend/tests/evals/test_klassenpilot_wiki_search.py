"""DeepEval wiki-search component goldens."""

from __future__ import annotations

import pytest
from deepeval import assert_test
from deepeval.dataset import Golden
from deepeval.test_case import LLMTestCase

from tests.evals.goldens.wiki_search import WIKI_SEARCH_GOLDENS
from tests.evals.metrics.wiki_search_metrics import WikiSearchMetric


@pytest.mark.parametrize(
    "golden",
    WIKI_SEARCH_GOLDENS,
    ids=[g.golden_id for g in WIKI_SEARCH_GOLDENS],
)
def test_wiki_search_golden(eval_wiki, golden):
    hits = eval_wiki.find_in_memory(golden.class_id, golden.query, max_results=8)
    test_case = LLMTestCase(
        input=golden.query,
        actual_output="",
        metadata={"hits": hits},
    )
    deepeval_golden = Golden(
        input=test_case.input,
        metadata={
            "golden_id": golden.golden_id,
            "class_id": golden.class_id,
        },
    )
    assert_test(
        test_case=test_case,
        metrics=[WikiSearchMetric(golden=golden)],
        golden=deepeval_golden,
        run_async=False,
    )
