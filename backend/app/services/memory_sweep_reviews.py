"""Durable Memory Sweep review storage.

Memory Sweep is a structured review workflow, not a chat/artifact workflow. This
store persists the generated cards plus teacher decisions so a sweep is generated
once for a ledger/wiki state and can be resumed after navigation or restart.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.memory_candidate_ledger import MemoryCandidateLedger
from app.services.memory_sweep import (
    build_student_summary_sweep_proposals,
    memory_sweep_target_excerpts,
)
from app.teacher_agent.memory_targets import canonical_memory_target
from app.teacher_agent.wiki_store import WikiStore


ACTIVE_STATUSES = {"generating", "ready", "stale", "applying", "failed"}
TERMINAL_STATUSES = {"completed", "discarded"}


def default_memory_sweep_review_store_path(wiki_root: str | Path) -> Path:
    return Path(wiki_root) / "workflow" / "memory_sweep_reviews.sqlite"


@dataclass(frozen=True)
class MemorySweepReviewRecord:
    review_id: str
    workspace_id: str
    class_id: str
    status: str
    source_fingerprint: str
    source: dict[str, Any]
    proposals: dict[str, Any]
    decisions: list[dict[str, Any]]
    has_teacher_edits: bool
    generated_at: str | None
    created_at: str
    updated_at: str
    completed_at: str | None
    error: str

    @classmethod
    def from_sqlite(cls, row: sqlite3.Row) -> "MemorySweepReviewRecord":
        return cls(
            review_id=row["review_id"],
            workspace_id=row["workspace_id"],
            class_id=row["class_id"],
            status=row["status"],
            source_fingerprint=row["source_fingerprint"],
            source=_loads_dict(row["source_json"]),
            proposals=_loads_dict(row["proposals_json"]),
            decisions=_loads_list(row["decisions_json"]),
            has_teacher_edits=bool(row["has_teacher_edits"]),
            generated_at=row["generated_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
            error=row["error"] or "",
        )


class MemorySweepReviewStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_sweep_review (
                  review_id TEXT PRIMARY KEY,
                  workspace_id TEXT NOT NULL DEFAULT 'local',
                  class_id TEXT NOT NULL,
                  status TEXT NOT NULL,
                  source_fingerprint TEXT NOT NULL,
                  source_json TEXT NOT NULL DEFAULT '{}',
                  proposals_json TEXT NOT NULL DEFAULT '{}',
                  decisions_json TEXT NOT NULL DEFAULT '[]',
                  has_teacher_edits INTEGER NOT NULL DEFAULT 0,
                  generated_at TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  completed_at TEXT,
                  error TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_sweep_review_active
                ON memory_sweep_review (workspace_id, class_id, status, updated_at)
                """
            )

    def get_active(self, class_id: str, *, workspace_id: str = "local") -> MemorySweepReviewRecord | None:
        statuses = tuple(sorted(ACTIVE_STATUSES))
        placeholders = ",".join("?" for _ in statuses)
        with self._connect() as conn:
            row = conn.execute(
                f"""
                SELECT * FROM memory_sweep_review
                WHERE workspace_id = ?
                  AND class_id = ?
                  AND status IN ({placeholders})
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 1
                """,
                (workspace_id, class_id, *statuses),
            ).fetchone()
        return MemorySweepReviewRecord.from_sqlite(row) if row is not None else None

    def get(self, review_id: str) -> MemorySweepReviewRecord:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM memory_sweep_review WHERE review_id = ?",
                (review_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown Memory Sweep review: {review_id}")
        return MemorySweepReviewRecord.from_sqlite(row)

    def create_generating(
        self,
        *,
        class_id: str,
        source_fingerprint: str,
        source: dict[str, Any],
        workspace_id: str = "local",
    ) -> MemorySweepReviewRecord:
        now = _utc_now()
        review_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memory_sweep_review (
                  review_id, workspace_id, class_id, status, source_fingerprint,
                  source_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review_id,
                    workspace_id,
                    class_id,
                    "generating",
                    source_fingerprint,
                    _dumps(source),
                    now,
                    now,
                ),
            )
        return self.get(review_id)

    def mark_ready(
        self,
        review_id: str,
        *,
        proposals: dict[str, Any],
        warnings: list[str] | None = None,
    ) -> MemorySweepReviewRecord:
        payload = dict(proposals)
        if warnings is not None and "warnings" not in payload:
            payload["warnings"] = warnings
        now = _utc_now()
        return self._update_while_generating(
            review_id,
            """
            status = ?,
            proposals_json = ?,
            generated_at = COALESCE(generated_at, ?),
            updated_at = ?,
            error = ''
            """,
            ("ready", _dumps(payload), now, now),
        )

    def mark_failed(self, review_id: str, *, error: str) -> MemorySweepReviewRecord:
        now = _utc_now()
        return self._update_while_generating(
            review_id,
            "status = ?, error = ?, updated_at = ?",
            ("failed", error, now),
        )

    def save_decisions(
        self, review_id: str, *, decisions: list[dict[str, Any]]
    ) -> MemorySweepReviewRecord:
        now = _utc_now()
        return self._update(
            review_id,
            "decisions_json = ?, has_teacher_edits = ?, updated_at = ?",
            (_dumps(decisions), int(bool(decisions)), now),
        )

    def mark_stale(self, review_id: str) -> MemorySweepReviewRecord:
        return self._set_status(review_id, "stale")

    def mark_applying(self, review_id: str) -> MemorySweepReviewRecord:
        return self._set_status(review_id, "applying")

    def mark_completed(self, review_id: str) -> MemorySweepReviewRecord:
        now = _utc_now()
        return self._update(
            review_id,
            "status = ?, updated_at = ?, completed_at = ?",
            ("completed", now, now),
        )

    def discard(self, review_id: str) -> MemorySweepReviewRecord:
        return self._set_status(review_id, "discarded")

    def _set_status(self, review_id: str, status: str) -> MemorySweepReviewRecord:
        now = _utc_now()
        return self._update(
            review_id,
            "status = ?, updated_at = ?",
            (status, now),
        )

    def _update(
        self, review_id: str, assignments: str, params: tuple[Any, ...]
    ) -> MemorySweepReviewRecord:
        with self._connect() as conn:
            cursor = conn.execute(
                f"UPDATE memory_sweep_review SET {assignments} WHERE review_id = ?",
                (*params, review_id),
            )
        if cursor.rowcount != 1:
            raise KeyError(f"Unknown Memory Sweep review: {review_id}")
        return self.get(review_id)

    def _update_while_generating(
        self, review_id: str, assignments: str, params: tuple[Any, ...]
    ) -> MemorySweepReviewRecord:
        """Finish only the review generation that still owns this record.

        Discarding or refreshing may supersede an in-flight model task. Its
        eventual completion must not restore that obsolete review.
        """
        with self._connect() as conn:
            conn.execute(
                f"""
                UPDATE memory_sweep_review
                SET {assignments}
                WHERE review_id = ? AND status = 'generating'
                """,
                (*params, review_id),
            )
        return self.get(review_id)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn


def build_memory_sweep_source_snapshot(
    *,
    wiki: WikiStore,
    ledger: MemoryCandidateLedger,
    class_id: str,
) -> dict[str, Any]:
    cls = wiki.get_class(class_id)
    rows = ledger.list_review_candidates(
        class_id=class_id,
        subject=cls.subject,
        include_global=True,
    )
    targets = {canonical_memory_target(row.target) for row in rows}
    synthetic = build_student_summary_sweep_proposals(wiki, class_id)
    for proposals in synthetic.values():
        for proposal in proposals:
            targets.add(canonical_memory_target(proposal.target))

    excerpts = memory_sweep_target_excerpts(wiki, class_id, targets)
    return {
        "class_id": class_id,
        "subject": cls.subject,
        "ledger_rows": [
            {
                "id": row.id,
                "status": row.status,
                "updated_at": row.updated_at,
                "target": canonical_memory_target(row.target),
                "section": row.section,
                "cluster_key": row.cluster_key or "",
                "content_hash": _sha256(row.candidate_update),
            }
            for row in rows
        ],
        "synthetic_student_summaries": [
            {
                "candidate_id": proposal.candidate_id,
                "target": canonical_memory_target(proposal.target),
                "content_hash": _sha256(proposal.content),
                "excerpt_hash": _sha256(proposal.current_memory_excerpt),
            }
            for proposals in synthetic.values()
            for proposal in proposals
        ],
        "wiki_targets": [
            {"target": target, "excerpt_hash": _sha256(excerpt)}
            for target, excerpt in sorted(excerpts.items())
        ],
    }


def memory_sweep_source_fingerprint(source: dict[str, Any]) -> str:
    return _sha256(_dumps(source))


def memory_sweep_stale_reasons(
    previous: dict[str, Any], current: dict[str, Any]
) -> list[str]:
    """Return teacher-readable reasons that a saved review no longer matches memory."""
    reasons: list[str] = []
    previous_rows = {row["id"]: row for row in previous.get("ledger_rows", [])}
    current_rows = {row["id"]: row for row in current.get("ledger_rows", [])}
    added = len(set(current_rows) - set(previous_rows))
    removed = len(set(previous_rows) - set(current_rows))
    changed = sum(
        previous_rows[row_id] != current_rows[row_id]
        for row_id in set(previous_rows) & set(current_rows)
    )
    if added:
        reasons.append(_counted_reason(added, "new memory candidate arrived after this draft was generated."))
    if removed:
        reasons.append(_counted_reason(removed, "memory candidate is no longer open for review."))
    if changed:
        reasons.append(_counted_reason(changed, "memory candidate changed after this draft was generated."))

    previous_targets = {
        item["target"]: item for item in previous.get("wiki_targets", [])
    }
    current_targets = {item["target"]: item for item in current.get("wiki_targets", [])}
    target_changes = sum(
        previous_targets[target] != current_targets.get(target)
        for target in set(previous_targets) | set(current_targets)
    )
    if target_changes:
        reasons.append(_counted_reason(target_changes, "memory page changed after this draft was generated."))

    previous_summaries = {
        item["candidate_id"]: item
        for item in previous.get("synthetic_student_summaries", [])
    }
    current_summaries = {
        item["candidate_id"]: item
        for item in current.get("synthetic_student_summaries", [])
    }
    summary_changes = sum(
        previous_summaries[candidate_id] != current_summaries.get(candidate_id)
        for candidate_id in set(previous_summaries) | set(current_summaries)
    )
    if summary_changes:
        reasons.append(_counted_reason(summary_changes, "student summary changed after this draft was generated."))
    return reasons


def _counted_reason(count: int, singular: str) -> str:
    if count == 1:
        return f"1 {singular}"
    return f"{count} {singular.replace('candidate ', 'candidates ').replace('page ', 'pages ').replace('summary ', 'summaries ').replace(' is ', ' are ').replace(' changed', ' changed')}"


def _sha256(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _loads_dict(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _loads_list(value: str | None) -> list[dict[str, Any]]:
    if not value:
        return []
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(loaded, list):
        return []
    return [item for item in loaded if isinstance(item, dict)]
