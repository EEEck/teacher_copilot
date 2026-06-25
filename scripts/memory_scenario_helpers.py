"""Shared helpers for live memory-capture scenario traces.

The scripts in this folder intentionally use only the standard library so they
can run anywhere the local backend is running. They are diagnostic traces, not
unit tests: each writes a run folder with raw API/SSE artifacts and a compact
summary JSON.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import sqlite3
import urllib.error
import urllib.request
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def resolve_output_root(output_root: str) -> pathlib.Path:
    root = pathlib.Path(output_root)
    if not root.is_absolute():
        root = REPO_ROOT / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def write_json(path: pathlib.Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_text(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text or "", encoding="utf-8")


def read_json(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def request_json(method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=240) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed: {exc.status} {detail}") from exc


def request_text(method: str, url: str, payload: dict[str, Any] | None = None) -> str:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=240) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed: {exc.status} {detail}") from exc


def parse_sse_events(body: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in body.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line.removeprefix("data:").strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            events.append(json.loads(payload))
        except json.JSONDecodeError:
            continue
    return events


def final_sse_event(body: str) -> dict[str, Any]:
    final: dict[str, Any] = {}
    for event in parse_sse_events(body):
        if event.get("type") in {"final", "final_message", "done"}:
            final = event
    return final


def ledger_rows_for_session(session_id: str) -> list[dict[str, Any]]:
    db_path = BACKEND_ROOT / "teacher_wiki" / "workflow" / "memory_candidates.sqlite"
    if not db_path.exists():
        return []
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            select
              id,
              workflow,
              session_id,
              turn_index,
              channel,
              target,
              section,
              candidate_update,
              evidence_summary,
              basis,
              confidence,
              status,
              cluster_key
            from memory_candidates
            where session_id = ?
            order by id
            """,
            (session_id,),
        ).fetchall()
    finally:
        con.close()
    return [dict(row) for row in rows]


def ledger_rows_by_ids(candidate_ids: list[str]) -> list[dict[str, Any]]:
    if not candidate_ids:
        return []
    db_path = BACKEND_ROOT / "teacher_wiki" / "workflow" / "memory_candidates.sqlite"
    if not db_path.exists():
        return []
    placeholders = ",".join("?" for _ in candidate_ids)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            f"""
            select id, target, section, candidate_update, status, promoted_at, review_batch_id
            from memory_candidates
            where id in ({placeholders})
            order by id
            """,
            candidate_ids,
        ).fetchall()
    finally:
        con.close()
    return [dict(row) for row in rows]


def flatten_sweep_cards(sweep: dict[str, Any]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for queue, items in (sweep.get("queues") or {}).items():
        for item in items:
            card = dict(item)
            card["queue"] = queue
            cards.append(card)
    return cards


def matching_cards(cards: list[dict[str, Any]], *, target: str, contains: str) -> list[dict[str, Any]]:
    needle = contains.lower()
    return [
        card
        for card in cards
        if card.get("target") == target and needle in json.dumps(card, ensure_ascii=False).lower()
    ]


def wiki_file(api_base: str, path: str) -> dict[str, Any]:
    url = f"{api_base.rstrip('/')}/api/wiki/file?path={urllib.request.quote(path)}"
    return request_json("GET", url)

