"""Memory-capture speech-act golden definitions."""

from __future__ import annotations

from dataclasses import dataclass

from app.teacher_agent.memory_capture import canonical_memory_target


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
    # A live-only regression expectation. It remains opt-in because judging
    # model tool calls requires an OpenAI run; deterministic tests pin its
    # fixture contract and documentation.
    expect_no_durable_candidates: bool = False
    known_live_gap: bool = False
    # Defaults to the primary fast-lane expectation for homogeneous cases.
    # Mixed captures can explicitly name only the fast-lane targets.
    fast_lane_targets: tuple[str, ...] = ()


def expected_fast_lane_for_target(golden: MemoryCaptureGolden, target: str) -> bool:
    """Return the expected priority for one target in a capture golden."""
    if not golden.fast_lane_targets:
        return golden.expected_fast_lane
    canonical = canonical_memory_target(target)
    return canonical in {
        canonical_memory_target(candidate_target)
        for candidate_target in golden.fast_lane_targets
    }


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
    MemoryCaptureGolden(
        golden_id="mbb_session_then_general_style_boundary",
        teacher_message=(
            "In general, use subtle humor and occasional short quotes in your "
            "responses."
        ),
        target="teacher_profile.md",
        speech_act="conduct_request",
        evidence=(
            "Direct teacher quote: In general, use subtle humor and occasional "
            "short quotes in your responses."
        ),
        expected_fast_lane=True,
        expected_source="teacher_explicit",
        workflow="plan",
        prior_message=(
            "For this session only, use an MBB-style tone while we plan the next "
            "Chemie 9b organic chemistry lesson."
        ),
        expected_targets=("teacher_profile.md",),
    ),
    MemoryCaptureGolden(
        golden_id="light_orbital_preference_class_fast_lane",
        teacher_message=(
            "For this class, include a light intuitive orbital perspective when "
            "helpful, but keep it middle-school accessible and non-derivational."
        ),
        target="copilot_profile.md",
        speech_act="conduct_request",
        evidence=(
            "Direct teacher quote: For this class, include a light intuitive "
            "orbital perspective when helpful, but keep it middle-school "
            "accessible and non-derivational."
        ),
        expected_fast_lane=True,
        expected_source="teacher_explicit",
        workflow="plan",
        prior_message="Plan the next Chemie 9b organic chemistry lesson.",
        expected_targets=("copilot_profile.md",),
        forbidden_targets=("teacher_profile.md",),
        known_live_gap=True,
    ),
    MemoryCaptureGolden(
        golden_id="phenomenon_first_instruction_and_evidence",
        teacher_message=(
            "For new organic chemistry concepts, I prefer a phenomenon-first "
            "structure: start with an everyday example or mini-demo, then derive "
            "the molecular explanation. This gave the class much better energy "
            "than redox."
        ),
        target="copilot_profile.md",
        speech_act="conduct_request",
        evidence=(
            "Direct teacher quote: For new organic chemistry concepts, I prefer "
            "a phenomenon-first structure: start with an everyday example or "
            "mini-demo, then derive the molecular explanation."
        ),
        expected_fast_lane=True,
        expected_source="teacher_explicit",
        workflow="ingest",
        prior_message="Log today's alkanes and solubility lesson results.",
        expected_targets=("copilot_profile.md", "teaching_patterns.md"),
        expected_min_candidates=2,
        known_live_gap=True,
        fast_lane_targets=("copilot_profile.md",),
    ),
    MemoryCaptureGolden(
        golden_id="five_minute_review_no_global_leakage",
        teacher_message=(
            "I like to have this as a general concept: start lessons with a "
            "5-minute review of the last block."
        ),
        target="copilot_profile.md",
        speech_act="conduct_request",
        evidence=(
            "Direct teacher quote: I like to have this as a general concept: "
            "start lessons with a 5-minute review of the last block."
        ),
        expected_fast_lane=True,
        expected_source="teacher_explicit",
        workflow="plan",
        prior_message="Plan the second Chemie 9b organic chemistry lesson.",
        expected_targets=("copilot_profile.md",),
        forbidden_targets=("teacher_profile.md",),
        known_live_gap=True,
    ),
    MemoryCaptureGolden(
        golden_id="unknown_scope_no_durable_capture",
        teacher_message="Please make this worksheet shorter.",
        target="copilot_profile.md",
        speech_act="unknown",
        evidence="Teacher asked to shorten the current worksheet.",
        expected_fast_lane=False,
        expected_source="inferred_from_session",
        workflow="plan",
        prior_message="Plan the next 45-minute Chemie 9b lesson on organic chemistry basics.",
        expect_no_durable_candidates=True,
        known_live_gap=True,
    ),
)
