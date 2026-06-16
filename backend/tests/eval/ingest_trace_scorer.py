"""Score ingest trace bundles against Update Memory startup contract."""

from __future__ import annotations

from typing import Any

from tests.eval.fckw_contract import STARTUP_CLASS_SLICE_SECTIONS, STARTUP_PROFILE_SECTIONS
from tests.eval.plan_trace_scorer import ScoreResult, _check_markers


def score_ingest_startup_context(trace: dict[str, Any]) -> ScoreResult:
    """Verify Update Memory startup trace before the first teacher turn."""
    failures: list[str] = []
    warnings: list[str] = []

    stack = trace.get("prompt_stack") or {}
    required_stack_keys = (
        "ingest_context",
        "teacher_context",
        "active_class_core",
        "memory_target_state",
        "memory_session_state",
        "lesson_result_state",
        "memory_evidence_briefs",
        "current_diary_markdown",
    )
    for key in required_stack_keys:
        if key not in stack:
            failures.append(f"prompt_stack missing key {key!r}")

    ingest_context = stack.get("ingest_context") or ""
    teacher_context = stack.get("teacher_context") or ""
    active_class_core = stack.get("active_class_core") or ""
    if "AGENTS.md" in ingest_context:
        failures.append("ingest_context must not include AGENTS.md")
    if "Wiki logging conventions" in ingest_context:
        failures.append("ingest_context must not include Wiki logging conventions")
    if "Class Copilot Profile" not in active_class_core:
        failures.append("active_class_core missing Class Copilot Profile")

    assembly = trace.get("prompt_assembly") or {}
    if assembly.get("stage") != "ingest_chat":
        failures.append(f"expected prompt_assembly.stage ingest_chat, got {assembly.get('stage')!r}")

    section_names = [str(s.get("name", "")) for s in assembly.get("sections") or []]
    for required in (
        "Teacher layer",
        "Active class core",
        "Memory target state",
        "Memory session state",
        "Lesson result state",
        "Memory evidence briefs",
    ):
        if required not in section_names:
            failures.append(f"prompt_assembly missing section {required!r}")
    if section_names.count("Teacher layer") != 1:
        failures.append("prompt_assembly must include Teacher layer exactly once")
    if section_names.count("Active class core") != 1:
        failures.append("prompt_assembly must include Active class core exactly once")

    for singleton in (
        "Update Memory task context",
        "Memory target state",
        "Memory session state",
        "Lesson result state",
        "Memory evidence briefs",
    ):
        if section_names.count(singleton) != 1:
            failures.append(f"prompt_assembly must include {singleton} exactly once")

    runtime = trace.get("runtime") or {}
    if runtime.get("phase") != "identify_target":
        failures.append(f"expected runtime.phase identify_target, got {runtime.get('phase')!r}")
    target = runtime.get("target") or {}
    if target.get("target_confirmed") is not False:
        failures.append("expected target_confirmed False before first message")

    if trace.get("event_trace"):
        failures.append("event_trace must be empty before first message")

    if not teacher_context.strip():
        failures.append("prompt_stack.teacher_context is empty")
    if not active_class_core.strip():
        failures.append("prompt_stack.active_class_core is empty")

    _check_markers(teacher_context, ("Prefers concise 45-minute lesson plans",), "teacher_context", failures)
    _check_markers(active_class_core, ("Quick diagnostic assessments",), "copilot_profile", failures)
    _check_markers(
        active_class_core,
        ("Planning brief", "Teaching patterns", "Top misconceptions"),
        "active_class_core",
        failures,
    )

    for expectation in STARTUP_CLASS_SLICE_SECTIONS:
        if not expectation.required or not expectation.content_markers:
            continue
        _check_markers(
            active_class_core,
            expectation.content_markers,
            expectation.canonical_name,
            failures,
        )

    for expectation in STARTUP_PROFILE_SECTIONS:
        if expectation.canonical_name == "Teacher profile":
            _check_markers(
                teacher_context,
                expectation.content_markers,
                expectation.canonical_name,
                failures,
            )
        elif expectation.canonical_name == "Class copilot profile":
            _check_markers(
                active_class_core,
                expectation.content_markers,
                expectation.canonical_name,
                failures,
            )

    instructions = assembly.get("instructions") or ""
    forbidden_markers = (
        "teacher_wiki/AGENTS.md",
        "AGENTS.md",
        "Wiki logging conventions",
        "Subject guide: ESL",
        "wiki/subjects/ESL.md",
        "Subject guide: mathe",
    )
    for marker in forbidden_markers:
        if marker in instructions or marker in active_class_core or marker in teacher_context:
            failures.append(f"ingest prompt context includes forbidden marker {marker!r}")
    if "Teacher context (global)" not in instructions and "Teacher and copilot profile" not in instructions:
        failures.append("rendered instructions missing teacher context block")
    if "Active class core context" not in instructions and "Class memory (compact)" not in instructions:
        failures.append("rendered instructions missing active class core block")

    return ScoreResult(passed=not failures, failures=failures, warnings=warnings)
