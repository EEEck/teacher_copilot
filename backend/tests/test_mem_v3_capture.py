"""Mem V3 Phase 3 goldens: capture discipline (docs/mem_v3/design.md lane 1).

Explicit/high durable-preference status must be corroborated by clearly
future-scoped teacher wording; otherwise candidates are weak inferred
signals routed through the sweep gate. This is the backend enforcement of
the owner rule from the beta round: a one-off "organize this in mbb style"
must never become a durable global preference.
"""

from __future__ import annotations

import pytest

from app.teacher_agent import memory_capture as capture
from app.teacher_agent.memory_capture import MemoryCandidate


# --- tightened future-scope markers ----------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        "From now on, use MBB-style communication for all lesson-planning summaries.",
        "Always start briefs with the recommendation.",
        "Going forward I want shorter homework blocks.",
        "Use this style in the future for all briefs.",
        "This is a general preference for me, not just this one class.",
        "Please keep answers concise for all future lessons.",
        "For the next block of organic chemistry, always use molecule examples first.",
    ],
)
def test_future_scoped_statements_are_durable(message: str):
    assert capture.has_durable_preference_scope(message)


@pytest.mark.parametrize(
    "message",
    [
        # The beta failure case: a one-off formatting request.
        "can you organize the lesson results in a mbb style so it is easier to review",
        # Bare "future" as a topic word must not trigger.
        "The future of chemistry teaching is exciting.",
        "let's discuss future lesson ideas for this unit",
        # One-off scoping words.
        "just for this answer, keep it short",
        "",
    ],
)
def test_one_off_requests_are_not_durable(message: str):
    assert not capture.has_durable_preference_scope(message)


# --- discipline: downgrade unsupported explicit claims ----------------------


def _explicit_candidate(text: str = "Prefers MBB-style summaries.") -> MemoryCandidate:
    return MemoryCandidate(
        target="teacher_profile.md",
        section="Communication",
        candidate_update=text,
        source="teacher_explicit",
        basis="explicit",
        confidence="high",
    )


def _require_discipline():
    fn = getattr(capture, "discipline_memory_candidates", None)
    if fn is None:
        pytest.xfail("mem_v3 phase 3: discipline_memory_candidates not implemented")
    return fn


def test_explicit_claim_without_scope_is_downgraded():
    discipline = _require_discipline()
    out = discipline(
        [_explicit_candidate()],
        teacher_message="can you organize the lesson results in a mbb style",
    )
    assert len(out) == 1
    downgraded = out[0]
    assert downgraded.source == "inferred_from_session"
    assert downgraded.basis == "inferred"
    assert downgraded.confidence == "low"


def test_explicit_claim_with_scope_is_kept():
    discipline = _require_discipline()
    out = discipline(
        [_explicit_candidate()],
        teacher_message="From now on, use MBB-style summaries for all briefs.",
    )
    assert out[0].source == "teacher_explicit"
    assert out[0].confidence == "high"
    assert "Direct teacher quote:" in out[0].evidence
    assert "From now on" in out[0].evidence


def test_explicit_claim_with_scope_but_non_preference_target_is_downgraded():
    # A directive about teaching approach is not a store request, so
    # teaching_patterns.md (store_request tier) stays regular-lane.
    discipline = _require_discipline()
    out = discipline(
        [
            _explicit_candidate(
                "Organic chemistry works better with concrete molecule examples."
            ).model_copy(update={"target": "teaching_patterns.md"})
        ],
        teacher_message=(
            "For the next block of organic chemistry, always use concrete "
            "molecule examples before terminology."
        ),
    )
    assert out[0].source == "inferred_from_session"
    assert out[0].basis == "inferred"
    assert out[0].confidence == "low"
    assert out[0].fast_lane is False


# --- speech-act lanes (dictation vs observation boundary) -------------------


def test_store_request_enables_content_target_fast_lane():
    discipline = _require_discipline()
    message = "Please add to the teaching patterns that this class needs visuals first."
    out = discipline(
        [
            _explicit_candidate("This class needs visual supports first.").model_copy(
                update={"target": "teaching_patterns.md", "speech_act": "store_request"}
            )
        ],
        teacher_message=message,
    )
    assert out[0].source == "teacher_explicit"
    assert out[0].fast_lane is True
    assert "Direct teacher quote:" in out[0].evidence


def test_conduct_request_keeps_profile_target_without_markers():
    # "can you communicate more concisely" has no future-scope marker; the
    # model's speech-act judgment carries it (industry pattern: direct
    # requests to the agent are first-class).
    discipline = _require_discipline()
    out = discipline(
        [
            _explicit_candidate("Prefers concise communication.").model_copy(
                update={"speech_act": "conduct_request"}
            )
        ],
        teacher_message="can you communicate more concisely with me",
    )
    assert out[0].source == "teacher_explicit"
    assert out[0].fast_lane is True


def test_conduct_request_never_fast_lanes_compiled_targets():
    discipline = _require_discipline()
    out = discipline(
        [
            _explicit_candidate("The class moved to organic chemistry.").model_copy(
                update={"target": "class_state.md", "speech_act": "conduct_request"}
            )
        ],
        teacher_message="From now on remember the class moved to organic chemistry.",
    )
    assert out[0].source == "inferred_from_session"
    assert out[0].fast_lane is False


# --- quote provenance (the one hard backend check) ---------------------------


def test_fabricated_quote_is_downgraded_and_stripped():
    discipline = _require_discipline()
    out = discipline(
        [
            _explicit_candidate().model_copy(
                update={
                    "speech_act": "conduct_request",
                    "evidence": (
                        "Direct teacher quote: Always answer in bullet points only."
                    ),
                }
            )
        ],
        teacher_message="can you communicate more concisely with me",
    )
    assert out[0].source == "inferred_from_session"
    assert out[0].fast_lane is False
    assert "Direct teacher quote:" not in out[0].evidence


def test_verified_model_quote_is_kept_and_canonicalized():
    discipline = _require_discipline()
    message = (
        "Thanks for the plan. Also, from now on use MBB-style summaries for "
        "all briefs. The redox part looked fine."
    )
    out = discipline(
        [
            _explicit_candidate().model_copy(
                update={
                    "speech_act": "conduct_request",
                    "evidence": (
                        "Direct teacher quote: from now on use MBB-style "
                        "summaries for all briefs"
                    ),
                }
            )
        ],
        teacher_message=message,
    )
    assert out[0].source == "teacher_explicit"
    assert out[0].fast_lane is True
    # The verified sentence, not the whole message, is the stamped proof.
    assert out[0].evidence.startswith("Direct teacher quote: from now on")
    assert "redox part" not in out[0].evidence


def test_downgraded_candidates_never_carry_the_quote_token():
    discipline = _require_discipline()
    out = discipline(
        [
            _explicit_candidate().model_copy(
                update={
                    "target": "class_state.md",
                    "evidence": "Direct teacher quote: whatever | other context",
                }
            )
        ],
        teacher_message="whatever",
    )
    assert "Direct teacher quote:" not in out[0].evidence
    assert "other context" in out[0].evidence


def test_inferred_candidates_pass_through_unchanged():
    discipline = _require_discipline()
    inferred = MemoryCandidate(
        target="teaching_patterns.md",
        section="class_learning_profile",
        candidate_update="Class benefits from concrete examples first.",
        source="inferred_from_session",
        basis="inferred",
        confidence="low",
    )
    out = discipline([inferred], teacher_message="whatever was said")
    assert out[0] == inferred


def test_state_repair_still_requires_scope():
    # The typed-state repair path must obey the same rule.
    candidates = capture.durable_preference_candidates_from_state_values(
        ["Use MBB-style summaries."],
        teacher_message="can you organize this in mbb style",
    )
    assert candidates == []
    candidates = capture.durable_preference_candidates_from_state_values(
        ["Use MBB-style summaries."],
        teacher_message="From now on use MBB-style summaries for all briefs.",
    )
    assert len(candidates) == 1
    assert candidates[0].source == "teacher_explicit"
