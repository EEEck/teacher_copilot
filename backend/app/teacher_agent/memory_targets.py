"""Shared target policy for durable memory candidates and apply routes."""

from __future__ import annotations

import re

TEACHER_PROFILE_TARGETS = {"user.md", "teacher_profile.md"}
COPILOT_PROFILE_TARGETS = {"copilot.md", "copilot_profile.md"}
COMPACT_TARGETS = {
    "class_state.md": "class_state",
    "planning_brief.md": "planning_brief",
    "taught_so_far.md": "taught_so_far",
    "teaching_patterns.md": "teaching_patterns",
}
CANONICAL_REVIEW_TARGET = "canonical_wiki"
TARGET_ALIASES = {
    "teacher_profile.md": "user.md",
    "copilot_profile.md": "copilot.md",
}


def normalize_memory_target(target: str) -> str:
    return (target or "").strip().lower()


def canonical_memory_target(target: str) -> str:
    normalized = normalize_memory_target(target)
    return TARGET_ALIASES.get(normalized, normalized)


def is_subject_guide_target(target: str) -> bool:
    return (
        re.fullmatch(r"wiki/subjects/[a-z0-9_-]+\.md", normalize_memory_target(target))
        is not None
    )


def is_global_teacher_target(target: str) -> bool:
    return normalize_memory_target(target) in TEACHER_PROFILE_TARGETS


def compact_key_for_target(target: str) -> str | None:
    return COMPACT_TARGETS.get(normalize_memory_target(target))


def is_supported_runtime_target(target: str) -> bool:
    normalized = normalize_memory_target(target)
    return (
        normalized in TEACHER_PROFILE_TARGETS
        or normalized in COPILOT_PROFILE_TARGETS
        or normalized in COMPACT_TARGETS
        or normalized == CANONICAL_REVIEW_TARGET
        or is_subject_guide_target(normalized)
    )


def memory_channel_for_target(target: str) -> str:
    normalized = normalize_memory_target(target)
    if normalized in TEACHER_PROFILE_TARGETS or normalized in COPILOT_PROFILE_TARGETS:
        return "teacher_behavior"
    if normalized == "teaching_patterns.md":
        return "class_learning_pattern"
    if normalized in {"class_state.md", "planning_brief.md", "taught_so_far.md"}:
        return "class_evolution"
    if is_subject_guide_target(normalized):
        return "subject_concept"
    if normalized == CANONICAL_REVIEW_TARGET:
        return "wiki_lint"
    return "memory_sweep"
