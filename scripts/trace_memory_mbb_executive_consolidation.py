"""Seed MBB/executive communication signals and inspect sweep consolidation.

This trace mocks three separate conversations by inserting three raw ledger
signals: two MBB-style communication preferences and one executive-style
communication preference. It then calls Memory Sweep propose and records what
review cards the backend/LLM suggests. Temporary current-memory setup is
restored after the run; ``--apply`` exercises the apply endpoint and may update
ledger statuses.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import datetime as dt
import pathlib
import sqlite3
import sys
from typing import Any, Iterator

SCRIPTS_ROOT = pathlib.Path(__file__).resolve().parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import memory_scenario_helpers as h  # noqa: E402


DB_PATH = h.BACKEND_ROOT / "teacher_wiki" / "workflow" / "memory_candidates.sqlite"
USER_PROFILE_PATH = h.BACKEND_ROOT / "teacher_wiki" / "wiki" / "teacher_profile.md"
TRACE_PROFILE_BULLETS = {
    "Teacher prefers MBB-style framing.",
    "Teacher prefers concise executive-style communication, including MBB/McKinsey-style framing when useful.",
}


def _seed_rows(class_id: str, *, batch_id: str) -> list[str]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    try:
        h.ensure_memory_candidates_table(con)
        rows = [
            (
                f"{batch_id}_mbb_comm_1",
                "2026-06-24T10:00:00Z",
                None,
                None,
                "plan",
                f"{batch_id}_sess_mbb_1",
                2,
                "teacher_behavior",
                "teacher_profile.md",
                "Communication",
                "Teacher prefers MBB-style communication as the standard for lesson planning.",
                "In planning chat 1, the teacher asked for MBB-style communication as the default.",
                '["trace:mbb_executive:conversation_1"]',
                "teacher_explicit",
                "explicit",
                "high",
                None,
                "captured",
            ),
            (
                f"{batch_id}_mbb_comm_2",
                "2026-06-24T10:05:00Z",
                None,
                None,
                "plan",
                f"{batch_id}_sess_mbb_2",
                2,
                "teacher_behavior",
                "teacher_profile.md",
                "Communication",
                "Teacher again requested MBB-style concise communication for planning outputs.",
                "In planning chat 2, the teacher repeated the MBB-style preference for concise plans.",
                '["trace:mbb_executive:conversation_2"]',
                "teacher_explicit",
                "explicit",
                "high",
                None,
                "captured",
            ),
            (
                f"{batch_id}_executive_comm_1",
                "2026-06-24T10:10:00Z",
                None,
                None,
                "plan",
                f"{batch_id}_sess_exec_1",
                2,
                "teacher_behavior",
                "teacher_profile.md",
                "Communication",
                "Teacher wants executive-style communication with concise framing and clear recommendations.",
                "In planning chat 3, the teacher described the desired style as executive communication.",
                '["trace:mbb_executive:conversation_3"]',
                "teacher_explicit",
                "explicit",
                "high",
                None,
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


@contextmanager
def _isolated_open_scope(class_id: str, candidate_ids: list[str], *, enabled: bool) -> Iterator[int]:
    """Temporarily hide other open rows so the trace shows only its mock batch."""
    if not enabled:
        yield 0
        return

    placeholders = ",".join("?" for _ in candidate_ids)
    open_statuses = ("captured", "grouped", "proposed", "snoozed")
    status_placeholders = ",".join("?" for _ in open_statuses)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    hidden_rows: list[tuple[str, str, str]] = []
    try:
        h.ensure_memory_candidates_table(con)
        hidden_rows = con.execute(
            f"""
            SELECT id, status, updated_at
            FROM memory_candidates
            WHERE status IN ({status_placeholders})
              AND id NOT IN ({placeholders})
              AND (class_id = ? OR class_id IS NULL)
            """,
            (*open_statuses, *candidate_ids, class_id),
        ).fetchall()
        if hidden_rows:
            now = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            con.executemany(
                "UPDATE memory_candidates SET status = ?, updated_at = ? WHERE id = ?",
                [("trace_hidden", now, row[0]) for row in hidden_rows],
            )
            con.commit()
        yield len(hidden_rows)
    finally:
        if hidden_rows:
            con.executemany(
                "UPDATE memory_candidates SET status = ?, updated_at = ? WHERE id = ?",
                [(row[1], row[2], row[0]) for row in hidden_rows],
            )
            con.commit()
        con.close()


def _represented_ids(card: dict[str, Any]) -> set[str]:
    candidate_ids = card.get("candidate_ids") or []
    if not candidate_ids and card.get("candidate_id"):
        candidate_ids = [card["candidate_id"]]
    return {str(candidate_id) for candidate_id in candidate_ids}


def _content_text(card: dict[str, Any]) -> str:
    parts = [
        card.get("content"),
        card.get("evidence_summary"),
        card.get("why_now"),
    ]
    return "\n".join(part for part in parts if isinstance(part, str)).lower()


def _card_content_text(card: dict[str, Any]) -> str:
    return str(card.get("content") or "").lower()


def _section_text_for_current_memory(mode: str) -> str:
    if mode == "narrow-mbb":
        return "- Teacher prefers MBB-style framing."
    if mode == "generalized":
        return (
            "- Teacher prefers concise executive-style communication, including "
            "MBB/McKinsey-style framing when useful."
        )
    return ""


@contextmanager
def _temporary_current_memory(mode: str) -> Iterator[None]:
    USER_PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    original = USER_PROFILE_PATH.read_text(encoding="utf-8") if USER_PROFILE_PATH.exists() else ""
    try:
        text = original.rstrip()
        lines = [
            line
            for line in text.splitlines()
            if line.strip().removeprefix("- ").strip() not in TRACE_PROFILE_BULLETS
        ]
        text = "\n".join(lines).rstrip()
        bullet = _section_text_for_current_memory(mode)
        if bullet:
            if "## Communication" not in text:
                text = text.rstrip() + "\n\n## Communication\n"
            text = text.rstrip() + f"\n{bullet}\n"
        USER_PROFILE_PATH.write_text(text.rstrip() + ("\n" if text.strip() else ""), encoding="utf-8")
        yield
    finally:
        USER_PROFILE_PATH.write_text(original, encoding="utf-8")


def _expected_operation(mode: str) -> str:
    return {
        "none": "add",
        "narrow-mbb": "adjust",
        "generalized": "already_covered",
    }[mode]


def _build_summary(
    run_dir: pathlib.Path,
    *,
    api_base: str,
    class_id: str,
    candidate_ids: list[str],
    current_memory: str,
    apply: bool,
    isolate: bool,
) -> dict[str, Any]:
    with _temporary_current_memory(current_memory):
        with _isolated_open_scope(class_id, candidate_ids, enabled=isolate) as hidden_open_rows:
            sweep = h.request_json("POST", f"{api_base.rstrip('/')}/api/classes/{class_id}/memory/sweep/propose", {})
    h.write_json(run_dir / "01-sweep-response.json", sweep)
    cards = h.flatten_sweep_cards(sweep)
    seeded_id_set = set(candidate_ids)
    expected_operation = _expected_operation(current_memory)
    matching_cards = [card for card in cards if _represented_ids(card) & seeded_id_set]
    full_merge_cards = [
        card
        for card in matching_cards
        if _represented_ids(card) >= seeded_id_set
        and card.get("target") == "teacher_profile.md"
    ]
    semantic_merge_cards = [
        card
        for card in full_merge_cards
        if "executive" in _card_content_text(card)
        and ("mbb" in _card_content_text(card) or "mckinsey" in _card_content_text(card))
    ]
    operation_match_cards = [
        card
        for card in full_merge_cards
        if (card.get("operation") or "add") == expected_operation
    ]

    apply_result = None
    status_rows: list[dict[str, Any]] = []
    if apply and full_merge_cards:
        card = operation_match_cards[0] if operation_match_cards else full_merge_cards[0]
        action = "already_covered" if (card.get("operation") == "already_covered") else "apply"
        with _temporary_current_memory(current_memory):
            apply_result = h.request_json(
                "POST",
                f"{api_base.rstrip('/')}/api/classes/{class_id}/memory/sweep/apply",
                {
                    "review_batch_id": f"scenario_mbb_exec_{dt.datetime.now():%Y%m%d%H%M%S}",
                    "decisions": [
                        {
                            "card_id": card.get("card_id") or card.get("candidate_id"),
                            "action": action,
                    "target": card.get("target") or "teacher_profile.md",
                            "section": card.get("section") or "Communication",
                            "content": card.get("content", ""),
                            "operation": card.get("operation") or "add",
                            "replaces_content": card.get("replaces_content") or "",
                            "candidate_ids": sorted(_represented_ids(card)),
                        }
                    ],
                },
            )
        status_rows = h.ledger_rows_by_ids(sorted(_represented_ids(card)))

    passed_sweep = bool(operation_match_cards) and bool(semantic_merge_cards)
    passed_apply = not apply or bool(
        apply_result
        and (
            apply_result.get("applied_wiki_paths")
            or expected_operation == "already_covered"
        )
        and apply_result.get("updated_candidate_ids")
        and not apply_result.get("warnings")
    )
    summary = {
        "scenario": "mbb_executive_communication_consolidation",
        "current_memory": current_memory,
        "expected_operation": expected_operation,
        "passed": passed_sweep and passed_apply,
        "run_dir": str(run_dir),
        "seeded_candidate_ids": candidate_ids,
        "isolated_open_rows_hidden_during_proposal": hidden_open_rows,
        "sweep": {
            "passed": passed_sweep,
            "semantic_merge_content_detected": bool(semantic_merge_cards),
            "operation_match_cards": operation_match_cards,
            "matching_cards": matching_cards,
            "full_merge_cards": full_merge_cards,
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
    parser.add_argument(
        "--no-isolate",
        action="store_true",
        help="Do not temporarily hide other open ledger rows while proposing.",
    )
    parser.add_argument(
        "--current-memory",
        choices=["none", "narrow-mbb", "generalized"],
        default="none",
        help="Temporary current teacher_profile.md state used to test add/adjust/already_covered.",
    )
    parser.add_argument("--apply", action="store_true", help="Apply the first full merged teacher_profile.md card.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_name = args.run_name or f"{h.now_stamp()}-scenario-mbb-executive-consolidation"
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
            "isolated": not args.no_isolate,
            "current_memory": args.current_memory,
            "expected_operation": _expected_operation(args.current_memory),
            "mocked_conversations": [
                "Teacher asks for MBB-style communication as the planning standard.",
                "Teacher repeats MBB-style concise plan communication.",
                "Teacher asks for executive-style communication with clear recommendations.",
            ],
        },
    )
    summary = _build_summary(
        run_dir,
        api_base=args.api_base,
        class_id=args.class_id,
        candidate_ids=candidate_ids,
        current_memory=args.current_memory,
        apply=args.apply,
        isolate=not args.no_isolate,
    )
    print(f"run_dir={run_dir}")
    print(f"seeded_candidates={len(candidate_ids)}")
    print(f"isolated_open_rows_hidden_during_proposal={summary['isolated_open_rows_hidden_during_proposal']}")
    print(f"passed={summary['passed']}")
    print(f"sweep_passed={summary['sweep']['passed']}")
    print(f"current_memory={args.current_memory}")
    print(f"expected_operation={summary['expected_operation']}")
    print(f"semantic_merge_content_detected={summary['sweep']['semantic_merge_content_detected']}")
    print(f"matching_cards={len(summary['sweep']['matching_cards'])}")
    print(f"full_merge_cards={len(summary['sweep']['full_merge_cards'])}")
    print(f"operation_match_cards={len(summary['sweep']['operation_match_cards'])}")
    print(f"apply_requested={args.apply}")
    print(f"apply_passed={summary['apply']['passed']}")
    print(f"summary={run_dir / 'scenario-summary.json'}")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
