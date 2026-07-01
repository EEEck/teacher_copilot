"""KlassenPilot developer CLI — interactive agent debugging."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from app.cli.repl import run_repl, run_turn_interactive
from app.cli.session import CliSession
from app.cli.trace import JsonlTraceWriter, TracePrinter
from app.config import get_settings
from app.openai_bootstrap import configure_openai_from_settings
from app.teacher_agent.agents import AgentRunner
from app.teacher_agent.wiki_store import WikiStore


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="Developer tools for KlassenPilot agent debugging.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    chat = sub.add_parser("chat", help="Interactive or one-shot agent chat")
    chat.add_argument("--mode", choices=("ingest", "plan"), required=True)
    chat.add_argument("--class", dest="class_id", required=True, help="Class id")
    chat.add_argument("-v", "--verbose", action="store_true", default=True)
    chat.add_argument("--no-verbose", action="store_false", dest="verbose")
    chat.add_argument(
        "--tool-limit",
        type=int,
        default=None,
        help="Max chars per tool result/args (default: unlimited)",
    )
    chat.add_argument(
        "--trace", type=Path, default=None, help="Append JSONL trace file"
    )
    chat.add_argument(
        "--trace-reasoning",
        action="store_true",
        help="Include aggregated model reasoning in the trace (default: omit)",
    )
    chat.add_argument(
        "--show-context",
        action="store_true",
        help="Print memory context pack at startup",
    )
    chat.add_argument(
        "--draft-file",
        type=Path,
        default=None,
        help="Load draft from file; save back on exit (interactive)",
    )
    chat.add_argument(
        "--message",
        type=str,
        default=None,
        help="Single turn then exit (non-interactive)",
    )
    return parser


def _create_session(args: argparse.Namespace) -> CliSession:
    settings = get_settings()
    if not configure_openai_from_settings(settings):
        print(
            "ERROR: OPENAI_API_KEY not set. Add it to backend/.env",
            file=sys.stderr,
        )
        sys.exit(1)

    wiki = WikiStore(root=settings.wiki_root)
    agents = AgentRunner(settings=settings, wiki=wiki)
    agents.tool_output_limit = args.tool_limit
    agents.tool_args_limit = args.tool_limit

    draft = ""
    if args.draft_file and args.draft_file.is_file():
        draft = args.draft_file.read_text(encoding="utf-8")

    return CliSession(
        mode=args.mode,
        class_id=args.class_id,
        wiki=wiki,
        agents=agents,
        draft=draft,
    )


async def _cmd_chat(args: argparse.Namespace) -> None:
    session = _create_session(args)

    if args.show_context:
        print("--- context pack ---")
        ctx = session.context_pack()
        print(ctx)
        print("--- end context ---\n")
    else:
        ctx = None

    if args.message:
        printer = TracePrinter(verbose=args.verbose)
        trace = (
            JsonlTraceWriter(args.trace, include_reasoning=args.trace_reasoning)
            if args.trace
            else None
        )
        if trace is not None:
            trace.write_session_meta(mode=session.mode, class_id=session.class_id)
            if ctx is not None:
                trace.write_context_pack(ctx)
        turn = trace.start_turn() if trace else 1
        await run_turn_interactive(
            session,
            args.message,
            printer=printer,
            trace=trace,
            turn_number=turn,
        )
        if trace:
            trace.close()
        if args.draft_file:
            args.draft_file.write_text(session.draft, encoding="utf-8")
        return

    await run_repl(
        session,
        verbose=args.verbose,
        trace_path=args.trace,
        include_reasoning_trace=args.trace_reasoning,
        context_pack_for_trace=ctx,
        draft_file=args.draft_file,
    )


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "chat":
        asyncio.run(_cmd_chat(args))
    else:
        parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
