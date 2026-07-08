"""Export memory-candidate ledger rows into an offline test fixture.

Reads a workspace's memory_candidates.sqlite and writes an anonymized JSON
fixture for the mem_v3 regression tests (docs/mem_v3/testing.md).

Usage (from backend/):
    .venv\\Scripts\\python scripts\\export_ledger_fixture.py \
        --db beta_data/workspaces/w_demo_chem9b/teacher_wiki/workflow/memory_candidates.sqlite \
        --status captured grouped proposed snoozed \
        --out tests/fixtures/mem_v3/organic_chemistry_ledger.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

FIXTURE_FIELDS = [
    "id",
    "class_id",
    "subject",
    "workflow",
    "session_id",
    "turn_index",
    "channel",
    "target",
    "section",
    "candidate_update",
    "evidence_summary",
    "source",
    "basis",
    "confidence",
    "cluster_key",
    "status",
    "created_at",
    "rejection_reason",
]


def export(db: Path, statuses: list[str], out: Path) -> int:
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    placeholders = ",".join("?" for _ in statuses)
    rows = con.execute(
        f"select * from memory_candidates where status in ({placeholders})"
        " order by created_at",
        statuses,
    ).fetchall()
    fixture = []
    for row in rows:
        item = {field: row[field] for field in FIXTURE_FIELDS if field in row.keys()}
        # Anonymize: student ids (S-###) are already pseudonymous; strip any
        # free-text evidence beyond a short excerpt.
        summary = item.get("evidence_summary") or ""
        item["evidence_summary"] = summary[:200]
        fixture.append(item)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(fixture, indent=2, ensure_ascii=False), encoding="utf-8")
    return len(fixture)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--status", nargs="+", default=["captured", "grouped", "proposed"])
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    count = export(args.db, args.status, args.out)
    print(f"wrote {count} rows -> {args.out}")


if __name__ == "__main__":
    main()
