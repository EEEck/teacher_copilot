"""Create a complete lesson-planning trace bundle for debugging.

This script calls the local KlassenPilot API, runs the default three-turn FCKW
planning scenario, and writes a timestamped folder containing:

- session start response
- trace before chat
- raw SSE for each turn
- trace after each turn
- exact prompt instructions/user input for each model call
- section-by-section prompt context
- tool call/result report
- raw evidence files by raw_ref
- final lesson plan

It uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import urllib.error
import urllib.request
from typing import Any


DEFAULT_PROMPT_1 = """Plan the next 45-minute lesson for Chemie 9b. Topic: redox reactions applied to CFC/FCKW compounds (Chlorfluorkohlenwasserstoffe). Include about 10 minutes on environmental impact (ozone layer, Montreal Protocol, alternatives). Build on our existing redox lessons in the wiki. Exam-oriented Gymnasium level.
Structure the lesson flow: 5 min redox recap, 15 min FCKW structure and redox half-reactions, 10 min environmental impact with one example (e.g. CFC-11), 10 min practice, 5 min exit ticket. Note the misconception: oxidation number vs charge.
Add differentiated practice and homework (2 questions). Teacher notes: no real CFCs in the lab; demo alternatives only.
"""

DEFAULT_PROMPT_2 = """Can we also add a 5 min review session of the last 4 lectures? I would like to consider what the class confused the last few sessions and incorporate key findings to make the introduction of FCKW simpler for them to digest.
"""

DEFAULT_PROMPT_3 = """I am very happy with it. Maybe as a last refinement, let's add only a 2 min recap together with students actively recalling the key learning.
"""


def _now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def _read_prompt(path: str | None, fallback: str) -> str:
    if not path:
        return fallback
    return pathlib.Path(path).read_text(encoding="utf-8")


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

    nested = assembly.get("nested", {}).get("class_slice", {}).get("sections", [])
    if nested:
        lines.extend(["", "## Nested Class Slice"])
        for sec in nested:
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
        "# Plan Trace Bundle",
        "",
        f"Run directory: `{run_dir}`",
        f"Session id: `{session.get('session_id', '')}`",
        f"Class: `{class_id}`",
        f"Created: {dt.datetime.now().isoformat()}",
        "",
        "## Files",
        "- `00-run-meta.json`: prompt inputs and run metadata",
        "- `01-session-start.json`: API session start response",
        "- `02-trace-before-first-message.json`: exact trace before any chat",
        "- `NN-turnX-sse.txt`: raw SSE stream for each turn",
        "- `NN-trace-after-turnX.json`: trace after each teacher prompt",
        "- `NN-final-lessonplan.md`: final teacher-facing plan artifact",
        "- `prompt-XX-*-instructions.txt`: exact model instructions for each model call",
        "- `prompt-XX-*-user-input.txt`: exact user input for each model call",
        "- `prompt-XX-*-sections.md`: readable section-by-section context",
        "- `snapshot-00-before-first-message-*`: exact prompt stack before any chat",
        "- `snapshot-01-after-turn1-next-prompt-*`: exact prompt stack after turn 1 if another turn starts",
        "- `snapshot-02-after-turn2-next-prompt-*`: exact prompt stack after turn 2 if another turn starts",
        "- `08-tool-calls-and-results.md`: tool call inputs and streamed outputs",
        "- `raw-evidence/`: full captured tool outputs by raw_ref",
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
                f"- Exact instructions: `prompt-{n}-{stage}-instructions.txt`",
                f"- Exact user input: `prompt-{n}-{stage}-user-input.txt`",
                f"- Section view: `prompt-{n}-{stage}-sections.md`",
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
            "## What The LLM Knew At Each Step",
            "- Before first message: no conversation yet; trace shows default plan-chat stack and empty artifact template.",
            "- Lazy opening call: compact class slice only plus opening instructions.",
            "- First planning call: compact class slice, teacher/copilot profiles, empty runtime state, empty plan artifact, no evidence briefs, opening assistant message, and teacher prompt.",
            "- Later planning calls: same compact class slice plus updated runtime state, current full lesson artifact, compact evidence briefs, full recent conversation window, and raw evidence refs available via tool.",
            f"- This bundle ran {len(prompts)} teacher turns.",
            "",
            "## Quick Quality Notes",
            "- Use `prompt-*-sections.md` to inspect exact context, not legacy flat context previews.",
            "- Use `08-tool-calls-and-results.md` and `raw-evidence/` to inspect what tools actually returned.",
        ]
    )
    _write_text(run_dir / "README.md", "\n".join(lines))


def run(args: argparse.Namespace) -> pathlib.Path:
    prompts = [
        _read_prompt(args.prompt1_file, DEFAULT_PROMPT_1),
        _read_prompt(args.prompt2_file, DEFAULT_PROMPT_2),
        _read_prompt(args.prompt3_file, DEFAULT_PROMPT_3),
    ]
    run_name = args.run_name or f"{_now_stamp()}-fckw-plan-3turn"
    output_root = pathlib.Path(args.output_root)
    if not output_root.is_absolute():
        output_root = pathlib.Path(__file__).resolve().parents[1] / output_root
    run_dir = output_root / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    base = f"{args.api_base.rstrip('/')}/api/classes/{args.class_id}/plan/sessions"
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

    trace0 = _request_json("GET", f"{base}/{session_id}/trace")
    _write_json(run_dir / "02-trace-before-first-message.json", trace0)
    _write_assembly(run_dir / "snapshot-00-before-first-message", trace0["prompt_assembly"], "Snapshot 00 - Before First Message")

    final_trace = trace0
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

    _write_text(run_dir / f"{file_idx:02d}-final-lessonplan.md", final_trace.get("artifact_markdown", ""))
    file_idx += 1

    assemblies = [e for e in final_trace.get("event_trace", []) if e.get("type") == "prompt_assembly"]
    for idx, assembly in enumerate(assemblies, start=1):
        n = f"{idx:02d}"
        stage = assembly.get("stage", "prompt")
        _write_assembly(run_dir / f"prompt-{n}-{stage}", assembly, f"Prompt {n} - {stage}")

    _write_text(run_dir / f"{file_idx:02d}-tool-calls-and-results.md", _tool_report(final_trace))
    raw_dir = run_dir / "raw-evidence"
    raw_dir.mkdir(exist_ok=True)
    for key, value in final_trace.get("raw_evidence", {}).items():
        _write_text(raw_dir / f"{key}.txt", str(value))

    _write_readme(run_dir, session, args.class_id, prompts, assemblies, final_trace)
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a KlassenPilot plan trace bundle.")
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
