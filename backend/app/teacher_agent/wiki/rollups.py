"""Wiki rollups operations (delegated from WikiStore)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional


from app.teacher_agent.wiki.constants import (
    STUDENT_ID_RE,
)

from app.teacher_agent.wiki import parsing


def _format_lesson_results(
    store, class_id: str, subject: str, diary_md: str, lesson_date: str, title: str
) -> str:
    slug = parsing.slugify(title)
    raw_link = f"../../../raw/classes/{class_id}/{lesson_date}-{slug}.md"
    header = (
        f"# Lesson Results — {lesson_date} — {title}\n\n"
        f"> Class: {class_id} | Subject: {subject}\n"
        f"> Raw: [{lesson_date}-{slug}]({raw_link})\n\n"
    )
    body = diary_md.strip()
    if body.startswith("#"):
        body = re.sub(r"^#\s+.+\n+", "", body, count=1)
    return header + body.strip() + "\n"


def _compile_rollups(
    store, class_id: str, diary_md: str, lesson_date: str, title: str
) -> list[tuple[str, str, str]]:
    covered = parsing.extract_section_body(diary_md, "What was covered")
    didnt = parsing.extract_section_body(diary_md, "What didn't go well")
    followups = parsing.extract_section_body(diary_md, "Homework & follow-ups")

    paths = store.roll_up_paths(class_id)
    results: list[tuple[str, str, str]] = []

    # course_state
    current = store.read_text(paths["course_state"])
    unit_line = (
        covered.split("\n")[0].strip().lstrip("- ")
        if covered.strip()
        else "See latest lesson"
    )
    new_state = store._upsert_course_state(
        current, lesson_date, title, unit_line, followups
    )
    results.append(
        ("course_state", new_state, "Update rolling course state from latest lesson.")
    )

    # misconceptions
    misc = store.read_text(paths["misconceptions"])
    new_misc = store._append_bullets(misc, parsing.lines_to_bullets(didnt), lesson_date)
    results.append(("misconceptions", new_misc, "Add problems from this lesson."))

    # students: built in _compile_students_and_timeline (with lesson previews)

    # open_loops
    loops = store.read_text(paths["open_loops"])
    new_loops = store._append_bullets(
        loops, parsing.lines_to_bullets(followups), lesson_date
    )
    results.append(("open_loops", new_loops, "Add follow-ups from this lesson."))

    return results


def _upsert_course_state(
    store, current: str, lesson_date: str, title: str, unit: str, followups: str
) -> str:
    next_focus = ""
    for line in followups.splitlines():
        if "next" in line.lower():
            next_focus = line.strip().lstrip("- ")
            break
    return (
        f"# Course State\n\n"
        f"## Current unit\n- {unit}\n\n"
        f"## Last lesson\n- {lesson_date}: {title}\n\n"
        f"## Next planned focus\n- {next_focus or 'See open loops'}\n\n"
        f"## Overall status\n- Updated {lesson_date}\n"
    )


def _student_display_name(text: str, fallback: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            name = line.lstrip("# ").strip()
            if name:
                return name
    return fallback


def _append_bullets(
    store, existing: str, new_bullets: list[str], lesson_date: str
) -> str:
    if not new_bullets:
        return existing or "# Notes\n\n"
    header = existing.strip() if existing.strip() else "# Notes\n"
    if not header.startswith("#"):
        header = f"# Notes\n\n{header}"
    lines = [header.rstrip(), "", f"## {lesson_date}"]
    for b in new_bullets:
        lines.append(f"- {b}")
    lines.append("")
    return "\n".join(lines)


def _parse_student_observations(store, students_block: str) -> dict[str, list[str]]:
    """Map S-### -> observation bullets from diary section."""
    by_student: dict[str, list[str]] = {}
    if not students_block.strip():
        return by_student
    current: Optional[str] = None
    for line in students_block.splitlines():
        line = line.strip()
        if not line:
            continue
        hm = re.match(r"^##\s+(S-\d{3})\s*$", line, re.I)
        if hm:
            current = hm.group(1).upper()
            by_student.setdefault(current, [])
            continue
        sm = re.match(r"^-\s*(S-\d{3})\s*:\s*(.+)$", line, re.I)
        if sm:
            sid = sm.group(1).upper()
            by_student.setdefault(sid, []).append(sm.group(2).strip())
            continue
        if current and line.startswith("-"):
            by_student[current].append(line.lstrip("- ").strip())
        else:
            for sid in STUDENT_ID_RE.findall(line):
                sid = sid.upper()
                by_student.setdefault(sid, []).append(line.lstrip("- ").strip())
    return by_student


def _upsert_student_entity(
    store, class_id: str, student_id: str, lesson_date: str, bullets: list[str]
) -> Path:
    path = store.student_path(class_id, student_id)
    existing = store.read_text(path)
    if not existing.strip():
        existing = f"# {student_id}\n\n> Class: {class_id}\n"
    section_pattern = rf"##\s*{re.escape(lesson_date)}\s*\n"
    if re.search(section_pattern, existing):
        existing = re.sub(
            rf"\n?##\s*{re.escape(lesson_date)}\s*\n.*?(?=\n##\s|\Z)",
            "",
            existing,
            flags=re.S,
        ).rstrip()
    lines = [existing.rstrip(), "", f"## {lesson_date}"]
    for b in bullets:
        lines.append(f"- {b}")
    lines.append("")
    store.write_text(path, "\n".join(lines))
    return path


def _rebuild_students_index(
    store, class_id: str, previews: Optional[dict[str, str]] = None
) -> str:
    lines = [
        "# Students",
        "",
        "> Class roster and student index. Details live in `students/S-###.md`.",
        "",
        "| ID | Name | Note | Page |",
        "|---|---|---|---|",
    ]
    previews = previews or {}
    sdir = store.students_dir(class_id)
    ids: set[str] = set(previews.keys())
    if sdir.exists():
        ids.update(p.stem.upper() for p in sdir.glob("S-*.md"))
    for sid in sorted(ids):
        text = previews.get(sid) or store.read_text(store.student_path(class_id, sid))
        if not text.strip():
            continue
        name = _student_display_name(text, sid)
        note = ""
        for ln in text.splitlines():
            if ln.strip().startswith("- "):
                note = ln.strip().lstrip("- ")[:120]
                break
        rel = f"students/{sid}.md"
        lines.append(f"| {sid} | {name} | {note} | [students/{sid}.md]({rel}) |")
    return "\n".join(lines).rstrip() + "\n"


def _compile_timeline_entry(
    store,
    class_id: str,
    lesson_date: str,
    title: str,
    diary_md: str,
) -> str:
    results_path = store.lesson_dir(class_id, lesson_date) / "lesson_results.md"
    lesson_results = store.read_text(results_path)
    if not lesson_results.strip():
        lesson_results = store._format_lesson_results(
            class_id,
            store.get_class(class_id).subject,
            diary_md,
            lesson_date,
            title,
        )
    summary, highlights, _, _ = parsing.build_timeline_summary(lesson_results)
    lesson_link = f"lessons/{lesson_date}/lesson_results.md"
    block = f"## {lesson_date} — {title}\n- [{title}]({lesson_link})\n- {summary}\n"
    if highlights:
        block += f"- Highlight: {highlights[0]}\n"
    return block


def _upsert_timeline_md(
    store, class_id: str, lesson_date: str, title: str, diary_md: str
) -> str:
    path = store.timeline_path(class_id)
    existing = store.read_text(path)
    if not existing.strip():
        existing = f"# Lesson Timeline\n\n> Class: {class_id}\n\n"
    new_block = store._compile_timeline_entry(class_id, lesson_date, title, diary_md)
    pattern = rf"\n?##\s*{re.escape(lesson_date)}\s*—.*?(?=\n##\s|\Z)"
    if re.search(pattern, existing, re.S):
        existing = re.sub(pattern, "", existing, flags=re.S).rstrip()
    parts = [existing.rstrip(), "", new_block.rstrip(), ""]
    body = "\n".join(parts)
    sections = re.split(r"(?=^##\s+\d{4}-\d{2}-\d{2}\s*—)", body, flags=re.M)
    header = sections[0] if sections else body
    dated = [s for s in sections[1:] if s.strip()]
    dated.sort(key=lambda s: s.split("—")[0].replace("##", "").strip(), reverse=True)
    return header.rstrip() + "\n\n" + "\n\n".join(dated).rstrip() + "\n"


def _compile_students_and_timeline(
    store,
    class_id: str,
    diary_md: str,
    lesson_date: str,
    title: str,
) -> list[tuple[Path, str, str]]:
    students_block = parsing.extract_section_body(diary_md, "Student observations")
    by_student = parsing.parse_student_observations(students_block)
    outputs: list[tuple[Path, str, str]] = []

    for sid, bullets in by_student.items():
        path = store.student_path(class_id, sid)
        proposed_path = path
        content = store.read_text(path)
        if bullets:
            preview = content
            if not preview.strip():
                preview = f"# {sid}\n\n> Class: {class_id}\n"
            section_pattern = rf"##\s*{re.escape(lesson_date)}\s*\n"
            if not re.search(section_pattern, preview):
                preview = (
                    preview.rstrip()
                    + "\n\n"
                    + f"## {lesson_date}\n"
                    + "\n".join(f"- {b}" for b in bullets)
                    + "\n"
                )
            outputs.append(
                (
                    proposed_path,
                    preview,
                    f"Update observations for {sid} from this lesson.",
                )
            )

    students_path = store.roll_up_paths(class_id)["students"]
    previews: dict[str, str] = {}
    for sid, bullets in by_student.items():
        path = store.student_path(class_id, sid)
        content = store.read_text(path)
        if bullets:
            if not content.strip():
                content = f"# {sid}\n\n> Class: {class_id}\n"
            if f"## {lesson_date}" not in content:
                content = (
                    content.rstrip()
                    + "\n\n"
                    + f"## {lesson_date}\n"
                    + "\n".join(f"- {b}" for b in bullets)
                    + "\n"
                )
            previews[sid] = content
    index_content = store._rebuild_students_index(class_id, previews=previews)
    outputs.append(
        (
            students_path,
            index_content,
            "Rebuild class student index linking to entity pages.",
        )
    )

    timeline_path = store.timeline_path(class_id)
    timeline_content = store._upsert_timeline_md(class_id, lesson_date, title, diary_md)
    outputs.append(
        (
            timeline_path,
            timeline_content,
            "Update chronological lesson timeline.",
        )
    )
    return outputs


def _finalize_lesson_writes(
    store,
    class_id: str,
    diary_md: str,
    lesson_date: str,
    title: str,
    applied: list[str],
) -> None:
    """Apply student entities, index, and timeline after lesson commit/revise."""
    students_block = parsing.extract_section_body(diary_md, "Student observations")
    by_student = parsing.parse_student_observations(students_block)
    for sid, bullets in by_student.items():
        path = store._upsert_student_entity(class_id, sid, lesson_date, bullets)
        rel = store.rel_wiki(path)
        if rel not in applied:
            applied.append(rel)

    students_path = store.roll_up_paths(class_id)["students"]
    store.write_text(students_path, store._rebuild_students_index(class_id))
    rel_students = store.rel_wiki(students_path)
    if rel_students not in applied:
        applied.append(rel_students)

    timeline_path = store.timeline_path(class_id)
    store.write_text(
        timeline_path,
        store._upsert_timeline_md(class_id, lesson_date, title, diary_md),
    )
    rel_tl = store.rel_wiki(timeline_path)
    if rel_tl not in applied:
        applied.append(rel_tl)
