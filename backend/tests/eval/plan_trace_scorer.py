"""Score plan trace bundles against the FCKW behavioral contract.

No third-party eval dependencies. Uses trace JSON structure from PlanTraceResponse
and optional per-turn SSE event lists for tool-call attribution.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tests.eval.fckw_contract import (
    LESSON_PLAN_QUALITY_CHECKS,
    STARTUP_CLASS_SLICE_SECTIONS,
    STARTUP_PROFILE_SECTIONS,
    STARTUP_PROMPT_SECTIONS,
    TOOL_ONLY_AT_STARTUP,
    TURN_ARTIFACT_EXPECTATIONS,
    TURN_RUNTIME_EXPECTATIONS,
    TURN_TOOL_EXPECTATIONS,
    SectionExpectation,
)


@dataclass
class ScoreResult:
    passed: bool
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def assert_ok(self) -> None:
        if self.failures:
            joined = "\n".join(f"- {item}" for item in self.failures)
            raise AssertionError(f"Plan trace contract failed:\n{joined}")


def _normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def _section_names(sections: list[dict[str, Any]], *, included_only: bool = True) -> set[str]:
    names: set[str] = set()
    for sec in sections:
        if included_only and not sec.get("included", True):
            continue
        names.add(_normalize_name(str(sec.get("name", ""))))
    return names


def _match_section(expectation: SectionExpectation, available: set[str]) -> bool:
    candidates = {_normalize_name(expectation.canonical_name), *(_normalize_name(a) for a in expectation.aliases)}
    return bool(candidates & available)


def _find_section(
    sections: list[dict[str, Any]],
    expectation: SectionExpectation,
) -> dict[str, Any] | None:
    for sec in sections:
        names = {_normalize_name(str(sec.get("name", "")))}
        candidates = {_normalize_name(expectation.canonical_name), *(_normalize_name(a) for a in expectation.aliases)}
        if names & candidates:
            return sec
    return None


def _check_markers(text: str, markers: tuple[str, ...], label: str, failures: list[str]) -> None:
    haystack = text or ""
    for marker in markers:
        if marker not in haystack:
            failures.append(f"{label}: missing content marker {marker!r}")


def _check_patterns(text: str, patterns: tuple[str, ...], label: str, failures: list[str]) -> None:
    haystack = text or ""
    for pattern in patterns:
        if not re.search(pattern, haystack, flags=re.IGNORECASE):
            failures.append(f"{label}: pattern did not match /{pattern}/")


_TOP_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "Teacher layer": ("Profiles",),
    "Active class core": ("Class slice",),
}


def _has_top_section(expected: str, available: set[str]) -> bool:
    names = {_normalize_name(expected)}
    names.update(_normalize_name(alias) for alias in _TOP_SECTION_ALIASES.get(expected, ()))
    return bool(names & available)


def score_startup_context(trace: dict[str, Any]) -> ScoreResult:
    """Verify memory hierarchy contributors are present before the first teacher turn."""
    failures: list[str] = []
    warnings: list[str] = []
    assembly = trace.get("prompt_assembly") or {}
    nested = assembly.get("nested") or {}
    class_trace = nested.get("active_class_core") or nested.get("class_slice") or {}
    teacher_trace = nested.get("teacher_context") or {}
    old_profile_trace = nested.get("profiles") or {}
    class_sections = class_trace.get("sections") or []
    profile_sections = (teacher_trace.get("sections") or []) + (old_profile_trace.get("sections") or [])
    top_sections = assembly.get("sections") or []

    included_class = _section_names(class_sections, included_only=True)
    included_profiles = _section_names(profile_sections, included_only=True)
    included_class_or_profile = _section_names(
        [*class_sections, *profile_sections], included_only=True
    )
    included_top = _section_names(top_sections, included_only=False)

    for expected in STARTUP_PROMPT_SECTIONS:
        if not _has_top_section(expected, included_top):
            failures.append(f"prompt_assembly missing top-level section {expected!r}")

    for singleton in ("Teacher layer", "Active class core"):
        count = sum(
            1
            for section in top_sections
            if _has_top_section(singleton, {_normalize_name(str(section.get("name", "")))})
        )
        if count != 1:
            failures.append(f"prompt_assembly must include {singleton!r} exactly once, got {count}")

    for expectation in STARTUP_CLASS_SLICE_SECTIONS:
        if not expectation.required:
            sec = _find_section(class_sections, expectation)
            if sec and not sec.get("included", True):
                warnings.append(
                    f"optional class slice section {expectation.canonical_name!r} not included "
                    f"(source {expectation.source_path or 'n/a'})"
                )
            continue
        if not _match_section(expectation, included_class):
            failures.append(f"class slice missing required section {expectation.canonical_name!r}")
            continue
        sec = _find_section(class_sections, expectation)
        if sec:
            _check_markers(str(sec.get("text", "")), expectation.content_markers, expectation.canonical_name, failures)

    for expectation in STARTUP_PROFILE_SECTIONS:
        if not _match_section(expectation, included_class_or_profile):
            failures.append(f"profiles missing required section {expectation.canonical_name!r}")
            continue
        sec = _find_section([*profile_sections, *class_sections], expectation)
        if sec and not sec.get("included", True):
            failures.append(f"profiles section {expectation.canonical_name!r} exists but is not included")
        elif sec:
            _check_markers(str(sec.get("text", "")), expectation.content_markers, expectation.canonical_name, failures)

    stack = trace.get("prompt_stack") or {}
    teacher_text = stack.get("teacher_context") or stack.get("teacher_profile", "")
    class_text = stack.get("active_class_core") or stack.get("class_slice", "")
    copilot_text = stack.get("copilot_profile") or class_text
    if not teacher_text.strip():
        failures.append("prompt_stack.teacher_context is empty")
    if not class_text.strip():
        failures.append("prompt_stack.active_class_core is empty")
    if not copilot_text.strip():
        failures.append("copilot profile text is empty")

    _check_markers(teacher_text, ("Prefers concise 45-minute lesson plans",), "teacher_context", failures)
    _check_markers(copilot_text, ("Quick diagnostic assessments",), "copilot_profile", failures)
    _check_markers(
        class_text,
        ("Planning brief", "Teaching patterns", "Top misconceptions"),
        "active_class_core",
        failures,
    )

    for tool_only in TOOL_ONLY_AT_STARTUP:
        if tool_only in class_text:
            warnings.append(
                f"{tool_only} appears in startup class slice; memory_hierarchy expects tool-fetch only"
            )

    forbidden_startup_markers = (
        "teacher_wiki/AGENTS.md",
        "AGENTS.md",
        "Wiki logging conventions",
        "Subject guide: ESL",
        "wiki/subjects/ESL.md",
        "Subject guide: mathe",
    )
    for marker in forbidden_startup_markers:
        if marker in class_text or marker in teacher_text:
            failures.append(f"startup context includes forbidden marker {marker!r}")

    instructions = assembly.get("instructions") or ""
    for marker in forbidden_startup_markers:
        if marker in instructions:
            failures.append(f"rendered instructions include forbidden marker {marker!r}")
    if "Teacher context (global)" not in instructions and "Teacher and copilot profile" not in instructions:
        failures.append("rendered instructions missing teacher context block")
    if "Active class core context" not in instructions and "Class memory (compact)" not in instructions:
        failures.append("rendered instructions missing active class core block")

    return ScoreResult(passed=not failures, failures=failures, warnings=warnings)


def tool_names_from_events(events: list[dict[str, Any]]) -> list[str]:
    return [str(e.get("name", "")) for e in events if e.get("type") == "tool_call" and e.get("name")]


def score_turn_tools(turn: int, events: list[dict[str, Any]]) -> ScoreResult:
    failures: list[str] = []
    names = tool_names_from_events(events)
    expectation = next((item for item in TURN_TOOL_EXPECTATIONS if item.turn == turn), None)
    if expectation is None:
        return ScoreResult(passed=True)

    for required in expectation.tools_required:
        if required not in names:
            failures.append(f"turn {turn}: missing required tool {required!r} (saw {names!r})")

    if expectation.tools_any_of:
        hits = [name for name in expectation.tools_any_of if name in names]
        if len(hits) < expectation.tools_any_of_min:
            failures.append(
                f"turn {turn}: expected at least {expectation.tools_any_of_min} of "
                f"{list(expectation.tools_any_of)!r}, saw {names!r}"
            )

    return ScoreResult(passed=not failures, failures=failures)


def score_turn_runtime(trace: dict[str, Any], turn: int) -> ScoreResult:
    failures: list[str] = []
    expectation = next((item for item in TURN_RUNTIME_EXPECTATIONS if item.turn == turn), None)
    if expectation is None:
        return ScoreResult(passed=True)

    runtime = trace.get("runtime") or {}
    session_state = runtime.get("session_state") or {}
    phase = session_state.get("phase")
    if phase != expectation.phase:
        failures.append(f"turn {turn}: expected phase {expectation.phase!r}, got {phase!r}")

    if turn == 1:
        duration = (runtime.get("lesson_planning_state") or {}).get("duration_minutes")
        if duration not in (45, None):
            failures.append(f"turn {turn}: expected duration_minutes 45, got {duration!r}")

    return ScoreResult(passed=not failures, failures=failures)


def score_turn_artifact(artifact_md: str, turn: int) -> ScoreResult:
    failures: list[str] = []
    expectation = next((item for item in TURN_ARTIFACT_EXPECTATIONS if item.turn == turn), None)
    if expectation is None:
        return ScoreResult(passed=True)

    label = f"turn {turn} artifact"
    for header in expectation.headers_required:
        if header not in (artifact_md or ""):
            failures.append(f"{label}: missing header {header!r}")
    _check_patterns(artifact_md or "", expectation.patterns, label, failures)
    return ScoreResult(passed=not failures, failures=failures)


def score_final_lesson_plan(artifact_md: str) -> ScoreResult:
    failures: list[str] = []
    _check_patterns(artifact_md or "", LESSON_PLAN_QUALITY_CHECKS, "final lesson plan", failures)
    if artifact_md and len(artifact_md.strip()) < 400:
        failures.append("final lesson plan looks too short (< 400 chars)")
    return ScoreResult(passed=not failures, failures=failures)


def score_trace_hygiene(trace: dict[str, Any], *, require_raw_evidence: bool = False) -> ScoreResult:
    failures: list[str] = []
    event_types = [str(e.get("type", "")) for e in trace.get("event_trace") or []]
    if "reasoning_delta" in event_types:
        failures.append("trace event_trace contains reasoning_delta noise")
    if require_raw_evidence and trace.get("raw_evidence") in (None, {}):
        failures.append("trace raw_evidence is empty after browsing turns")
    return ScoreResult(passed=not failures, failures=failures)


def merge_results(*results: ScoreResult) -> ScoreResult:
    failures: list[str] = []
    warnings: list[str] = []
    for result in results:
        failures.extend(result.failures)
        warnings.extend(result.warnings)
    return ScoreResult(passed=not failures, failures=failures, warnings=warnings)


def score_fckw_scenario(
    *,
    trace_before_turn_1: dict[str, Any],
    traces_after_turns: list[dict[str, Any]],
    events_per_turn: list[list[dict[str, Any]]],
    final_artifact: str,
    require_raw_evidence: bool = False,
) -> ScoreResult:
    """Score a complete three-turn FCKW run."""
    parts = [score_startup_context(trace_before_turn_1)]

    for idx, trace in enumerate(traces_after_turns, start=1):
        turn_events = events_per_turn[idx - 1] if idx - 1 < len(events_per_turn) else []
        artifact = (
            trace.get("artifact_markdown") or final_artifact
            if idx == len(traces_after_turns)
            else trace.get("artifact_markdown", "")
        )
        parts.extend(
            [
                score_turn_tools(idx, turn_events),
                score_turn_runtime(trace, idx),
                score_turn_artifact(artifact or "", idx),
            ]
        )

    parts.append(score_final_lesson_plan(final_artifact))
    parts.append(
        score_trace_hygiene(traces_after_turns[-1], require_raw_evidence=require_raw_evidence)
    )
    return merge_results(*parts)


def load_trace_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
