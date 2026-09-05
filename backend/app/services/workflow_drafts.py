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

from app.services.sqlite_util import connect as sqlite_connect
from app.teacher_agent.executive_verification import (
    artifact_fingerprint as artifact_hash,
)

TERMINAL_STATUSES = {"committed", "saved", "discarded"}
_ADOPTING_STATUS = "adopting"
# Ingest review phase always means the teacher has compiled wiki proposals.
_TOUCHED_STATUSES = frozenset({"reviewing"})


def default_workflow_draft_store_path(wiki_root: str | Path) -> Path:
    return Path(wiki_root) / "workflow" / "workflow_drafts.sqlite"


def serialize_structured_artifact(value: Any) -> str:
    """Return the one stable representation used for structured draft guards."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def draft_has_resumable_work(row: WorkflowDraftRow) -> bool:
    """True when a draft is more than an empty page-open shell.

    Opening Plan / Update Memory creates a durable draft immediately (often with
    an assistant opening message). Class-home Draft chips and timeline
    "Edit memory draft" should only appear after teacher progress.
    """
    if row.artifact_revision > 0:
        return True
    if row.status in _TOUCHED_STATUSES:
        return True
    return any(
        isinstance(item, dict) and item.get("role") == "user"
        for item in (row.messages_json or [])
    )


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
    active_review_json: dict[str, Any]
    review_generation: int
    created_at: str
    updated_at: str

    @classmethod
    def from_sqlite(cls, row: sqlite3.Row) -> WorkflowDraftRow:
        columns = row.keys()
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
            artifact_hash=row["artifact_hash"]
            or artifact_hash(row["artifact_markdown"] or ""),
            runtime_json=_loads_dict(row["runtime_json"]),
            executive_json=(
                _loads_dict(row["executive_json"])
                if "executive_json" in columns
                else {}
            ),
            messages_json=_loads_list(row["messages_json"]),
            backend_session_id=row["backend_session_id"] or "",
            turn_in_progress=bool(row["turn_in_progress"])
            if "turn_in_progress" in columns
            else False,
            latest_turn_complete=(
                bool(row["latest_turn_complete"])
                if "latest_turn_complete" in columns
                else True
            ),
            pending_turn_json=(
                _loads_dict(row["pending_turn_json"])
                if "pending_turn_json" in columns
                else {}
            ),
            active_review_revision=(
                int(row["active_review_revision"])
                if row["active_review_revision"] is not None
                else None
            ),
            active_review_hash=row["active_review_hash"],
            active_review_json=(
                _loads_dict(row["active_review_json"])
                if "active_review_json" in columns
                else {}
            ),
            review_generation=(
                int(row["review_generation"]) if "review_generation" in columns else 0
            ),
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
                  active_review_json TEXT NOT NULL DEFAULT '{}',
                  review_generation INTEGER NOT NULL DEFAULT 0,
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
            self._ensure_column(
                conn, "latest_turn_complete", "INTEGER NOT NULL DEFAULT 1"
            )
            self._ensure_column(conn, "pending_turn_json", "TEXT NOT NULL DEFAULT '{}'")
            self._ensure_column(conn, "executive_json", "TEXT NOT NULL DEFAULT '{}'")
            # These two are in the CREATE TABLE above, but a DB created before
            # they were added would lack them — migrate additively like the rest.
            self._ensure_column(conn, "active_review_revision", "INTEGER")
            self._ensure_column(conn, "active_review_hash", "TEXT")
            self._ensure_column(
                conn, "active_review_json", "TEXT NOT NULL DEFAULT '{}'"
            )
            self._ensure_column(conn, "review_generation", "INTEGER NOT NULL DEFAULT 0")

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
        now = _utc_now()
        draft_id = str(uuid.uuid4())
        session_id = backend_session_id or str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
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
            if existing is not None:
                return OpenWorkflowDraftResult(
                    row=WorkflowDraftRow.from_sqlite(existing), created=False
                )
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
            inserted = conn.execute(
                "SELECT * FROM workflow_draft WHERE draft_id = ?", (draft_id,)
            ).fetchone()
            if inserted is None:  # pragma: no cover - guarded by the same transaction
                raise RuntimeError("workflow draft insert was not visible")
            return OpenWorkflowDraftResult(
                row=WorkflowDraftRow.from_sqlite(inserted), created=True
            )

    def open_structured_draft(
        self,
        identity: WorkflowDraftIdentity,
        *,
        default_status: str,
        artifact: Any,
        runtime_json: dict[str, Any] | None = None,
    ) -> OpenWorkflowDraftResult:
        """Open/resume a draft whose artifact is canonical compact JSON."""
        return self.open_draft(
            identity,
            default_status=default_status,
            artifact_markdown=serialize_structured_artifact(artifact),
            runtime_json=runtime_json,
        )

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

    def list_touched_for_class(
        self, class_id: str, *, mode: str | None = None
    ) -> list[WorkflowDraftRow]:
        """Active drafts with teacher progress (for class-home / timeline chips)."""
        return [
            row
            for row in self.list_active_for_class(class_id, mode=mode)
            if draft_has_resumable_work(row)
        ]

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
        if current.status == _ADOPTING_STATUS:
            raise WorkflowDraftConflict("draft_adoption_in_progress")
        new_hash = artifact_hash(artifact_markdown)
        revision = current.artifact_revision
        artifact_changed = new_hash != current.artifact_hash
        if artifact_changed:
            revision += 1
        now = _utc_now()
        with self._connect() as conn:
            cursor = conn.execute(
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
                    active_review_revision = ?,
                    active_review_hash = ?,
                    active_review_json = ?,
                    review_generation = ?,
                    updated_at = ?
                WHERE draft_id = ?
                  AND status = ?
                  AND artifact_revision = ?
                  AND artifact_hash = ?
                  AND review_generation = ?
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
                    None if artifact_changed else current.active_review_revision,
                    None if artifact_changed else current.active_review_hash,
                    _dumps({} if artifact_changed else current.active_review_json),
                    current.review_generation + int(artifact_changed),
                    now,
                    draft_id,
                    current.status,
                    current.artifact_revision,
                    current.artifact_hash,
                    current.review_generation,
                ),
            )
        if cursor.rowcount != 1:
            row = self.get(draft_id)
            if row.status == _ADOPTING_STATUS:
                raise WorkflowDraftConflict("draft_adoption_in_progress")
            raise WorkflowDraftConflict("draft_changed_since_save_started")
        return self.get(draft_id)

    def mark_review_snapshot(
        self,
        draft_id: str,
        *,
        revision: int,
        artifact_hash_value: str,
        review_json: dict[str, Any] | None = None,
        review_generation: int | None = None,
    ) -> WorkflowDraftRow:
        if review_json:
            self._validate_review_snapshot_json(
                review_json, revision=revision, artifact_hash_value=artifact_hash_value
            )
        now = _utc_now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE workflow_draft
                SET active_review_revision = ?,
                    active_review_hash = ?,
                    active_review_json = ?,
                    updated_at = ?
                WHERE draft_id = ?
                  AND artifact_revision = ?
                  AND artifact_hash = ?
                  AND status NOT IN ('committed', 'saved', 'discarded', 'adopting')
                  AND (? IS NULL OR review_generation = ?)
                """,
                (
                    revision,
                    artifact_hash_value,
                    _dumps(review_json or {}),
                    now,
                    draft_id,
                    revision,
                    artifact_hash_value,
                    review_generation,
                    review_generation,
                ),
            )
        if cursor.rowcount != 1:
            self.get(draft_id)
            raise WorkflowDraftConflict("draft_changed_since_review_created")
        return self.get(draft_id)

    def begin_course_network_review(
        self,
        draft_id: str,
        *,
        expected_revision: int,
        expected_hash: str,
    ) -> WorkflowDraftRow:
        """Invalidate prior review state and reserve a generation for one review.

        Completion must present this generation, preventing an older in-flight
        reviewer from replacing a newer review for the same artifact.
        """
        now = _utc_now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE workflow_draft
                SET active_review_revision = NULL,
                    active_review_hash = NULL,
                    active_review_json = '{}',
                    review_generation = review_generation + 1,
                    updated_at = ?
                WHERE draft_id = ?
                  AND status = 'draft'
                  AND artifact_revision = ?
                  AND artifact_hash = ?
                """,
                (now, draft_id, expected_revision, expected_hash),
            )
            claimed = (
                WorkflowDraftRow.from_sqlite(
                    conn.execute(
                        "SELECT * FROM workflow_draft WHERE draft_id = ?", (draft_id,)
                    ).fetchone()
                )
                if cursor.rowcount == 1
                else None
            )
        if cursor.rowcount != 1:
            row = self.get(draft_id)
            if row.status in TERMINAL_STATUSES or row.status == _ADOPTING_STATUS:
                raise WorkflowDraftConflict("course_network_draft_not_active")
            raise WorkflowDraftConflict("draft_changed_since_review_created")
        assert claimed is not None
        return claimed

    def reserve_course_network_adoption(
        self,
        draft_id: str,
        *,
        expected_revision: int,
        expected_hash: str,
    ) -> WorkflowDraftRow:
        """Atomically claim one exact reviewed course-network draft for adoption."""
        now = _utc_now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE workflow_draft
                SET status = ?, updated_at = ?
                WHERE draft_id = ?
                  AND status = 'draft'
                  AND artifact_revision = ?
                  AND artifact_hash = ?
                  AND active_review_revision = ?
                  AND active_review_hash = ?
                """,
                (
                    _ADOPTING_STATUS,
                    now,
                    draft_id,
                    expected_revision,
                    expected_hash,
                    expected_revision,
                    expected_hash,
                ),
            )
        if cursor.rowcount != 1:
            row = self.get(draft_id)
            if row.status == _ADOPTING_STATUS:
                raise WorkflowDraftConflict("draft_adoption_in_progress")
            if row.status in TERMINAL_STATUSES:
                raise WorkflowDraftConflict("course_network_draft_not_active")
            raise WorkflowDraftConflict("draft_changed_since_review_created")
        return self.get(draft_id)

    def release_course_network_adoption(
        self, draft_id: str, *, expected_revision: int, expected_hash: str
    ) -> WorkflowDraftRow:
        now = _utc_now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE workflow_draft
                SET status = 'draft', updated_at = ?
                WHERE draft_id = ?
                  AND status = 'adopting'
                  AND artifact_revision = ?
                  AND artifact_hash = ?
                """,
                (now, draft_id, expected_revision, expected_hash),
            )
        if cursor.rowcount != 1:
            raise WorkflowDraftConflict("draft_adoption_state_lost")
        return self.get(draft_id)

    def complete_course_material_approval(
        self,
        draft_id: str,
        *,
        expected_revision: int,
        expected_hash: str,
        runtime_json: dict,
    ) -> WorkflowDraftRow:
        """Finish an exact reserved publication while preserving the mapping-review draft."""
        with self._connect() as conn:
            cursor = conn.execute(
                """UPDATE workflow_draft SET status = 'draft', runtime_json = ?, updated_at = ?
                   WHERE draft_id = ? AND status = 'adopting'
                     AND artifact_revision = ? AND artifact_hash = ?
                     AND active_review_revision = ? AND active_review_hash = ?""",
                (
                    _dumps(runtime_json),
                    _utc_now(),
                    draft_id,
                    expected_revision,
                    expected_hash,
                    expected_revision,
                    expected_hash,
                ),
            )
        if cursor.rowcount != 1:
            raise WorkflowDraftConflict("draft_adoption_state_lost")
        return self.get(draft_id)

    def record_course_network_adoption_recovery(
        self,
        draft_id: str,
        *,
        expected_revision: int,
        expected_hash: str,
        operation_id: str,
    ) -> WorkflowDraftRow:
        """Retain a durable repair marker instead of silently reopening a draft."""
        row = self.get(draft_id)
        recovery = {
            "course_network_adoption_recovery": {
                "operation_id": operation_id,
                "expected_revision": expected_revision,
                "expected_hash": expected_hash,
            }
        }
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE workflow_draft
                SET pending_turn_json = ?, updated_at = ?
                WHERE draft_id = ?
                  AND status = 'adopting'
                  AND artifact_revision = ?
                  AND artifact_hash = ?
                """,
                (
                    _dumps({**row.pending_turn_json, **recovery}),
                    _utc_now(),
                    draft_id,
                    expected_revision,
                    expected_hash,
                ),
            )
        if cursor.rowcount != 1:
            raise WorkflowDraftConflict("draft_adoption_state_lost")
        return self.get(draft_id)

    def complete_course_network_adoption(
        self, draft_id: str, *, expected_revision: int, expected_hash: str
    ) -> WorkflowDraftRow:
        now = _utc_now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE workflow_draft
                SET status = 'committed', updated_at = ?
                WHERE draft_id = ?
                  AND status = 'adopting'
                  AND artifact_revision = ?
                  AND artifact_hash = ?
                  AND active_review_revision = ?
                  AND active_review_hash = ?
                """,
                (
                    now,
                    draft_id,
                    expected_revision,
                    expected_hash,
                    expected_revision,
                    expected_hash,
                ),
            )
        if cursor.rowcount != 1:
            raise WorkflowDraftConflict("draft_adoption_state_lost")
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
        if (
            row.artifact_revision != expected_revision
            or row.artifact_hash != expected_hash
        ):
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
                WHERE draft_id = ? AND status != 'adopting'
                """,
                (status, now, draft_id),
            )
        if cursor.rowcount != 1:
            row = self.get(draft_id)
            if row.status == _ADOPTING_STATUS:
                raise WorkflowDraftConflict("draft_adoption_in_progress")
            raise KeyError(f"Unknown workflow draft: {draft_id}")
        return self.get(draft_id)

    def _connect(self) -> sqlite3.Connection:
        return sqlite_connect(self.db_path, row_factory=True)

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, name: str, definition: str) -> None:
        columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(workflow_draft)")
        }
        if name not in columns:
            conn.execute(f"ALTER TABLE workflow_draft ADD COLUMN {name} {definition}")

    @staticmethod
    def _validate_review_snapshot_json(
        review_json: dict[str, Any], *, revision: int, artifact_hash_value: str
    ) -> None:
        has_artifact_binding = (
            "artifact_revision" in review_json or "artifact_hash" in review_json
        )
        if has_artifact_binding and review_json.get("artifact_revision") != revision:
            raise ValueError("review snapshot revision does not match artifact")
        if (
            has_artifact_binding
            and review_json.get("artifact_hash") != artifact_hash_value
        ):
            raise ValueError("review snapshot hash does not match artifact")
        if review_json.get("decision") == "accept" and any(
            isinstance(finding, dict) and finding.get("severity") == "block"
            for finding in review_json.get("findings", [])
        ):
            raise ValueError("accept review cannot contain blocking findings")


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
