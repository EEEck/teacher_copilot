#!/usr/bin/env python3
"""One-off migration: student entity pages, timeline.md, rich index.md."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.teacher_agent.wiki_store import WikiStore  # noqa: E402

CLASS_ID = "chemie_9b_2026_27"
STUDENT_SECTION = re.compile(r"^##\s+(S-\d{3})\s*$", re.M | re.I)
DATE_SECTION = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*$", re.M)


def migrate_class(wiki: WikiStore, class_id: str) -> None:
    notes_path = wiki.roll_up_paths(class_id)["student_notes"]
    notes_text = wiki.read_text(notes_path)
    students_dir = wiki.students_dir(class_id)
    students_dir.mkdir(parents=True, exist_ok=True)

    for m in STUDENT_SECTION.finditer(notes_text):
        sid = m.group(1).upper()
        start = m.end()
        next_m = STUDENT_SECTION.search(notes_text, start)
        next_date = DATE_SECTION.search(notes_text, start)
        ends = [notes_text.find("\n", start)]
        if next_m:
            ends.append(next_m.start())
        if next_date:
            ends.append(next_date.start())
        end = min(e for e in ends if e >= 0)
        body = notes_text[start:end].strip()
        entity_path = wiki.student_path(class_id, sid)
        if not entity_path.exists():
            wiki.write_text(
                entity_path,
                f"# {sid}\n\n> Class: {class_id}\n\n{body}\n",
            )

    for m in DATE_SECTION.finditer(notes_text):
        block_start = m.end()
        next_date = DATE_SECTION.search(notes_text, block_start)
        block_end = next_date.start() if next_date else len(notes_text)
        block = notes_text[block_start:block_end].strip()
        lesson_date = m.group(1)
        for line in block.splitlines():
            sm = re.match(r"^-\s*(S-\d{3})\s*:\s*(.+)$", line.strip(), re.I)
            if not sm:
                continue
            sid = sm.group(1).upper()
            note = sm.group(2).strip()
            entity_path = wiki.student_path(class_id, sid)
            existing = wiki.read_text(entity_path)
            if not existing.strip():
                wiki.write_text(
                    entity_path,
                    f"# {sid}\n\n> Class: {class_id}\n\n",
                )
                existing = wiki.read_text(entity_path)
            if f"## {lesson_date}" not in existing:
                wiki.write_text(
                    entity_path,
                    existing.rstrip() + f"\n\n## {lesson_date}\n- {note}\n",
                )

    wiki.write_text(notes_path, wiki._rebuild_student_notes_index(class_id))

    timeline = wiki.get_timeline(class_id)
    lines = ["# Lesson Timeline", "", f"> Class: {class_id}", ""]
    for entry in reversed(timeline.entries):
        lesson_link = f"lessons/{entry.date}/lesson_results.md"
        lines.append(f"## {entry.date} — {entry.title}")
        lines.append(f"- [{entry.title}]({lesson_link})")
        if entry.covered:
            lines.append(f"- Covered: {entry.covered[0][:100]}")
        if entry.highlights:
            lines.append(f"- Highlight: {entry.highlights[0][:100]}")
        lines.append("")
    wiki.write_text(wiki.timeline_path(class_id), "\n".join(lines))

    wiki.rebuild_index()


def main() -> None:
    wiki_root = ROOT / "teacher_wiki"
    wiki = WikiStore(root=wiki_root)
    migrate_class(wiki, CLASS_ID)
    print(f"Migrated {CLASS_ID} under {wiki_root}")


if __name__ == "__main__":
    main()
