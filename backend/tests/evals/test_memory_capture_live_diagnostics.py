from __future__ import annotations

from app.teacher_agent.memory_capture import MemoryCandidate
from tests.evals.test_klassenpilot_memory_capture_live import (
    _forbidden_target_message,
    _missing_expected_target_message,
)


def test_missing_expected_target_message_reports_wrong_target_and_reason():
    emitted = [
        MemoryCandidate(
            target="planning_brief.md",
            candidate_update="Upcoming electricity block should start with kits.",
            speech_act="store_request",
            routing_reason=(
                "Immediate next-block priority, but this missed the durable "
                "class-learning-pattern target."
            ),
        )
    ]

    message = _missing_expected_target_message(
        golden_id="store_request_teaching_patterns_fast_lane",
        expected_target="teaching_patterns.md",
        emitted=emitted,
        teacher_message=(
            "Remember for the next electricity block: start with real circuit "
            "kits before Ohm's law equations."
        ),
    )

    assert "wrong target" in message
    assert "missing expected target(s): teaching_patterns.md" in message
    assert "planning_brief.md" in message
    assert "speech_act=store_request" in message
    assert "Immediate next-block priority" in message


def test_missing_expected_target_message_reports_partial_dual_capture():
    emitted = [
        MemoryCandidate(
            target="teaching_patterns.md",
            candidate_update="This class benefits from circuit kits before formulas.",
            speech_act="store_request",
            routing_reason="Durable class-learning pattern.",
        )
    ]

    message = _missing_expected_target_message(
        golden_id="store_request_teaching_patterns_fast_lane",
        expected_targets=("teaching_patterns.md", "planning_brief.md"),
        emitted=emitted,
        teacher_message="Remember for the next electricity block: start with kits.",
    )

    assert "missing expected target(s): planning_brief.md" in message
    assert "got ['teaching_patterns.md']" in message
    assert "Durable class-learning pattern" in message


def test_forbidden_target_message_reports_leaked_profile_capture():
    emitted = [
        MemoryCandidate(
            target="teacher_profile.md",
            candidate_update="Teacher prefers circuit kits before formulas.",
            speech_act="store_request",
            routing_reason="Misread a class-scoped learning pattern as global.",
        )
    ]

    message = _forbidden_target_message(
        golden_id="store_request_teaching_patterns_fast_lane",
        forbidden_targets=("teacher_profile.md", "copilot_profile.md"),
        emitted=emitted,
        teacher_message="Remember for the next electricity block: start with kits.",
    )

    assert "forbidden target" in message
    assert "teacher_profile.md" in message
    assert "Misread a class-scoped learning pattern" in message
