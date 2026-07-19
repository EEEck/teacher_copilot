"""Shared target policy for durable memory candidates and apply routes."""

from __future__ import annotations

import re

TEACHER_PROFILE_TARGETS = {"user.md", "teacher_profile.md"}
COPILOT_PROFILE_TARGETS = {"copilot.md", "copilot_profile.md"}
TEACHING_FRAMEWORK_PROFILE_TARGET = "teaching_framework_profile.md"
# class_state.md and taught_so_far.md were retired (mem_v3 PR2): the "current
# unit / taught sequence" facts they held are deterministic projections of the
# diary + timeline and now live only in the canonical rollups (course_state.md,
# timeline.md). The sweep reads those; it no longer curates compact twins.
COMPACT_TARGETS = {
    "planning_brief.md": "planning_brief",
    "teaching_patterns.md": "teaching_patterns",
}
CANONICAL_REVIEW_TARGET = "canonical_wiki"
TARGET_ALIASES = {
    "user.md": "teacher_profile.md",
    "copilot.md": "copilot_profile.md",
}
STUDENT_PAGE_RE = re.compile(r"students/s-\d{3}\.md")


def normalize_memory_target(target: str) -> str:
    return (target or "").strip().lower()


def canonical_memory_target(target: str) -> str:
    normalized = normalize_memory_target(target)
    if STUDENT_PAGE_RE.fullmatch(normalized):
        sid = normalized.removesuffix(".md").rsplit("/", 1)[-1].upper()
        return f"students/{sid}.md"
    return TARGET_ALIASES.get(normalized, normalized)


def is_subject_guide_target(target: str) -> bool:
    return (
        re.fullmatch(r"wiki/subjects/[a-z0-9_-]+\.md", normalize_memory_target(target))
        is not None
    )


def is_student_page_target(target: str) -> bool:
    return STUDENT_PAGE_RE.fullmatch(normalize_memory_target(target)) is not None


def student_id_from_target(target: str) -> str | None:
    if not is_student_page_target(target):
        return None
    return normalize_memory_target(target).removesuffix(".md").rsplit("/", 1)[-1].upper()


def is_global_teacher_target(target: str) -> bool:
    return normalize_memory_target(target) in TEACHER_PROFILE_TARGETS


def compact_key_for_target(target: str) -> str | None:
    return COMPACT_TARGETS.get(canonical_memory_target(target))


def is_supported_runtime_target(target: str) -> bool:
    normalized = canonical_memory_target(target)
    return (
        normalized in TEACHER_PROFILE_TARGETS
        or normalized in COPILOT_PROFILE_TARGETS
        or normalized == TEACHING_FRAMEWORK_PROFILE_TARGET
        or normalized in COMPACT_TARGETS
        or normalized == CANONICAL_REVIEW_TARGET
        or is_subject_guide_target(normalized)
        or is_student_page_target(normalized)
    )


# Mem V3: fixed section vocabulary per target (docs/mem_v3/design.md lane 1).
# Capture LLMs invent section names freely; free-form sections fragment
# cluster keys and sweep grouping, so ledger inserts normalize onto this
# vocabulary. First entry per target is the default bucket.
SECTION_VOCABULARY: dict[str, tuple[str, ...]] = {
    "teaching_patterns.md": (
        "class_learning_profile",
        "what_worked_well",
        "what_didnt_work",
    ),
    "copilot_profile.md": (
        "planning_patterns",
        "avoid_rules",
        "structuring_lessons",
        "communication",
    ),
    "teacher_profile.md": (
        "communication",
        "lesson_style",
        "language",
    ),
    "planning_brief.md": ("planning_notes",),
}

_SECTION_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _section_tokens(value: str) -> set[str]:
    return {
        token
        for token in _SECTION_TOKEN_RE.findall((value or "").lower())
        if len(token) >= 3
    }


def normalize_section(target: str, section: str) -> str:
    """Map a free-form section name onto the target's fixed vocabulary.

    Exact (snake-normalized) matches win; otherwise the vocabulary entry with
    the largest token overlap; otherwise the target's default bucket.
    Targets without a vocabulary keep their snake-normalized section.
    """
    canonical_target = canonical_memory_target(target)
    snake = "_".join(_SECTION_TOKEN_RE.findall((section or "").lower()))
    vocabulary = SECTION_VOCABULARY.get(canonical_target)
    if not vocabulary:
        return snake or "notes"
    if snake in vocabulary:
        return snake
    tokens = _section_tokens(snake)
    best: tuple[int, str] | None = None
    for entry in vocabulary:
        overlap = len(tokens & _section_tokens(entry))
        if overlap > 0 and (best is None or overlap > best[0]):
            best = (overlap, entry)
    if best is not None:
        return best[1]
    return vocabulary[0]


def memory_channel_for_target(target: str) -> str:
    normalized = canonical_memory_target(target)
    if normalized in TEACHER_PROFILE_TARGETS or normalized in COPILOT_PROFILE_TARGETS:
        return "teacher_behavior"
    if normalized == TEACHING_FRAMEWORK_PROFILE_TARGET:
        return "class_teaching_framework"
    if normalized == "teaching_patterns.md":
        return "class_learning_pattern"
    if normalized == "planning_brief.md":
        return "class_evolution"
    if is_subject_guide_target(normalized):
        return "subject_concept"
    if is_student_page_target(normalized):
        return "student_memory"
    if normalized == CANONICAL_REVIEW_TARGET:
        return "wiki_lint"
    return "memory_sweep"
