"""Layer-isolation expectations for context pack builders."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from tests.eval.plan_trace_scorer import ScoreResult, _check_markers


class LayerScope(str, Enum):
    GLOBAL_ONLY = "global_only"
    GLOBAL_PLUS_CLASS = "global_plus_class"
    GLOBAL_PLUS_CLASS_PLUS_SUBJECT = "global_plus_class_plus_subject"


@dataclass(frozen=True)
class LayerExpectation:
    golden_id: str
    class_id: str
    layer_scope: LayerScope
    required_markers: tuple[str, ...] = ()
    forbidden_markers: tuple[str, ...] = ()
    subject_id: str = ""
    subject_required_markers: tuple[str, ...] = ()
    required_memory_files: tuple[str, ...] = ()


def _section_text(sections: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for section in sections:
        if not section.get("included", True):
            continue
        parts.append(str(section.get("text", "")))
    return "\n".join(parts)


def _combined_text(
    teacher_trace: dict[str, Any],
    core_trace: dict[str, Any] | None,
    subject_trace: dict[str, Any] | None,
    *,
    layer_scope: LayerScope,
) -> str:
    parts = [str(teacher_trace.get("text", ""))]
    if (
        layer_scope
        in {LayerScope.GLOBAL_PLUS_CLASS, LayerScope.GLOBAL_PLUS_CLASS_PLUS_SUBJECT}
        and core_trace is not None
    ):
        parts.append(_section_text(core_trace.get("sections") or []))
    if (
        layer_scope == LayerScope.GLOBAL_PLUS_CLASS_PLUS_SUBJECT
        and subject_trace is not None
    ):
        parts.append(_section_text(subject_trace.get("sections") or []))
    return "\n".join(parts)


def _subject_section_text(subject_trace: dict[str, Any] | None, subject_id: str) -> str:
    if not subject_trace or not subject_id:
        return ""
    target = f"subject guide: {subject_id}".lower()
    for section in subject_trace.get("sections") or []:
        if not section.get("included", True):
            continue
        if str(section.get("name", "")).lower() == target:
            return str(section.get("text", "")).strip()
    return ""


def score_layer_context(
    *,
    teacher_trace: dict[str, Any],
    core_trace: dict[str, Any] | None,
    subject_trace: dict[str, Any] | None,
    expectation: LayerExpectation,
) -> ScoreResult:
    failures: list[str] = []
    warnings: list[str] = []
    label = expectation.golden_id

    if expectation.layer_scope == LayerScope.GLOBAL_ONLY:
        scored_text = _combined_text(
            teacher_trace, None, None, layer_scope=expectation.layer_scope
        )
    else:
        if core_trace is None:
            failures.append(f"{label}: missing active class core trace")
            return ScoreResult(passed=False, failures=failures, warnings=warnings)
        scored_text = _combined_text(
            teacher_trace,
            core_trace,
            subject_trace
            if expectation.layer_scope == LayerScope.GLOBAL_PLUS_CLASS_PLUS_SUBJECT
            else None,
            layer_scope=expectation.layer_scope,
        )

    if not str(teacher_trace.get("text", "")).strip():
        failures.append(f"{label}: teacher context is empty")

    _check_markers(scored_text, expectation.required_markers, label, failures)
    for marker in expectation.forbidden_markers:
        if marker in scored_text:
            failures.append(f"{label}: forbidden marker present {marker!r}")

    if expectation.layer_scope == LayerScope.GLOBAL_PLUS_CLASS_PLUS_SUBJECT:
        subject_text = _subject_section_text(subject_trace, expectation.subject_id)
        if not subject_text:
            failures.append(
                f"{label}: missing included subject guide section for {expectation.subject_id!r}"
            )
        _check_markers(
            subject_text,
            expectation.subject_required_markers,
            f"{label} subject",
            failures,
        )

    if core_trace and expectation.required_memory_files:
        included_sources = {
            str(section.get("source", ""))
            for section in core_trace.get("sections") or []
            if section.get("included", True)
        }
        for filename in expectation.required_memory_files:
            expected_suffix = f"memory/{filename}"
            if not any(source.endswith(expected_suffix) for source in included_sources):
                failures.append(f"{label}: missing compact memory file {filename!r}")

    return ScoreResult(passed=not failures, failures=failures, warnings=warnings)
