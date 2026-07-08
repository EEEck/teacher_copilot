"""Mem V3 Phase 4: consolidation-call input building (pure parts).

The single sweep call receives current memory bullets enumerated with
ephemeral ids (no file-format change) plus gate-passing claims with
reinforcement metadata. These tests pin the deterministic builders.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.services import memory_sweep as sweep
from tests.mem_v3_fixtures import organic_chemistry_rows

NOW = datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc)

MEMORY_MD = """# Class State

> Class: chemie_9b_2026_27

- **Current Unit:** Practicing redox half equations with peer checking.
- **Next Planned Focus:** Use more worked examples.

## Student participation
- S-046 understands concepts but needs encouragement.
"""


def test_enumerate_memory_bullets_assigns_stable_ids():
    enumerate_bullets = getattr(sweep, "enumerate_memory_bullets", None)
    if enumerate_bullets is None:
        pytest.xfail("mem_v3 phase 4: enumerate_memory_bullets not implemented")
    index = enumerate_bullets(MEMORY_MD, prefix="CS")
    assert list(index.keys()) == ["CS1", "CS2", "CS3"]
    assert index["CS1"].startswith("**Current Unit:**")
    assert index["CS3"].startswith("S-046")
    # Headings, blockquotes, and blank lines are not bullets.
    assert not any("Class State" in text for text in index.values())


def test_claims_payload_from_gated_clusters():
    build_claims = getattr(sweep, "claims_from_clusters", None)
    if build_claims is None:
        pytest.xfail("mem_v3 phase 4: claims_from_clusters not implemented")
    rows = [
        r
        for r in organic_chemistry_rows()
        if r.status == "captured" and r.target == "planning_brief.md"
    ]
    # Simulate phase-2 folding (shared cluster) and phase-3 discipline (the
    # fixture preserves V2's over-promoted teacher_explicit labels).
    cluster = [
        replace(r, cluster_key="folded.cluster", source="inferred_from_session")
        for r in rows
    ]
    claims = build_claims([cluster], NOW)
    assert len(claims) == 1
    claim = claims[0]
    assert claim["claim_id"]
    assert claim["target"] == "planning_brief.md"
    assert claim["signal_count"] == len(cluster)
    assert claim["session_count"] >= 3
    # Representative text is the most recent phrasing.
    newest = max(cluster, key=lambda r: r.created_at)
    assert claim["text"] == newest.candidate_update
    assert claim["explicit"] is False
    assert set(claim["candidate_ids"]) == {r.id for r in cluster}


def test_claims_payload_requires_direct_quote_for_explicit_fast_lane():
    build_claims = getattr(sweep, "claims_from_clusters", None)
    if build_claims is None:
        pytest.xfail("mem_v3 phase 4: claims_from_clusters not implemented")
    row = next(
        r
        for r in organic_chemistry_rows()
        if r.status == "captured" and r.target == "teacher_profile.md"
    )
    legacy = replace(
        row,
        source="teacher_explicit",
        basis="explicit",
        confidence="high",
        evidence_summary=(
            "Teacher explicitly said organic chemistry needs concrete examples."
        ),
    )
    proof_backed = replace(
        row,
        id="proof-backed",
        source="teacher_explicit",
        basis="explicit",
        confidence="high",
        evidence_summary=(
            "Direct teacher quote: From now on, use concrete molecule "
            "examples for all organic chemistry briefs."
        ),
    )

    claims = build_claims([[legacy], [proof_backed]], NOW)

    assert claims[0]["explicit"] is False
    assert claims[1]["explicit"] is True


def test_claims_payload_keeps_compiled_class_memory_out_of_explicit_lane():
    build_claims = getattr(sweep, "claims_from_clusters", None)
    if build_claims is None:
        pytest.xfail("mem_v3 phase 4: claims_from_clusters not implemented")
    row = next(
        r
        for r in organic_chemistry_rows()
        if r.status == "captured" and r.target == "teaching_patterns.md"
    )
    proof_backed = replace(
        row,
        source="teacher_explicit",
        basis="explicit",
        confidence="high",
        evidence_summary=(
            "Direct teacher quote: For the next block of organic chemistry, "
            "always use concrete molecule examples before terminology."
        ),
    )

    claims = build_claims([[proof_backed]], NOW)

    assert claims[0]["explicit"] is False
