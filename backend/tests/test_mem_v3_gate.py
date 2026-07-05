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


def test_two_session_inferred_cluster_is_eligible():
    gate = _gate_module()
    base = _base_inferred()
    cluster = [
        _row(base, id="a", session_id="session-1"),
        _row(base, id="b", session_id="session-2"),
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
    )
    result = gate.gate_clusters([[explicit]], NOW)
    assert len(result.eligible) == 1


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
