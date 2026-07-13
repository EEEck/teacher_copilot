"""Shared executive-verification state for teacher-facing workflows."""

from __future__ import annotations

import hashlib
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
    write_verification_fingerprint: str = ""
    write_verification_message: str = ""

    def open_findings(self) -> list[ExecutiveFinding]:
        return [item for item in self.findings.values() if item.status == "open"]

    def open_blocking_findings(self) -> list[ExecutiveFinding]:
        return [
            item
            for item in self.open_findings()
            if item.severity == "blocking"
        ]


@dataclass(frozen=True)
class WriteGateResult:
    allowed: bool
    reason: str = ""


@dataclass(frozen=True)
class WriteVerificationResult:
    artifact_fingerprint: str
    patch: ExecutivePatch
    message: str


class WriteVerificationBlocked(RuntimeError):
    """Raised before a durable action when exact-draft verification blocks it."""

    def __init__(
        self,
        action: str,
        result: WriteVerificationResult,
        gate: WriteGateResult,
        runtime: ExecutiveRuntime,
    ) -> None:
        self.action = action
        self.result = result
        self.gate = gate
        self.runtime = runtime
        message = result.message or "I didn't save this yet; one detail needs your call."
        super().__init__(message)


def artifact_fingerprint(markdown: str) -> str:
    """Return the backend-owned digest for one exact artifact submission."""
    normalized = (markdown or "").replace("\r\n", "\n").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def executive_runtime_dump(runtime: ExecutiveRuntime) -> dict:
    """Serialize executive state for durable workflow-draft persistence."""
    return {
        "findings": {
            finding_id: finding.model_dump()
            for finding_id, finding in runtime.findings.items()
        },
        "checked_categories": sorted(runtime.checked_categories),
        "assumptions": list(runtime.assumptions),
        "verification_summary": runtime.verification_summary,
        "write_verification_fingerprint": runtime.write_verification_fingerprint,
        "write_verification_message": runtime.write_verification_message,
    }


def executive_runtime_load(data: dict | None) -> ExecutiveRuntime:
    """Restore executive state from a workflow-draft payload."""
    payload = data or {}
    findings_raw = payload.get("findings") or {}
    findings: dict[str, ExecutiveFinding] = {}
    if isinstance(findings_raw, dict):
        for finding_id, finding in findings_raw.items():
            if isinstance(finding, dict):
                findings[str(finding_id)] = ExecutiveFinding.model_validate(finding)
    categories = payload.get("checked_categories") or []
    assumptions = payload.get("assumptions") or []
    return ExecutiveRuntime(
        findings=findings,
        checked_categories={str(item) for item in categories},
        assumptions=[str(item) for item in assumptions],
        verification_summary=str(payload.get("verification_summary") or ""),
        write_verification_fingerprint=str(
            payload.get("write_verification_fingerprint") or ""
        ),
        write_verification_message=str(
            payload.get("write_verification_message") or ""
        ),
    )


def enforce_applied_write_verification(
    runtime: ExecutiveRuntime,
    *,
    artifact: str,
    verification: WriteVerificationResult,
    action: str,
    structurally_ready: bool,
) -> None:
    """Apply exact-draft verification and raise when the write gate blocks."""
    apply_write_verification(
        runtime,
        artifact=artifact,
        patch=verification.patch,
        message=verification.message,
    )
    gate = evaluate_write_gate(
        runtime,
        artifact,
        structurally_ready=structurally_ready,
    )
    if not gate.allowed:
        raise WriteVerificationBlocked(action, verification, gate, runtime)


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


def apply_write_verification(
    runtime: ExecutiveRuntime,
    *,
    artifact: str,
    patch: ExecutivePatch,
    message: str = "",
) -> ExecutiveRuntime:
    """Replace open artifact findings with a fresh exact-draft verification."""
    for finding_id, finding in list(runtime.findings.items()):
        if finding.status == "open":
            runtime.findings[finding_id] = finding.model_copy(
                update={
                    "status": "dismissed",
                    "resolution": "Superseded by fresh write verification.",
                }
            )
    apply_executive_patch(runtime, patch)
    runtime.write_verification_fingerprint = artifact_fingerprint(artifact)
    runtime.write_verification_message = _clean(message)
    return runtime


def evaluate_write_gate(
    runtime: ExecutiveRuntime,
    artifact: str,
    *,
    structurally_ready: bool,
) -> WriteGateResult:
    """Allow a durable action only for the current verified artifact."""
    if not structurally_ready:
        return WriteGateResult(False, "artifact_not_ready")
    if runtime.write_verification_fingerprint != artifact_fingerprint(artifact):
        return WriteGateResult(False, "artifact_changed_since_verification")
    if runtime.open_blocking_findings():
        return WriteGateResult(False, "unresolved_blocking_finding")
    return WriteGateResult(True)


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
