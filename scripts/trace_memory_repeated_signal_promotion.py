"""Seed repeated weak memory signals and verify sweep grouping/apply promotion."""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import sqlite3
import sys
from typing import Any

SCRIPTS_ROOT = pathlib.Path(__file__).resolve().parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import memory_scenario_helpers as h  # noqa: E402


DB_PATH = h.BACKEND_ROOT / "teacher_wiki" / "workflow" / "memory_candidates.sqlite"


def _seed_rows(class_id: str, *, batch_id: str) -> list[str]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    try:
        h.ensure_memory_candidates_table(con)
        rows = [
            (
                f"{batch_id}_group_roles_1",
                "2026-06-24T09:00:00Z",
                class_id,
                "chemie",
                "plan",
                f"{batch_id}_sess_1",
                2,
                "class_learning_pattern",
                "teaching_patterns.md",
                "Class Learning Profile",
                "Structured group roles helped Chemie 9b start symbolic redox tasks with less confusion.",
                "Teacher noted group roles made the first symbolic FCKW task smoother.",
                '["trace:group_roles:1"]',
                "inferred_from_session",
                "inferred",
                "medium",
                f"{class_id}.teaching_patterns.group_roles_symbolic_redox",
                "captured",
            ),
            (
                f"{batch_id}_group_roles_2",
                "2026-06-24T09:05:00Z",
                class_id,
                "chemie",
                "ingest",
                f"{batch_id}_sess_2",
                3,
                "class_learning_pattern",
                "teaching_patterns.md",
                "Class Learning Profile",
                "Chemie 9b handled abstraction better after assigned group roles before redox notation.",
                "Lesson reflection said assigned roles kept students oriented before notation work.",
                '["trace:group_roles:2"]',
                "inferred_from_session",
                "inferred",
                "medium",
                f"{class_id}.teaching_patterns.group_roles_symbolic_redox",
                "captured",
            ),
            (
                f"{batch_id}_group_roles_3",
                "2026-06-24T09:10:00Z",
                class_id,
                "chemie",
                "plan",
                f"{batch_id}_sess_3",
                2,
                "class_learning_pattern",
                "teaching_patterns.md",
                "Class Learning Profile",
                "Use structured group roles before symbolic chemistry tasks for Chemie 9b when abstraction rises.",
                "Repeated planning correction asked for roles before symbolic redox tasks.",
                '["trace:group_roles:3"]',
                "teacher_explicit",
                "explicit",
                "high",
                f"{class_id}.teaching_patterns.group_roles_symbolic_redox",
                "captured",
            ),
        ]
        con.executemany(
            """
            INSERT OR REPLACE INTO memory_candidates (
              id, created_at, updated_at, class_id, subject, workflow,
              session_id, turn_index, channel, target, section, candidate_update,
              evidence_summary, evidence_refs_json, source, basis, confidence,
              cluster_key, status
            ) VALUES (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [(row[0], row[1], row[1], *row[2:]) for row in rows],
        )
        con.commit()
    finally:
        con.close()
    return [row[0] for row in rows]


def _build_summary(
    run_dir: pathlib.Path,
    *,
    api_base: str,
    class_id: str,
    candidate_ids: list[str],
    apply: bool,
) -> dict[str, Any]:
    sweep = h.request_json("POST", f"{api_base.rstrip('/')}/api/classes/{class_id}/memory/sweep/propose", {})
    cards = h.flatten_sweep_cards(sweep)
    matches = [
        card
        for card in cards
        if card.get("candidate_id") in candidate_ids
        and card.get("target") == "teaching_patterns.md"
    ]
    apply_result = None
    status_rows: list[dict[str, Any]] = []
    if apply and matches:
        card = matches[0]
        represented_ids = card.get("candidate_ids") or [card["candidate_id"]]
        apply_result = h.request_json(
            "POST",
            f"{api_base.rstrip('/')}/api/classes/{class_id}/memory/sweep/apply",
            {
                "review_batch_id": f"scenario_repeated_{dt.datetime.now():%Y%m%d%H%M%S}",
                "decisions": [
                    {
                        "card_id": card.get("card_id") or card["candidate_id"],
                        "action": "apply",
                        "target": "teaching_patterns.md",
                        "section": card.get("section") or "Class Learning Profile",
                        "content": card["content"],
                        "candidate_ids": represented_ids,
                    }
                ]
            },
        )
        status_rows = h.ledger_rows_by_ids(represented_ids)

    passed_sweep = any(
        set(card.get("candidate_ids") or [card.get("candidate_id")]) >= set(candidate_ids)
        and card.get("target") == "teaching_patterns.md"
        for card in matches
    )
    passed_apply = not apply or bool(
        apply_result
        and apply_result.get("applied_wiki_paths")
        and apply_result.get("updated_candidate_ids")
        and not apply_result.get("warnings")
    )
    summary = {
        "scenario": "repeated_group_learning_signal_promotion",
        "passed": passed_sweep and passed_apply,
        "run_dir": str(run_dir),
        "seeded_candidate_ids": candidate_ids,
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
    parser.add_argument("--apply", action="store_true", help="Apply one grouped review card to teaching_patterns.md.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_name = args.run_name or f"{h.now_stamp()}-scenario-repeated-group-signals"
    run_dir = h.resolve_output_root(args.output_root) / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    batch_id = run_name.replace("-", "_")
    candidate_ids = _seed_rows(args.class_id, batch_id=batch_id)
    h.write_json(
        run_dir / "00-run-meta.json",
        {
            "run_dir": str(run_dir),
            "created_at": dt.datetime.now().isoformat(),
            "api_base": args.api_base,
            "class_id": args.class_id,
            "seeded_candidate_ids": candidate_ids,
        },
    )
    summary = _build_summary(
        run_dir,
        api_base=args.api_base,
        class_id=args.class_id,
        candidate_ids=candidate_ids,
        apply=args.apply,
    )
    print(f"run_dir={run_dir}")
    print(f"seeded_candidates={len(candidate_ids)}")
    print(f"passed={summary['passed']}")
    print(f"sweep_passed={summary['sweep']['passed']}")
    print(f"apply_requested={args.apply}")
    print(f"apply_passed={summary['apply']['passed']}")
    print(f"summary={run_dir / 'scenario-summary.json'}")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
