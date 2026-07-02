"""Small operator CLI for provisioning invite-code beta testers."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.config import get_settings
from app.services.beta import BetaAuthService


def _seed_wiki_root() -> Path:
    settings = get_settings()
    configured = Path(settings.wiki_root)
    if configured.exists():
        return configured
    local = Path(__file__).resolve().parents[2] / "teacher_wiki"
    if local.exists():
        return local
    return configured


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision a beta tester workspace.")
    parser.add_argument("--tester-id", required=True)
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--invite-code", required=True)
    parser.add_argument("--display-label", default="")
    parser.add_argument("--seed-label", default="")
    args = parser.parse_args()

    settings = get_settings()
    service = BetaAuthService(
        db_path=Path(settings.beta_data_root) / "beta.sqlite3",
        data_root=Path(settings.beta_data_root),
        seed_wiki_root=_seed_wiki_root(),
        cookie_name=settings.beta_cookie_name,
        session_days=settings.beta_session_days,
        cookie_secure=settings.beta_cookie_secure,
    )
    identity = service.provision_tester(
        tester_id=args.tester_id,
        workspace_id=args.workspace_id,
        invite_code=args.invite_code,
        display_label=args.display_label,
        seed_label=args.seed_label,
    )
    print(f"Provisioned {identity.tester_id} -> {identity.workspace_id}")
    print(f"Wiki root: {identity.wiki_root}")


if __name__ == "__main__":
    main()
