"""End-to-end workflow scenario goldens."""

from __future__ import annotations

from dataclasses import dataclass

from tests.eval.fckw_prompts import CLASS_ID as CHEMIE_9B_CLASS_ID, FCKW_PROMPTS
from tests.eval.memory_update_prompts import MEMORY_UPDATE_PROMPTS


@dataclass(frozen=True)
class WorkflowScenarioGolden:
    golden_id: str
    workflow: str
    class_id: str
    messages: tuple[str, ...]
    expected_final_phase: str
    expected_ready: bool
    tools_any_of: tuple[str, ...] = ()
    tools_any_of_min: int = 0
    require_raw_evidence: bool = False
    artifact_patterns: tuple[str, ...] = ()
    forbidden_artifact_patterns: tuple[str, ...] = ()
    geval_criteria: str = ""


WORKFLOW_SCENARIO_GOLDENS: tuple[WorkflowScenarioGolden, ...] = (
    WorkflowScenarioGolden(
        golden_id="9b_plan_fckw_3turn_e2e",
        workflow="plan",
        class_id=CHEMIE_9B_CLASS_ID,
        messages=FCKW_PROMPTS,
        expected_final_phase="finalize",
        expected_ready=True,
        tools_any_of=("search_memory", "read_lesson", "read_lesson_range", "list_lessons"),
        tools_any_of_min=2,
        require_raw_evidence=True,
        artifact_patterns=(
            r"FCKW|CFC",
            r"45[\s-]*min",
            r"Montreal Protocol",
            r"oxidation number",
            r"charge",
            r"2[\s-]*minute|2[\s-]*min",
            r"recall",
        ),
        forbidden_artifact_patterns=(r"## Evidence briefs", r"raw_ref"),
        geval_criteria=(
            "The final lesson plan should satisfy the teacher's multi-turn request, "
            "stay grounded in Chemie 9b class memory and retrieved wiki evidence, "
            "include FCKW/CFC redox, Montreal Protocol context, differentiated "
            "practice, homework, and a short active-recall recap, without leaking "
            "debug context or inventing unsupported class history."
        ),
    ),
    WorkflowScenarioGolden(
        golden_id="9b_memory_update_3turn_e2e",
        workflow="ingest",
        class_id=CHEMIE_9B_CLASS_ID,
        messages=tuple(MEMORY_UPDATE_PROMPTS),
        expected_final_phase="review_draft",
        expected_ready=True,
        tools_any_of=("read_memory_target", "list_memory_targets", "search_memory"),
        tools_any_of_min=1,
        require_raw_evidence=True,
        artifact_patterns=(
            r"2026-05-29",
            r"common anions",
            r"ion charge",
            r"oxidation number",
            r"S-\d{3}",
            r"metal displacement",
        ),
        forbidden_artifact_patterns=(r"\bJoonho\b", r"\bAlex\b", r"\bRita\b", r"\bMatt\b", r"raw_ref"),
        geval_criteria=(
            "The final lesson-results diary should reflect the teacher's 2026-05-29 "
            "corrections, preserve uncertainty about what was not covered, use "
            "pseudonymous student IDs only, and avoid unsupported claims beyond "
            "the teacher notes and retrieved lesson target."
        ),
    ),
)
