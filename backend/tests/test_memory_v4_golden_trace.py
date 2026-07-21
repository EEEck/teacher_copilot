from __future__ import annotations

import sys
from pathlib import Path

from app.teacher_agent.memory_capture import MemoryCandidate

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_memory_v4_golden_trace import build_candidate_stage_trace
from scripts.memory_scenario_helpers import reasoning_events, reasoning_text


def test_golden_trace_separates_admission_from_priority():
    message = "From now on, always keep lesson plans concise."
    candidate = MemoryCandidate(
        target="teacher_profile.md",
        candidate_update="Keep lesson plans concise.",
        evidence=f"Direct teacher quote: {message}",
        source="teacher_explicit",
        basis="explicit",
        confidence="high",
        speech_act="conduct_request",
    )

    trace = build_candidate_stage_trace(
        candidate,
        teacher_message=message,
        expected_scope="global",
    )

    assert trace["admission"]["decision"] == "admitted"
    assert trace["priority"]["decision"] == "fast_lane"


def test_golden_trace_observation_with_always_is_not_priority():
    message = "The students always confuse resonance structures."
    candidate = MemoryCandidate(
        target="teaching_patterns.md",
        candidate_update="The class confuses resonance structures.",
        evidence=f"Direct teacher quote: {message}",
        source="teacher_explicit",
        basis="explicit",
        confidence="high",
        speech_act="observation",
    )

    trace = build_candidate_stage_trace(
        candidate,
        teacher_message=message,
        expected_scope="class",
    )

    assert trace["admission"]["decision"] == "admitted"
    assert trace["priority"]["decision"] == "not_fast_lane"


def test_golden_trace_missing_quote_needs_review():
    candidate = MemoryCandidate(
        target="teacher_profile.md",
        candidate_update="Prefer concise plans.",
        evidence="Teacher prefers concise plans.",
        source="teacher_explicit",
        basis="explicit",
        confidence="high",
        speech_act="conduct_request",
    )

    trace = build_candidate_stage_trace(
        candidate,
        teacher_message="Please plan tomorrow's lesson.",
        expected_scope="global",
    )

    assert trace["admission"]["decision"] == "needs_review"
    assert trace["priority"]["decision"] == "not_fast_lane"


def test_reasoning_trace_helpers_keep_raw_local_reasoning_events():
    events = [
        {"type": "reasoning_delta", "text": "first "},
        {"type": "tool_call", "name": "remember"},
        {"type": "reasoning_delta", "text": "second"},
    ]

    assert reasoning_events(events) == [events[0], events[2]]
    assert reasoning_text(events) == "first second"
