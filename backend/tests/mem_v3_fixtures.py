"""Helpers to load mem_v3 ledger fixtures (recorded beta data)."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.memory_candidate_ledger import MemoryCandidateRow

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "mem_v3"


def load_fixture_rows(name: str) -> list[MemoryCandidateRow]:
    raw = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    rows: list[MemoryCandidateRow] = []
    for item in raw:
        rows.append(
            MemoryCandidateRow(
                id=item["id"],
                created_at=item["created_at"],
                updated_at=item.get("updated_at") or item["created_at"],
                class_id=item.get("class_id"),
                subject=item.get("subject"),
                workflow=item.get("workflow") or "ingest",
                session_id=item.get("session_id"),
                turn_index=int(item.get("turn_index") or 0),
                channel=item["channel"],
                target=item["target"],
                section=item["section"],
                candidate_update=item["candidate_update"],
                evidence_summary=item.get("evidence_summary") or "",
                source=item.get("source") or "inferred_from_session",
                basis=item.get("basis") or "inferred",
                confidence=item.get("confidence") or "low",
                cluster_key=item.get("cluster_key"),
                status=item.get("status") or "captured",
                rejection_reason=item.get("rejection_reason"),
            )
        )
    return rows


def organic_chemistry_rows() -> list[MemoryCandidateRow]:
    """12 captured + 2 snoozed rows from the beta over-capture case.

    Four test sessions re-captured ~5 distinct claims with different wording
    and different LLM-invented section names (see docs/mem_v3/design.md §1).
    """
    return load_fixture_rows("organic_chemistry_ledger.json")


def mbb_applied_rows() -> list[MemoryCandidateRow]:
    """Applied-history fixture; contains the 6x near-duplicate MBB preference."""
    return load_fixture_rows("mbb_repetition_ledger.json")
