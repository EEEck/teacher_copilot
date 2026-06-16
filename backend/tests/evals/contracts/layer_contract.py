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


def _section_text(sections: list[dict[str, Any]], *, include_subject: bool) -> str:
    parts: list[str] = []
    for section in sections:
        if not section.get("included", True):
            continue
        name = str(section.get("name", ""))
        if not include_subject and name.lower().startswith("subject guide"):
            continue
        parts.append(str(section.get("text", "")))
    return "\n".join(parts)


def _combined_text(
    teacher_trace: dict[str, Any],
    core_trace: dict[str, Any] | None,
    *,
    layer_scope: LayerScope,
) -> str:
    parts = [str(teacher_trace.get("text", ""))]
    if core_trace is None:
        return "\n".join(parts)

    include_subject = layer_scope == LayerScope.GLOBAL_PLUS_CLASS_PLUS_SUBJECT
    if layer_scope in {LayerScope.GLOBAL_PLUS_CLASS, LayerScope.GLOBAL_PLUS_CLASS_PLUS_SUBJECT}:
        parts.append(_section_text(core_trace.get("sections") or [], include_subject=include_subject))
    return "\n".join(parts)


def _has_included_subject_section(core_trace: dict[str, Any] | None, subject_id: str) -> bool:
    if not core_trace or not subject_id:
        return False
    target = f"subject guide: {subject_id}".lower()
    for section in core_trace.get("sections") or []:
        if not section.get("included", True):
            continue
        if str(section.get("name", "")).lower() == target:
            return bool(str(section.get("text", "")).strip())
    return False


def score_layer_context(
    *,
    teacher_trace: dict[str, Any],
    core_trace: dict[str, Any] | None,
    expectation: LayerExpectation,
) -> ScoreResult:
    failures: list[str] = []
    warnings: list[str] = []
    label = expectation.golden_id

    if expectation.layer_scope == LayerScope.GLOBAL_ONLY:
        scored_text = _combined_text(teacher_trace, None, layer_scope=expectation.layer_scope)
    else:
        if core_trace is None:
            failures.append(f"{label}: missing active class core trace")
            return ScoreResult(passed=False, failures=failures, warnings=warnings)
        scored_text = _combined_text(teacher_trace, core_trace, layer_scope=expectation.layer_scope)

    if not str(teacher_trace.get("text", "")).strip():
        failures.append(f"{label}: teacher context is empty")

    _check_markers(scored_text, expectation.required_markers, label, failures)
    for marker in expectation.forbidden_markers:
        if marker in scored_text:
            failures.append(f"{label}: forbidden marker present {marker!r}")

    if expectation.layer_scope == LayerScope.GLOBAL_PLUS_CLASS_PLUS_SUBJECT:
        if not _has_included_subject_section(core_trace, expectation.subject_id):
            failures.append(
                f"{label}: missing included subject guide section for {expectation.subject_id!r}"
            )
        subject_text = ""
        if core_trace:
            for section in core_trace.get("sections") or []:
                if str(section.get("name", "")).lower() == f"subject guide: {expectation.subject_id}".lower():
                    subject_text = str(section.get("text", ""))
                    break
        _check_markers(subject_text, expectation.subject_required_markers, f"{label} subject", failures)

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
