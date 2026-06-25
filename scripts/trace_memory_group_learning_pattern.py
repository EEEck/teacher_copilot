"""Trace class group-learning pattern capture through planning and memory sweep."""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import sys
from types import SimpleNamespace
from typing import Any

SCRIPTS_ROOT = pathlib.Path(__file__).resolve().parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import memory_scenario_helpers as h  # noqa: E402
import run_plan_trace_bundle  # noqa: E402


DURABLE_PROMPT_1 = """Plan the next 45-minute lesson for Chemie 9b. Topic: redox reactions applied to CFC/FCKW compounds. Keep it exam-oriented and use the class wiki.
"""

DURABLE_PROMPT_2 = """I learned a durable class pattern: Chemie 9b understands abstract chemistry better when I assign structured group roles before symbolic tasks. Please use group roles for the FCKW lesson and remember this as a general learning pattern for this class.
"""

DURABLE_PROMPT_3 = """Looks good. Keep the group-role structure and make the plan ready to save.
"""

ONE_OFF_PROMPT_2 = """For this FCKW lesson only, try structured group roles before the symbolic task. This is just for today's plan, not a general class pattern.
"""


def _write_prompts(run_name: str, *, one_off: bool) -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
    prompt_dir = SCRIPTS_ROOT / ".logs" / run_name
    p2 = ONE_OFF_PROMPT_2 if one_off else DURABLE_PROMPT_2
    files = [
        prompt_dir / "prompt1.txt",
        prompt_dir / ("prompt2-one-off-group-roles.txt" if one_off else "prompt2-durable-group-roles.txt"),
        prompt_dir / "prompt3.txt",
    ]
    for path, text in zip(files, [DURABLE_PROMPT_1, p2, DURABLE_PROMPT_3]):
        h.write_text(path, text)
    return files[0], files[1], files[2]


def _build_summary(run_dir: pathlib.Path, *, api_base: str, class_id: str, one_off: bool, apply: bool) -> dict[str, Any]:
    meta = h.read_json(run_dir / "00-run-meta.json")
    session_id = str(meta["session_id"])
    trace_files = sorted(run_dir.glob("*-trace-after-turn*.json"))
    final_trace = h.read_json(trace_files[-1])
    final_sse = h.final_sse_event(sorted(run_dir.glob("*-turn*-sse.txt"))[-1].read_text(encoding="utf-8"))
    rows = h.ledger_rows_for_session(session_id)
    target_rows = [
        row
        for row in rows
        if row["target"] == "teaching_patterns.md"
        and ("group" in row["candidate_update"].lower() or "structured role" in row["candidate_update"].lower())
    ]
    sweep = h.request_json("POST", f"{api_base.rstrip('/')}/api/classes/{class_id}/memory/sweep/propose", {})
    cards = h.flatten_sweep_cards(sweep)
    matches = [
        card
        for card in cards
        if card.get("target") == "teaching_patterns.md"
        and ("group" in card.get("content", "").lower() or "structured role" in card.get("content", "").lower())
    ]

    apply_result = None
    status_rows: list[dict[str, Any]] = []
    if apply and matches:
        card = matches[0]
        apply_result = h.request_json(
            "POST",
            f"{api_base.rstrip('/')}/api/classes/{class_id}/memory/apply",
            {
                "items": [
                    {
                        "target": card["target"],
                        "section": card.get("section") or "Class Learning Profile",
                        "content": card["content"],
                    }
                ]
            },
        )
        h.request_json(
            "POST",
            f"{api_base.rstrip('/')}/api/classes/{class_id}/memory/candidates/{card['candidate_id']}/status",
            {
                "status": "applied",
                "review_batch_id": f"scenario_group_{dt.datetime.now():%Y%m%d%H%M%S}",
            },
        )
        status_rows = h.ledger_rows_by_ids([card["candidate_id"]])

    if one_off:
        passed_capture = not target_rows
        passed_sweep = True
        passed_apply = True
    else:
        passed_capture = bool(target_rows)
        passed_sweep = bool(matches)
        passed_apply = not apply or bool(
            apply_result
            and apply_result.get("applied_wiki_paths")
            and not apply_result.get("warnings")
        )

    summary = {
        "scenario": "one_off_group_roles_no_durable_memory" if one_off else "durable_group_learning_pattern",
        "passed": passed_capture and passed_sweep and passed_apply,
        "run_dir": str(run_dir),
        "session_id": session_id,
        "capture": {
            "passed": passed_capture,
            "runtime_candidates": final_trace.get("runtime", {}).get("memory_candidates", []),
            "final_sse_candidates": final_sse.get("memory_candidates", []),
            "ledger_rows": rows,
            "matching_teaching_pattern_rows": target_rows,
        },
        "sweep": {
            "passed": passed_sweep,
            "matching_cards": matches,
            "warnings": sweep.get("warnings", []),
        },
        "apply": {
            "requested": apply,
            "passed": passed_apply,
            "result": apply_result,
            "status_rows": status_rows,
        },
    }
    h.write_json(run_dir / "scenario-summary.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default="http://localhost:8010")
    parser.add_argument("--class-id", default="chemie_9b_2026_27")
    parser.add_argument("--output-root", default="backend/runs")
    parser.add_argument("--run-name", default="")
    parser.add_argument("--one-off", action="store_true", help="Run the negative one-off variant.")
    parser.add_argument("--apply", action="store_true", help="Apply the first matching sweep card.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    suffix = "one-off-group-roles" if args.one_off else "durable-group-roles"
    run_name = args.run_name or f"{h.now_stamp()}-scenario-{suffix}"
    p1, p2, p3 = _write_prompts(run_name, one_off=args.one_off)
    trace_args = SimpleNamespace(
        api_base=args.api_base,
        class_id=args.class_id,
        output_root=args.output_root,
        run_name=run_name,
        prompt1_file=str(p1),
        prompt2_file=str(p2),
        prompt3_file=str(p3),
    )
    run_dir = run_plan_trace_bundle.run(trace_args)
    summary = _build_summary(
        run_dir,
        api_base=args.api_base,
        class_id=args.class_id,
        one_off=args.one_off,
        apply=args.apply,
    )
    print(f"run_dir={run_dir}")
    print(f"session_id={summary['session_id']}")
    print(f"scenario={summary['scenario']}")
    print(f"passed={summary['passed']}")
    print(f"capture_passed={summary['capture']['passed']}")
    print(f"sweep_passed={summary['sweep']['passed']}")
    print(f"apply_requested={args.apply}")
    print(f"apply_passed={summary['apply']['passed']}")
    print(f"summary={run_dir / 'scenario-summary.json'}")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

