"""Mem V3 Phase 2 goldens: deterministic ledger folding and history awareness.

Written test-first (docs/mem_v3/testing.md). Tests xfail until the target
API lands in app/services/memory_candidate_ledger.py:

- insert_with_folding(ledger, row) -> MemoryCandidateRow (stored row with
  final cluster_key/status: exact dup -> 'duplicate', near-dup adopts the
  matched open cluster_key, applied match -> 'already_covered', rejected
  match -> 'suppressed' unless explicit).
- memory_targets.normalize_section(target, section) -> canonical section.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from app.services import memory_candidate_ledger as mcl
from tests.mem_v3_fixtures import mbb_applied_rows, organic_chemistry_rows


def _require(name: str):
    fn = getattr(mcl, name, None)
    if fn is None:
        pytest.xfail(f"mem_v3 phase 2: {name} not implemented yet")
    return fn


def _ledger(tmp_path: Path) -> mcl.MemoryCandidateLedger:
    ledger = mcl.MemoryCandidateLedger(tmp_path / "ledger.sqlite")
    ledger.initialize()
    return ledger


# --- fixture integrity (pass now; guard the recorded evidence) -------------


def test_fixture_captures_the_overcapture_case():
    rows = organic_chemistry_rows()
    captured = [r for r in rows if r.status == "captured"]
    assert len(captured) >= 12
    transitions = [
        r
        for r in captured
        if r.target == "class_state.md" and "organic" in r.candidate_update.lower()
    ]
    # Four sessions each re-captured the unit transition with new wording.
    assert len(transitions) >= 3
    assert len({r.session_id for r in transitions}) >= 3
    assert len({r.cluster_key for r in transitions}) == len(transitions), (
        "exact-hash clustering gave every rephrasing its own cluster — "
        "the V2 defect this fixture preserves"
    )


def test_fixture_shows_section_fragmentation():
    rows = [
        r
        for r in organic_chemistry_rows()
        if r.status == "captured" and r.target == "teaching_patterns.md"
    ]
    assert len({r.section for r in rows}) >= 3, (
        "the same claim landed in multiple LLM-invented sections"
    )


def test_fixture_contains_repeated_applied_preference():
    rows = [
        r
        for r in mbb_applied_rows()
        if "mbb" in r.candidate_update.lower() and r.status == "applied"
    ]
    assert len(rows) >= 5, "the MBB preference was applied as near-duplicates"


# --- folding goldens (xfail until phase 2) ---------------------------------


def test_same_session_exact_duplicate_is_rejected(tmp_path: Path):
    insert_with_folding = _require("insert_with_folding")
    ledger = _ledger(tmp_path)
    row = next(r for r in organic_chemistry_rows() if r.status == "captured")
    first = insert_with_folding(ledger, row)
    assert first.status == "captured"
    dup = replace(row, id="dup-row")  # same session: within-session noise
    second = insert_with_folding(ledger, dup)
    assert second.status == "duplicate"


def test_cross_session_exact_recapture_reinforces_the_cluster(tmp_path: Path):
    # An identical re-statement in a NEW session is the strongest
    # reinforcement signal — it must stay open and join the cluster so the
    # promotion gate counts the second session.
    insert_with_folding = _require("insert_with_folding")
    ledger = _ledger(tmp_path)
    row = next(r for r in organic_chemistry_rows() if r.status == "captured")
    first = insert_with_folding(ledger, row)
    recapture = replace(row, id="recap-row", session_id="another-session")
    second = insert_with_folding(ledger, recapture)
    assert second.status == "captured"
    assert second.cluster_key == first.cluster_key


def test_near_duplicate_adopts_existing_open_cluster(tmp_path: Path):
    insert_with_folding = _require("insert_with_folding")
    ledger = _ledger(tmp_path)
    rows = [
        r
        for r in organic_chemistry_rows()
        if r.target == "class_state.md" and "organic" in r.candidate_update.lower()
    ]
    assert len(rows) >= 3
    stored = [insert_with_folding(ledger, r) for r in rows]
    clusters = {r.cluster_key for r in stored}
    assert len(clusters) == 1, (
        "rephrasings of the same claim must fold into one cluster "
        f"(got {len(clusters)})"
    )


def test_organic_fixture_folds_to_few_clusters(tmp_path: Path):
    insert_with_folding = _require("insert_with_folding")
    ledger = _ledger(tmp_path)
    captured = [r for r in organic_chemistry_rows() if r.status == "captured"]
    stored = [insert_with_folding(ledger, r) for r in captured]
    open_clusters = {
        r.cluster_key for r in stored if r.status in ("captured", "grouped")
    }
    # 12 recorded rows encode ~5 distinct claims; allow one cluster of slack.
    assert len(open_clusters) <= 6


def test_applied_match_becomes_already_covered(tmp_path: Path):
    insert_with_folding = _require("insert_with_folding")
    ledger = _ledger(tmp_path)
    applied = next(
        r for r in mbb_applied_rows() if "mbb" in r.candidate_update.lower()
    )
    ledger.add(applied)
    recapture = replace(
        applied, id="recapture-1", session_id="new-session", status="captured"
    )
    stored = insert_with_folding(ledger, recapture)
    assert stored.status == "already_covered"


def test_rejected_match_is_suppressed_unless_explicit(tmp_path: Path):
    insert_with_folding = _require("insert_with_folding")
    ledger = _ledger(tmp_path)
    base = next(r for r in organic_chemistry_rows() if r.status == "captured")
    rejected = replace(
        base,
        id="rejected-1",
        status="rejected",
        rejection_reason="Teacher rejected in sweep.",
    )
    ledger.add(rejected)

    recapture = replace(
        base,
        id="recapture-2",
        session_id="new-session",
        status="captured",
        source="inferred_from_session",
        basis="inferred",
        confidence="low",
    )
    stored = insert_with_folding(ledger, recapture)
    assert stored.status == "suppressed"

    explicit = replace(
        base,
        id="recapture-3",
        session_id="new-session-2",
        status="captured",
        source="teacher_explicit",
        basis="explicit",
        confidence="high",
    )
    stored_explicit = insert_with_folding(ledger, explicit)
    assert stored_explicit.status == "captured", (
        "a fresh explicit teacher ask may resurface a rejected claim"
    )


def test_section_is_normalized_onto_vocabulary(tmp_path: Path):
    from app.teacher_agent import memory_targets

    normalize_section = getattr(memory_targets, "normalize_section", None)
    if normalize_section is None:
        pytest.xfail("mem_v3 phase 2: normalize_section not implemented yet")
    variants = [
        "organic_chemistry",
        "organic_chemistry_lesson_design",
        "class_learning_profile",
        "What Worked Well",
    ]
    normalized = {
        normalize_section("teaching_patterns.md", section) for section in variants
    }
    # Free-form LLM sections must collapse onto the fixed per-target
    # vocabulary (at most two canonical buckets for these four variants).
    assert len(normalized) <= 2
