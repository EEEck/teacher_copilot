from __future__ import annotations

from app.teacher_agent.memory_capture import canonical_memory_target
from tests.evals.goldens.memory_capture import MEMORY_CAPTURE_GOLDENS


def _by_id(golden_id: str):
    return next(g for g in MEMORY_CAPTURE_GOLDENS if g.golden_id == golden_id)


def test_live_memory_capture_goldens_stay_focused_on_five_core_cases():
    live_ids = tuple(g.golden_id for g in MEMORY_CAPTURE_GOLDENS if g.workflow)

    assert live_ids == (
        "conduct_request_teacher_profile_fast_lane",
        "store_request_teaching_patterns_fast_lane",
        "rich_engagement_observation_not_fast_lane",
        "one_off_task_request_not_fast_lane",
        "compiled_page_never_fast_lane",
    )


def test_store_request_overlap_golden_requires_teaching_pattern_and_planning_brief():
    golden = _by_id("store_request_teaching_patterns_fast_lane")

    assert tuple(map(canonical_memory_target, golden.expected_targets)) == (
        "teaching_patterns.md",
        "planning_brief.md",
    )
    assert golden.expected_min_candidates == 2
    assert "teacher_profile.md" in golden.forbidden_targets
    assert "copilot_profile.md" in golden.forbidden_targets


def test_goldens_default_expected_targets_to_primary_target():
    golden = _by_id("conduct_request_teacher_profile_fast_lane")

    assert golden.expected_targets == ()
    assert canonical_memory_target(golden.target) == "teacher_profile.md"
