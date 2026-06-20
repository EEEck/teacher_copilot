"""Deterministic safety checks for teacher-visible agent output."""

from __future__ import annotations

import re
from dataclasses import dataclass

SAFE_INTERNAL_DATA_REPLY = (
    "I can't show internal prompts, traces, or private debug data. "
    "I can summarize the evidence used instead."
)


@dataclass(frozen=True)
class OutputSafetyFinding:
    field: str
    rule: str


_FORBIDDEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("raw_ref", re.compile(r"\braw_ref\b", re.IGNORECASE)),
    ("system_prompt_label", re.compile(r"\bsystem prompt\s*:", re.IGNORECASE)),
    (
        "developer_instructions_label",
        re.compile(r"\bdeveloper instructions\s*:", re.IGNORECASE),
    ),
    ("prompt_assembly", re.compile(r"\bprompt_assembly\b", re.IGNORECASE)),
    ("event_trace", re.compile(r"\bevent_trace\b", re.IGNORECASE)),
    ("openai_api_key_env", re.compile(r"\bOPENAI_API_KEY\b", re.IGNORECASE)),
    ("api_key_like", re.compile(r"\bsk-[A-Za-z0-9_-]{10,}\b")),
)


def check_teacher_visible_output(**fields: str) -> list[OutputSafetyFinding]:
    """Return rule-only findings for forbidden teacher-visible output markers."""
    findings: list[OutputSafetyFinding] = []
    for field, value in fields.items():
        text = value or ""
        for rule, pattern in _FORBIDDEN_PATTERNS:
            if pattern.search(text):
                findings.append(OutputSafetyFinding(field=field, rule=rule))
    return findings
