from __future__ import annotations

from tests.evals.goldens.discussion import DISCUSSION_GOLDENS
from tests.evals.harness import _workflow_paths


def test_dota_detour_golden_requires_a_brief_return_to_the_teacher_task():
    golden = DISCUSSION_GOLDENS[0]

    assert golden.golden_id == "discussion_dota_detour_task_anchor"
    assert golden.workflow == "discussion"
    assert "briefly" in golden.geval_criteria.lower()
    assert "return" in golden.geval_criteria.lower()
    assert "lesson" in golden.geval_criteria.lower()


def test_eval_harness_supports_discussion_sessions():
    workflow, base, trace = _workflow_paths("discussion", "chemie_9b_2026_27")

    assert workflow == "discussion"
    assert base.endswith("/discussion/sessions")
    assert trace.endswith("/discussion/sessions/{session_id}/trace")
