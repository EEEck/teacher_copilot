"""Invite-code beta identity, workspace provisioning, and telemetry storage."""

from __future__ import annotations

import difflib
import hashlib
import json
import secrets
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json(payload: dict[str, Any] | None) -> str:
    return json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)


@dataclass(frozen=True)
class RequestIdentity:
    tester_id: str
    workspace_id: str
    role: str
    wiki_root: Path


@dataclass(frozen=True)
class LoginResult:
    tester_id: str
    workspace_id: str
    role: str
    session_token: str
    expires_at: str


class BetaStorage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(
                """
                create table if not exists tester (
                    tester_id text primary key,
                    display_label text not null default '',
                    invite_hash text not null,
                    role text not null default 'tester',
                    disabled integer not null default 0,
                    created_at text not null,
                    updated_at text not null
                );

                create table if not exists workspace (
                    workspace_id text primary key,
                    tester_id text not null,
                    wiki_root text not null,
                    seed_label text not null default '',
                    created_at text not null,
                    foreign key(tester_id) references tester(tester_id)
                );

                create table if not exists auth_session (
                    token_hash text primary key,
                    tester_id text not null,
                    workspace_id text not null,
                    role text not null,
                    created_at text not null,
                    expires_at text not null,
                    revoked_at text,
                    foreign key(tester_id) references tester(tester_id),
                    foreign key(workspace_id) references workspace(workspace_id)
                );

                create table if not exists app_session (
                    app_session_id text primary key,
                    tester_id text not null,
                    workspace_id text not null,
                    class_id text not null,
                    mode text not null,
                    status text not null,
                    started_at text not null,
                    last_active_at text not null
                );

                create table if not exists event (
                    event_id integer primary key autoincrement,
                    timestamp text not null,
                    tester_id text not null,
                    workspace_id text not null,
                    class_id text,
                    app_session_id text,
                    mode text,
                    type text not null,
                    payload_json text not null
                );

                create table if not exists message (
                    message_id integer primary key autoincrement,
                    timestamp text not null,
                    tester_id text not null,
                    workspace_id text not null,
                    class_id text not null,
                    app_session_id text not null,
                    mode text not null,
                    role text not null,
                    content text not null
                );

                create table if not exists artifact_snapshot (
                    snapshot_id integer primary key autoincrement,
                    timestamp text not null,
                    tester_id text not null,
                    workspace_id text not null,
                    class_id text not null,
                    app_session_id text not null,
                    mode text not null,
                    artifact_kind text not null,
                    markdown text not null
                );

                create table if not exists wiki_commit (
                    commit_id integer primary key autoincrement,
                    timestamp text not null,
                    tester_id text not null,
                    workspace_id text not null,
                    class_id text not null,
                    app_session_id text,
                    mode text not null,
                    action text not null,
                    changed_paths_json text not null,
                    metadata_json text not null
                );

                create table if not exists wiki_file_diff (
                    diff_id integer primary key autoincrement,
                    commit_id integer not null,
                    wiki_path text not null,
                    before_hash text not null,
                    after_hash text not null,
                    diff_text text not null,
                    foreign key(commit_id) references wiki_commit(commit_id)
                );
                """
            )


class BetaTelemetry(BetaStorage):
    def record_event(
        self,
        identity: RequestIdentity,
        *,
        event_type: str,
        class_id: str | None = None,
        app_session_id: str | None = None,
        mode: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.initialize()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                insert into event (
                    timestamp, tester_id, workspace_id, class_id, app_session_id,
                    mode, type, payload_json
                ) values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _utc_now(),
                    identity.tester_id,
                    identity.workspace_id,
                    class_id,
                    app_session_id,
                    mode,
                    event_type,
                    _json(payload),
                ),
            )

    def record_app_session(
        self,
        identity: RequestIdentity,
        *,
        app_session_id: str,
        class_id: str,
        mode: str,
        status: str,
    ) -> None:
        self.initialize()
        now = _utc_now()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                insert into app_session (
                    app_session_id, tester_id, workspace_id, class_id, mode, status,
                    started_at, last_active_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(app_session_id) do update set
                    status = excluded.status,
                    last_active_at = excluded.last_active_at
                """,
                (
                    app_session_id,
                    identity.tester_id,
                    identity.workspace_id,
                    class_id,
                    mode,
                    status,
                    now,
                    now,
                ),
            )
        self.record_event(
            identity,
            event_type="session_started",
            class_id=class_id,
            app_session_id=app_session_id,
            mode=mode,
            payload={"status": status},
        )

    def update_app_session_status(
        self, app_session_id: str, status: str
    ) -> None:
        self.initialize()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                update app_session set status = ?, last_active_at = ?
                where app_session_id = ?
                """,
                (status, _utc_now(), app_session_id),
            )

    def record_message(
        self,
        identity: RequestIdentity,
        *,
        app_session_id: str,
        class_id: str,
        mode: str,
        role: str,
        content: str,
    ) -> None:
        self.initialize()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                insert into message (
                    timestamp, tester_id, workspace_id, class_id, app_session_id,
                    mode, role, content
                ) values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _utc_now(),
                    identity.tester_id,
                    identity.workspace_id,
                    class_id,
                    app_session_id,
                    mode,
                    role,
                    content,
                ),
            )

    def record_artifact_snapshot(
        self,
        identity: RequestIdentity,
        *,
        app_session_id: str,
        class_id: str,
        mode: str,
        artifact_kind: str,
        markdown: str,
    ) -> None:
        self.initialize()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                insert into artifact_snapshot (
                    timestamp, tester_id, workspace_id, class_id, app_session_id,
                    mode, artifact_kind, markdown
                ) values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _utc_now(),
                    identity.tester_id,
                    identity.workspace_id,
                    class_id,
                    app_session_id,
                    mode,
                    artifact_kind,
                    markdown,
                ),
            )

    def record_wiki_commit(
        self,
        identity: RequestIdentity,
        *,
        app_session_id: str | None,
        class_id: str,
        mode: str,
        action: str,
        changed_files: list[tuple[str, str, str]],
        metadata: dict[str, Any] | None = None,
    ) -> int:
        self.initialize()
        paths = [path for path, _, _ in changed_files]
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                insert into wiki_commit (
                    timestamp, tester_id, workspace_id, class_id, app_session_id,
                    mode, action, changed_paths_json, metadata_json
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _utc_now(),
                    identity.tester_id,
                    identity.workspace_id,
                    class_id,
                    app_session_id,
                    mode,
                    action,
                    json.dumps(paths, ensure_ascii=False),
                    _json(metadata),
                ),
            )
            commit_id = int(cursor.lastrowid)
            for wiki_path, before, after in changed_files:
                conn.execute(
                    """
                    insert into wiki_file_diff (
                        commit_id, wiki_path, before_hash, after_hash, diff_text
                    ) values (?, ?, ?, ?, ?)
                    """,
                    (
                        commit_id,
                        wiki_path,
                        _hash_text(before),
                        _hash_text(after),
                        "\n".join(
                            difflib.unified_diff(
                                before.splitlines(),
                                after.splitlines(),
                                fromfile=f"{wiki_path}:before",
                                tofile=f"{wiki_path}:after",
                                lineterm="",
                            )
                        ),
                    ),
                )
        self.record_event(
            identity,
            event_type=action,
            class_id=class_id,
            app_session_id=app_session_id,
            mode=mode,
            payload={"changed_paths": paths, **(metadata or {})},
        )
        return commit_id


class BetaAuthService(BetaStorage):
    def __init__(
        self,
        *,
        db_path: Path,
        data_root: Path,
        seed_wiki_root: Path,
        cookie_name: str,
        session_days: int,
        cookie_secure: bool,
    ) -> None:
        super().__init__(db_path)
        self.data_root = Path(data_root)
        self.seed_wiki_root = Path(seed_wiki_root)
        self.cookie_name = cookie_name
        self.session_days = session_days
        self.cookie_secure = cookie_secure

    @property
    def telemetry(self) -> BetaTelemetry:
        return BetaTelemetry(self.db_path)

    def provision_tester(
        self,
        *,
        tester_id: str,
        workspace_id: str,
        invite_code: str,
        display_label: str = "",
        seed_label: str = "",
    ) -> RequestIdentity:
        self.initialize()
        now = _utc_now()
        wiki_root = self.data_root / "workspaces" / workspace_id / "teacher_wiki"
        if not wiki_root.exists():
            wiki_root.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(
                self.seed_wiki_root,
                wiki_root,
                ignore=shutil.ignore_patterns("workflow"),
            )
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                insert into tester (
                    tester_id, display_label, invite_hash, role, disabled,
                    created_at, updated_at
                ) values (?, ?, ?, 'tester', 0, ?, ?)
                on conflict(tester_id) do update set
                    display_label = excluded.display_label,
                    invite_hash = excluded.invite_hash,
                    updated_at = excluded.updated_at
                """,
                (tester_id, display_label, _hash_secret(invite_code), now, now),
            )
            conn.execute(
                """
                insert into workspace (
                    workspace_id, tester_id, wiki_root, seed_label, created_at
                ) values (?, ?, ?, ?, ?)
                on conflict(workspace_id) do update set
                    tester_id = excluded.tester_id,
                    wiki_root = excluded.wiki_root,
                    seed_label = excluded.seed_label
                """,
                (workspace_id, tester_id, str(wiki_root), seed_label, now),
            )
        return RequestIdentity(
            tester_id=tester_id,
            workspace_id=workspace_id,
            role="tester",
            wiki_root=wiki_root,
        )

    def login(self, invite_code: str) -> LoginResult | None:
        self.initialize()
        invite_hash = _hash_secret(invite_code.strip())
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                select t.tester_id, t.role, w.workspace_id
                from tester t
                join workspace w on w.tester_id = t.tester_id
                where t.invite_hash = ? and t.disabled = 0
                """,
                (invite_hash,),
            ).fetchone()
            if row is None:
                return None
            token = secrets.token_urlsafe(32)
            expires_at = (
                datetime.now(UTC) + timedelta(days=self.session_days)
            ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            conn.execute(
                """
                insert into auth_session (
                    token_hash, tester_id, workspace_id, role, created_at,
                    expires_at, revoked_at
                ) values (?, ?, ?, ?, ?, ?, null)
                """,
                (
                    _hash_secret(token),
                    row["tester_id"],
                    row["workspace_id"],
                    row["role"],
                    _utc_now(),
                    expires_at,
                ),
            )
            return LoginResult(
                tester_id=row["tester_id"],
                workspace_id=row["workspace_id"],
                role=row["role"],
                session_token=token,
                expires_at=expires_at,
            )

    def resolve_session_token(self, session_token: str) -> RequestIdentity:
        self.initialize()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                select
                    s.tester_id, s.workspace_id, s.role, s.expires_at,
                    w.wiki_root, t.disabled
                from auth_session s
                join tester t on t.tester_id = s.tester_id
                join workspace w on w.workspace_id = s.workspace_id
                where s.token_hash = ? and s.revoked_at is null
                """,
                (_hash_secret(session_token),),
            ).fetchone()
        if row is None or row["disabled"]:
            raise ValueError("Invalid beta session")
        expires_at = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
        if expires_at <= datetime.now(UTC):
            raise ValueError("Expired beta session")
        return RequestIdentity(
            tester_id=row["tester_id"],
            workspace_id=row["workspace_id"],
            role=row["role"],
            wiki_root=Path(row["wiki_root"]),
        )

    def revoke_session_token(self, session_token: str) -> None:
        self.initialize()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "update auth_session set revoked_at = ? where token_hash = ?",
                (_utc_now(), _hash_secret(session_token)),
            )
