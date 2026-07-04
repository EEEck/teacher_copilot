"""SQLite-backed durable memory candidate ledger.

The ledger is evidence for review, not canonical memory. It stores proposed
memory observations across sessions so later review jobs can group, approve,
reject, or snooze them without replaying full chats.
"""

from __future__ import annotations

import json
import hashlib
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable

from app.teacher_agent.memory_targets import (
    canonical_memory_target,
    is_global_teacher_target,
    is_supported_runtime_target,
    memory_channel_for_target,
)

if TYPE_CHECKING:
    from app.services.memory_sweep import MemorySweepProposal


VALID_STATUSES = {
    "captured",
    "grouped",
    "proposed",
    "approved",
    "applied",
    "rejected",
    "snoozed",
    "deleted",
    "expired",
}

OPEN_STATUSES = ("captured", "grouped", "proposed", "snoozed")
REVIEW_STATUSES = ("captured", "grouped", "proposed")
SNOOZE_DAYS = 7


def default_memory_candidate_ledger_path(wiki_root: str | Path) -> Path:
    return Path(wiki_root) / "workflow" / "memory_candidates.sqlite"


@dataclass(frozen=True)
class MemoryCandidateRow:
    id: str
    created_at: str
    updated_at: str
    class_id: str | None
    subject: str | None
    workflow: str
    session_id: str | None
    turn_index: int
    channel: str
    target: str
    section: str
    candidate_update: str
    evidence_summary: str
    evidence_refs: list[str] = field(default_factory=list)
    source: str = "inferred_from_session"
    basis: str = "inferred"
    confidence: str = "low"
    cluster_key: str | None = None
    status: str = "captured"
    promoted_at: str | None = None
    review_batch_id: str | None = None
    rejection_reason: str | None = None
    snoozed_until: str | None = None

    @classmethod
    def from_sqlite(cls, row: sqlite3.Row) -> "MemoryCandidateRow":
        refs_raw = row["evidence_refs_json"] or "[]"
        try:
            refs = json.loads(refs_raw)
        except json.JSONDecodeError:
            refs = []
        if not isinstance(refs, list):
            refs = []
        return cls(
            id=row["id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            class_id=row["class_id"],
            subject=row["subject"],
            workflow=row["workflow"],
            session_id=row["session_id"],
            turn_index=int(row["turn_index"] or 0),
            channel=row["channel"],
            target=row["target"],
            section=row["section"],
            candidate_update=row["candidate_update"],
            evidence_summary=row["evidence_summary"],
            evidence_refs=[str(ref) for ref in refs],
            source=row["source"],
            basis=row["basis"],
            confidence=row["confidence"],
            cluster_key=row["cluster_key"],
            status=row["status"],
            promoted_at=row["promoted_at"],
            review_batch_id=row["review_batch_id"],
            rejection_reason=row["rejection_reason"],
            snoozed_until=row["snoozed_until"],
        )


class MemoryCandidateLedger:
    """Small SQLite facade for durable memory candidates."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_candidates (
                  id TEXT PRIMARY KEY,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  class_id TEXT,
                  subject TEXT,
                  workflow TEXT NOT NULL,
                  session_id TEXT,
                  turn_index INTEGER NOT NULL DEFAULT 0,
                  channel TEXT NOT NULL,
                  target TEXT NOT NULL,
                  section TEXT NOT NULL,
                  candidate_update TEXT NOT NULL,
                  evidence_summary TEXT NOT NULL,
                  evidence_refs_json TEXT NOT NULL DEFAULT '[]',
                  source TEXT NOT NULL,
                  basis TEXT NOT NULL,
                  confidence TEXT NOT NULL,
                  cluster_key TEXT,
                  status TEXT NOT NULL,
                  promoted_at TEXT,
                  review_batch_id TEXT,
                  rejection_reason TEXT,
                  snoozed_until TEXT
                )
                """
            )
            self._ensure_column(conn, "snoozed_until", "TEXT")
            self._backfill_snoozed_until(conn)
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_candidates_scope_status
                ON memory_candidates (class_id, subject, status, channel)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_candidates_cluster
                ON memory_candidates (cluster_key, status)
                """
            )

    def add(self, candidate: MemoryCandidateRow) -> None:
        self.add_many([candidate])

    def add_many(self, candidates: Iterable[MemoryCandidateRow]) -> None:
        rows = list(candidates)
        if not rows:
            return
        for candidate in rows:
            self._validate_candidate(candidate)
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO memory_candidates (
                  id, created_at, updated_at, class_id, subject, workflow,
                  session_id, turn_index, channel, target, section,
                  candidate_update, evidence_summary, evidence_refs_json,
                  source, basis, confidence, cluster_key, status, promoted_at,
                  review_batch_id, rejection_reason, snoozed_until
                ) VALUES (
                  :id, :created_at, :updated_at, :class_id, :subject,
                  :workflow, :session_id, :turn_index, :channel, :target,
                  :section, :candidate_update, :evidence_summary,
                  :evidence_refs_json, :source, :basis, :confidence,
                  :cluster_key, :status, :promoted_at, :review_batch_id,
                  :rejection_reason, :snoozed_until
                )
                ON CONFLICT(id) DO NOTHING
                """,
                [self._to_params(candidate) for candidate in rows],
            )

    def list_candidates(
        self,
        *,
        class_id: str | None = None,
        subject: str | None = None,
        statuses: Iterable[str] | None = None,
        include_global: bool = True,
    ) -> list[MemoryCandidateRow]:
        where: list[str] = []
        params: list[str] = []
        if statuses is not None:
            status_list = tuple(statuses)
            for status in status_list:
                self._validate_status(status)
            if status_list:
                placeholders = ",".join("?" for _ in status_list)
                where.append(f"status IN ({placeholders})")
                params.extend(status_list)
        if class_id is not None:
            if include_global:
                where.append("(class_id = ? OR class_id IS NULL)")
            else:
                where.append("class_id = ?")
            params.append(class_id)
        if subject is not None:
            where.append("(subject = ? OR subject IS NULL)")
            params.append(subject)
        sql = "SELECT * FROM memory_candidates"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY created_at, id"
        with self._connect() as conn:
            return [
                MemoryCandidateRow.from_sqlite(row) for row in conn.execute(sql, params)
            ]

    def list_review_candidates(
        self,
        *,
        class_id: str | None = None,
        subject: str | None = None,
        include_global: bool = True,
        now: str | None = None,
    ) -> list[MemoryCandidateRow]:
        review_now = now or _utc_now()
        active_statuses = REVIEW_STATUSES
        active_placeholders = ", ".join("?" for _ in active_statuses)
        where = [
            f"""(
              status IN ({active_placeholders})
              OR (status = ? AND snoozed_until IS NOT NULL AND snoozed_until <= ?)
              OR (
                status = ?
                AND EXISTS (
                  SELECT 1 FROM memory_candidates newer
                  WHERE newer.status IN ({active_placeholders})
                    AND newer.created_at > memory_candidates.updated_at
                    AND COALESCE(newer.class_id, '') = COALESCE(memory_candidates.class_id, '')
                    AND COALESCE(newer.subject, '') = COALESCE(memory_candidates.subject, '')
                    AND newer.channel = memory_candidates.channel
                    AND newer.target = memory_candidates.target
                    AND newer.section = memory_candidates.section
                )
              )
            )"""
        ]
        params = [*active_statuses, "snoozed", review_now, "snoozed", *active_statuses]
        if class_id is not None:
            if include_global:
                where.append("(class_id = ? OR class_id IS NULL)")
            else:
                where.append("class_id = ?")
            params.append(class_id)
        if subject is not None:
            where.append("(subject = ? OR subject IS NULL)")
            params.append(subject)
        sql = "SELECT * FROM memory_candidates WHERE " + " AND ".join(where)
        sql += " ORDER BY created_at, id"
        with self._connect() as conn:
            return [
                MemoryCandidateRow.from_sqlite(row) for row in conn.execute(sql, params)
            ]

    def propose_for_sweep(
        self,
        *,
        class_id: str,
        subject: str | None = None,
        now: str | None = None,
    ) -> dict[str, list["MemorySweepProposal"]]:
        """Compatibility adapter for Memory Sweep grouping."""
        from app.services.memory_sweep import build_sweep_proposals

        candidates = self.list_review_candidates(
            class_id=class_id,
            subject=subject,
            include_global=True,
            now=now,
        )
        return build_sweep_proposals(candidates)

    def update_status(
        self,
        candidate_id: str,
        status: str,
        *,
        updated_at: str,
        rejection_reason: str | None = None,
        review_batch_id: str | None = None,
        promoted_at: str | None = None,
        snoozed_until: str | None = None,
    ) -> None:
        self._validate_status(status)
        if status == "snoozed" and snoozed_until is None:
            snoozed_until = _add_days(updated_at, SNOOZE_DAYS)
        if status != "snoozed":
            snoozed_until = None
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE memory_candidates
                SET status = ?,
                    updated_at = ?,
                    rejection_reason = ?,
                    review_batch_id = COALESCE(?, review_batch_id),
                    promoted_at = COALESCE(?, promoted_at),
                    snoozed_until = ?
                WHERE id = ?
                """,
                (
                    status,
                    updated_at,
                    rejection_reason,
                    review_batch_id,
                    promoted_at,
                    snoozed_until,
                    candidate_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"unknown memory candidate: {candidate_id}")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, name: str, definition: str) -> None:
        columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(memory_candidates)")
        }
        if name not in columns:
            conn.execute(f"ALTER TABLE memory_candidates ADD COLUMN {name} {definition}")

    @staticmethod
    def _backfill_snoozed_until(conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            """
            SELECT id, updated_at FROM memory_candidates
            WHERE status = 'snoozed' AND snoozed_until IS NULL
            """
        ).fetchall()
        for row in rows:
            conn.execute(
                """
                UPDATE memory_candidates
                SET snoozed_until = ?
                WHERE id = ?
                """,
                (_add_days(row["updated_at"], SNOOZE_DAYS), row["id"]),
            )

    @staticmethod
    def _to_params(candidate: MemoryCandidateRow) -> dict[str, object]:
        return {
            "id": candidate.id,
            "created_at": candidate.created_at,
            "updated_at": candidate.updated_at,
            "class_id": candidate.class_id,
            "subject": candidate.subject,
            "workflow": candidate.workflow,
            "session_id": candidate.session_id,
            "turn_index": candidate.turn_index,
            "channel": candidate.channel,
            "target": candidate.target,
            "section": candidate.section,
            "candidate_update": candidate.candidate_update,
            "evidence_summary": candidate.evidence_summary,
            "evidence_refs_json": json.dumps(candidate.evidence_refs),
            "source": candidate.source,
            "basis": candidate.basis,
            "confidence": candidate.confidence,
            "cluster_key": candidate.cluster_key,
            "status": candidate.status,
            "promoted_at": candidate.promoted_at,
            "review_batch_id": candidate.review_batch_id,
            "rejection_reason": candidate.rejection_reason,
            "snoozed_until": candidate.snoozed_until,
        }

    @staticmethod
    def _validate_candidate(candidate: MemoryCandidateRow) -> None:
        if not candidate.id.strip():
            raise ValueError("candidate id cannot be empty")
        if not candidate.channel.strip():
            raise ValueError("candidate channel cannot be empty")
        if not candidate.target.strip():
            raise ValueError("candidate target cannot be empty")
        if not candidate.candidate_update.strip():
            raise ValueError("candidate update cannot be empty")
        MemoryCandidateLedger._validate_status(candidate.status)

    @staticmethod
    def _validate_status(status: str) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(f"unsupported memory candidate status: {status}")


def rows_from_runtime_candidates(
    candidates: Iterable[Any],
    *,
    class_id: str,
    subject: str | None,
    workflow: str,
    session_id: str,
    turn_index: int,
    now: str | None = None,
) -> list[MemoryCandidateRow]:
    """Convert validated runtime candidates into durable ledger rows.

    Runtime candidates are session state; ledger rows are cross-session review
    evidence. The row id includes the source session so repeated behavior across
    sessions remains visible as multiple signals, while duplicate capture within
    a turn/session is idempotent.
    """
    ts = now or _utc_now()
    rows: list[MemoryCandidateRow] = []
    for candidate in candidates:
        raw_target = _field(candidate, "target").strip()
        update = " ".join(_field(candidate, "candidate_update").split())
        if not raw_target or not update:
            continue
        if not is_supported_runtime_target(raw_target):
            continue
        target = canonical_memory_target(raw_target)
        section = _field(candidate, "section") or "General"
        source = _field(candidate, "source") or "inferred_from_session"
        basis = _field(candidate, "basis") or "inferred"
        confidence = _field(candidate, "confidence") or "low"
        refs = _list_field(candidate, "evidence_refs")
        channel = memory_channel_for_target(target)
        row_class_id = None if is_global_teacher_target(target) else class_id
        row_subject = subject if channel == "subject_concept" else None
        cluster_key = _cluster_key(row_class_id, subject, target, section, update)
        row_id = _row_id(
            workflow=workflow,
            session_id=session_id,
            target=target,
            section=section,
            update=update,
        )
        rows.append(
            MemoryCandidateRow(
                id=row_id,
                created_at=ts,
                updated_at=ts,
                class_id=row_class_id,
                subject=row_subject,
                workflow=workflow,
                session_id=session_id,
                turn_index=turn_index,
                channel=channel,
                target=target,
                section=section,
                candidate_update=update,
                evidence_summary=_field(candidate, "evidence"),
                evidence_refs=refs,
                source=source,
                basis=basis,
                confidence=confidence,
                cluster_key=cluster_key,
                status="captured",
            )
        )
    return rows


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _add_days(value: str, days: int) -> str:
    return (
        (_parse_utc(value) + timedelta(days=days))
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _field(candidate: Any, name: str) -> str:
    if isinstance(candidate, dict):
        value = candidate.get(name, "")
    else:
        value = getattr(candidate, name, "")
    return str(value or "")


def _list_field(candidate: Any, name: str) -> list[str]:
    if isinstance(candidate, dict):
        value = candidate.get(name, [])
    else:
        value = getattr(candidate, name, [])
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _row_id(
    *,
    workflow: str,
    session_id: str,
    target: str,
    section: str,
    update: str,
) -> str:
    raw = "|".join(
        [
            workflow.strip().lower(),
            session_id.strip(),
            target.strip().lower(),
            section.strip().lower(),
            update.strip().lower(),
        ]
    )
    return "cand_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _cluster_key(
    class_id: str | None,
    subject: str | None,
    target: str,
    section: str,
    update: str,
) -> str:
    scope = class_id or subject or "global"
    digest = hashlib.sha256(update.strip().lower().encode("utf-8")).hexdigest()[:12]
    return ".".join(
        part
        for part in (
            scope.strip().lower().replace("/", "_"),
            target.strip().lower().replace("/", "_"),
            section.strip().lower().replace(" ", "_"),
            digest,
        )
        if part
    )


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
