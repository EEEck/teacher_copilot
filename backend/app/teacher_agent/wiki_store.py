"""Wiki file I/O, lesson diary templates, and compile logic."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from app.schemas.api import (
    ApprovedWikiUpdate,
    ClassMemorySnapshot,
    ClassSummary,
    ClassTimeline,
    CompletenessChecklist,
    CompletenessItem,
    LessonDetail,
    RollupExcerpt,
    TimelineEntry,
    WikiUpdateProposal,
)

ROLLUP_LABELS = {
    "course_state": "Course state",
    "open_loops": "Open loops",
    "misconceptions": "Misconceptions",
    "student_notes": "Student notes",
}

CLASS_REGISTRY: list[ClassSummary] = [
    ClassSummary(id="chemie_9b_2026_27", label="Chemie 9b — 2026/27", subject="chemie"),
]

LESSON_RESULTS_SECTIONS: list[tuple[str, str, bool]] = [
    ("what_was_covered", "What was covered", True),
    ("student_participation", "Student participation", True),
    ("what_went_well", "What went well", True),
    ("what_didnt_go_well", "What didn't go well", True),
    ("student_observations", "Student observations", True),
    ("homework_and_followups", "Homework & follow-ups", True),
]

DIARY_SECTION_HEADINGS = [label for _, label, _ in LESSON_RESULTS_SECTIONS]


@dataclass
class WikiStore:
    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root)

    # --- paths ---

    def class_dir(self, class_id: str) -> Path:
        return self.root / "wiki" / "classes" / class_id

    def lesson_dir(self, class_id: str, lesson_date: str) -> Path:
        return self.class_dir(class_id) / "lessons" / lesson_date

    def roll_up_paths(self, class_id: str) -> dict[str, Path]:
        base = self.class_dir(class_id)
        return {
            "course_state": base / "course_state.md",
            "student_notes": base / "student_notes.md",
            "misconceptions": base / "misconceptions.md",
            "open_loops": base / "open_loops.md",
        }

    def rel_wiki(self, path: Path) -> str:
        try:
            return path.relative_to(self.root).as_posix()
        except ValueError:
            return path.as_posix()

    def read_text(self, path: Path) -> str:
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def write_text(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    # --- registry ---

    def list_classes(self) -> list[ClassSummary]:
        return CLASS_REGISTRY

    def get_class(self, class_id: str) -> ClassSummary:
        for c in CLASS_REGISTRY:
            if c.id == class_id:
                return c
        raise KeyError(f"Unknown class: {class_id}")

    # --- timeline ---

    def get_timeline(self, class_id: str) -> ClassTimeline:
        lessons_root = self.class_dir(class_id) / "lessons"
        log_by_date = self._parse_log_by_date()
        entries: list[TimelineEntry] = []
        if lessons_root.exists():
            for day_dir in sorted(lessons_root.iterdir()):
                if not day_dir.is_dir():
                    continue
                results = day_dir / "lesson_results.md"
                plan = day_dir / "lesson_plan.md"
                if not results.exists():
                    continue
                lesson_date = day_dir.name
                text = results.read_text(encoding="utf-8")
                title = self._extract_title(text) or lesson_date
                covered = self._extract_section_bullets(text, "What was covered")
                homework = self._extract_homework(text)
                raw_path = self._extract_raw_link(text)
                log_meta = log_by_date.get(lesson_date, {})
                summary, highlights, issues, follow_ups = self._build_timeline_summary(text)
                entries.append(
                    TimelineEntry(
                        date=lesson_date,
                        title=title,
                        month_key=lesson_date[:7] if len(lesson_date) >= 7 else lesson_date,
                        summary=summary,
                        highlights=highlights,
                        issues=issues,
                        follow_ups=follow_ups,
                        covered=covered,
                        homework=homework,
                        raw_path=raw_path,
                        has_plan=plan.exists(),
                        committed_at=log_meta.get("committed_at"),
                        wiki_paths=log_meta.get("wiki_paths", []),
                    )
                )
        entries.sort(key=lambda e: e.date, reverse=True)
        months = sorted({e.month_key for e in entries if e.month_key}, reverse=True)
        return ClassTimeline(class_id=class_id, entries=entries, months=months)

    def get_snapshot(self, class_id: str) -> ClassMemorySnapshot:
        cls = self.get_class(class_id)
        timeline = self.get_timeline(class_id)
        course_state = self.read_text(self.roll_up_paths(class_id)["course_state"])
        open_loops = self.read_text(self.roll_up_paths(class_id)["open_loops"])
        misconceptions = self.read_text(self.roll_up_paths(class_id)["misconceptions"])

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
        last_committed = self._latest_log_commit()

        return ClassMemorySnapshot(
            class_id=class_id,
            label=cls.label,
            current_unit=current_unit or "Not set",
            last_lesson_date=timeline.entries[0].date if timeline.entries else None,
            last_committed_date=last_committed.get("lesson_date"),
            last_committed_at=last_committed.get("committed_at"),
            open_loop_count=open_loop_count,
            top_misconceptions=top_misconceptions,
            recent_lessons=recent,
        )

    def get_lesson_detail(self, class_id: str, lesson_date: str) -> LessonDetail:
        self.get_class(class_id)
        results_path = self.lesson_dir(class_id, lesson_date) / "lesson_results.md"
        if not results_path.exists():
            raise KeyError(f"No lesson for date: {lesson_date}")
        primary = self.read_text(results_path)
        title = self._extract_title(primary) or lesson_date
        diary_md = self._diary_body_from_lesson_results(primary, lesson_date, title)
        raw_md = ""
        raw_link = self._extract_raw_link(primary)
        if raw_link:
            rel = raw_link.replace("../../../", "") if raw_link.startswith("../../../") else raw_link
            raw_path = self.root / rel
            if raw_path.exists():
                raw_md = self.read_text(raw_path)
        plan_path = self.lesson_dir(class_id, lesson_date) / "lesson_plan.md"
        plan_md = self.read_text(plan_path) if plan_path.exists() else None
        excerpts: list[RollupExcerpt] = []
        for key, path in self.roll_up_paths(class_id).items():
            excerpt = self._extract_date_section(self.read_text(path), lesson_date)
            if excerpt.strip():
                excerpts.append(
                    RollupExcerpt(
                        wiki_path=self.rel_wiki(path),
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

    def revise_lesson(self, class_id: str, lesson_date: str, diary_md: str) -> tuple[TimelineEntry, list[str]]:
        cls = self.get_class(class_id)
        title = self._extract_title(diary_md) or self._extract_title(
            self.read_text(self.lesson_dir(class_id, lesson_date) / "lesson_results.md")
        ) or "Lesson"
        if self._extract_date_from_diary(diary_md) and self._extract_date_from_diary(diary_md) != lesson_date:
            diary_md = re.sub(
                r"Lesson Results\s*—\s*\d{4}-\d{2}-\d{2}",
                f"Lesson Results — {lesson_date}",
                diary_md,
                count=1,
            )
        lesson_results = self._format_lesson_results(class_id, cls.subject, diary_md, lesson_date, title)
        results_path = self.lesson_dir(class_id, lesson_date) / "lesson_results.md"
        self.write_text(results_path, lesson_results)

        slug = self._slugify(title)
        raw_path = self.root / "raw" / "classes" / class_id / f"{lesson_date}-{slug}.md"
        raw_body = (
            f"> Revised: {datetime.now().isoformat(timespec='seconds')}\n\n"
            f"{diary_md.strip()}\n"
        )
        self.write_text(raw_path, raw_body)

        applied: list[str] = []
        applied.append(self.rel_wiki(results_path))
        applied.append(self.rel_wiki(raw_path))

        covered = self._extract_section_body(diary_md, "What was covered")
        didnt = self._extract_section_body(diary_md, "What didn't go well")
        students = self._extract_section_body(diary_md, "Student observations")
        followups = self._extract_section_body(diary_md, "Homework & follow-ups")
        paths = self.roll_up_paths(class_id)

        unit_line = covered.split("\n")[0].strip().lstrip("- ") if covered.strip() else "See latest lesson"
        new_state = self._upsert_course_state(
            self.read_text(paths["course_state"]), lesson_date, title, unit_line, followups
        )
        self.write_text(paths["course_state"], new_state)
        applied.append(self.rel_wiki(paths["course_state"]))

        misc = self._remove_date_section(self.read_text(paths["misconceptions"]), lesson_date)
        self.write_text(
            paths["misconceptions"],
            self._append_bullets(misc, self._lines_to_bullets(didnt), lesson_date),
        )
        applied.append(self.rel_wiki(paths["misconceptions"]))

        notes = self._remove_date_section(self.read_text(paths["student_notes"]), lesson_date)
        self.write_text(
            paths["student_notes"],
            self._merge_student_notes(notes, students, lesson_date),
        )
        applied.append(self.rel_wiki(paths["student_notes"]))

        loops = self._remove_date_section(self.read_text(paths["open_loops"]), lesson_date)
        self.write_text(
            paths["open_loops"],
            self._append_bullets(loops, self._lines_to_bullets(followups), lesson_date),
        )
        applied.append(self.rel_wiki(paths["open_loops"]))

        self._append_log(class_id, lesson_date, title, applied, kind="revise")
        self._update_index(class_id)
        timeline = self.get_timeline(class_id)
        entry = next((e for e in timeline.entries if e.date == lesson_date), None)
        if entry is None:
            raise KeyError(f"Lesson entry missing after revise: {lesson_date}")
        return entry, applied

    # --- diary completeness ---

    def checklist_from_diary(self, diary_md: str) -> CompletenessChecklist:
        items: list[CompletenessItem] = []
        for key, label, required in LESSON_RESULTS_SECTIONS:
            section = self._extract_section_body(diary_md, label)
            complete = bool(section.strip()) and section.strip().lower() not in {"none", "n/a", "tbd", "-"}
            items.append(
                CompletenessItem(field=key, label=label, complete=complete, required=required)
            )
        return CompletenessChecklist(items=items)

    def is_diary_complete(self, diary_md: str) -> bool:
        checklist = self.checklist_from_diary(diary_md)
        return all(i.complete for i in checklist.items if i.required)

    # --- compile diary → wiki proposals ---

    def compile_from_diary(
        self, class_id: str, diary_md: str, lesson_date: Optional[str] = None
    ) -> tuple[str, list[WikiUpdateProposal]]:
        """Return (lesson_date, wiki proposals)."""
        lesson_date = lesson_date or self._extract_date_from_diary(diary_md) or date.today().isoformat()
        title = self._extract_title(diary_md) or "Lesson"
        cls = self.get_class(class_id)

        lesson_results_path = self.lesson_dir(class_id, lesson_date) / "lesson_results.md"
        lesson_results_content = self._format_lesson_results(class_id, cls.subject, diary_md, lesson_date, title)

        proposals: list[WikiUpdateProposal] = [
            WikiUpdateProposal(
                wiki_path=self.rel_wiki(lesson_results_path),
                current_content=self.read_text(lesson_results_path),
                proposed_content=lesson_results_content,
                rationale="Primary lesson results for this date.",
            )
        ]

        rollups = self._compile_rollups(class_id, diary_md, lesson_date, title)
        for key, content, rationale in rollups:
            path = self.roll_up_paths(class_id)[key]
            proposals.append(
                WikiUpdateProposal(
                    wiki_path=self.rel_wiki(path),
                    current_content=self.read_text(path),
                    proposed_content=content,
                    rationale=rationale,
                )
            )

        return lesson_date, proposals

    def commit_ingest(
        self,
        class_id: str,
        diary_md: str,
        approved: list[ApprovedWikiUpdate],
        session_id: str,
    ) -> tuple[str, list[str], str]:
        lesson_date = self._extract_date_from_diary(diary_md) or date.today().isoformat()
        title = self._extract_title(diary_md) or "lesson"
        slug = self._slugify(title)

        raw_path = (
            self.root
            / "raw"
            / "classes"
            / class_id
            / f"{lesson_date}-{slug}.md"
        )
        raw_body = (
            f"> Session: {session_id}\n"
            f"> Committed: {datetime.now().isoformat(timespec='seconds')}\n\n"
            f"{diary_md.strip()}\n"
        )
        self.write_text(raw_path, raw_body)

        applied: list[str] = []
        for update in approved:
            if not update.approved:
                continue
            path = Path(update.wiki_path)
            if not path.is_absolute():
                path = self.root / update.wiki_path
            self.write_text(path, update.content)
            applied.append(update.wiki_path)

        log_id = self._append_log(class_id, lesson_date, title, applied)
        self._update_index(class_id)
        return self.rel_wiki(raw_path), applied, log_id

    def save_lesson_plan(self, class_id: str, lesson_date: str, content: str) -> str:
        path = self.lesson_dir(class_id, lesson_date) / "lesson_plan.md"
        self.write_text(path, content)
        self._update_index(class_id)
        return self.rel_wiki(path)

    def load_class_context(self, class_id: str) -> str:
        cls = self.get_class(class_id)
        parts = [
            f"# Class context: {cls.label}",
            "",
            "## AGENTS conventions",
            self.read_text(self.root / "AGENTS.md")[:3000],
            "",
            "## Teacher profile",
            self.read_text(self.root / "wiki" / "teacher_profile.md"),
            "",
            f"## Subject: {cls.subject}",
            self.read_text(self.root / "wiki" / "subjects" / f"{cls.subject}.md"),
            "",
            "## Course state",
            self.read_text(self.roll_up_paths(class_id)["course_state"]),
            "",
            "## Open loops",
            self.read_text(self.roll_up_paths(class_id)["open_loops"]),
            "",
            "## Misconceptions",
            self.read_text(self.roll_up_paths(class_id)["misconceptions"]),
            "",
            "## Student notes",
            self.read_text(self.roll_up_paths(class_id)["student_notes"]),
            "",
            "## Recent lessons",
        ]
        timeline = self.get_timeline(class_id)
        for entry in timeline.entries[:5]:
            results_path = self.lesson_dir(class_id, entry.date) / "lesson_results.md"
            parts.append(f"### {entry.date} — {entry.title}")
            parts.append(self.read_text(results_path)[:2000])
            parts.append("")
        return "\n".join(parts)

    def empty_diary_template(self, lesson_date: Optional[str] = None) -> str:
        d = lesson_date or date.today().isoformat()
        lines = [f"# Lesson Results — {d} — ", ""]
        for _, label, _ in LESSON_RESULTS_SECTIONS:
            lines.extend([f"## {label}", "", ""])
        return "\n".join(lines)

    # --- helpers ---

    def _format_lesson_results(
        self, class_id: str, subject: str, diary_md: str, lesson_date: str, title: str
    ) -> str:
        slug = self._slugify(title)
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
        self, class_id: str, diary_md: str, lesson_date: str, title: str
    ) -> list[tuple[str, str, str]]:
        covered = self._extract_section_body(diary_md, "What was covered")
        participation = self._extract_section_body(diary_md, "Student participation")
        went_well = self._extract_section_body(diary_md, "What went well")
        didnt = self._extract_section_body(diary_md, "What didn't go well")
        students = self._extract_section_body(diary_md, "Student observations")
        followups = self._extract_section_body(diary_md, "Homework & follow-ups")

        paths = self.roll_up_paths(class_id)
        results: list[tuple[str, str, str]] = []

        # course_state
        current = self.read_text(paths["course_state"])
        unit_line = covered.split("\n")[0].strip().lstrip("- ") if covered.strip() else "See latest lesson"
        new_state = self._upsert_course_state(current, lesson_date, title, unit_line, followups)
        results.append(("course_state", new_state, "Update rolling course state from latest lesson."))

        # misconceptions
        misc = self.read_text(paths["misconceptions"])
        new_misc = self._append_bullets(misc, self._lines_to_bullets(didnt), lesson_date)
        results.append(("misconceptions", new_misc, "Add problems from this lesson."))

        # student_notes
        notes = self.read_text(paths["student_notes"])
        new_notes = self._merge_student_notes(notes, students, lesson_date)
        results.append(("student_notes", new_notes, "Merge student observations."))

        # open_loops
        loops = self.read_text(paths["open_loops"])
        new_loops = self._append_bullets(loops, self._lines_to_bullets(followups), lesson_date)
        results.append(("open_loops", new_loops, "Add follow-ups from this lesson."))

        return results

    def _upsert_course_state(
        self, current: str, lesson_date: str, title: str, unit: str, followups: str
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

    def _append_bullets(self, existing: str, new_bullets: list[str], lesson_date: str) -> str:
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

    def _merge_student_notes(self, existing: str, students_block: str, lesson_date: str) -> str:
        header = "# Student Notes\n\n"
        body = existing if existing.strip() else header
        if students_block.strip():
            body = body.rstrip() + f"\n\n## {lesson_date}\n{students_block.strip()}\n"
        return body

    def _lines_to_bullets(self, text: str) -> list[str]:
        bullets = []
        for line in text.splitlines():
            line = line.strip().lstrip("- ").strip()
            if line and line.lower() not in {"none", "n/a"}:
                bullets.append(line)
        return bullets

    def _extract_title(self, text: str) -> Optional[str]:
        m = re.search(r"^#\s+Lesson Results\s*—\s*[\d-]+\s*—\s*(.+)$", text, re.M)
        if m:
            return m.group(1).strip()
        m = re.search(r"^#\s+(.+)$", text, re.M)
        return m.group(1).strip() if m else None

    def _extract_date_from_diary(self, text: str) -> Optional[str]:
        m = re.search(r"Lesson Results\s*—\s*(\d{4}-\d{2}-\d{2})", text)
        if m:
            return m.group(1)
        m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
        return m.group(1) if m else None

    def _extract_section_body(self, text: str, heading: str) -> str:
        pattern = rf"##\s*{re.escape(heading)}\s*\n(.*?)(?=\n##\s|\Z)"
        m = re.search(pattern, text, re.S | re.I)
        return m.group(1).strip() if m else ""

    def _extract_section_bullets(self, text: str, heading: str) -> list[str]:
        body = self._extract_section_body(text, heading)
        return [ln.lstrip("- ").strip() for ln in body.splitlines() if ln.strip().startswith("-")]

    def _extract_homework(self, text: str) -> Optional[str]:
        body = self._extract_section_body(text, "Homework & follow-ups")
        for line in body.splitlines():
            if "homework" in line.lower():
                return line.strip().lstrip("- ")
        return None

    def _extract_raw_link(self, text: str) -> Optional[str]:
        m = re.search(r"\> Raw: \[.+?\]\((.+?)\)", text)
        return m.group(1) if m else None

    def _slugify(self, title: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        return slug[:60] or "lesson"

    def _one_line(self, text: str, max_len: int = 120) -> str:
        line = " ".join(text.replace("\n", " ").split()).strip()
        if len(line) > max_len:
            return line[: max_len - 1] + "…"
        return line

    def _build_timeline_summary(
        self, lesson_results: str
    ) -> tuple[str, list[str], list[str], list[str]]:
        covered = self._extract_section_bullets(lesson_results, "What was covered")
        participation = self._one_line(self._extract_section_body(lesson_results, "Student participation"))
        went_well = self._one_line(self._extract_section_body(lesson_results, "What went well"))
        didnt = self._extract_section_bullets(lesson_results, "What didn't go well")
        students = self._one_line(self._extract_section_body(lesson_results, "Student observations"))
        followups = self._lines_to_bullets(
            self._extract_section_body(lesson_results, "Homework & follow-ups")
        )

        parts: list[str] = []
        if covered:
            parts.append(f"Covered: {self._one_line(covered[0], 80)}")
        if participation:
            parts.append(participation)
        if went_well:
            parts.append(f"Went well: {went_well}")
        if didnt:
            parts.append(f"Issues: {self._one_line(didnt[0], 80)}")
        summary = " · ".join(parts) if parts else "Lesson logged."
        if students and students.lower() not in {"none", "n/a", "(specifics needed)"}:
            summary += f" Students: {students[:80]}"

        highlights = []
        if covered:
            highlights.append(covered[0][:100])
        if went_well:
            highlights.append(went_well[:100])
        if participation:
            highlights.append(participation[:100])
        highlights = highlights[:3]

        return summary[:280], highlights, didnt[:2], followups[:2]

    def _diary_body_from_lesson_results(
        self, lesson_results: str, lesson_date: str, title: str
    ) -> str:
        body = lesson_results.strip()
        body = re.sub(r"^#\s+Lesson Results\s*—\s*[\d-]+\s*—\s*.+\n+", "", body, count=1)
        body = re.sub(r"^>\s+Class:.*\n", "", body, flags=re.M)
        body = re.sub(r"^>\s+Raw:.*\n+", "", body, flags=re.M)
        header = f"# Lesson Results — {lesson_date} — {title}\n\n"
        return header + body.strip() + "\n"

    def _extract_date_section(self, text: str, lesson_date: str) -> str:
        pattern = rf"##\s*{re.escape(lesson_date)}\s*\n(.*?)(?=\n##\s|\Z)"
        m = re.search(pattern, text, re.S)
        return m.group(1).strip() if m else ""

    def _remove_date_section(self, text: str, lesson_date: str) -> str:
        pattern = rf"\n?##\s*{re.escape(lesson_date)}\s*\n.*?(?=\n##\s|\Z)"
        cleaned = re.sub(pattern, "", text, flags=re.S).strip()
        if not cleaned:
            return "# Notes\n\n" if "misconception" not in text.lower() else "# Misconceptions\n\n"
        return cleaned + "\n"

    def _parse_log_by_date(self) -> dict[str, dict]:
        """Map lesson_date -> latest log metadata."""
        log_text = self.read_text(self.root / "log.md")
        by_date: dict[str, dict] = {}
        for m in re.finditer(
            r"##\s*\[(\d{4}-\d{2}-\d{2})\]\s+(\w+)\s*\|\s*(.+?)\s*\(id:([a-f0-9]+)\)",
            log_text,
        ):
            lesson_date, _kind, title, entry_id = m.groups()
            block_end = m.end()
            next_m = re.search(r"\n##\s*\[", log_text[block_end:])
            block = log_text[block_end : block_end + next_m.start()] if next_m else log_text[block_end:]
            paths = re.findall(r"- Updated:\s*(.+)", block)
            by_date[lesson_date] = {
                "title": title.strip(),
                "entry_id": entry_id,
                "wiki_paths": [p.strip() for p in paths],
                "committed_at": lesson_date,
            }
        return by_date

    def _latest_log_commit(self) -> dict[str, str]:
        log_text = self.read_text(self.root / "log.md")
        matches = list(
            re.finditer(
                r"##\s*\[(\d{4}-\d{2}-\d{2})\]\s+(\w+)\s*\|\s*(.+?)\s*\(id:",
                log_text,
            )
        )
        if not matches:
            return {}
        last = matches[-1]
        return {"lesson_date": last.group(1), "committed_at": last.group(1), "title": last.group(3).strip()}

    def _append_log(
        self,
        class_id: str,
        lesson_date: str,
        title: str,
        applied: list[str],
        kind: str = "ingest",
    ) -> str:
        log_path = self.root / "log.md"
        entry_id = str(uuid.uuid4())[:8]
        lines = [f"\n## [{lesson_date}] {kind} | {title} (id:{entry_id})"]
        for path in applied:
            lines.append(f"- Updated: {path}")
        existing = self.read_text(log_path)
        if not existing.strip():
            existing = "# Wiki Log\n"
        self.write_text(log_path, existing.rstrip() + "\n" + "\n".join(lines) + "\n")
        return entry_id

    def _update_index(self, class_id: str) -> None:
        cls = self.get_class(class_id)
        index_path = self.root / "index.md"
        timeline = self.get_timeline(class_id)
        lines = [
            "# KlassenPilot Wiki Index",
            "",
            f"## Class — {cls.label}",
            "",
            "| Date | Title | Has plan |",
            "|------|-------|----------|",
        ]
        for e in timeline.entries:
            lines.append(f"| {e.date} | {e.title} | {'yes' if e.has_plan else 'no'} |")
        lines.append("")
        self.write_text(index_path, "\n".join(lines))
