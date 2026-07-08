"""Clean known-bad pre-MemV3 memory-candidate ledger rows.

The script is intentionally conservative and report-first:

- creates a timestamped backup before any delete;
- writes before/after markdown reports beside each ledger;
- hard-deletes only open rows that match known pre-V3 over-capture patterns.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


CLEANUP_STATUSES = {
    "captured",
    "grouped",
    "proposed",
    "snoozed",
    "deleted",
    "expired",
    "duplicate",
    "suppressed",
}
NEVER_FAST_LANE_TARGETS = {
    "class_state.md",
    "taught_so_far.md",
    "session_summaries.md",
}
CONTENT_FAST_LANE_TARGETS = {
    "teaching_patterns.md",
    "planning_brief.md",
}
ORGANIC_TERMS = (
    "organic chemistry",
    "organic chem",
    "organische chemie",
    "organic",
)


@dataclass(frozen=True)
class CleanupMatch:
    row_id: str
    reason: str


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _has_column(conn: sqlite3.Connection, name: str) -> bool:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(memory_candidates)")}
    return name in columns


def _row_text(row: sqlite3.Row) -> str:
    return " ".join(
        str(row[key] or "")
        for key in ("candidate_update", "evidence_summary", "section", "target")
        if key in row.keys()
    ).lower()


def _fast_lane(row: sqlite3.Row) -> bool:
    return bool(row["fast_lane"]) if "fast_lane" in row.keys() else False


def _is_subject_target(target: str) -> bool:
    return target.startswith("wiki/subjects/")


def classify(row: sqlite3.Row) -> CleanupMatch | None:
    status = str(row["status"] or "")
    if status not in CLEANUP_STATUSES:
        return None

    target = str(row["target"] or "")
    source = str(row["source"] or "")
    basis = str(row["basis"] or "")
    evidence = str(row["evidence_summary"] or "")
    text = _row_text(row)
    has_quote = "direct teacher quote:" in evidence.lower()

    if target in NEVER_FAST_LANE_TARGETS and (
        source == "teacher_explicit" or basis == "explicit" or _fast_lane(row) or has_quote
    ):
        return CleanupMatch(row["id"], "compiled target incorrectly marked explicit")

    if (
        target in CONTENT_FAST_LANE_TARGETS or _is_subject_target(target)
    ) and source == "teacher_explicit" and not _fast_lane(row):
        return CleanupMatch(row["id"], "content target explicit without verified fast_lane")

    if (
        target in {"class_state.md", "teaching_patterns.md", "copilot_profile.md"}
        and any(term in text for term in ORGANIC_TERMS)
        and not _fast_lane(row)
    ):
        return CleanupMatch(row["id"], "old organic-chemistry over-capture signal")

    if (
        target in {"teacher_profile.md", "user.md"}
        and status in {"deleted", "expired"}
        and source == "teacher_explicit"
        and not _fast_lane(row)
        and any(term in text for term in ("mbb", "executive-style", "bottom-line-first", "bluf"))
    ):
        return CleanupMatch(row["id"], "old duplicate communication-preference artifact")

    return None


def _report_rows(title: str, rows: list[sqlite3.Row], matches: dict[str, str]) -> str:
    lines = [f"# {title}", ""]
    lines.append(f"Rows: {len(rows)}")
    lines.append(f"Matched for deletion: {len(matches)}")
    lines.append("")
    lines.append(
        "| delete | status | target | source | fast_lane | reason | update |"
    )
    lines.append("|---|---|---|---|---:|---|---|")
    for row in rows:
        row_id = row["id"]
        update = " ".join(str(row["candidate_update"] or "").split())[:120]
        reason = matches.get(row_id, "")
        lines.append(
            "| {delete} | {status} | {target} | {source} | {fast_lane} | {reason} | {update} |".format(
                delete="yes" if row_id in matches else "",
                status=row["status"],
                target=row["target"],
                source=row["source"],
                fast_lane=int(_fast_lane(row)),
                reason=reason.replace("|", "/"),
                update=update.replace("|", "/"),
            )
        )
    lines.append("")
    return "\n".join(lines)


def clean_ledger(path: Path, *, apply: bool) -> tuple[Path | None, Path, Path]:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    before_report = path.with_name(f"{path.stem}.cleanup_before_{ts}.md")
    after_report = path.with_name(f"{path.stem}.cleanup_after_{ts}.md")
    backup_path = path.with_name(f"{path.name}.{ts}.bak") if apply else None

    with _connect(path) as conn:
        if not _has_column(conn, "fast_lane"):
            conn.execute(
                "ALTER TABLE memory_candidates ADD COLUMN fast_lane INTEGER NOT NULL DEFAULT 0"
            )
        rows = list(
            conn.execute(
                """
                SELECT * FROM memory_candidates
                ORDER BY created_at, id
                """
            )
        )
        matches = {
            match.row_id: match.reason
            for row in rows
            if (match := classify(row)) is not None
        }
        before_report.write_text(
            _report_rows(f"Before cleanup: {path}", rows, matches),
            encoding="utf-8",
        )

    if apply and matches:
        assert backup_path is not None
        shutil.copy2(path, backup_path)
        with _connect(path) as conn:
            placeholders = ",".join("?" for _ in matches)
            conn.execute(
                f"DELETE FROM memory_candidates WHERE id IN ({placeholders})",
                tuple(matches),
            )

    with _connect(path) as conn:
        rows = list(
            conn.execute(
                """
                SELECT * FROM memory_candidates
                ORDER BY created_at, id
                """
            )
        )
        remaining_matches = {
            match.row_id: match.reason
            for row in rows
            if (match := classify(row)) is not None
        }
        after_report.write_text(
            _report_rows(f"After cleanup: {path}", rows, remaining_matches),
            encoding="utf-8",
        )

    return backup_path, before_report, after_report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ledgers", nargs="+", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    for ledger in args.ledgers:
        backup, before, after = clean_ledger(ledger, apply=args.apply)
        print(f"ledger={ledger}")
        if backup:
            print(f"backup={backup}")
        print(f"before_report={before}")
        print(f"after_report={after}")


if __name__ == "__main__":
    main()
