"""Wiki read api operations (delegated from WikiStore)."""

from __future__ import annotations

import re
from datetime import datetime

from app.schemas.api import (
    ClassMemorySnapshot,
    ClassTimeline,
    LessonDetail,
    RollupExcerpt,
    TimelineEntry,
)

from app.teacher_agent.wiki.constants import (
    ROLLUP_LABELS,
)

from app.teacher_agent.wiki import parsing


def get_timeline(store, class_id: str) -> ClassTimeline:
    lessons_root = store.class_dir(class_id) / "lessons"
    log_by_date = store._parse_log_by_date()
    entries: list[TimelineEntry] = []
    if lessons_root.exists():
        for day_dir in sorted(lessons_root.iterdir()):
            if not day_dir.is_dir():
                continue
            results = day_dir / "lesson_results.md"
            plan = day_dir / "lesson_plan.md"
            lesson_date = day_dir.name
            log_meta = log_by_date.get(lesson_date, {})
            month_key = lesson_date[:7] if len(lesson_date) >= 7 else lesson_date
            if results.exists():
                text = results.read_text(encoding="utf-8")
                title = parsing.extract_title(text) or lesson_date
                covered = parsing.extract_section_bullets(text, "What was covered")
                homework = parsing.extract_homework(text)
                raw_path = parsing.extract_raw_link(text)
                summary, highlights, issues, follow_ups = (
                    parsing.build_timeline_summary(text)
                )
                entries.append(
                    TimelineEntry(
                        date=lesson_date,
                        title=title,
                        month_key=month_key,
                        summary=summary,
                        highlights=highlights,
                        issues=issues,
                        follow_ups=follow_ups,
                        covered=covered,
                        homework=homework,
                        raw_path=raw_path,
                        has_plan=plan.exists(),
                        status="taught",
                        committed_at=log_meta.get("committed_at"),
                        wiki_paths=log_meta.get("wiki_paths", []),
                    )
                )
            elif plan.exists():
                # Planned but not yet taught: show it so saving a plan is visible.
                plan_text = plan.read_text(encoding="utf-8")
                title = parsing.extract_title(plan_text) or lesson_date
                entries.append(
                    TimelineEntry(
                        date=lesson_date,
                        title=title,
                        month_key=month_key,
                        has_plan=True,
                        status="planned",
                        committed_at=log_meta.get("committed_at"),
                        wiki_paths=log_meta.get("wiki_paths", []),
                    )
                )
            else:
                continue
    entries.sort(key=lambda e: e.date, reverse=True)
    months = sorted({e.month_key for e in entries if e.month_key}, reverse=True)
    return ClassTimeline(class_id=class_id, entries=entries, months=months)


def get_snapshot(store, class_id: str) -> ClassMemorySnapshot:
    cls = store.get_class(class_id)
    timeline = store.get_timeline(class_id)
    course_state = store.read_text(store.roll_up_paths(class_id)["course_state"])
    open_loops = store.read_text(store.roll_up_paths(class_id)["open_loops"])
    misconceptions = store.read_text(store.roll_up_paths(class_id)["misconceptions"])

    current_unit = ""
    m = re.search(r"## Current unit\s*\n(.+?)(?:\n##|\Z)", course_state, re.S)
    if m:
        current_unit = m.group(1).strip().split("\n")[0].lstrip("- ")

    open_loop_count = len(re.findall(r"^-\s", open_loops, re.M))
    top_misconceptions = [
        line.lstrip("- ").strip()
        for line in misconceptions.splitlines()
        if line.strip().startswith("-")
    ][:5]
    recent = [f"{e.date} — {e.title}" for e in timeline.entries[:3]]
    last_committed = store._latest_log_commit(class_id)

    return ClassMemorySnapshot(
        class_id=class_id,
        label=cls.label,
        current_unit=current_unit or "Not set",
        last_lesson_date=timeline.entries[0].date if timeline.entries else None,
        last_committed_date=last_committed.get("lesson_date"),
        last_committed_at=last_committed.get("committed_at"),
        last_committed_title=last_committed.get("title") or None,
        open_loop_count=open_loop_count,
        top_misconceptions=top_misconceptions,
        recent_lessons=recent,
    )


def get_lesson_detail(store, class_id: str, lesson_date: str) -> LessonDetail:
    store.get_class(class_id)
    results_path = store.lesson_dir(class_id, lesson_date) / "lesson_results.md"
    plan_path = store.lesson_dir(class_id, lesson_date) / "lesson_plan.md"
    if not results_path.exists() and not plan_path.exists():
        raise KeyError(f"No lesson for date: {lesson_date}")

    plan_md = store.read_text(plan_path) if plan_path.exists() else None

    # Planned-only lesson (saved plan, not yet taught): no results/diary yet.
    if not results_path.exists():
        title = (parsing.extract_title(plan_md or "") if plan_md else "") or lesson_date
        return LessonDetail(
            class_id=class_id,
            date=lesson_date,
            title=title,
            primary_markdown="",
            diary_markdown="",
            raw_markdown="",
            lesson_plan_markdown=plan_md or None,
            rollup_excerpts=[],
        )

    primary = store.read_text(results_path)
    title = parsing.extract_title(primary) or lesson_date
    diary_md = parsing.diary_body_from_lesson_results(primary, lesson_date, title)
    raw_md = ""
    raw_link = parsing.extract_raw_link(primary)
    if raw_link:
        rel = (
            raw_link.replace("../../../", "")
            if raw_link.startswith("../../../")
            else raw_link
        )
        raw_path = store.root / rel
        if raw_path.exists():
            raw_md = store.read_text(raw_path)
    excerpts: list[RollupExcerpt] = []
    for key, path in store.roll_up_paths(class_id).items():
        excerpt = parsing.extract_date_section(store.read_text(path), lesson_date)
        if excerpt.strip():
            excerpts.append(
                RollupExcerpt(
                    wiki_path=store.rel_wiki(path),
                    label=ROLLUP_LABELS.get(key, key),
                    markdown=excerpt.strip(),
                )
            )
    return LessonDetail(
        class_id=class_id,
        date=lesson_date,
        title=title,
        primary_markdown=primary,
        diary_markdown=diary_md,
        raw_markdown=raw_md,
        lesson_plan_markdown=plan_md or None,
        rollup_excerpts=excerpts,
    )


def revise_lesson(
    store, class_id: str, lesson_date: str, diary_md: str
) -> tuple[TimelineEntry, list[str]]:
    cls = store.get_class(class_id)
    title = (
        parsing.extract_title(diary_md)
        or parsing.extract_title(
            store.read_text(
                store.lesson_dir(class_id, lesson_date) / "lesson_results.md"
            )
        )
        or "Lesson"
    )
    if (
        parsing.extract_date_from_diary(diary_md)
        and parsing.extract_date_from_diary(diary_md) != lesson_date
    ):
        diary_md = re.sub(
            r"Lesson Results\s*—\s*\d{4}-\d{2}-\d{2}",
            f"Lesson Results — {lesson_date}",
            diary_md,
            count=1,
        )
    lesson_results = store._format_lesson_results(
        class_id, cls.subject, diary_md, lesson_date, title
    )
    results_path = store.lesson_dir(class_id, lesson_date) / "lesson_results.md"
    store.write_text(results_path, lesson_results)

    slug = parsing.slugify(title)
    raw_path = store.root / "raw" / "classes" / class_id / f"{lesson_date}-{slug}.md"
    raw_body = (
        f"> Revised: {datetime.now().isoformat(timespec='seconds')}\n\n"
        f"{diary_md.strip()}\n"
    )
    store.write_text(raw_path, raw_body)

    applied: list[str] = []
    applied.append(store.rel_wiki(results_path))
    applied.append(store.rel_wiki(raw_path))

    covered = parsing.extract_section_body(diary_md, "What was covered")
    didnt = parsing.extract_section_body(diary_md, "What didn't go well")
    followups = parsing.extract_section_body(diary_md, "Homework & follow-ups")
    paths = store.roll_up_paths(class_id)

    unit_line = (
        covered.split("\n")[0].strip().lstrip("- ")
        if covered.strip()
        else "See latest lesson"
    )
    new_state = store._upsert_course_state(
        store.read_text(paths["course_state"]), lesson_date, title, unit_line, followups
    )
    store.write_text(paths["course_state"], new_state)
    applied.append(store.rel_wiki(paths["course_state"]))

    misc = parsing.remove_date_section(
        store.read_text(paths["misconceptions"]), lesson_date
    )
    store.write_text(
        paths["misconceptions"],
        store._append_bullets(misc, parsing.lines_to_bullets(didnt), lesson_date),
    )
    applied.append(store.rel_wiki(paths["misconceptions"]))

    loops = parsing.remove_date_section(
        store.read_text(paths["open_loops"]), lesson_date
    )
    store.write_text(
        paths["open_loops"],
        store._append_bullets(loops, parsing.lines_to_bullets(followups), lesson_date),
    )
    applied.append(store.rel_wiki(paths["open_loops"]))

    store._finalize_lesson_writes(class_id, diary_md, lesson_date, title, applied)
    store._append_log(class_id, lesson_date, title, applied, kind="revise")
    store.rebuild_index()
    timeline = store.get_timeline(class_id)
    entry = next((e for e in timeline.entries if e.date == lesson_date), None)
    if entry is None:
        raise KeyError(f"Lesson entry missing after revise: {lesson_date}")
    return entry, applied
