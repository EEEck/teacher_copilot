"""Shared executive-verification state for teacher-facing workflows."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

VerificationCategory = Literal[
    "scope",
    "identity",
    "time_state",
    "grounding",
    "persistence",
    "consequence",
]
FindingSeverity = Literal["advisory", "blocking"]
FindingStatus = Literal["open", "resolved", "dismissed"]


class ExecutiveFinding(BaseModel):
    finding_id: str
    category: VerificationCategory
    severity: FindingSeverity
    summary: str
    question: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    status: FindingStatus = "open"
    resolution: str = ""

    @model_validator(mode="after")
    def blocking_findings_require_a_question(self):
        if self.severity == "blocking" and not self.question.strip():
            raise ValueError("blocking findings require a teacher question")
        return self


class ExecutiveResolution(BaseModel):
    finding_id: str
    resolution: str


class ExecutivePatch(BaseModel):
    checked_categories: list[VerificationCategory] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    findings: list[ExecutiveFinding] = Field(default_factory=list)
    resolved_findings: list[ExecutiveResolution] = Field(default_factory=list)
    verification_summary: str = ""

    @field_validator("resolved_findings", mode="before")
    @classmethod
    def accept_legacy_resolution_map(cls, value):
        if isinstance(value, dict):
            return [
                {"finding_id": finding_id, "resolution": resolution}
                for finding_id, resolution in value.items()
            ]
        return value


@dataclass
class ExecutiveRuntime:
    findings: dict[str, ExecutiveFinding] = field(default_factory=dict)
    checked_categories: set[str] = field(default_factory=set)
    assumptions: list[str] = field(default_factory=list)
    verification_summary: str = ""

    def open_findings(self) -> list[ExecutiveFinding]:
        return [item for item in self.findings.values() if item.status == "open"]

    def open_blocking_findings(self) -> list[ExecutiveFinding]:
        return [
            item
            for item in self.open_findings()
            if item.severity == "blocking"
        ]


def _clean(value: str) -> str:
    return " ".join((value or "").split())


def apply_executive_patch(
    runtime: ExecutiveRuntime, patch: ExecutivePatch
) -> ExecutiveRuntime:
    runtime.checked_categories.update(patch.checked_categories)
    for assumption in patch.assumptions:
        text = _clean(assumption)
        if text and text not in runtime.assumptions:
            runtime.assumptions.append(text)
    for finding in patch.findings:
        runtime.findings[finding.finding_id] = finding
    for resolved in patch.resolved_findings:
        existing = runtime.findings.get(resolved.finding_id)
        text = _clean(resolved.resolution)
        if existing and text:
            runtime.findings[resolved.finding_id] = existing.model_copy(
                update={"status": "resolved", "resolution": text}
            )
    summary = _clean(patch.verification_summary)
    if summary:
        runtime.verification_summary = summary
    return runtime


def executive_api_payload(runtime: ExecutiveRuntime) -> dict:
    open_findings = [item.model_dump() for item in runtime.open_findings()]
    if any(item["severity"] == "blocking" for item in open_findings):
        status = "needs_decision"
    elif open_findings:
        status = "advisory"
    else:
        status = "clear"
    return {
        "status": status,
        "open_findings": open_findings,
        "assumptions": runtime.assumptions[-5:],
        "checked_categories": sorted(runtime.checked_categories),
        "verification_summary": runtime.verification_summary,
    }


def render_executive_runtime(runtime: ExecutiveRuntime) -> str:
    return (
        "<executive_state>\n"
        + json.dumps(executive_api_payload(runtime), ensure_ascii=False, indent=2)
        + "\n</executive_state>"
    )
