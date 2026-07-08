"""Memory-capture speech-act golden definitions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryCaptureGolden:
    golden_id: str
    teacher_message: str
    target: str
    speech_act: str
    evidence: str
    expected_fast_lane: bool
    expected_source: str
    # Workflow the live judge eval runs the message through. Conduct requests
    # about the agent's behavior are natural in planning; lesson observations
    # and content stores are natural in update-memory (ingest).
    workflow: str = "ingest"
    # A prior turn establishing realistic work context. Capture emission needs
    # the agent to be doing work; a cold session with only a standalone
    # preference emits nothing, which is itself a known finding.
    prior_message: str = ""
    # Component-level tool-call expectations, inspired by tool-correctness
    # evals: live runs compare emitted memory candidates against expected and
    # forbidden targets, instead of only checking one final fast-lane verdict.
    expected_targets: tuple[str, ...] = ()
    forbidden_targets: tuple[str, ...] = ()
    expected_min_candidates: int = 0


MEMORY_CAPTURE_GOLDENS: tuple[MemoryCaptureGolden, ...] = (
    MemoryCaptureGolden(
        golden_id="conduct_request_teacher_profile_fast_lane",
        teacher_message="From now on, always keep future lesson plans in English.",
        target="teacher_profile.md",
        speech_act="conduct_request",
        evidence=(
            "Direct teacher quote: From now on, always keep future lesson plans "
            "in English."
        ),
        expected_fast_lane=True,
        expected_source="teacher_explicit",
        workflow="plan",
        prior_message="Plan the next 45-minute Chemie 9b lesson on organic chemistry basics.",
    ),
    MemoryCaptureGolden(
        golden_id="store_request_teaching_patterns_fast_lane",
        teacher_message=(
            "For the next block of organic chemistry, remember to use molecule "
            "kits before formal terminology."
        ),
        target="teaching_patterns.md",
        speech_act="store_request",
        evidence=(
            "Direct teacher quote: For the next block of organic chemistry, "
            "remember to use molecule kits before formal terminology."
        ),
        expected_fast_lane=True,
        expected_source="teacher_explicit",
        workflow="ingest",
        prior_message=(
            "We finished the organic chemistry intro today; the class was "
            "engaged and covered carbon bonding."
        ),
        expected_targets=("teaching_patterns.md", "planning_brief.md"),
        forbidden_targets=("teacher_profile.md", "copilot_profile.md"),
        expected_min_candidates=2,
    ),
    MemoryCaptureGolden(
        # Beta 2026-07-07: this rich, blended report was over-classified as a
        # store_request and fast-laned into teaching_patterns on gpt-5.4-mini.
        # It should stay an inferred signal unless the teacher says to store it.
        golden_id="rich_engagement_observation_not_fast_lane",
        teacher_message=(
            "Compared with redox, this lesson had much better energy when I "
            "started with a phenomenon first and only then introduced the rule."
        ),
        target="teaching_patterns.md",
        speech_act="observation",
        evidence="Teacher reported higher energy when starting phenomenon-first.",
        expected_fast_lane=False,
        expected_source="inferred_from_session",
        workflow="ingest",
        prior_message=(
            "Log today's alkanes and solubility lesson: water and oil demo, "
            "students grasped like-dissolves-like, some overgeneralized it."
        ),
    ),
    MemoryCaptureGolden(
        golden_id="one_off_task_request_not_fast_lane",
        # A bounded request about the current artifact, not standing conduct.
        teacher_message="Please make this worksheet shorter.",
        target="copilot_profile.md",
        speech_act="observation",
        evidence="Teacher asked to shorten the current worksheet.",
        expected_fast_lane=False,
        expected_source="inferred_from_session",
        workflow="plan",
        prior_message="Plan the next 45-minute Chemie 9b lesson on organic chemistry basics.",
    ),
    MemoryCaptureGolden(
        # session_summaries.md is a compiled page; current-unit facts belong in
        # canonical lesson/course rollups, not fast-lane memory capture.
        golden_id="compiled_page_never_fast_lane",
        teacher_message="From now on, remember that the class is starting organics.",
        target="session_summaries.md",
        speech_act="conduct_request",
        evidence=(
            "Direct teacher quote: From now on, remember that the class is "
            "starting organics."
        ),
        expected_fast_lane=False,
        expected_source="inferred_from_session",
        workflow="ingest",
        prior_message=(
            "We finished the organic chemistry intro today; the class was "
            "engaged and covered carbon bonding."
        ),
    ),
)
