"""Workflow startup golden definitions for Chemie 9b."""

from __future__ import annotations

from dataclasses import dataclass

CHEMIE_9B_CLASS_ID = "chemie_9b_2026_27"


@dataclass(frozen=True)
class WorkflowGolden:
    golden_id: str
    workflow: str
    class_id: str


WORKFLOW_GOLDENS: tuple[WorkflowGolden, ...] = (
    WorkflowGolden(
        golden_id="9b_plan_startup",
        workflow="plan",
        class_id=CHEMIE_9B_CLASS_ID,
    ),
    WorkflowGolden(
        golden_id="9b_ingest_startup",
        workflow="ingest",
        class_id=CHEMIE_9B_CLASS_ID,
    ),
)
