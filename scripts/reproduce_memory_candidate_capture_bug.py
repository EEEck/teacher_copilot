"""Reproduce the missing memory-candidate capture bug for teacher preferences.

The scenario is intentionally explicit: the teacher states that MBB-style
communication is a general lesson-planning preference, not a one-off request.
Expected behavior is a proposed durable-memory candidate for user.md /
Communication. The observed bug is that the planner follows the preference in
the reply and runtime state, but emits no memory candidate and writes no ledger
row.

Prerequisite: the backend is running locally, for example on
http://localhost:8010.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sqlite3
import sys
from types import SimpleNamespace
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
SCRIPTS_ROOT = REPO_ROOT / "scripts"

if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import run_plan_trace_bundle  # noqa: E402


PROMPT_1 = """Plan the next 45-minute lesson for Chemie 9b. Topic: redox reactions applied to CFC/FCKW compounds. Build on our existing redox lessons in the wiki and keep it exam-oriented.
"""

PROMPT_2 = """Please adjust the plan. From now on, for all lesson-planning summaries, I want you to use MBB-style communication: start with the recommendation, then give 2-3 crisp reasons, then only the essential next steps. This is a general communication preference for me, not just this one class.
"""

PROMPT_3 = """Looks good. Do one final concise pass in that MBB style and make it ready to save.
"""


def _write_text(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_json(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_turn_trace(run_dir: pathlib.Path) -> dict[str, Any]:
    trace_files = sorted(run_dir.glob("*-trace-after-turn*.json"))
    if not trace_files:
        raise RuntimeError(f"No turn trace files found in {run_dir}")
    return _read_json(trace_files[-1])


def _final_sse_event(run_dir: pathlib.Path) -> dict[str, Any]:
    sse_files = sorted(run_dir.glob("*-turn*-sse.txt"))
    if not sse_files:
        return {}

    final_event: dict[str, Any] = {}
    for line in sse_files[-1].read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("data:"):
            continue
        payload = line.removeprefix("data:").strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if event.get("type") in {"final", "final_message", "done"}:
            final_event = event
    return final_event


def _ledger_rows(session_id: str) -> list[dict[str, Any]]:
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
              channel,
              target,
              section,
              candidate_update,
              basis,
              confidence,
              status
            from memory_candidates
            where session_id = ?
            order by id
            """,
            (session_id,),
        ).fetchall()
    finally:
        con.close()
    return [dict(row) for row in rows]


def _contains_mbb_text(value: Any) -> bool:
    return "mbb" in json.dumps(value, ensure_ascii=False).lower()


def _build_summary(run_dir: pathlib.Path) -> dict[str, Any]:
    meta = _read_json(run_dir / "00-run-meta.json")
    trace = _latest_turn_trace(run_dir)
    final_sse = _final_sse_event(run_dir)
    session_id = str(meta["session_id"])
    rows = _ledger_rows(session_id)

    runtime_candidates = trace.get("runtime", {}).get("memory_candidates") or []
    final_candidates = final_sse.get("memory_candidates") or []
    artifact = trace.get("artifact_markdown", "")
    event_trace = trace.get("event_trace", [])

    bug_reproduced = (
        _contains_mbb_text(artifact)
        and len(runtime_candidates) == 0
        and len(final_candidates) == 0
        and len(rows) == 0
    )

    return {
        "bug": "explicit_teacher_preference_not_captured_as_memory_candidate",
        "bug_reproduced": bug_reproduced,
        "run_dir": str(run_dir),
        "session_id": session_id,
        "api_base": meta.get("api_base"),
        "class_id": meta.get("class_id"),
        "expected": {
            "ledger_row": {
                "target": "user.md",
                "section": "Communication",
                "basis": "explicit",
                "confidence": "high",
                "candidate_update_contains": "MBB-style communication for lesson-planning summaries",
            }
        },
        "observed": {
            "artifact_mentions_mbb": _contains_mbb_text(artifact),
            "runtime_memory_candidates_count": len(runtime_candidates),
            "final_sse_memory_candidates_count": len(final_candidates),
            "sqlite_ledger_rows_count": len(rows),
            "sqlite_ledger_rows": rows,
        },
        "trace_counts": {
            "prompt_calls": len([e for e in event_trace if e.get("type") == "prompt_assembly"]),
            "tool_calls": len([e for e in event_trace if e.get("type") == "tool_call"]),
            "raw_evidence_items": len(trace.get("raw_evidence", {})),
        },
        "raw_artifacts": sorted(
            str(path.relative_to(run_dir)).replace("\\", "/")
            for path in run_dir.rglob("*")
            if path.is_file()
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the explicit MBB preference planning trace and inspect memory-candidate capture."
    )
    parser.add_argument("--api-base", default="http://localhost:8010")
    parser.add_argument("--class-id", default="chemie_9b_2026_27")
    parser.add_argument("--output-root", default="backend/runs")
    parser.add_argument("--run-name", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    prompt_dir = SCRIPTS_ROOT / ".logs" / "memory-candidate-capture-bug"
    prompt1_file = prompt_dir / "prompt1.txt"
    prompt2_file = prompt_dir / "prompt2-explicit-mbb-preference.txt"
    prompt3_file = prompt_dir / "prompt3.txt"
    _write_text(prompt1_file, PROMPT_1)
    _write_text(prompt2_file, PROMPT_2)
    _write_text(prompt3_file, PROMPT_3)

    trace_args = SimpleNamespace(
        api_base=args.api_base,
        class_id=args.class_id,
        output_root=args.output_root,
        run_name=args.run_name or f"{dt.datetime.now():%Y%m%d-%H%M%S}-memory-candidate-capture-bug",
        prompt1_file=str(prompt1_file),
        prompt2_file=str(prompt2_file),
        prompt3_file=str(prompt3_file),
    )
    run_dir = run_plan_trace_bundle.run(trace_args)
    summary = _build_summary(run_dir)
    summary_path = run_dir / "bug-repro-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"run_dir={run_dir}")
    print(f"session_id={summary['session_id']}")
    print(f"bug_reproduced={summary['bug_reproduced']}")
    print(f"runtime_memory_candidates={summary['observed']['runtime_memory_candidates_count']}")
    print(f"final_sse_memory_candidates={summary['observed']['final_sse_memory_candidates_count']}")
    print(f"sqlite_ledger_rows={summary['observed']['sqlite_ledger_rows_count']}")
    print(f"summary={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
