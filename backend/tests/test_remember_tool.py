"""PR4: the remember(...) capture tool's validation core.

The tool makes durable capture an explicit, quote-grounded model action to
close the emission gap (durable teacher instructions were dropped when capture
was only a passive output field). validate_remember_call is the deterministic
guard: it accepts a well-formed, teacher-grounded call or returns a structured
error the model can act on and retry. See docs/mem_v3/next_implementation.md.
"""

from __future__ import annotations

from app.teacher_agent.memory_capture import (
    DIRECT_TEACHER_QUOTE_PREFIX,
    discipline_memory_candidates,
    validate_remember_call,
)

MESSAGE = "From now on, always keep future lesson plans in English please."


def test_valid_call_builds_a_grounded_explicit_candidate():
    cand, error = validate_remember_call(
        target="teacher_profile.md",
        content="Keep future lesson plans in English.",
        quote="always keep future lesson plans in English",
        speech_act="conduct_request",
        teacher_message=MESSAGE,
    )
    assert error == ""
    assert cand is not None
    assert cand.target == "teacher_profile.md"
    assert cand.source == "teacher_explicit"
    assert cand.evidence.startswith(DIRECT_TEACHER_QUOTE_PREFIX)
    assert "always keep future lesson plans in English" in cand.evidence


def test_alias_targets_are_canonicalized():
    cand, error = validate_remember_call(
        target="copilot.md",
        content="Draft early, then refine the markdown directly.",
        quote="always keep future lesson plans in English",
        speech_act="conduct_request",
        teacher_message=MESSAGE,
    )
    assert error == ""
    assert cand is not None
    assert cand.target == "copilot_profile.md"


def test_subject_guide_target_is_accepted():
    cand, error = validate_remember_call(
        target="wiki/subjects/chemie.md",
        content="Introduce oxidation numbers after concrete electron-transfer examples.",
        quote="always keep future lesson plans in English",
        speech_act="store_request",
        teacher_message=MESSAGE,
    )
    assert error == ""
    assert cand is not None


def test_empty_content_is_rejected():
    cand, error = validate_remember_call(
        target="teacher_profile.md",
        content="   ",
        quote="always keep future lesson plans in English",
        speech_act="conduct_request",
        teacher_message=MESSAGE,
    )
    assert cand is None
    assert "remember" in error.lower()


def test_unsupported_target_is_rejected_with_guidance():
    for bad in ("class_state.md", "canonical_wiki", "students/S-046.md"):
        cand, error = validate_remember_call(
            target=bad,
            content="Something durable.",
            quote="always keep future lesson plans in English",
            speech_act="conduct_request",
            teacher_message=MESSAGE,
        )
        assert cand is None, bad
        assert "teacher_profile.md" in error  # points at valid targets


def test_missing_quote_is_rejected():
    cand, error = validate_remember_call(
        target="teacher_profile.md",
        content="Keep future lesson plans in English.",
        quote="",
        speech_act="conduct_request",
        teacher_message=MESSAGE,
    )
    assert cand is None
    assert "quote" in error.lower()


def test_fabricated_quote_is_rejected():
    cand, error = validate_remember_call(
        target="teacher_profile.md",
        content="Answer only in bullet points.",
        quote="always answer in bullet points only",  # never said
        speech_act="conduct_request",
        teacher_message=MESSAGE,
    )
    assert cand is None
    assert "not in the teacher's message" in error


def test_valid_call_fast_lanes_through_discipline():
    # The tool stages a raw explicit candidate; persist-time discipline makes
    # the authoritative fast-lane decision. A grounded conduct request to a
    # preference file must fast-lane.
    cand, error = validate_remember_call(
        target="teacher_profile.md",
        content="Keep future lesson plans in English.",
        quote="always keep future lesson plans in English",
        speech_act="conduct_request",
        teacher_message=MESSAGE,
    )
    assert error == ""
    disciplined = discipline_memory_candidates([cand], teacher_message=MESSAGE)
    assert disciplined[0].fast_lane is True
    assert disciplined[0].source == "teacher_explicit"
