from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.config import Settings
from app.services.beta import RequestIdentity
from app.services.memory_v4_debug_capture import MemoryV4DebugRecorder


def _identity(tmp_path: Path) -> RequestIdentity:
    return RequestIdentity(
        tester_id="t_debug",
        workspace_id="w_debug",
        role="tester",
        wiki_root=tmp_path / "teacher_wiki",
    )


def test_capture_requires_beta_development_and_explicit_flag() -> None:
    assert not Settings(
        beta_enabled=False,
        app_env="development",
        memory_v4_debug_capture=True,
    ).is_memory_v4_debug_capture_enabled()
    assert not Settings(
        beta_enabled=True,
        app_env="production",
        memory_v4_debug_capture=True,
    ).is_memory_v4_debug_capture_enabled()
    assert not Settings(
        beta_enabled=True,
        app_env="development",
        memory_v4_debug_capture=False,
    ).is_memory_v4_debug_capture_enabled()
    assert Settings(
        beta_enabled=True,
        app_env="development",
        memory_v4_debug_capture=True,
    ).is_memory_v4_debug_capture_enabled()


def test_recorder_writes_index_and_readable_append_only_bundle(tmp_path: Path) -> None:
    db_path = tmp_path / "beta.sqlite3"
    recorder = MemoryV4DebugRecorder(db_path=db_path, beta_data_root=tmp_path / "beta_data")
    trace_id = recorder.capture_turn(
        _identity(tmp_path),
        class_id="chemie_9b_2026_27",
        session_id="session-1",
        workflow="ingest",
        turn_index=1,
        payload={"teacher_message": "Please remember this preference."},
    )

    assert trace_id is not None
    recorder.append(trace_id, "turn_completed", {"candidate_count": 1})

    bundle = json.loads(recorder.bundle_path(trace_id).read_text(encoding="utf-8"))
    assert bundle["trace_id"] == trace_id
    assert [event["type"] for event in bundle["events"]] == [
        "turn_started",
        "turn_completed",
    ]
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "select workflow, session_id, bundle_path from memory_v4_debug_trace"
        ).fetchone()
    assert row == ("ingest", "session-1", str(recorder.bundle_path(trace_id)))
