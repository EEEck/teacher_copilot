"""Wiki rollups operations (delegated from WikiStore)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional


from app.teacher_agent.wiki.constants import (
    STUDENT_ID_RE,
)

from app.teacher_agent.wiki import parsing

STUDENT_SUMMARY_HEADING = "Student Summary"
STUDENT_SUMMARY_FALLBACK = "No approved summary yet."


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


def _student_summary_note(text: str) -> str:
    body = parsing.extract_section_body(text, STUDENT_SUMMARY_HEADING)
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        note = stripped.lstrip("- ").strip()
        if note:
            return _first_sentence(note)
    return STUDENT_SUMMARY_FALLBACK


def _first_sentence(text: str) -> str:
    cleaned = " ".join((text or "").strip().split())
    if not cleaned:
        return STUDENT_SUMMARY_FALLBACK
    match = re.match(r"^(.+?[.!?])(?:\s+|$)", cleaned)
    return match.group(1).strip() if match else cleaned


def _student_header_and_body(text: str, class_id: str, student_id: str) -> tuple[str, str]:
    existing = text.strip()
    if not existing:
        existing = f"# {student_id}\n\n> Class: {class_id}"
    if not existing.startswith("#"):
        existing = f"# {student_id}\n\n> Class: {class_id}\n\n{existing}"
    match = re.search(r"^##\s+", existing, flags=re.M)
    if not match:
        return existing.rstrip(), ""
    return existing[: match.start()].rstrip(), existing[match.start() :].strip()


def _strip_student_summary_sections(body: str) -> str:
    return re.sub(
        rf"\n?##\s*{re.escape(STUDENT_SUMMARY_HEADING)}\s*\n.*?(?=\n##\s|\Z)",
        "",
        body,
        flags=re.I | re.S,
    ).strip()


def _split_student_sections(body: str) -> tuple[list[str], list[tuple[str, str]]]:
    other_sections: list[str] = []
    dated_sections: list[tuple[str, str]] = []
    for match in re.finditer(r"^##\s+(.+?)\s*\n(.*?)(?=^##\s+|\Z)", body, re.M | re.S):
        heading = match.group(1).strip()
        block = match.group(0).strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", heading):
            dated_sections.append((heading, block))
        else:
            other_sections.append(block)
    return other_sections, dated_sections


def _normalize_student_entity(
    store,
    class_id: str,
    student_id: str,
    text: str,
    *,
    summary: str | None = None,
) -> str:
    current_summary = summary or _student_summary_note(text)
    if not current_summary:
        current_summary = STUDENT_SUMMARY_FALLBACK
    header, body = _student_header_and_body(text, class_id, student_id)
    body = _strip_student_summary_sections(body)
    other_sections, dated_sections = _split_student_sections(body)
    dated_blocks = [
        block
        for _, block in sorted(
            dated_sections,
            key=lambda item: item[0],
        )
    ]
    sections = [
        header,
        f"## {STUDENT_SUMMARY_HEADING}\n- {current_summary}",
        *other_sections,
        *dated_blocks,
    ]
    return "\n\n".join(section.strip() for section in sections if section.strip()) + "\n"


def _set_student_summary(
    store, class_id: str, student_id: str, summary: str
) -> str:
    path = store.student_path(class_id, student_id)
    existing = store.read_text(path)
    return _normalize_student_entity(
        store,
        class_id,
        student_id,
        existing,
        summary=" ".join(summary.strip().split()) or STUDENT_SUMMARY_FALLBACK,
    )


def _student_sweep_excerpt(store, class_id: str, student_id: str) -> str:
    text = store.read_text(store.student_path(class_id, student_id))
    normalized = _normalize_student_entity(store, class_id, student_id, text)
    _, body = _student_header_and_body(normalized, class_id, student_id)
    return body[:1600]


def _append_bullets(
    store, existing: str, new_bullets: list[str], lesson_date: str
) -> str:
    if not new_bullets:
        return existing or "# Notes\n\n"
    header = existing.strip() if existing.strip() else "# Notes\n"
    if not header.startswith("#"):
        header = f"# Notes\n\n{header}"
    date_section_pattern = rf"\n?##\s*{re.escape(lesson_date)}\s*\n.*?(?=\n##\s|\Z)"
    header = re.sub(date_section_pattern, "", header, flags=re.S).rstrip()
    lines = [header.rstrip(), "", f"## {lesson_date}"]
    for b in new_bullets:
        lines.append(f"- {b}")
    lines.append("")
    return "\n".join(lines)


def _replace_date_section(text: str, lesson_date: str, bullets: list[str]) -> str:
    """Upsert a ``## {lesson_date}`` section: drop any existing one, re-add it.

    Keeps the wiki idempotent per lesson date — revising the same lesson
    replaces that date's bullets instead of ignoring the correction (the student
    page had an add-only-if-absent bug) or duplicating the section.
    """
    stripped = re.sub(
        rf"\n?##\s*{re.escape(lesson_date)}\s*\n.*?(?=\n##\s|\Z)",
        "",
        text,
        flags=re.S,
    ).rstrip()
    lines = [stripped, "", f"## {lesson_date}"]
    lines.extend(f"- {b}" for b in bullets)
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
    existing = _normalize_student_entity(store, class_id, student_id, existing)
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
    store.write_text(
        path,
        _normalize_student_entity(
            store, class_id, student_id, "\n".join(lines)
        ),
    )
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
        note = _student_summary_note(text)[:120]
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
            preview = _normalize_student_entity(store, class_id, sid, content)
            preview = _replace_date_section(preview, lesson_date, bullets)
            preview = _normalize_student_entity(store, class_id, sid, preview)
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
            content = _normalize_student_entity(store, class_id, sid, content)
            content = _replace_date_section(content, lesson_date, bullets)
            previews[sid] = _normalize_student_entity(store, class_id, sid, content)
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
    store.write_text(students_path, store._rebuild_students_index(class_id, previews={}))
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
