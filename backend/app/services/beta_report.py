"""Markdown reports for beta tester telemetry."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def render_beta_report(
    db_path: Path,
    *,
    tester_id: str | None = None,
    workspace_id: str | None = None,
    app_session_id: str | None = None,
    limit_sessions: int = 10,
    diff_char_limit: int = 4000,
) -> str:
    """Render a read-only Markdown report from beta telemetry SQLite data."""

    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"Beta telemetry database not found: {db_path}")

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        filters, params = _filters(
            tester_id=tester_id,
            workspace_id=workspace_id,
            app_session_id=app_session_id,
        )
        sessions = _fetch(
            conn,
            f"""
            select app_session_id, tester_id, workspace_id, class_id, mode, status,
                   started_at, last_active_at
            from app_session
            {filters}
            order by started_at desc
            limit ?
            """,
            (*params, limit_sessions),
        )
        events = _fetch(
            conn,
            f"""
            select event_id, timestamp, tester_id, workspace_id, class_id,
                   app_session_id, mode, type, payload_json
            from event
            {filters}
            order by timestamp asc, event_id asc
            """,
            params,
        )
        messages = _fetch(
            conn,
            f"""
            select message_id, timestamp, tester_id, workspace_id, class_id,
                   app_session_id, mode, role, content
            from message
            {filters}
            order by timestamp asc, message_id asc
            """,
            params,
        )
        artifacts = _fetch(
            conn,
            f"""
            select snapshot_id, timestamp, tester_id, workspace_id, class_id,
                   app_session_id, mode, artifact_kind, markdown
            from artifact_snapshot
            {filters}
            order by timestamp asc, snapshot_id asc
            """,
            params,
        )
        commits = _fetch(
            conn,
            f"""
            select commit_id, timestamp, tester_id, workspace_id, class_id,
                   app_session_id, mode, action, changed_paths_json, metadata_json
            from wiki_commit
            {filters}
            order by timestamp asc, commit_id asc
            """,
            params,
        )
        diffs = _fetch_diffs(conn, filters, params)

    diff_by_commit: dict[int, list[sqlite3.Row]] = defaultdict(list)
    for diff in diffs:
        diff_by_commit[int(diff["commit_id"])].append(diff)

    lines = [
        "# Beta Telemetry Report",
        "",
        f"Database: `{db_path}`",
        f"Tester: `{tester_id or 'all'}`",
        f"Workspace: `{workspace_id or 'all'}`",
        f"App session: `{app_session_id or 'all'}`",
        "",
    ]
    lines.extend(_render_sessions(sessions))
    lines.extend(_render_warnings(events, diffs))
    lines.extend(_render_teacher_feedback(events, messages))
    lines.extend(_render_timeline(events))
    lines.extend(_render_messages(messages))
    lines.extend(_render_artifacts(artifacts))
    lines.extend(_render_commits(commits, diff_by_commit, diff_char_limit))
    return "\n".join(lines).rstrip() + "\n"


def _filters(
    *,
    tester_id: str | None,
    workspace_id: str | None,
    app_session_id: str | None,
) -> tuple[str, tuple[str, ...]]:
    clauses: list[str] = []
    params: list[str] = []
    if tester_id:
        clauses.append("tester_id = ?")
        params.append(tester_id)
    if workspace_id:
        clauses.append("workspace_id = ?")
        params.append(workspace_id)
    if app_session_id:
        clauses.append("app_session_id = ?")
        params.append(app_session_id)
    if not clauses:
        return "", ()
    return "where " + " and ".join(clauses), tuple(params)


def _fetch(
    conn: sqlite3.Connection,
    query: str,
    params: tuple[Any, ...],
) -> list[sqlite3.Row]:
    return list(conn.execute(query, params))


def _fetch_diffs(
    conn: sqlite3.Connection,
    filters: str,
    params: tuple[str, ...],
) -> list[sqlite3.Row]:
    commit_filter = f"where c.{filters.removeprefix('where ')}" if filters else ""
    return _fetch(
        conn,
        f"""
        select d.diff_id, d.commit_id, d.wiki_path, d.before_hash, d.after_hash,
               d.diff_text
        from wiki_file_diff d
        join wiki_commit c on c.commit_id = d.commit_id
        {commit_filter}
        order by c.timestamp asc, d.diff_id asc
        """,
        params,
    )


def _render_sessions(rows: list[sqlite3.Row]) -> list[str]:
    lines = ["## Sessions", ""]
    if not rows:
        return [*lines, "_No matching sessions._", ""]
    for row in rows:
        lines.append(
            "- "
            f"`{row['app_session_id']}` "
            f"{row['class_id']} / {row['mode']} / {row['status']} "
            f"({row['started_at']} -> {row['last_active_at']})"
        )
    lines.append("")
    return lines


def _render_warnings(
    events: list[sqlite3.Row],
    diffs: list[sqlite3.Row],
) -> list[str]:
    incomplete = _incomplete_chat_turns(events)
    no_op_diffs = [
        diff
        for diff in diffs
        if diff["before_hash"] == diff["after_hash"] or not diff["diff_text"].strip()
    ]

    lines = ["## Warnings", ""]
    if not incomplete and not no_op_diffs:
        return [*lines, "_No obvious telemetry warnings._", ""]
    if incomplete:
        lines.append("### Incomplete chat turns")
        lines.append("")
        for session, mode, counts in incomplete:
            lines.append(
                f"- `{session}` / `{mode}`: "
                f"{counts['chat_turn_started']} started, "
                f"{counts['chat_turn_completed']} completed"
            )
        lines.append("")
    if no_op_diffs:
        lines.append("### No-op wiki diffs")
        lines.append("")
        for diff in no_op_diffs:
            lines.append(f"- Commit `{diff['commit_id']}`: `{diff['wiki_path']}`")
        lines.append("")
    return lines


def _incomplete_chat_turns(
    events: list[sqlite3.Row],
) -> list[tuple[str, str, Counter[str]]]:
    counts_by_key: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for event in events:
        if event["type"] not in {"chat_turn_started", "chat_turn_completed"}:
            continue
        key = (event["app_session_id"] or "none", event["mode"] or "none")
        counts_by_key[key][event["type"]] += 1
    incomplete: list[tuple[str, str, Counter[str]]] = []
    for (session, mode), counts in sorted(counts_by_key.items()):
        if counts["chat_turn_started"] > counts["chat_turn_completed"]:
            incomplete.append((session, mode, counts))
    return incomplete


def _render_teacher_feedback(
    events: list[sqlite3.Row],
    messages: list[sqlite3.Row],
) -> list[str]:
    """Dedicated rollup for Give-feedback notes (events + message rows)."""
    lines = ["## Teacher feedback", ""]
    feedback_events = [row for row in events if row["type"] == "teacher_feedback"]
    feedback_messages = [
        row
        for row in messages
        if row["mode"] == "feedback" or row["role"] == "teacher_feedback"
    ]
    if not feedback_events and not feedback_messages:
        return [*lines, "_No teacher feedback submitted._", ""]

    if feedback_events:
        for row in feedback_events:
            payload = _payload_dict(row["payload_json"])
            page = payload.get("page")
            message = str(payload.get("message") or "").strip()
            page_bit = f" page=`{page}`" if page else ""
            lines.append(f"### {row['timestamp']}{page_bit}")
            lines.append("")
            lines.append(_clip(message or "_empty_", 2000))
            lines.append("")
        return lines

    for row in feedback_messages:
        lines.append(f"### {row['timestamp']} `{row['role']}`")
        lines.append("")
        lines.append(_clip(row["content"], 2000))
        lines.append("")
    return lines


def _render_timeline(rows: list[sqlite3.Row]) -> list[str]:
    lines = ["## Event timeline", ""]
    if not rows:
        return [*lines, "_No matching events._", ""]
    for row in rows:
        payload = _json_summary(row["payload_json"])
        lines.append(
            f"- {row['timestamp']} `{row['type']}` "
            f"session=`{row['app_session_id'] or 'none'}` {payload}"
        )
    lines.append("")
    return lines


def _render_messages(rows: list[sqlite3.Row]) -> list[str]:
    lines = ["## Messages", ""]
    # Feedback has its own section; keep chat Messages focused on workflow turns.
    chat_rows = [
        row
        for row in rows
        if not (row["mode"] == "feedback" or row["role"] == "teacher_feedback")
    ]
    if not chat_rows:
        return [*lines, "_No matching messages._", ""]
    for row in chat_rows:
        lines.append(
            f"### {row['timestamp']} `{row['role']}` "
            f"session=`{row['app_session_id']}`"
        )
        lines.append("")
        lines.append(_clip(row["content"], 1200))
        lines.append("")
    return lines


def _payload_dict(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _render_artifacts(rows: list[sqlite3.Row]) -> list[str]:
    lines = ["## Artifact snapshots", ""]
    if not rows:
        return [*lines, "_No matching artifact snapshots._", ""]
    for row in rows:
        lines.append(
            f"### Snapshot `{row['snapshot_id']}` {row['artifact_kind']} "
            f"session=`{row['app_session_id']}`"
        )
        lines.append("")
        lines.append("```markdown")
        lines.append(_clip(row["markdown"], 1200))
        lines.append("```")
        lines.append("")
    return lines


def _render_commits(
    commits: list[sqlite3.Row],
    diff_by_commit: dict[int, list[sqlite3.Row]],
    diff_char_limit: int,
) -> list[str]:
    lines = ["## Wiki commits", ""]
    if not commits:
        return [*lines, "_No matching wiki commits._", ""]
    for commit in commits:
        commit_id = int(commit["commit_id"])
        paths = _json_list(commit["changed_paths_json"])
        metadata = _json_summary(commit["metadata_json"])
        lines.append(
            f"### Commit `{commit_id}` {commit['action']} "
            f"session=`{commit['app_session_id'] or 'none'}`"
        )
        lines.append("")
        lines.append(f"- Timestamp: `{commit['timestamp']}`")
        lines.append(f"- Class: `{commit['class_id']}`")
        lines.append(f"- Paths: {', '.join(f'`{path}`' for path in paths) or '_none_'}")
        if metadata:
            lines.append(f"- Metadata: {metadata}")
        lines.append("")
        for diff in diff_by_commit.get(commit_id, []):
            status = (
                "no-op"
                if diff["before_hash"] == diff["after_hash"]
                or not diff["diff_text"].strip()
                else "changed"
            )
            lines.append(f"#### `{diff['wiki_path']}` ({status})")
            lines.append("")
            lines.append("```diff")
            lines.append(_clip(diff["diff_text"] or "(no textual diff)", diff_char_limit))
            lines.append("```")
            lines.append("")
    return lines


def _json_list(raw: str) -> list[str]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _json_summary(raw: str) -> str:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return ""
    if not value:
        return ""
    return "`" + json.dumps(value, ensure_ascii=False, sort_keys=True) + "`"


def _clip(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 24].rstrip() + "\n... [truncated]"
