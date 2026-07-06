"""Mem V3 Phase 2 goldens: the promotion gate (docs/mem_v3/design.md lane 2).

xfail until app/services/memory_gate.py lands with:

- gate_clusters(rows, now) -> GateResult with .eligible and .held lists of
  clusters (a cluster = list of rows sharing cluster_key).
- expire_stale_candidates(ledger, now) -> int (rows expired).

Gate rules: explicit_ask (source == "teacher_explicit") always eligible;
inferred needs captures in >= 2 distinct sessions, recency-weighted; stale
unreinforced singletons expire silently after ~42 days.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.services import memory_candidate_ledger as mcl
from tests.mem_v3_fixtures import organic_chemistry_rows


def _gate_module():
    try:
        from app.services import memory_gate  # noqa: PLC0415
    except ImportError:
        pytest.xfail("mem_v3 phase 2: app/services/memory_gate.py not implemented yet")
    return memory_gate


NOW = datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc)


def _row(base, **overrides):
    return replace(base, **overrides)


def _base_inferred():
    row = next(r for r in organic_chemistry_rows() if r.status == "captured")
    return replace(
        row,
        source="inferred_from_session",
        basis="inferred",
        confidence="low",
        status="captured",
        cluster_key="test.cluster.one",
        created_at=(NOW - timedelta(days=1)).isoformat(),
    )


def test_singleton_inferred_claim_is_held():
    gate = _gate_module()
    base = _base_inferred()
    result = gate.gate_clusters([[base]], NOW)
    assert not result.eligible
    assert len(result.held) == 1


def test_two_occasion_inferred_cluster_is_eligible():
    # Two different lesson anchors = two independent occasions.
    gate = _gate_module()
    base = _base_inferred()
    cluster = [
        _row(base, id="a", session_id="session-1", occasion_key="lesson:2026-07-01"),
        _row(base, id="b", session_id="session-2", occasion_key="lesson:2026-07-03"),
    ]
    result = gate.gate_clusters([cluster], NOW)
    assert len(result.eligible) == 1


def test_retry_sessions_about_the_same_lesson_are_one_occasion():
    # The beta failure case: the same lesson report pasted into four
    # sessions within an hour must not count as reinforcement.
    gate = _gate_module()
    base = _base_inferred()
    cluster = [
        _row(base, id="a", session_id="session-1", occasion_key="lesson:2026-07-04"),
        _row(base, id="b", session_id="session-2", occasion_key="lesson:2026-07-04"),
        _row(base, id="c", session_id="session-3", occasion_key="lesson:2026-07-04"),
    ]
    result = gate.gate_clusters([cluster], NOW)
    assert not result.eligible


def test_unanchored_sessions_within_six_hours_are_one_occasion():
    gate = _gate_module()
    base = _base_inferred()
    early = (NOW - timedelta(hours=26)).isoformat()
    late = (NOW - timedelta(hours=25)).isoformat()
    cluster = [
        _row(base, id="a", session_id="session-1", created_at=early),
        _row(base, id="b", session_id="session-2", created_at=late),
    ]
    result = gate.gate_clusters([cluster], NOW)
    assert not result.eligible


def test_unanchored_sessions_on_different_days_are_two_occasions():
    gate = _gate_module()
    base = _base_inferred()
    cluster = [
        _row(base, id="a", created_at=(NOW - timedelta(days=2)).isoformat()),
        _row(base, id="b", created_at=(NOW - timedelta(days=1)).isoformat()),
    ]
    result = gate.gate_clusters([cluster], NOW)
    assert len(result.eligible) == 1


def test_two_plan_sessions_are_two_occasions_even_within_six_hours():
    # Plan sessions anchor on the session (not a time bucket), so two distinct
    # planning sessions in one evening are two genuine occasions — they are
    # not the re-paste failure mode that occasion counting guards against.
    from app.teacher_agent.memory_capture import occasion_key_for

    gate = _gate_module()
    base = _base_inferred()
    early = (NOW - timedelta(hours=26)).isoformat()
    late = (NOW - timedelta(hours=25)).isoformat()
    cluster = [
        _row(
            base,
            id="a",
            created_at=early,
            occasion_key=occasion_key_for("plan", "plan-session-1"),
        ),
        _row(
            base,
            id="b",
            created_at=late,
            occasion_key=occasion_key_for("plan", "plan-session-2"),
        ),
    ]
    result = gate.gate_clusters([cluster], NOW)
    assert len(result.eligible) == 1


def test_one_plan_session_across_turns_is_one_occasion():
    from app.teacher_agent.memory_capture import occasion_key_for

    gate = _gate_module()
    base = _base_inferred()
    key = occasion_key_for("plan", "plan-session-1")
    cluster = [
        _row(base, id="a", turn_index=1, occasion_key=key),
        _row(base, id="b", turn_index=3, occasion_key=key),
    ]
    result = gate.gate_clusters([cluster], NOW)
    assert not result.eligible


def test_same_evening_burst_on_different_lessons_counts_as_occasions():
    # Teachers work in bursts: logging two different lessons in one evening
    # is two genuine occasions.
    gate = _gate_module()
    base = _base_inferred()
    cluster = [
        _row(base, id="a", session_id="s1", occasion_key="lesson:2026-07-01"),
        _row(base, id="b", session_id="s1", occasion_key="lesson:2026-07-02"),
    ]
    result = gate.gate_clusters([cluster], NOW)
    assert len(result.eligible) == 1


def test_repeat_capture_in_same_session_does_not_count_as_reinforcement():
    gate = _gate_module()
    base = _base_inferred()
    cluster = [
        _row(base, id="a", session_id="session-1", turn_index=1),
        _row(base, id="b", session_id="session-1", turn_index=3),
    ]
    result = gate.gate_clusters([cluster], NOW)
    assert not result.eligible


def test_explicit_ask_is_always_eligible():
    gate = _gate_module()
    base = _base_inferred()
    explicit = _row(
        base,
        id="exp",
        source="teacher_explicit",
        basis="explicit",
        confidence="high",
        evidence_summary=(
            "Direct teacher quote: From now on, use MBB-style summaries "
            "for all briefs."
        ),
    )
    result = gate.gate_clusters([[explicit]], NOW)
    assert len(result.eligible) == 1


def test_overpromoted_explicit_without_direct_proof_is_held():
    gate = _gate_module()
    base = _base_inferred()
    legacy_explicit = _row(
        base,
        id="legacy-exp",
        source="teacher_explicit",
        basis="explicit",
        confidence="high",
        evidence_summary="Teacher explicitly said organic chemistry needs visual models.",
    )
    result = gate.gate_clusters([[legacy_explicit]], NOW)
    assert not result.eligible
    assert len(result.held) == 1


def test_proof_backed_explicit_on_compiled_class_memory_is_held():
    gate = _gate_module()
    base = _base_inferred()
    teaching_pattern = _row(
        base,
        id="exp-teaching-pattern",
        target="teaching_patterns.md",
        source="teacher_explicit",
        basis="explicit",
        confidence="high",
        evidence_summary=(
            "Direct teacher quote: For the next block of organic chemistry, "
            "always use concrete molecule examples before terminology."
        ),
    )
    class_state = _row(
        base,
        id="exp-class-state",
        target="class_state.md",
        source="teacher_explicit",
        basis="explicit",
        confidence="high",
        evidence_summary=(
            "Direct teacher quote: From now on, remember the class is starting "
            "organic chemistry."
        ),
        cluster_key="test.cluster.class_state",
    )
    result = gate.gate_clusters([[teaching_pattern], [class_state]], NOW)
    assert not result.eligible
    assert len(result.held) == 2


def test_stale_singletons_expire_silently(tmp_path: Path):
    gate = _gate_module()
    expire = getattr(gate, "expire_stale_candidates", None)
    if expire is None:
        pytest.xfail("mem_v3 phase 2: expire_stale_candidates not implemented yet")
    ledger = mcl.MemoryCandidateLedger(tmp_path / "ledger.sqlite")
    ledger.initialize()
    base = _base_inferred()
    stale = _row(
        base,
        id="stale-1",
        created_at=(NOW - timedelta(days=60)).isoformat(),
        updated_at=(NOW - timedelta(days=60)).isoformat(),
    )
    fresh = _row(base, id="fresh-1", cluster_key="test.cluster.two")
    ledger.add_many([stale, fresh])
    expired_count = expire(ledger, NOW)
    assert expired_count == 1
    open_rows = ledger.list_candidates(statuses=("captured",))
    assert {r.id for r in open_rows} == {"fresh-1"}
