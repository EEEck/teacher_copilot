"""Small operator CLI for provisioning invite-code beta testers."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.config import get_settings
from app.services.beta import BetaAuthService
from app.services.beta_report import render_beta_report, write_all_beta_reports


def _seed_wiki_root() -> Path:
    settings = get_settings()
    configured = Path(settings.wiki_root)
    if configured.exists():
        return configured
    local = Path(__file__).resolve().parents[2] / "teacher_wiki"
    if local.exists():
        return local
    return configured


def _default_db_path() -> Path:
    settings = get_settings()
    return Path(settings.beta_data_root) / "beta.sqlite3"


def _default_reports_dir() -> Path:
    settings = get_settings()
    return Path(settings.beta_data_root) / "reports"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Operate beta tester workspaces.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    provision = subparsers.add_parser(
        "provision", help="Provision an invite-code beta tester workspace."
    )
    provision.add_argument("--tester-id", required=True)
    provision.add_argument("--workspace-id", required=True)
    provision.add_argument("--invite-code", required=True)
    provision.add_argument("--display-label", default="")
    provision.add_argument("--seed-label", default="")
    provision.add_argument(
        "--workspace-mode", choices=("empty", "demo"), default="demo",
        help="New workspace contents: demo (beta default) or empty. Existing workspaces are preserved.",
    )

    report = subparsers.add_parser(
        "report", help="Render a Markdown report from beta telemetry."
    )
    report.add_argument("--db", type=Path, default=_default_db_path())
    report.add_argument("--tester", dest="tester_id")
    report.add_argument("--workspace", dest="workspace_id")
    report.add_argument("--session", dest="app_session_id")
    report.add_argument("--limit-sessions", type=int, default=10)
    report.add_argument("--out", type=Path)

    report_all = subparsers.add_parser(
        "report-all",
        help="Render Markdown reports for every provisioned beta tester.",
    )
    report_all.add_argument("--db", type=Path, default=_default_db_path())
    report_all.add_argument(
        "--reports-dir",
        type=Path,
        default=_default_reports_dir(),
        help="Directory for per-tester Markdown files (default: BETA_DATA_ROOT/reports).",
    )
    report_all.add_argument("--limit-sessions", type=int, default=10)
    report_all.add_argument(
        "--include-disabled",
        action="store_true",
        help="Include testers marked disabled in beta.sqlite3.",
    )

    list_cmd = subparsers.add_parser(
        "list", help="List provisioned beta testers and workspaces."
    )
    list_cmd.add_argument("--db", type=Path, default=_default_db_path())
    list_cmd.add_argument(
        "--include-disabled",
        action="store_true",
        help="Include testers marked disabled.",
    )

    disable = subparsers.add_parser(
        "disable", help="Disable a tester (invite stops working; sessions fail)."
    )
    disable.add_argument("--tester-id", required=True)
    disable.add_argument("--db", type=Path, default=_default_db_path())

    enable = subparsers.add_parser(
        "enable", help="Re-enable a previously disabled tester."
    )
    enable.add_argument("--tester-id", required=True)
    enable.add_argument("--db", type=Path, default=_default_db_path())

    args_list = list(sys.argv[1:] if argv is None else argv)
    if args_list and args_list[0] not in {
        "provision",
        "report",
        "report-all",
        "list",
        "disable",
        "enable",
        "-h",
        "--help",
    }:
        args_list.insert(0, "provision")
    args = parser.parse_args(args_list)

    if args.command == "list":
        import sqlite3

        if not args.db.exists():
            print(f"No beta DB at {args.db}", file=sys.stderr)
            return 1
        with sqlite3.connect(args.db) as conn:
            conn.row_factory = sqlite3.Row
            where = "" if args.include_disabled else "where t.disabled = 0"
            rows = conn.execute(
                f"""
                select
                    t.tester_id, t.display_label, t.disabled, t.created_at,
                    w.workspace_id, w.wiki_root
                from tester t
                left join workspace w on w.tester_id = t.tester_id
                {where}
                order by t.created_at
                """
            ).fetchall()
        if not rows:
            print("No testers found.")
            return 0
        for row in rows:
            flag = "DISABLED" if row["disabled"] else "active"
            label = row["display_label"] or "-"
            print(
                f"{row['tester_id']}\t{row['workspace_id'] or '-'}\t{flag}\t{label}"
            )
        return 0

    if args.command in {"disable", "enable"}:
        import sqlite3

        if not args.db.exists():
            print(f"No beta DB at {args.db}", file=sys.stderr)
            return 1
        disabled = 1 if args.command == "disable" else 0
        with sqlite3.connect(args.db) as conn:
            cur = conn.execute(
                "update tester set disabled = ?, updated_at = datetime('now') "
                "where tester_id = ?",
                (disabled, args.tester_id),
            )
            if cur.rowcount == 0:
                print(f"Unknown tester: {args.tester_id}", file=sys.stderr)
                return 1
        print(f"{args.command}d {args.tester_id}")
        return 0

    if args.command == "report-all":
        written = write_all_beta_reports(
            args.db,
            args.reports_dir,
            limit_sessions=args.limit_sessions,
            include_disabled=args.include_disabled,
        )
        for path in written:
            print(f"Wrote beta report: {path}")
        print(f"Wrote {len(written)} beta report(s) under {args.reports_dir}")
        return 0

    if args.command == "report":
        markdown = render_beta_report(
            args.db,
            tester_id=args.tester_id,
            workspace_id=args.workspace_id,
            app_session_id=args.app_session_id,
            limit_sessions=args.limit_sessions,
        )
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(markdown, encoding="utf-8")
            print(f"Wrote beta report: {args.out}")
        else:
            print(markdown, end="")
        return 0

    settings = get_settings()
    service = BetaAuthService(
        db_path=_default_db_path(),
        data_root=Path(settings.beta_data_root),
        seed_wiki_root=_seed_wiki_root(),
        cookie_name=settings.beta_cookie_name,
        cookie_samesite=settings.beta_cookie_samesite,
        session_days=settings.beta_session_days,
        cookie_secure=settings.beta_cookie_secure,
    )
    identity = service.provision_tester(
        tester_id=args.tester_id,
        workspace_id=args.workspace_id,
        invite_code=args.invite_code,
        display_label=args.display_label,
        seed_label=args.seed_label,
        workspace_mode=args.workspace_mode,
    )
    print(f"Provisioned {identity.tester_id} -> {identity.workspace_id}")
    print(f"Wiki root: {identity.wiki_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
