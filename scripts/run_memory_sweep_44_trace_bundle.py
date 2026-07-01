"""Create a Memory Sweep section 4.4 trace bundle.

This script seeds temporary memory-candidate rows for the examples in
``docs/mem_v2/design.md`` section 4.4, calls the local KlassenPilot API, and
writes a timestamped review bundle under ``backend/runs/``.

Default scenario:
- class-specific redox observation -> teaching_patterns.md
- subject-wide redox observation -> wiki/subjects/chemie.md

Use ``--scenario all`` to include the teacher-profile and class-copilot examples
too. By default the script removes its temporary smoke bullets from wiki files
after verification; use ``--keep-writes`` when you want to inspect the durable
wiki changes in place.

It uses only the Python standard library plus backend app modules.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.memory_candidate_ledger import (  # noqa: E402
    MemoryCandidateLedger,
    MemoryCandidateRow,
)


@dataclass(frozen=True)
class Example:
    key: str
    channel: str
    target: str
    section: str
    content: str
    expected_queue: str
    expected_applied_path: str
    wiki_snapshot_path: str
    class_id: str | None = "chemie_9b_2026_27"
    subject: str | None = "chemie"
    workflow: str = "memory_sweep"


EXAMPLES: dict[str, Example] = {
    "class_redox": Example(
        key="class_redox",
        channel="class_learning_pattern",
        target="teaching_patterns.md",
        section="What Worked Well",
        content="9b finally understood redox after metal-displacement demos.",
        expected_queue="Class Evolution",
        expected_applied_path=(
            "wiki/classes/chemie_9b_2026_27/memory/teaching_patterns.md"
        ),
        wiki_snapshot_path=(
            "wiki/classes/chemie_9b_2026_27/memory/teaching_patterns.md"
        ),
        workflow="ingest",
    ),
    "subject_redox": Example(
        key="subject_redox",
        channel="subject_concept",
        target="wiki/subjects/chemie.md",
        section="Common lesson patterns",
        content=(
            "For chemistry classes, always introduce oxidation numbers after "
            "electron transfer."
        ),
        expected_queue="Subject Concepts",
        expected_applied_path="wiki/subjects/chemie.md",
        wiki_snapshot_path="wiki/subjects/chemie.md",
        workflow="plan",
    ),
    "teacher_mbb": Example(
        key="teacher_mbb",
        channel="teacher_behavior",
        target="user.md",
        section="Communication",
        content="This teacher wants all plan summaries in MBB style.",
        expected_queue="Teacher/Copilot Preferences",
        expected_applied_path="wiki/teacher_profile.md",
        wiki_snapshot_path="wiki/teacher_profile.md",
        class_id=None,
        subject=None,
        workflow="plan",
    ),
    "friday_discovery": Example(
        key="friday_discovery",
        channel="teacher_behavior",
        target="copilot.md",
        section="Planning Patterns",
        content="For this class, avoid long discovery phases on Fridays.",
        expected_queue="Teacher/Copilot Preferences",
        expected_applied_path=(
            "wiki/classes/chemie_9b_2026_27/memory/copilot_profile.md"
        ),
        wiki_snapshot_path=(
            "wiki/classes/chemie_9b_2026_27/memory/copilot_profile.md"
        ),
        workflow="plan",
    ),
}


def _now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def _write_json(path: pathlib.Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_text(path: pathlib.Path, text: str) -> None:
    path.write_text(text or "", encoding="utf-8")


def _request_json(method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
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


def _api_url(api_base: str, path: str) -> str:
    return api_base.rstrip("/") + path


def _wiki_file(api_base: str, class_id: str, wiki_path: str) -> dict[str, Any]:
    encoded = urllib.parse.quote(wiki_path, safe="")
    return _request_json(
        "GET",
        _api_url(api_base, f"/api/classes/{class_id}/wiki/file?path={encoded}"),
    )


def _select_examples(scenario: str) -> list[Example]:
    if scenario == "two":
        return [EXAMPLES["class_redox"], EXAMPLES["subject_redox"]]
    return [
        EXAMPLES["class_redox"],
        EXAMPLES["subject_redox"],
        EXAMPLES["teacher_mbb"],
        EXAMPLES["friday_discovery"],
    ]


def _seed_rows(
    ledger: MemoryCandidateLedger,
    examples: list[Example],
    *,
    class_id: str,
    run_id: str,
    marker: str,
) -> list[MemoryCandidateRow]:
    ts = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    rows: list[MemoryCandidateRow] = []
    for idx, example in enumerate(examples, start=1):
        row_class_id = example.class_id if example.class_id is not None else None
        if row_class_id == "chemie_9b_2026_27":
            row_class_id = class_id
        rows.append(
            MemoryCandidateRow(
                id=f"{run_id}_{example.key}",
                created_at=ts,
                updated_at=ts,
                class_id=row_class_id,
                subject=example.subject,
                workflow=example.workflow,
                session_id=run_id,
                turn_index=idx,
                channel=example.channel,
                target=example.target,
                section=example.section,
                candidate_update=f"{marker}: {example.content}",
                evidence_summary=(
                    "Temporary section 4.4 trace candidate seeded by "
                    "run_memory_sweep_44_trace_bundle.py."
                ),
                evidence_refs=[f"trace:{run_id}:{example.key}"],
                source="trace_script",
                basis="explicit",
                confidence="high",
                cluster_key=f"trace.{run_id}.{example.key}",
            )
        )
    ledger.add_many(rows)
    return rows


def _proposal_items(proposal: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for candidates in (proposal.get("queues") or {}).values():
        if isinstance(candidates, list):
            items.extend(candidate for candidate in candidates if isinstance(candidate, dict))
    return items


def _snapshot_files(
    api_base: str,
    class_id: str,
    paths: list[str],
    out_dir: pathlib.Path,
    label: str,
) -> dict[str, str]:
    snapshots: dict[str, str] = {}
    snapshot_dir = out_dir / f"wiki-{label}"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    for wiki_path in sorted(set(paths)):
        file_payload = _wiki_file(api_base, class_id, wiki_path)
        markdown = str(file_payload.get("markdown", ""))
        snapshots[wiki_path] = markdown
        safe_name = wiki_path.replace("/", "__")
        _write_text(snapshot_dir / f"{safe_name}.md", markdown)
    return snapshots


def _cleanup_marker_lines(wiki_root: pathlib.Path, paths: list[str], marker: str) -> list[str]:
    cleaned: list[str] = []
    for wiki_path in sorted(set(paths)):
        full = wiki_root / wiki_path
        if not full.exists():
            continue
        lines = full.read_text(encoding="utf-8").splitlines()
        next_lines = [line for line in lines if marker not in line]
        if next_lines != lines:
            full.write_text("\n".join(next_lines).rstrip() + "\n", encoding="utf-8")
            cleaned.append(wiki_path)
    return cleaned


def _write_readme(
    run_dir: pathlib.Path,
    *,
    api_base: str,
    class_id: str,
    scenario: str,
    marker: str,
    selected: list[Example],
    applied: list[dict[str, Any]],
    cleaned: list[str],
    keep_writes: bool,
) -> None:
    rows = [
        "# Memory Sweep 4.4 Trace Bundle",
        "",
        f"- API base: `{api_base}`",
        f"- Class: `{class_id}`",
        f"- Scenario: `{scenario}`",
        f"- Marker: `{marker}`",
        f"- Cleanup mode: `{'kept writes' if keep_writes else 'removed smoke bullets'}`",
        "",
        "## Examples",
        "",
        "| Example | Expected queue | Target | Expected write |",
        "| --- | --- | --- | --- |",
    ]
    for example in selected:
        rows.append(
            "| "
            f"`{example.key}` | {example.expected_queue} | "
            f"`{example.target}` | `{example.expected_applied_path}` |"
        )
    rows.extend(
        [
            "",
            "## Files",
            "",
            "- `01-seeded-candidates.json`: rows inserted into the SQLite ledger.",
            "- `02-wiki-before/`: file snapshots before applying candidates.",
            "- `03-sweep-propose-before.json`: public proposal endpoint response.",
            "- `04-selected-proposals.json`: candidates selected from the proposal.",
            "- `05-apply-results.json`: `/memory/apply` and status results.",
            "- `06-sweep-propose-after.json`: proposal response after marking applied.",
            "- `07-wiki-after/`: file snapshots after applying candidates.",
            "- `08-cleanup.json`: smoke cleanup details.",
            "",
            "## Applied",
            "",
        ]
    )
    for item in applied:
        rows.append(
            f"- `{item['candidate_id']}` -> `{item['target']}` -> "
            f"`{', '.join(item.get('applied_wiki_paths', []))}`"
        )
    rows.extend(["", "## Cleanup", ""])
    if keep_writes:
        rows.append("- Smoke bullets were kept in the wiki files.")
    elif cleaned:
        rows.append("- Removed smoke bullets from:")
        rows.extend(f"  - `{path}`" for path in cleaned)
    else:
        rows.append("- No smoke bullets needed cleanup.")
    _write_text(run_dir / "README.md", "\n".join(rows) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a Memory Sweep section 4.4 trace bundle."
    )
    parser.add_argument("--api-base", default="http://localhost:8010")
    parser.add_argument("--class-id", default="chemie_9b_2026_27")
    parser.add_argument("--wiki-root", default=str(BACKEND_ROOT / "teacher_wiki"))
    parser.add_argument("--scenario", choices=("two", "all"), default="two")
    parser.add_argument("--run-name", default="")
    parser.add_argument("--keep-writes", action="store_true")
    args = parser.parse_args()

    wiki_root = pathlib.Path(args.wiki_root).resolve()
    run_name = args.run_name or f"{_now_stamp()}-memory-sweep-44-{args.scenario}"
    run_id = "trace_" + run_name.replace("-", "_").replace(":", "_")
    marker = f"TRACE44 {run_id}"
    run_dir = BACKEND_ROOT / "runs" / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    selected = _select_examples(args.scenario)
    target_paths = [example.wiki_snapshot_path for example in selected]

    ledger = MemoryCandidateLedger(wiki_root / "workflow" / "memory_candidates.sqlite")
    ledger.initialize()
    rows = _seed_rows(
        ledger,
        selected,
        class_id=args.class_id,
        run_id=run_id,
        marker=marker,
    )
    _write_json(run_dir / "01-seeded-candidates.json", [asdict(row) for row in rows])

    before = _snapshot_files(args.api_base, args.class_id, target_paths, run_dir, "before")
    _write_json(
        run_dir / "02-wiki-before-summary.json",
        {path: {"chars": len(text), "contains_marker": marker in text} for path, text in before.items()},
    )

    proposal_before = _request_json(
        "POST",
        _api_url(args.api_base, f"/api/classes/{args.class_id}/memory/sweep/propose"),
    )
    _write_json(run_dir / "03-sweep-propose-before.json", proposal_before)

    selected_ids = {row.id for row in rows}
    proposal_items = [
        item for item in _proposal_items(proposal_before) if item.get("candidate_id") in selected_ids
    ]
    _write_json(run_dir / "04-selected-proposals.json", proposal_items)
    if len(proposal_items) != len(rows):
        raise RuntimeError(
            f"Expected {len(rows)} seeded candidates in proposal, found {len(proposal_items)}"
        )

    apply_results: list[dict[str, Any]] = []
    examples_by_id = {row.id: example for row, example in zip(rows, selected, strict=True)}
    for item in proposal_items:
        example = examples_by_id[item["candidate_id"]]
        content_to_apply = f"{marker}: {example.content}"
        apply_payload = {
            "items": [
                {
                    "target": item["target"],
                    "section": item["section"],
                    "content": content_to_apply,
                }
            ]
        }
        apply_response = _request_json(
            "POST",
            _api_url(args.api_base, f"/api/classes/{args.class_id}/memory/apply"),
            apply_payload,
        )
        status_response = _request_json(
            "POST",
            _api_url(
                args.api_base,
                f"/api/classes/{args.class_id}/memory/candidates/{item['candidate_id']}/status",
            ),
            {"status": "applied", "review_batch_id": run_id},
        )
        apply_results.append(
            {
                "candidate_id": item["candidate_id"],
                "queue": item["review_queue"],
                "target": item["target"],
                "section": item["section"],
                "content": item["content"],
                "applied_content": content_to_apply,
                "apply_response": apply_response,
                "status_response": status_response,
                "applied_wiki_paths": apply_response.get("applied_wiki_paths", []),
            }
        )
    _write_json(run_dir / "05-apply-results.json", apply_results)

    proposal_after = _request_json(
        "POST",
        _api_url(args.api_base, f"/api/classes/{args.class_id}/memory/sweep/propose"),
    )
    _write_json(run_dir / "06-sweep-propose-after.json", proposal_after)
    remaining_ids = {
        item.get("candidate_id")
        for item in _proposal_items(proposal_after)
        if item.get("candidate_id") in selected_ids
    }
    if remaining_ids:
        raise RuntimeError(f"Applied candidates still appear in sweep: {sorted(remaining_ids)}")

    after = _snapshot_files(args.api_base, args.class_id, target_paths, run_dir, "after")
    _write_json(
        run_dir / "07-wiki-after-summary.json",
        {path: {"chars": len(text), "contains_marker": marker in text} for path, text in after.items()},
    )

    cleaned: list[str] = []
    if not args.keep_writes:
        cleaned = _cleanup_marker_lines(wiki_root, target_paths, marker)
    cleanup_payload = {
        "keep_writes": args.keep_writes,
        "marker": marker,
        "cleaned_paths": cleaned,
        "ledger_rows_left_as_applied_history": [row.id for row in rows],
    }
    _write_json(run_dir / "08-cleanup.json", cleanup_payload)

    _write_readme(
        run_dir,
        api_base=args.api_base,
        class_id=args.class_id,
        scenario=args.scenario,
        marker=marker,
        selected=selected,
        applied=apply_results,
        cleaned=cleaned,
        keep_writes=args.keep_writes,
    )
    print(f"Memory Sweep 4.4 trace bundle written to: {run_dir}")


if __name__ == "__main__":
    main()
