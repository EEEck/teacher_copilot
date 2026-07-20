"""Durable workflow draft store shared by artifact-style workflows.

The store is intentionally workflow-agnostic. It persists the common lifecycle
surface every chat-artifact workflow needs: identity, messages, runtime JSON,
artifact markdown, revision/hash guards, and terminal status.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.teacher_agent.executive_verification import artifact_fingerprint as artifact_hash

TERMINAL_STATUSES = {"committed", "saved", "discarded"}


def default_workflow_draft_store_path(wiki_root: str | Path) -> Path:
    return Path(wiki_root) / "workflow" / "workflow_drafts.sqlite"


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


@dataclass(frozen=True)
class WorkflowDraftIdentity:
    workspace_id: str
    class_id: str
    mode: str
    intent: str
    target_kind: str = ""
    lesson_date: str = ""
    lesson_title: str = ""


@dataclass(frozen=True)
class WorkflowDraftRow:
    draft_id: str
    workspace_id: str
    class_id: str
    mode: str
    intent: str
    target_kind: str
    lesson_date: str
    lesson_title: str
    status: str
    artifact_markdown: str
    artifact_revision: int
    artifact_hash: str
    runtime_json: dict[str, Any]
    executive_json: dict[str, Any]
    messages_json: list[dict[str, Any]]
    backend_session_id: str
    turn_in_progress: bool
    latest_turn_complete: bool
    pending_turn_json: dict[str, Any]
    active_review_revision: int | None
    active_review_hash: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_sqlite(cls, row: sqlite3.Row) -> "WorkflowDraftRow":
        return cls(
            draft_id=row["draft_id"],
            workspace_id=row["workspace_id"],
            class_id=row["class_id"],
            mode=row["mode"],
            intent=row["intent"],
            target_kind=row["target_kind"] or "",
            lesson_date=row["lesson_date"] or "",
            lesson_title=row["lesson_title"] or "",
            status=row["status"],
            artifact_markdown=row["artifact_markdown"] or "",
            artifact_revision=int(row["artifact_revision"] or 0),
            artifact_hash=row["artifact_hash"] or artifact_hash(row["artifact_markdown"] or ""),
            runtime_json=_loads_dict(row["runtime_json"]),
            executive_json=(
                _loads_dict(row["executive_json"])
                if "executive_json" in row.keys()
                else {}
            ),
            messages_json=_loads_list(row["messages_json"]),
            backend_session_id=row["backend_session_id"] or "",
            turn_in_progress=bool(row["turn_in_progress"]) if "turn_in_progress" in row.keys() else False,
            latest_turn_complete=(
                bool(row["latest_turn_complete"])
                if "latest_turn_complete" in row.keys()
                else True
            ),
            pending_turn_json=(
                _loads_dict(row["pending_turn_json"])
                if "pending_turn_json" in row.keys()
                else {}
            ),
            active_review_revision=(
                int(row["active_review_revision"])
                if row["active_review_revision"] is not None
                else None
            ),
            active_review_hash=row["active_review_hash"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass(frozen=True)
class OpenWorkflowDraftResult:
    row: WorkflowDraftRow
    created: bool


class WorkflowDraftConflict(ValueError):
    """Raised when a save/review request targets a stale artifact revision."""


class WorkflowDraftStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_draft (
                  draft_id TEXT PRIMARY KEY,
                  workspace_id TEXT NOT NULL DEFAULT 'local',
                  class_id TEXT NOT NULL,
                  mode TEXT NOT NULL,
                  intent TEXT NOT NULL,
                  target_kind TEXT NOT NULL DEFAULT '',
                  lesson_date TEXT NOT NULL DEFAULT '',
                  lesson_title TEXT NOT NULL DEFAULT '',
                  status TEXT NOT NULL,
                  artifact_markdown TEXT NOT NULL DEFAULT '',
                  artifact_revision INTEGER NOT NULL DEFAULT 0,
                  artifact_hash TEXT NOT NULL DEFAULT '',
                  runtime_json TEXT NOT NULL DEFAULT '{}',
                  executive_json TEXT NOT NULL DEFAULT '{}',
                  messages_json TEXT NOT NULL DEFAULT '[]',
                  backend_session_id TEXT NOT NULL DEFAULT '',
                  turn_in_progress INTEGER NOT NULL DEFAULT 0,
                  latest_turn_complete INTEGER NOT NULL DEFAULT 1,
                  pending_turn_json TEXT NOT NULL DEFAULT '{}',
                  active_review_revision INTEGER,
                  active_review_hash TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_workflow_draft_identity
                ON workflow_draft (
                  workspace_id, class_id, mode, intent, target_kind, lesson_date, status
                )
                """
            )
            self._ensure_column(conn, "turn_in_progress", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "latest_turn_complete", "INTEGER NOT NULL DEFAULT 1")
            self._ensure_column(conn, "pending_turn_json", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column(conn, "executive_json", "TEXT NOT NULL DEFAULT '{}'")

    def open_draft(
        self,
        identity: WorkflowDraftIdentity,
        *,
        default_status: str,
        artifact_markdown: str,
        runtime_json: dict[str, Any] | None = None,
        messages_json: list[dict[str, Any]] | None = None,
        backend_session_id: str | None = None,
    ) -> OpenWorkflowDraftResult:
        existing = self.find_active(identity)
        if existing is not None:
            return OpenWorkflowDraftResult(row=existing, created=False)

        now = _utc_now()
        draft_id = str(uuid.uuid4())
        session_id = backend_session_id or str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO workflow_draft (
                  draft_id, workspace_id, class_id, mode, intent, target_kind,
                  lesson_date, lesson_title, status, artifact_markdown,
                  artifact_revision, artifact_hash, runtime_json, messages_json,
                  backend_session_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_id,
                    identity.workspace_id,
                    identity.class_id,
                    identity.mode,
                    identity.intent,
                    identity.target_kind,
                    identity.lesson_date,
                    identity.lesson_title,
                    default_status,
                    artifact_markdown,
                    0,
                    artifact_hash(artifact_markdown),
                    _dumps(runtime_json or {}),
                    _dumps(messages_json or []),
                    session_id,
                    now,
                    now,
                ),
            )
        row = self.get(draft_id)
        return OpenWorkflowDraftResult(row=row, created=True)

    def find_active(self, identity: WorkflowDraftIdentity) -> WorkflowDraftRow | None:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM workflow_draft
                WHERE workspace_id = ?
                  AND class_id = ?
                  AND mode = ?
                  AND intent = ?
                  AND target_kind = ?
                  AND lesson_date = ?
                  AND status NOT IN ('committed', 'saved', 'discarded')
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 1
                """,
                (
                    identity.workspace_id,
                    identity.class_id,
                    identity.mode,
                    identity.intent,
                    identity.target_kind,
                    identity.lesson_date,
                ),
            ).fetchone()
        return WorkflowDraftRow.from_sqlite(rows) if rows is not None else None

    def find_active_by_backend_session_id(
        self, backend_session_id: str
    ) -> WorkflowDraftRow | None:
        """Find a resumable draft by the session ID held by an already-open UI."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM workflow_draft
                WHERE backend_session_id = ?
                  AND status NOT IN ('committed', 'saved', 'discarded')
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 1
                """,
                (backend_session_id,),
            ).fetchone()
        return WorkflowDraftRow.from_sqlite(row) if row is not None else None

    def list_active_for_class(
        self, class_id: str, *, mode: str | None = None
    ) -> list[WorkflowDraftRow]:
        query = """
            SELECT * FROM workflow_draft
            WHERE class_id = ?
              AND status NOT IN ('committed', 'saved', 'discarded')
        """
        params: list[Any] = [class_id]
        if mode is not None:
            query += " AND mode = ?"
            params.append(mode)
        query += " ORDER BY updated_at DESC, created_at DESC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [WorkflowDraftRow.from_sqlite(row) for row in rows]

    def list_in_progress(
        self, *, workspace_id: str | None = None
    ) -> list[WorkflowDraftRow]:
        """Draft turns the backend is running right now, across all classes.

        Backs the active-work query the frontend polls instead of keeping its
        own sessionStorage bookkeeping. Idle-but-active drafts are excluded:
        they are resumable work, not running work.
        """
        terminal = tuple(sorted(TERMINAL_STATUSES))
        placeholders = ",".join("?" for _ in terminal)
        query = f"""
            SELECT * FROM workflow_draft
            WHERE turn_in_progress = 1
              AND status NOT IN ({placeholders})
        """
        params: list[Any] = [*terminal]
        if workspace_id is not None:
            query += " AND workspace_id = ?"
            params.append(workspace_id)
        query += " ORDER BY updated_at DESC, created_at DESC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [WorkflowDraftRow.from_sqlite(row) for row in rows]

    def get(self, draft_id: str) -> WorkflowDraftRow:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM workflow_draft WHERE draft_id = ?",
                (draft_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown workflow draft: {draft_id}")
        return WorkflowDraftRow.from_sqlite(row)

    def save_from_session(
        self,
        *,
        draft_id: str,
        status: str,
        artifact_markdown: str,
        runtime_json: dict[str, Any] | None,
        messages_json: list[dict[str, Any]],
        backend_session_id: str,
        pending_turn_json: dict[str, Any] | None = None,
        turn_in_progress: bool = False,
        latest_turn_complete: bool = True,
        executive_json: dict[str, Any] | None = None,
    ) -> WorkflowDraftRow:
        current = self.get(draft_id)
        new_hash = artifact_hash(artifact_markdown)
        revision = current.artifact_revision
        if new_hash != current.artifact_hash:
            revision += 1
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE workflow_draft
                SET status = ?,
                    artifact_markdown = ?,
                    artifact_revision = ?,
                    artifact_hash = ?,
                    runtime_json = ?,
                    executive_json = ?,
                    messages_json = ?,
                    backend_session_id = ?,
                    turn_in_progress = ?,
                    latest_turn_complete = ?,
                    pending_turn_json = ?,
                    updated_at = ?
                WHERE draft_id = ?
                """,
                (
                    status,
                    artifact_markdown,
                    revision,
                    new_hash,
                    _dumps(runtime_json or {}),
                    _dumps(executive_json or {}),
                    _dumps(messages_json),
                    backend_session_id,
                    int(turn_in_progress),
                    int(latest_turn_complete),
                    _dumps(pending_turn_json or {}),
                    now,
                    draft_id,
                ),
            )
        return self.get(draft_id)

    def mark_review_snapshot(
        self, draft_id: str, *, revision: int, artifact_hash_value: str
    ) -> WorkflowDraftRow:
        now = _utc_now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE workflow_draft
                SET active_review_revision = ?,
                    active_review_hash = ?,
                    updated_at = ?
                WHERE draft_id = ?
                """,
                (revision, artifact_hash_value, now, draft_id),
            )
        if cursor.rowcount != 1:
            raise KeyError(f"Unknown workflow draft: {draft_id}")
        return self.get(draft_id)

    def validate_review_snapshot(
        self,
        draft_id: str,
        *,
        expected_revision: int,
        expected_hash: str,
    ) -> WorkflowDraftRow:
        row = self.get(draft_id)
        if row.active_review_revision != expected_revision:
            raise WorkflowDraftConflict("draft_changed_since_review_created")
        if row.active_review_hash != expected_hash:
            raise WorkflowDraftConflict("draft_changed_since_review_created")
        if row.artifact_revision != expected_revision:
            raise WorkflowDraftConflict("draft_changed_since_review_created")
        if row.artifact_hash != expected_hash:
            raise WorkflowDraftConflict("draft_changed_since_review_created")
        return row

    def validate_current_snapshot(
        self,
        draft_id: str,
        *,
        expected_revision: int,
        expected_hash: str,
    ) -> WorkflowDraftRow:
        row = self.get(draft_id)
        if row.artifact_revision != expected_revision or row.artifact_hash != expected_hash:
            raise WorkflowDraftConflict("draft_changed_since_review_created")
        return row

    def discard(self, draft_id: str) -> WorkflowDraftRow:
        return self._set_status(draft_id, "discarded")

    def mark_committed(self, draft_id: str) -> WorkflowDraftRow:
        return self._set_status(draft_id, "committed")

    def mark_saved(self, draft_id: str) -> WorkflowDraftRow:
        return self._set_status(draft_id, "saved")

    def _set_status(self, draft_id: str, status: str) -> WorkflowDraftRow:
        now = _utc_now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE workflow_draft
                SET status = ?,
                    updated_at = ?
                WHERE draft_id = ?
                """,
                (status, now, draft_id),
            )
        if cursor.rowcount != 1:
            raise KeyError(f"Unknown workflow draft: {draft_id}")
        return self.get(draft_id)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, name: str, definition: str) -> None:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(workflow_draft)")}
        if name not in columns:
            conn.execute(f"ALTER TABLE workflow_draft ADD COLUMN {name} {definition}")


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


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
