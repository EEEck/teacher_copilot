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
    # A prior turn establishing realistic work context. Capture emission
    # needs the agent to be doing work — a cold session with only a
    # standalone preference emits nothing (which is itself a known finding).
    prior_message: str = ""


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
        prior_message='Plan the next 45-minute Chemie 9b lesson on organic chemistry basics.',
    ),
    MemoryCaptureGolden(
        golden_id="conduct_request_no_marker_fast_lane",
        # No future-scope marker at all — the model's speech-act judgment is
        # the only thing that can carry this to the fast lane.
        teacher_message="Please be more concise in how you talk to me.",
        target="teacher_profile.md",
        speech_act="conduct_request",
        evidence="Direct teacher quote: Please be more concise in how you talk to me.",
        expected_fast_lane=True,
        expected_source="teacher_explicit",
        workflow="plan",
        prior_message='Plan the next 45-minute Chemie 9b lesson on organic chemistry basics.',
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
        prior_message='We finished the organic chemistry intro today; the class was engaged and covered carbon bonding.',
    ),
    MemoryCaptureGolden(
        golden_id="observation_not_fast_lane",
        teacher_message="The molecule kits worked well today before terminology.",
        target="teaching_patterns.md",
        speech_act="observation",
        evidence="Teacher observed that molecule kits worked well today.",
        expected_fast_lane=False,
        expected_source="inferred_from_session",
        workflow="ingest",
        prior_message='We finished the organic chemistry intro today; the class was engaged and covered carbon bonding.',
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
        prior_message='Plan the next 45-minute Chemie 9b lesson on organic chemistry basics.',
    ),
    MemoryCaptureGolden(
        golden_id="fabricated_quote_downgrades",
        teacher_message="Please make the worksheet shorter.",
        target="copilot_profile.md",
        speech_act="conduct_request",
        evidence=(
            "Direct teacher quote: From now on, always make every lesson brief "
            "two pages."
        ),
        expected_fast_lane=False,
        expected_source="inferred_from_session",
        # Deterministic-only: exercises the fabricated-quote guard. A real
        # model would not invent this quote, so the live judge eval skips it.
        workflow="",
    ),
    MemoryCaptureGolden(
        golden_id="class_state_never_fast_lane",
        teacher_message="From now on, remember that the class is starting organics.",
        target="class_state.md",
        speech_act="conduct_request",
        evidence=(
            "Direct teacher quote: From now on, remember that the class is "
            "starting organics."
        ),
        expected_fast_lane=False,
        expected_source="inferred_from_session",
        workflow="ingest",
        prior_message='We finished the organic chemistry intro today; the class was engaged and covered carbon bonding.',
    ),
)
