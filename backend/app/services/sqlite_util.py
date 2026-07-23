"""Shared SQLite connection helper.

Every local SQLite store (workflow drafts, memory-candidate ledger, sweep
reviews, beta telemetry, debug capture) opens short-lived connections. The
frontend polls ``GET /api/workflow/active`` every ~3s (a read on the workflow
draft DB) while a chat turn is writing it, and beta telemetry writes on every
message — so concurrent access is routine. SQLite's default ``busy_timeout`` is
0, which turns any lock contention into an immediate ``database is locked``
error. Routing every connection through here sets a sane busy timeout so a
brief writer lock makes the other caller wait instead of failing.

WAL is intentionally NOT forced: the hosted beta targets EFS/NFS storage, where
SQLite WAL is explicitly discouraged. ``busy_timeout`` fixes the contention risk
without that footgun; WAL can be enabled per-store later for local-only setups.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

# Wait up to 5s for a competing lock before raising "database is locked".
BUSY_TIMEOUT_MS = 5000


def connect(db_path: str | Path, *, row_factory: bool = False) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=BUSY_TIMEOUT_MS / 1000)
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    if row_factory:
        conn.row_factory = sqlite3.Row
    return conn
