"""Interactive REPL for agent debug CLI."""

from __future__ import annotations

from pathlib import Path

from app.cli.session import CliSession
from app.cli.trace import JsonlTraceWriter, TracePrinter


async def run_turn_interactive(
    session: CliSession,
    user_message: str,
    *,
    printer: TracePrinter,
    trace: JsonlTraceWriter | None,
    turn_number: int,
) -> bool:
    """Run one user turn. Returns False if the session should exit."""
    printer.reset_turn_buffers()
    events, final, error = await session.run_turn(user_message)

    for event in events:
        printer.print_event(event)
        if trace is not None:
            trace.write_event(event, turn=turn_number)

    if error is not None:
        return True
    return True


def _handle_slash(
    session: CliSession,
    line: str,
    printer: TracePrinter,
    *,
    draft_file: Path | None,
) -> str | None:
    """Returns 'quit', 'continue', or None after handling."""
    cmd = line.strip().lower()
    if cmd in ("/quit", "/exit", "/q"):
        return "quit"
    if cmd == "/context":
        printer.stream.write("\n--- context pack ---\n")
        printer.stream.write(session.context_pack())
        printer.stream.write("\n--- end context ---\n\n")
        return "continue"
    if cmd == "/draft":
        printer.stream.write("\n--- draft ---\n")
        printer.stream.write(session.draft)
        if not session.draft.endswith("\n"):
            printer.stream.write("\n")
        printer.stream.write("--- end draft ---\n\n")
        return "continue"
    if cmd == "/tools":
        printer.stream.write("\n--- tools (last turn) ---\n")
        printer.print_tools_summary()
        printer.stream.write("\n")
        return "continue"
    if cmd == "/propose":
        if session.mode != "ingest":
            printer.stream.write("/propose is only available in ingest mode.\n")
            return "continue"
        paths = session.propose_paths()
        printer.stream.write(f"\n--- propose ({len(paths)} paths) ---\n")
        for path, rationale in paths:
            printer.stream.write(f"  {path}\n    {rationale}\n")
        printer.stream.write("\n")
        return "continue"
    if cmd == "/help":
        printer.stream.write(
            "Commands: /context /draft /tools /propose (ingest) /help /quit\n"
        )
        return "continue"
    printer.stream.write(f"Unknown command: {line}\n")
    return "continue"


async def run_repl(
    session: CliSession,
    *,
    verbose: bool = True,
    trace_path: Path | None = None,
    draft_file: Path | None = None,
) -> None:
    printer = TracePrinter(verbose=verbose)
    trace = JsonlTraceWriter(trace_path) if trace_path else None
    turn = 0

    printer.stream.write(
        f"KlassenPilot agent CLI — mode={session.mode} class={session.class_id}\n"
        "Type a message, or /help for commands. /quit to exit.\n\n"
    )

    try:
        while True:
            try:
                line = input("klassenpilot> ").strip()
            except (EOFError, KeyboardInterrupt):
                printer.stream.write("\n")
                break
            if not line:
                continue
            if line.startswith("/"):
                action = _handle_slash(session, line, printer, draft_file=draft_file)
                if action == "quit":
                    break
                continue

            turn += 1
            if trace is not None:
                trace.start_turn()
            await run_turn_interactive(
                session,
                line,
                printer=printer,
                trace=trace,
                turn_number=turn,
            )
    finally:
        if trace is not None:
            trace.close()
        if draft_file is not None:
            draft_file.write_text(session.draft, encoding="utf-8")
            printer.stream.write(f"Draft saved to {draft_file}\n")
