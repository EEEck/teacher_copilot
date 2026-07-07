"""Retire the wiki-derived compact memory twins (mem_v3 PR2).

``class_state.md`` and ``taught_so_far.md`` held facts that are deterministic
projections of the canonical rollups (``course_state.md`` / ``timeline.md``),
so they are retired as durable memory pages. This script removes any leftover
copies from a workspace tree.

Report-first and lean (beta, mock data): by default it only reports what it
would remove and prints each file's current content so nothing is lost
silently. Pass ``--apply`` to delete. Point ``--root`` at a workspace's
``teacher_wiki`` (or a parent dir; the tree is scanned recursively).

    python -m scripts.migrate_retire_compact_state --root beta_data/workspaces
    python -m scripts.migrate_retire_compact_state --root beta_data/workspaces --apply
"""

from __future__ import annotations

import argparse
from pathlib import Path

RETIRED_FILES = ("class_state.md", "taught_so_far.md")


def find_retired(root: Path) -> list[Path]:
    hits: list[Path] = []
    for name in RETIRED_FILES:
        hits.extend(p for p in root.rglob(name) if p.parent.name == "memory")
    return sorted(hits)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path, help="dir to scan")
    parser.add_argument("--apply", action="store_true", help="delete (default: report only)")
    args = parser.parse_args()

    root: Path = args.root
    if not root.exists():
        print(f"root does not exist: {root}")
        return 1

    hits = find_retired(root)
    if not hits:
        print(f"No retired compact-memory files under {root}.")
        return 0

    print(f"{'Deleting' if args.apply else 'Would delete'} {len(hits)} file(s):\n")
    for path in hits:
        content = path.read_text(encoding="utf-8").strip()
        print(f"--- {path} ---")
        print(content or "(empty)")
        print()
        if args.apply:
            path.unlink()

    if not args.apply:
        print("Re-run with --apply to delete. Current unit / taught sequence")
        print("live in the canonical course_state.md and timeline.md rollups.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
