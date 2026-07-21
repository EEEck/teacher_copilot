"""Shared memory target policy tests."""

from __future__ import annotations

from app.teacher_agent.memory_targets import (
    canonical_memory_target,
    compact_key_for_target,
    is_global_teacher_target,
    is_supported_runtime_target,
    memory_channel_for_target,
)


def test_memory_target_policy_covers_doc_44_targets():
    assert memory_channel_for_target("teaching_patterns.md") == "class_learning_pattern"
    assert compact_key_for_target("teaching_patterns.md") == "teaching_patterns"
    assert (
        compact_key_for_target("teaching_framework_adjustments.md")
        == "teaching_framework_adjustments"
    )
    assert is_supported_runtime_target("teaching_framework_adjustments.md")

    assert memory_channel_for_target("wiki/subjects/chemie.md") == "subject_concept"
    assert is_supported_runtime_target("wiki/subjects/chemie.md")

    assert memory_channel_for_target("teacher_profile.md") == "teacher_behavior"
    assert is_global_teacher_target("teacher_profile.md")
    assert canonical_memory_target("teacher_profile.md") == "teacher_profile.md"
    assert canonical_memory_target("user.md") == "teacher_profile.md"

    assert memory_channel_for_target("copilot_profile.md") == "teacher_behavior"
    assert canonical_memory_target("copilot_profile.md") == "copilot_profile.md"
    assert canonical_memory_target("copilot.md") == "copilot_profile.md"

    assert not is_supported_runtime_target("wiki/classes/chemie_9b_2026_27/timeline.md")
    assert not is_supported_runtime_target("../subjects/chemie.md")


def test_retired_compact_targets_are_no_longer_durable():
    """mem_v3 PR2: class_state.md / taught_so_far.md were retired.

    Their "current unit / taught sequence" facts are derived from the canonical
    course_state.md / timeline.md rollups, so they are no longer supported
    durable targets and do not route to a compact memory page.
    """
    for retired in ("class_state.md", "taught_so_far.md"):
        assert compact_key_for_target(retired) is None
        assert not is_supported_runtime_target(retired)
        # No longer routed to the class-evolution channel; falls through.
        assert memory_channel_for_target(retired) == "memory_sweep"
