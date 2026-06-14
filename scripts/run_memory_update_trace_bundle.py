"""Create an Update Memory trace bundle for debugging.

This mirrors ``run_plan_trace_bundle.py`` but targets the ingest/update-memory
API. It runs a default three-turn lesson-results scenario and writes a local
bundle with raw SSE, trace JSON, prompt assembly, tool calls/results, raw
evidence, and final diary markdown.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import urllib.error
import urllib.request
from typing import Any


DEFAULT_PROMPT_1 = """I want to update the lesson outcome from 05/29
"""

DEFAULT_PROMPT_2 = """Lesson Results — 2026-05-29 —
What was covered
no problem on those two items:
Review common anions and their charges.
Separate ion charge from oxidation number.
I could not fully cover the following due to student confusin and interruption:
Connect chloride, oxide, and phosphate back to the redox sequence.
Student participation
student were engaged but too much confusion and student did not let me know early
What went well
they understood the common anions quickly, that concept was explained well by me
What didn't go well
went into a rabbit whole with phosphates and confused students too much
Student observations
Joonho was the only one who understood phosphate redox states he is doing very well, Alex was constantly interrupting and not following at all, Rita was participating well but not everything was correct
Homework & follow-ups
gave mainly homework about common anions
"""

DEFAULT_PROMPT_3 = """I want to add more information about student participation:
Matt was also doing well and helped other students
with reguards to interruption that was mainly due to my poor lesson organization

in terms of open loops from 5-25,
I review metal displacement and student should have gotten that concept now, I had no time for the other open loop items

That is enough detail. Please make the lesson results ready to save memory.
"""


def _now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def _read_prompt(path: str | None, fallback: str) -> str:
    if not path:
        return fallback
    return pathlib.Path(path).read_text(encoding="utf-8")


def _request_json(method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
    text = _request_text(method, url, payload)
    return json.loads(text)


def _request_text(method: str, url: str, payload: dict[str, Any] | None = None) -> str:
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


def _write_json(path: pathlib.Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_text(path: pathlib.Path, text: str) -> None:
    path.write_text(text or "", encoding="utf-8")


def _section_lines(assembly: dict[str, Any], title: str) -> list[str]:
    lines = [
        f"# {title}",
        "",
        f"Stage: {assembly.get('stage', '')}",
        f"Model call: {assembly.get('model_call', '')}",
        f"Instruction chars: {assembly.get('instruction_chars', 0)}",
        f"User input chars: {assembly.get('user_input_chars', 0)}",
        "",
        "## Sections",
    ]
    for sec in assembly.get("sections", []):
        lines.extend(
            [
                "",
                f"### {sec.get('name', '')}",
                f"- function: `{sec.get('function', '')}`",
                f"- source: `{sec.get('source', '')}`",
                f"- included: {sec.get('included', True)}",
                f"- chars: {sec.get('chars', 0)}",
                "",
                "```text",
                str(sec.get("text", "")),
                "```",
            ]
        )
    return lines


def _write_assembly(prefix: pathlib.Path, assembly: dict[str, Any], title: str) -> None:
    _write_json(prefix.with_suffix(".json"), assembly)
    _write_text(prefix.parent / f"{prefix.name}-instructions.txt", assembly.get("instructions", ""))
    _write_text(prefix.parent / f"{prefix.name}-user-input.txt", assembly.get("user_input", ""))
    _write_text(prefix.parent / f"{prefix.name}-sections.md", "\n".join(_section_lines(assembly, title)))


def _tool_report(trace: dict[str, Any]) -> str:
    lines = ["# Tool Calls And Results", ""]
    idx = 0
    for event in trace.get("event_trace", []):
        if event.get("type") == "tool_call":
            idx += 1
            lines.extend(
                [
                    f"## Tool call {idx} - {event.get('name', '')}",
                    "",
                    f"Call id: `{event.get('call_id', '')}`",
                    "",
                    "```json",
                    str(event.get("args", "")),
                    "```",
                    "",
                ]
            )
        elif event.get("type") == "tool_result":
            lines.extend(
                [
                    "### Result",
                    "",
                    f"Call id: `{event.get('call_id', '')}`",
                    "",
                    "```text",
                    str(event.get("output", "")),
                    "```",
                    "",
                ]
            )
    return "\n".join(lines)


def _write_readme(
    run_dir: pathlib.Path,
    session: dict[str, Any],
    class_id: str,
    prompts: list[str],
    assemblies: list[dict[str, Any]],
    trace: dict[str, Any],
) -> None:
    lines = [
        "# Update Memory Trace Bundle",
        "",
        f"Run directory: `{run_dir}`",
        f"Session id: `{session.get('session_id', '')}`",
        f"Class: `{class_id}`",
        f"Created: {dt.datetime.now().isoformat()}",
        "",
        "## Files",
        "- `00-run-meta.json`: prompt inputs and run metadata",
        "- `01-session-start.json`: API session start response",
        "- `02-trace-before-first-message.json`: trace before chat",
        "- `NN-turnX-sse.txt`: raw SSE stream for each turn",
        "- `NN-trace-after-turnX.json`: trace after each teacher prompt",
        "- `NN-final-diary.md`: final lesson-results artifact",
        "- `prompt-XX-ingest_chat-*`: exact model instructions/user input/context sections",
        "- `08-tool-calls-and-results.md`: tool call inputs and streamed outputs",
        "- `raw-evidence/`: captured tool outputs by raw_ref",
        "",
        "## Prompt Calls",
    ]
    for idx, assembly in enumerate(assemblies, start=1):
        n = f"{idx:02d}"
        stage = assembly.get("stage", "")
        lines.extend(
            [
                f"### {n} - {stage}",
                f"- Model call: `{assembly.get('model_call', '')}`",
                f"- Instructions: {assembly.get('instruction_chars', 0)} chars",
                f"- User input: {assembly.get('user_input_chars', 0)} chars",
                "",
            ]
        )
    lines.extend(["## Tool Calls"])
    for event in trace.get("event_trace", []):
        if event.get("type") == "tool_call":
            lines.append(f"- `{event.get('name', '')}` with args: `{event.get('args', '')}`")
    lines.extend(["", "## Raw Evidence Refs"])
    for key, value in trace.get("raw_evidence", {}).items():
        lines.append(f"- `{key}` -> `raw-evidence/{key}.txt` ({len(str(value))} chars)")
    lines.extend(
        [
            "",
            "## Debug Focus",
            "- Check whether the agent identified the 2026-05-29 target early.",
            "- Check whether it used `read_memory_target` for 2026-05-25 before updating open loops.",
            "- Check that real student names are converted to pseudonymous IDs in the final diary.",
        ]
    )
    _write_text(run_dir / "README.md", "\n".join(lines))


def run(args: argparse.Namespace) -> pathlib.Path:
    prompts = [
        _read_prompt(args.prompt1_file, DEFAULT_PROMPT_1),
        _read_prompt(args.prompt2_file, DEFAULT_PROMPT_2),
        _read_prompt(args.prompt3_file, DEFAULT_PROMPT_3),
    ]
    run_name = args.run_name or f"{_now_stamp()}-memory-update-3turn"
    output_root = pathlib.Path(args.output_root)
    if not output_root.is_absolute():
        output_root = pathlib.Path(__file__).resolve().parents[1] / output_root
    run_dir = output_root / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    base = f"{args.api_base.rstrip('/')}/api/classes/{args.class_id}/ingest/sessions"
    session = _request_json("POST", base, {})
    session_id = session["session_id"]

    _write_json(
        run_dir / "00-run-meta.json",
        {
            "run_dir": str(run_dir),
            "created_at": dt.datetime.now().isoformat(),
            "api_base": args.api_base,
            "class_id": args.class_id,
            "session_id": session_id,
            "prompts": prompts,
        },
    )
    _write_json(run_dir / "01-session-start.json", session)

    final_trace = _request_json("GET", f"{base}/{session_id}/trace")
    _write_json(run_dir / "02-trace-before-first-message.json", final_trace)
    _write_assembly(
        run_dir / "snapshot-00-before-first-message",
        final_trace["prompt_assembly"],
        "Snapshot 00 - Before First Message",
    )

    file_idx = 3
    for turn_idx, prompt in enumerate(prompts, start=1):
        turn = _request_text("POST", f"{base}/{session_id}/chat/stream", {"message": prompt})
        _write_text(run_dir / f"{file_idx:02d}-turn{turn_idx}-sse.txt", turn)
        file_idx += 1
        final_trace = _request_json("GET", f"{base}/{session_id}/trace")
        _write_json(run_dir / f"{file_idx:02d}-trace-after-turn{turn_idx}.json", final_trace)
        _write_assembly(
            run_dir / f"snapshot-{turn_idx:02d}-after-turn{turn_idx}-next-prompt",
            final_trace["prompt_assembly"],
            f"Snapshot {turn_idx:02d} - After Turn {turn_idx} Next Prompt",
        )
        file_idx += 1

    _write_text(run_dir / f"{file_idx:02d}-final-diary.md", final_trace.get("artifact_markdown", ""))
    file_idx += 1

    assemblies = [e for e in final_trace.get("event_trace", []) if e.get("type") == "prompt_assembly"]
    for idx, assembly in enumerate(assemblies, start=1):
        _write_assembly(run_dir / f"prompt-{idx:02d}-ingest_chat", assembly, f"Prompt {idx:02d} - Ingest Chat")

    _write_text(run_dir / f"{file_idx:02d}-tool-calls-and-results.md", _tool_report(final_trace))
    raw_dir = run_dir / "raw-evidence"
    raw_dir.mkdir(exist_ok=True)
    for key, value in final_trace.get("raw_evidence", {}).items():
        _write_text(raw_dir / f"{key}.txt", str(value))

    _write_readme(run_dir, session, args.class_id, prompts, assemblies, final_trace)
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a KlassenPilot Update Memory trace bundle.")
    parser.add_argument("--api-base", default="http://localhost:8010")
    parser.add_argument("--class-id", default="chemie_9b_2026_27")
    parser.add_argument("--output-root", default="backend/runs")
    parser.add_argument("--run-name", default="")
    parser.add_argument("--prompt1-file", default="")
    parser.add_argument("--prompt2-file", default="")
    parser.add_argument("--prompt3-file", default="")
    args = parser.parse_args()
    run_dir = run(args)
    trace_files = sorted(run_dir.glob("*-trace-after-turn*.json"))
    trace = json.loads(trace_files[-1].read_text(encoding="utf-8"))
    prompt_calls = len([e for e in trace.get("event_trace", []) if e.get("type") == "prompt_assembly"])
    tool_calls = len([e for e in trace.get("event_trace", []) if e.get("type") == "tool_call"])
    raw_evidence = len(trace.get("raw_evidence", {}))
    print(f"run_dir={run_dir}")
    print(f"prompt_calls={prompt_calls}")
    print(f"tool_calls={tool_calls}")
    print(f"raw_evidence={raw_evidence}")


if __name__ == "__main__":
    main()
