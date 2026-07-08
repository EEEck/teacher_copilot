"""Declarative FCKW plan-trace contract aligned with docs/memory_hierarchy.md."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SectionExpectation:
    """One memory contributor that should appear in the startup prompt."""

    canonical_name: str
    aliases: tuple[str, ...] = ()
    source_path: str = ""
    content_markers: tuple[str, ...] = ()
    required: bool = True


@dataclass(frozen=True)
class TurnToolExpectation:
    turn: int
    tools_required: tuple[str, ...] = ()
    tools_any_of: tuple[str, ...] = ()
    tools_any_of_min: int = 1


@dataclass(frozen=True)
class TurnRuntimeExpectation:
    turn: int
    phase: str


@dataclass(frozen=True)
class TurnArtifactExpectation:
    turn: int
    patterns: tuple[str, ...] = ()
    headers_required: tuple[str, ...] = ()


# Section names may drift slightly in prompt_assembly; aliases tolerate renames.
STARTUP_CLASS_SLICE_SECTIONS: tuple[SectionExpectation, ...] = (
    SectionExpectation("Class identity snapshot"),
    SectionExpectation("Top misconceptions", content_markers=("ion charge", "oxidation number")),
    SectionExpectation("Recent lessons", content_markers=("2026-05-25", "Redox")),
    SectionExpectation(
        "Subject guide",
        aliases=("Subject guide: chemie",),
        content_markers=("Confusing oxidation number with ionic charge",),
        source_path="wiki/subjects/chemie.md",
    ),
    SectionExpectation(
        "Planning brief",
        aliases=("Class memory: planning_brief.md",),
        content_markers=("Distinguish ion charge from oxidation number",),
        source_path="memory/planning_brief.md",
    ),
    SectionExpectation(
        "Teaching patterns",
        aliases=("Class memory: teaching_patterns.md",),
        content_markers=("Peer checking", "concrete examples"),
        source_path="memory/teaching_patterns.md",
    ),
    SectionExpectation(
        "Class state",
        aliases=("Class memory: class_state.md",),
        required=False,
        source_path="memory/class_state.md",
    ),
)

STARTUP_PROFILE_SECTIONS: tuple[SectionExpectation, ...] = (
    SectionExpectation(
        "Teacher profile",
        aliases=("Teacher (user.md)",),
        source_path="wiki/teacher_profile.md",
        content_markers=("Prefers concise 45-minute lesson plans", "pair exercises"),
    ),
    SectionExpectation(
        "Class copilot profile",
        aliases=("Copilot working agreement (copilot.md)", "Class memory: copilot_profile.md"),
        source_path="memory/copilot_profile.md",
        content_markers=("Quick diagnostic assessments", "peer checking"),
    ),
)

STARTUP_PROMPT_SECTIONS: tuple[str, ...] = (
    "Plan chat system template",
    "Active skill",
    "Memory policy",
    "Teacher layer",
    "Active class core",
    "Session state",
    "Lesson planning state",
    "Current lesson artifact",
    "Evidence briefs",
    "Wiki tools policy",
)

# Canonical detail and broad roll-ups stay behind tools at startup.
TOOL_ONLY_AT_STARTUP: tuple[str, ...] = (
    "course_state.md",
    "open_loops.md",
    "students.md",
    "lesson_results.md",
)

TURN_TOOL_EXPECTATIONS: tuple[TurnToolExpectation, ...] = (
    TurnToolExpectation(turn=1, tools_required=("search_memory",), tools_any_of=("read_lesson", "read_lesson_range")),
    TurnToolExpectation(
        turn=2,
        tools_any_of=("read_lesson_range", "read_lesson", "list_lessons"),
        tools_any_of_min=1,
    ),
    TurnToolExpectation(turn=3, tools_required=(), tools_any_of=()),
)

TURN_RUNTIME_EXPECTATIONS: tuple[TurnRuntimeExpectation, ...] = (
    TurnRuntimeExpectation(turn=1, phase="lesson_refinement"),
    TurnRuntimeExpectation(turn=2, phase="lesson_refinement"),
    TurnRuntimeExpectation(turn=3, phase="finalize"),
)

TURN_ARTIFACT_EXPECTATIONS: tuple[TurnArtifactExpectation, ...] = (
    TurnArtifactExpectation(
        turn=1,
        headers_required=("Learning goals", "Lesson flow", "Homework", "Teacher notes"),
        patterns=(r"45[\s-]*min", r"FCKW|CFC", r"Montreal Protocol", r"oxidation number", r"charge", r"no real CFCs"),
    ),
    TurnArtifactExpectation(
        turn=2,
        patterns=(r"review|recap", r"confus", r"lecture|lesson"),
    ),
    TurnArtifactExpectation(
        turn=3,
        headers_required=("Learning goals", "Lesson flow"),
        patterns=(r"2[\s-]*min", r"recall"),
    ),
)

LESSON_PLAN_QUALITY_CHECKS: tuple[str, ...] = (
    r"## Learning goals",
    r"## Lesson flow",
    r"## Warmup",
    r"## Practice tasks",
    r"## Homework",
    r"## Teacher notes",
    r"45[\s-]*min",
    r"FCKW|CFC",
    r"Montreal Protocol",
    r"oxidation number",
    r"charge",
)
