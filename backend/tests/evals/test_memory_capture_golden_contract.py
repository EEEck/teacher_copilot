from __future__ import annotations

from pathlib import Path

from app.teacher_agent.memory_capture import canonical_memory_target
from tests.evals.goldens.memory_capture import (
    MEMORY_CAPTURE_GOLDENS,
    expected_fast_lane_for_target,
)


def _by_id(golden_id: str):
    return next(g for g in MEMORY_CAPTURE_GOLDENS if g.golden_id == golden_id)


def test_live_memory_capture_goldens_include_the_beta_derived_cases():
    live_ids = tuple(g.golden_id for g in MEMORY_CAPTURE_GOLDENS if g.workflow)

    assert {
        "mbb_session_then_general_style_boundary",
        "light_orbital_preference_class_fast_lane",
        "phenomenon_first_instruction_and_evidence",
        "five_minute_review_no_global_leakage",
        "unknown_scope_no_durable_capture",
    }.issubset(live_ids)


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


def test_live_beta_memory_capture_goldens_pin_scope_and_leakage_boundaries():
    style = _by_id("mbb_session_then_general_style_boundary")
    orbital = _by_id("light_orbital_preference_class_fast_lane")
    review = _by_id("five_minute_review_no_global_leakage")
    unknown = _by_id("unknown_scope_no_durable_capture")

    assert tuple(map(canonical_memory_target, style.expected_targets)) == (
        "teacher_profile.md",
    )
    assert canonical_memory_target(orbital.target) == "copilot_profile.md"
    assert "teacher_profile.md" in tuple(
        map(canonical_memory_target, review.forbidden_targets)
    )
    assert unknown.expect_no_durable_candidates is True
    assert unknown.known_live_gap is True


def test_mixed_instruction_and_evidence_golden_has_one_fast_lane_target():
    golden = _by_id("phenomenon_first_instruction_and_evidence")

    assert expected_fast_lane_for_target(golden, "copilot_profile.md") is True
    assert expected_fast_lane_for_target(golden, "teaching_patterns.md") is False


def test_live_eval_ledger_tracks_all_beta_derived_golden_ids():
    ledger = (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "mem_v4"
        / "mem_v4_live_eval_ledger.md"
    )

    assert ledger.is_file()
    text = ledger.read_text(encoding="utf-8")
    for identifier in (
        "mbb_session_then_general_style_boundary",
        "light_orbital_preference_class_fast_lane",
        "phenomenon_first_instruction_and_evidence",
        "five_minute_review_no_global_leakage",
        "unknown_scope_no_durable_capture",
        "discussion_dota_detour_task_anchor",
        "M4-LIVE-07",
    ):
        assert identifier in text
