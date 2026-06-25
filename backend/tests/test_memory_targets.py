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

    assert memory_channel_for_target("wiki/subjects/chemie.md") == "subject_concept"
    assert is_supported_runtime_target("wiki/subjects/chemie.md")

    assert memory_channel_for_target("user.md") == "teacher_behavior"
    assert is_global_teacher_target("teacher_profile.md")
    assert canonical_memory_target("teacher_profile.md") == "user.md"

    assert memory_channel_for_target("copilot.md") == "teacher_behavior"
    assert canonical_memory_target("copilot_profile.md") == "copilot.md"

    assert not is_supported_runtime_target("wiki/classes/chemie_9b_2026_27/timeline.md")
    assert not is_supported_runtime_target("../subjects/chemie.md")
