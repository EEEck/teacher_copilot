"""Best-effort local beta trace bundles for Memory V4 development."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services.beta import BetaStorage, RequestIdentity
from app.services.sqlite_util import connect as sqlite_connect

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class MemoryV4DebugRecorder:
    """Persist inspectable local bundles without affecting a teacher workflow."""

    def __init__(self, *, db_path: Path, beta_data_root: Path) -> None:
        self.db_path = Path(db_path)
        self.trace_root = Path(beta_data_root) / "memory_v4_debug_traces"

    def bundle_path(self, trace_id: str) -> Path:
        return self.trace_root / f"{trace_id}.json"

    def capture_turn(
        self,
        identity: RequestIdentity,
        *,
        class_id: str,
        session_id: str,
        workflow: str,
        turn_index: int,
        payload: dict[str, Any],
    ) -> str | None:
        return self._capture(
            identity,
            class_id=class_id,
            session_id=session_id,
            workflow=workflow,
            turn_index=turn_index,
            event_type="turn_started",
            payload=payload,
        )

    def capture_operation(
        self,
        identity: RequestIdentity,
        *,
        class_id: str,
        operation: str,
        payload: dict[str, Any],
    ) -> str | None:
        return self._capture(
            identity,
            class_id=class_id,
            session_id="",
            workflow=operation,
            turn_index=None,
            event_type="operation_started",
            payload=payload,
        )

    def append(
        self, trace_id: str | None, event_type: str, payload: dict[str, Any]
    ) -> None:
        if not trace_id:
            return
        try:
            path = self.bundle_path(trace_id)
            bundle = json.loads(path.read_text(encoding="utf-8"))
            bundle.setdefault("events", []).append(
                {"timestamp": _utc_now(), "type": event_type, "payload": payload}
            )
            path.write_text(
                json.dumps(bundle, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception:  # noqa: BLE001 - diagnostics must not fail workflows
            logger.exception("Memory V4 debug trace append failed: %s", trace_id)

    def _capture(
        self,
        identity: RequestIdentity,
        *,
        class_id: str,
        session_id: str,
        workflow: str,
        turn_index: int | None,
        event_type: str,
        payload: dict[str, Any],
    ) -> str | None:
        trace_id = "memv4_" + uuid.uuid4().hex
        path = self.bundle_path(trace_id)
        try:
            BetaStorage(self.db_path).initialize()
            self.trace_root.mkdir(parents=True, exist_ok=True)
            bundle = {
                "trace_id": trace_id,
                "tester_id": identity.tester_id,
                "workspace_id": identity.workspace_id,
                "class_id": class_id,
                "session_id": session_id,
                "workflow": workflow,
                "turn_index": turn_index,
                "events": [
                    {"timestamp": _utc_now(), "type": event_type, "payload": payload}
                ],
            }
            path.write_text(
                json.dumps(bundle, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            with sqlite_connect(self.db_path) as conn:
                conn.execute(
                    """
                    insert into memory_v4_debug_trace (
                        trace_id, timestamp, tester_id, workspace_id, class_id,
                        session_id, workflow, turn_index, bundle_path
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        trace_id,
                        _utc_now(),
                        identity.tester_id,
                        identity.workspace_id,
                        class_id,
                        session_id or None,
                        workflow,
                        turn_index,
                        str(path),
                    ),
                )
            return trace_id
        except Exception:  # noqa: BLE001 - diagnostics must not fail workflows
            logger.exception("Memory V4 debug trace creation failed")
            return None
