"""Run Memory V4 golden cases and write inspectable stage traces.

This is a small diagnostic harness, not a second evaluation framework. It
reuses the existing memory-capture goldens and the existing live API trace
shape. The bundle makes the four control stages explicit:

    admission -> priority -> sweep -> apply

Default mode is deterministic and does not call the API. Live mode runs the
golden through the local Plan/Update Memory API and stores the full prompt
assembly, SSE stream, workflow trace, runtime candidates, and a shadow V4
stage trace. Sweep is opt-in because it may call the configured model.

Examples:

    python scripts/run_memory_v4_golden_trace.py
    python scripts/run_memory_v4_golden_trace.py --scenario all
    python scripts/run_memory_v4_golden_trace.py --mode live --scenario two
    python scripts/run_memory_v4_golden_trace.py --mode live --run-sweep
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
import urllib.error
import urllib.request
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from app.teacher_agent.memory_capture import (  # noqa: E402
    MemoryCandidate,
    _verified_quote,
    candidate_is_allowed,
    discipline_memory_candidates,
)
from tests.evals.goldens.memory_capture import MEMORY_CAPTURE_GOLDENS  # noqa: E402
from memory_scenario_helpers import reasoning_events, reasoning_text  # noqa: E402


DEFAULT_CLASS_ID = "chemie_9b_2026_27"
DEFAULT_GOLDEN_IDS = (
    "conduct_request_teacher_profile_fast_lane",
    "rich_engagement_observation_not_fast_lane",
)

EXPECTED_SCOPES = {
    "conduct_request_teacher_profile_fast_lane": "global",
    "store_request_teaching_patterns_fast_lane": "block",
    "rich_engagement_observation_not_fast_lane": "lesson",
    "one_off_task_request_not_fast_lane": "turn",
    "compiled_page_never_fast_lane": "block",
}


def _now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def _write_json(path: pathlib.Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def _write_text(path: pathlib.Path, value: str) -> None:
    path.write_text(value or "", encoding="utf-8")


def _request_json(method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed: {exc.status} {detail}") from exc


def _request_text(method: str, url: str, payload: dict[str, Any] | None = None) -> str:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed: {exc.status} {detail}") from exc


def _parse_sse(body: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for block in body.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data:"):
                try:
                    events.append(json.loads(line[5:].strip()))
                except json.JSONDecodeError:
                    events.append({"type": "unparsed_sse", "data": line[5:].strip()})
    return events


def _golden_by_id(golden_id: str):
    for golden in MEMORY_CAPTURE_GOLDENS:
        if golden.golden_id == golden_id:
            return golden
    available = ", ".join(g.golden_id for g in MEMORY_CAPTURE_GOLDENS)
    raise ValueError(f"Unknown golden {golden_id!r}. Available: {available}")


def selected_goldens(scenario: str, requested: tuple[str, ...]) -> list[Any]:
    if requested:
        return [_golden_by_id(golden_id) for golden_id in requested]
    if scenario == "all":
        return list(MEMORY_CAPTURE_GOLDENS)
    return [_golden_by_id(golden_id) for golden_id in DEFAULT_GOLDEN_IDS]


def _quote_text(candidate: MemoryCandidate, teacher_message: str) -> str | None:
    return _verified_quote(candidate.evidence, teacher_message)


def build_candidate_stage_trace(
    candidate: MemoryCandidate,
    *,
    teacher_message: str,
    expected_scope: str = "unknown",
) -> dict[str, Any]:
    """Build a shadow V4 trace from one model/runtime candidate.

    Current production code does not yet expose Admission and Priority as
    separate objects. This function makes the proposed boundaries observable
    without changing production behavior. It is intentionally conservative:
    missing origin/quote/scope information becomes needs_review.
    """

    quote = _quote_text(candidate, teacher_message)
    admission_checks = {
        "teacher_origin": candidate.source == "teacher_explicit",
        "quote_present_in_origin": bool(quote),
        "target_supported": candidate_is_allowed(candidate),
        "claim_nonempty": bool(candidate.candidate_update.strip()),
        "speech_act_known": candidate.speech_act
        in {"conduct_request", "store_request", "observation"},
        "scope_known": expected_scope != "unknown",
    }
    admission_ok = all(admission_checks.values())
    admission = {
        "decision": "admitted" if admission_ok else "needs_review",
        "checks": admission_checks,
        "reason_codes": [
            name for name, passed in admission_checks.items() if not passed
        ],
    }

    # Deterministic goldens keep the expected scope beside the legacy fixture
    # shape. Feed that oracle into the candidate so the backend simulation
    # exercises the same typed contract as a live model emission.
    candidate_for_backend = candidate.model_copy(update={"scope": expected_scope})
    disciplined = discipline_memory_candidates(
        [candidate_for_backend], teacher_message=teacher_message
    )[0]
    priority_ok = (
        admission_ok
        and disciplined.fast_lane
        and candidate.speech_act in {"conduct_request", "store_request"}
        and expected_scope in {"class", "global"}
    )
    priority = {
        "decision": "fast_lane" if priority_ok else "not_fast_lane",
        "fast_lane_backend_verdict": disciplined.fast_lane,
        "reason_codes": [
            "explicit_standing_request"
            if priority_ok
            else "not_explicitly_priority_eligible"
        ],
    }

    return {
        "candidate": candidate_for_backend.model_dump(),
        "scope": {"expected": expected_scope},
        "admission": admission,
        "priority": priority,
        "sweep": {
            "decision": "queued_for_sweep"
            if admission_ok
            else "held_for_review",
            "input_claim": candidate.candidate_update,
            "input_quote": quote or "",
            "input_origin": "teacher_message" if admission_ok else "uncertain",
        },
        "apply": {
            "decision": "not_run",
            "reason": "This diagnostic never approves or writes curated Markdown.",
        },
    }


def _synthetic_candidates(golden: Any) -> list[MemoryCandidate]:
    targets = golden.expected_targets or (golden.target,)
    return [
        MemoryCandidate(
            target=target,
            section="General",
            candidate_update="Golden durable memory candidate.",
            evidence=golden.evidence,
            source="teacher_explicit",
            basis="explicit",
            confidence="high",
            speech_act=golden.speech_act,
        )
        for target in targets
    ]


def _runtime_candidates(trace: dict[str, Any]) -> list[MemoryCandidate]:
    raw = (trace.get("runtime") or {}).get("memory_candidates") or []
    fields = set(MemoryCandidate.model_fields)
    return [
        MemoryCandidate(**{key: value for key, value in item.items() if key in fields})
        for item in raw
        if isinstance(item, dict)
    ]


def _write_prompt_assemblies(run_dir: pathlib.Path, trace: dict[str, Any]) -> int:
    assemblies = [
        event
        for event in trace.get("event_trace", [])
        if event.get("type") == "prompt_assembly"
    ]
    for index, assembly in enumerate(assemblies, start=1):
        prefix = run_dir / f"prompt-{index:02d}"
        _write_json(prefix.with_suffix(".json"), assembly)
        _write_text(prefix.with_name(prefix.name + "-instructions.txt"), assembly.get("instructions", ""))
        _write_text(prefix.with_name(prefix.name + "-user-input.txt"), assembly.get("user_input", ""))
        sections: list[str] = [
            f"# Prompt {index:02d}",
            "",
            f"Stage: {assembly.get('stage', '')}",
            f"Model call: {assembly.get('model_call', '')}",
        ]
        for section in assembly.get("sections", []):
            sections.extend(
                [
                    "",
                    f"## {section.get('name', '')}",
                    f"- function: `{section.get('function', '')}`",
                    f"- source: `{section.get('source', '')}`",
                    f"- chars: {section.get('chars', 0)}",
                    "",
                    "```text",
                    str(section.get("text", "")),
                    "```",
                ]
            )
        _write_text(prefix.with_name(prefix.name + "-sections.md"), "\n".join(sections))
    return len(assemblies)


def _run_deterministic_case(run_dir: pathlib.Path, golden: Any) -> dict[str, Any]:
    candidates = _synthetic_candidates(golden)
    traces = [
        build_candidate_stage_trace(
            candidate,
            teacher_message=golden.teacher_message,
            expected_scope=EXPECTED_SCOPES.get(golden.golden_id, "unknown"),
        )
        for candidate in candidates
    ]
    _write_json(run_dir / "01-golden.json", golden.__dict__)
    _write_json(run_dir / "02-admission-priority-sweep-apply.json", traces)
    _write_json(
        run_dir / "03-run-status.json",
        {"mode": "deterministic", "sweep_called": False, "apply_called": False},
    )
    return {"mode": "deterministic", "candidates": len(candidates), "traces": traces}


def _workflow_paths(workflow: str, class_id: str) -> tuple[str, str, str]:
    normalized = workflow.strip().lower()
    if normalized == "plan":
        base = f"/api/classes/{class_id}/plan/sessions"
        return normalized, base, f"{base}/{{session_id}}/trace"
    if normalized in {"ingest", "memory", "update_memory"}:
        base = f"/api/classes/{class_id}/ingest/sessions"
        return "ingest", base, f"{base}/{{session_id}}/trace"
    raise ValueError(f"Unknown workflow: {workflow!r}")


def _run_live_case(
    run_dir: pathlib.Path,
    golden: Any,
    *,
    api_base: str,
    class_id: str,
    run_sweep: bool,
) -> dict[str, Any]:
    workflow, base, trace_path = _workflow_paths(golden.workflow, class_id)
    session = _request_json("POST", api_base.rstrip("/") + base, {})
    session_id = session["session_id"]
    _write_json(run_dir / "01-golden.json", golden.__dict__)
    _write_json(run_dir / "02-session-start.json", session)

    trace = _request_json(
        "GET", api_base.rstrip("/") + trace_path.format(session_id=session_id)
    )
    _write_json(run_dir / "03-trace-before-first-message.json", trace)

    prompts = [message for message in (golden.prior_message, golden.teacher_message) if message]
    for index, prompt in enumerate(prompts, start=1):
        stream = _request_text(
            "POST",
            api_base.rstrip("/") + f"{base}/{session_id}/chat/stream",
            {"message": prompt},
        )
        _write_text(run_dir / f"turn-{index:02d}-sse.txt", stream)
        sse_events = _parse_sse(stream)
        _write_json(run_dir / f"turn-{index:02d}-sse-events.json", sse_events)
        _write_json(
            run_dir / f"turn-{index:02d}-reasoning.json",
            reasoning_events(sse_events),
        )
        _write_text(
            run_dir / f"turn-{index:02d}-reasoning.txt",
            reasoning_text(sse_events),
        )
        trace = _request_json(
            "GET", api_base.rstrip("/") + trace_path.format(session_id=session_id)
        )
        _write_json(run_dir / f"turn-{index:02d}-trace.json", trace)

    candidates = _runtime_candidates(trace)
    traces = [
        build_candidate_stage_trace(
            candidate,
            teacher_message=golden.teacher_message,
            expected_scope=EXPECTED_SCOPES.get(golden.golden_id, "unknown"),
        )
        for candidate in candidates
    ]
    _write_json(run_dir / "04-runtime-candidates.json", [c.model_dump() for c in candidates])
    _write_json(run_dir / "05-admission-priority-sweep-apply.json", traces)
    prompt_count = _write_prompt_assemblies(run_dir, trace)

    if run_sweep:
        sweep = _request_json(
            "POST",
            api_base.rstrip("/") + f"/api/classes/{class_id}/memory/sweep/propose",
        )
        _write_json(run_dir / "06-sweep-proposal.json", sweep)
    else:
        _write_json(
            run_dir / "06-sweep-proposal.json",
            {"status": "not_run", "reason": "Pass --run-sweep to call Memory Sweep."},
        )

    apply_status = {
        "status": "not_run",
        "reason": "This diagnostic never approves or writes curated Markdown.",
    }
    _write_json(run_dir / "07-apply-status.json", apply_status)
    return {
        "mode": "live",
        "workflow": workflow,
        "session_id": session_id,
        "candidates": len(candidates),
        "prompt_assemblies": prompt_count,
        "sweep_called": run_sweep,
        "traces": traces,
    }


def _write_readme(
    run_dir: pathlib.Path,
    *,
    golden: Any,
    summary: dict[str, Any],
) -> None:
    lines = [
        f"# Memory V4 Golden Trace: {golden.golden_id}",
        "",
        f"- Mode: `{summary.get('mode', '')}`",
        f"- Workflow: `{golden.workflow}`",
        f"- Expected speech act: `{golden.speech_act}`",
        f"- Expected scope: `{EXPECTED_SCOPES.get(golden.golden_id, 'unknown')}`",
        f"- Teacher message: {golden.teacher_message}",
        "",
        "## Four-stage interpretation",
        "",
        "1. `Admission`: valid teacher-originated evidence?",
        "2. `Priority`: explicit and worth early attention?",
        "3. `Sweep`: merge, downgrade, reject, or propose?",
        "4. `Apply`: teacher-approved curated Markdown write?",
        "",
        "## Files",
        "",
        "- `01-golden.json`: source golden and expected outcome.",
        "- `02-session-start.json` / `03-trace-before-first-message.json`: live startup context when applicable.",
        "- `turn-*-sse.txt` and `turn-*-trace.json`: raw stream and full workflow trace.",
        "- `turn-*-reasoning.txt` and `turn-*-reasoning.json`: raw local development reasoning events.",
        "- `04-runtime-candidates.json`: candidates emitted by the live runtime.",
        "- `05-admission-priority-sweep-apply.json`: stage-by-stage shadow trace.",
        "- `06-sweep-proposal.json`: Sweep response, or an explicit not-run record.",
        "- `07-apply-status.json`: explicit proof that this diagnostic did not write Markdown.",
        "- `prompt-*.json`, `prompt-*-sections.md`: full prompt assembly snapshots.",
    ]
    _write_text(run_dir / "README.md", "\n".join(lines) + "\n")


def run(args: argparse.Namespace) -> pathlib.Path:
    goldens = selected_goldens(args.scenario, tuple(args.golden))
    output_root = pathlib.Path(args.output_root)
    if not output_root.is_absolute():
        output_root = REPO_ROOT / output_root
    run_dir = output_root / (args.run_name or f"{_now_stamp()}-memory-v4-goldens")
    run_dir.mkdir(parents=True, exist_ok=True)

    summaries: list[dict[str, Any]] = []
    for golden in goldens:
        case_dir = run_dir / golden.golden_id
        case_dir.mkdir(parents=True, exist_ok=True)
        if args.mode == "live":
            summary = _run_live_case(
                case_dir,
                golden,
                api_base=args.api_base,
                class_id=args.class_id,
                run_sweep=args.run_sweep,
            )
        else:
            summary = _run_deterministic_case(case_dir, golden)
        _write_readme(case_dir, golden=golden, summary=summary)
        summaries.append({"golden_id": golden.golden_id, **summary})

    _write_json(
        run_dir / "00-run-meta.json",
        {
            "created_at": dt.datetime.now().isoformat(),
            "mode": args.mode,
            "api_base": args.api_base,
            "class_id": args.class_id,
            "run_sweep": args.run_sweep,
            "goldens": [golden.golden_id for golden in goldens],
            "summaries": summaries,
        },
    )
    _write_text(
        run_dir / "README.md",
        "# Memory V4 Golden Trace Bundle\n\n"
        + "The bundle is organized around Admission, Priority, Sweep, and Apply.\n\n"
        + "Cases:\n"
        + "\n".join(f"- `{item['golden_id']}`" for item in summaries)
        + "\n",
    )
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write deterministic or live Memory V4 golden trace bundles."
    )
    parser.add_argument("--mode", choices=("deterministic", "live"), default="deterministic")
    parser.add_argument("--scenario", choices=("two", "all"), default="two")
    parser.add_argument("--golden", action="append", default=[], help="Repeat to select explicit golden ids.")
    parser.add_argument("--api-base", default="http://localhost:8010")
    parser.add_argument("--class-id", default=DEFAULT_CLASS_ID)
    parser.add_argument("--output-root", default="backend/runs")
    parser.add_argument("--run-name", default="")
    parser.add_argument("--run-sweep", action="store_true")
    args = parser.parse_args()
    run_dir = run(args)
    print(f"Memory V4 golden trace bundle written to: {run_dir}")


if __name__ == "__main__":
    main()
