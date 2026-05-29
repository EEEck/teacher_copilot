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

STUDENT_ID_RE = re.compile(r"\b(S-\d{3})\b", re.I)


def dedupe_wiki_proposals(proposals: list[WikiUpdateProposal]) -> list[WikiUpdateProposal]:
    """Keep first proposal per wiki_path (compile used to emit student_notes twice)."""
    seen: set[str] = set()
    unique: list[WikiUpdateProposal] = []
    for proposal in proposals:
        if proposal.wiki_path in seen:
            continue
        seen.add(proposal.wiki_path)
        unique.append(proposal)
    return unique
LOG_HEADER_RE = re.compile(
    r"##\s*\[([^\]]+)\]\s+(\w+)\s*\|\s*(?:([\d]{4}-[\d]{2}-[\d]{2})\s*[-—]\s*)?(.+?)\s*\(id:([a-f0-9]+)\)"
)
LOG_HEADER_LEGACY_RE = re.compile(
    r"##\s*\[(\d{4}-\d{2}-\d{2})\]\s+(\w+)\s*\|\s*(.+?)\s*\(id:([a-f0-9]+)\)"
)


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

    def students_dir(self, class_id: str) -> Path:
        return self.class_dir(class_id) / "students"

    def student_path(self, class_id: str, student_id: str) -> Path:
        sid = student_id.upper()
        return self.students_dir(class_id) / f"{sid}.md"

    def timeline_path(self, class_id: str) -> Path:
        return self.class_dir(class_id) / "timeline.md"

    def class_config_path(self, class_id: str) -> Path:
        return self.class_dir(class_id) / "class_config.md"

    @property
    def index_path(self) -> Path:
        return self.root / "index.md"

    @property
    def log_path(self) -> Path:
        return self.root / "log.md"

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

    def resolve_path(self, relative_path: str) -> Path:
        """Resolve a wiki-relative path; reject escapes outside root."""
        rel = relative_path.strip().lstrip("/").replace("\\", "/")
        if ".." in rel.split("/"):
            raise ValueError(f"Invalid path: {relative_path}")
        full = (self.root / rel).resolve()
        root_resolved = self.root.resolve()
        if not str(full).startswith(str(root_resolved)):
            raise ValueError(f"Path outside wiki root: {relative_path}")
        return full

    def read_wiki_page(self, relative_path: str, max_chars: int = 12000) -> str:
        path = self.resolve_path(relative_path)
        text = self.read_text(path)
        if len(text) > max_chars:
            return text[: max_chars - 20] + "\n\n… [truncated]"
        return text

    def read_wiki_index(self, class_id: Optional[str] = None) -> str:
        text = self.read_text(self.index_path)
        if not class_id:
            return text
        marker = f"## Class: {class_id}"
        alt = f"## Class —"
        if marker in text:
            start = text.index(marker)
            rest = text[start + len(marker) :]
            next_class = rest.find("\n## Class")
            section = text[start : start + len(marker) + (next_class if next_class >= 0 else len(rest))]
            if next_class >= 0:
                section = text[start : start + len(marker) + next_class]
            return section
        cls = self.get_class(class_id)
        if cls.label in text:
            start = text.find(f"## Class — {cls.label}")
            if start >= 0:
                rest = text[start + 10 :]
                next_class = rest.find("\n## Class")
                end = start + 10 + (next_class if next_class >= 0 else len(rest))
                return text[start:end]
        return text

    def list_class_pages(
        self, class_id: str, kind: Optional[str] = None
    ) -> list[dict[str, str]]:
        self.get_class(class_id)
        pages: list[dict[str, str]] = []
        base = self.class_dir(class_id)
        kinds = {kind} if kind else {"rollups", "lessons", "students", "timeline", "raw"}

        if "rollups" in kinds:
            for key, path in self.roll_up_paths(class_id).items():
                pages.append(
                    {"kind": "rollup", "id": key, "path": self.rel_wiki(path)}
                )
            for name in ("timeline.md", "class_config.md"):
                p = base / name
                if p.exists():
                    pages.append({"kind": "meta", "id": name, "path": self.rel_wiki(p)})

        if "lessons" in kinds:
            lessons_root = base / "lessons"
            if lessons_root.exists():
                for day_dir in sorted(lessons_root.iterdir()):
                    if not day_dir.is_dir():
                        continue
                    for fname in ("lesson_results.md", "lesson_plan.md"):
                        p = day_dir / fname
                        if p.exists():
                            pages.append(
                                {
                                    "kind": "lesson",
                                    "id": day_dir.name,
                                    "path": self.rel_wiki(p),
                                }
                            )

        if "students" in kinds:
            sdir = self.students_dir(class_id)
            if sdir.exists():
                for p in sorted(sdir.glob("S-*.md")):
                    pages.append(
                        {
                            "kind": "student",
                            "id": p.stem,
                            "path": self.rel_wiki(p),
                        }
                    )

        if "raw" in kinds:
            raw_root = self.root / "raw" / "classes" / class_id
            if raw_root.exists():
                for p in sorted(raw_root.glob("*.md")):
                    pages.append(
                        {"kind": "raw", "id": p.stem, "path": self.rel_wiki(p)}
                    )
        return pages

    def search_wiki(
        self, class_id: str, query: str, max_results: int = 15
    ) -> list[dict[str, str]]:
        self.get_class(class_id)
        q = query.lower().strip()
        if not q:
            return []
        hits: list[dict[str, str]] = []
        for page in self.list_class_pages(class_id):
            try:
                text = self.read_text(self.resolve_path(page["path"]))
            except ValueError:
                continue
            if q in text.lower():
                idx = text.lower().index(q)
                start = max(0, idx - 80)
                snippet = " ".join(text[start : idx + 80].split())
                hits.append(
                    {
                        "path": page["path"],
                        "snippet": snippet[:200],
                    }
                )
            if len(hits) >= max_results:
                break
        return hits

    # --- registry ---

    def list_classes(self) -> list[ClassSummary]:
        discovered: list[ClassSummary] = []
        classes_root = self.root / "wiki" / "classes"
        if classes_root.exists():
            for class_dir in sorted(classes_root.iterdir()):
                if not class_dir.is_dir():
                    continue
                class_id = class_dir.name
                label, subject = self._read_class_meta(class_id)
                discovered.append(
                    ClassSummary(id=class_id, label=label, subject=subject)
                )
        if discovered:
            return discovered
        return CLASS_REGISTRY

    def _read_class_meta(self, class_id: str) -> tuple[str, str]:
        config = self.read_text(self.class_config_path(class_id))
        label = class_id.replace("_", " ")
        subject = "general"
        m = re.search(r"^#\s+(.+)$", config, re.M)
        if m:
            label = m.group(1).strip()
        m = re.search(r"^subject:\s*(\S+)", config, re.M | re.I)
        if m:
            subject = m.group(1).strip().lower()
        for c in CLASS_REGISTRY:
            if c.id == class_id:
                return c.label, c.subject
        return label, subject

    def get_class(self, class_id: str) -> ClassSummary:
        for c in self.list_classes():
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
                lesson_date = day_dir.name
                log_meta = log_by_date.get(lesson_date, {})
                month_key = lesson_date[:7] if len(lesson_date) >= 7 else lesson_date
                if results.exists():
                    text = results.read_text(encoding="utf-8")
                    title = self._extract_title(text) or lesson_date
                    covered = self._extract_section_bullets(text, "What was covered")
                    homework = self._extract_homework(text)
                    raw_path = self._extract_raw_link(text)
                    summary, highlights, issues, follow_ups = self._build_timeline_summary(text)
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
                    title = self._extract_title(plan_text) or lesson_date
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
            last_committed_title=last_committed.get("title") or None,
            open_loop_count=open_loop_count,
            top_misconceptions=top_misconceptions,
            recent_lessons=recent,
        )

    def get_lesson_detail(self, class_id: str, lesson_date: str) -> LessonDetail:
        self.get_class(class_id)
        results_path = self.lesson_dir(class_id, lesson_date) / "lesson_results.md"
        plan_path = self.lesson_dir(class_id, lesson_date) / "lesson_plan.md"
        if not results_path.exists() and not plan_path.exists():
            raise KeyError(f"No lesson for date: {lesson_date}")

        plan_md = self.read_text(plan_path) if plan_path.exists() else None

        # Planned-only lesson (saved plan, not yet taught): no results/diary yet.
        if not results_path.exists():
            title = (self._extract_title(plan_md or "") if plan_md else "") or lesson_date
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

        loops = self._remove_date_section(self.read_text(paths["open_loops"]), lesson_date)
        self.write_text(
            paths["open_loops"],
            self._append_bullets(loops, self._lines_to_bullets(followups), lesson_date),
        )
        applied.append(self.rel_wiki(paths["open_loops"]))

        self._finalize_lesson_writes(class_id, diary_md, lesson_date, title, applied)
        self._append_log(class_id, lesson_date, title, applied, kind="revise")
        self.rebuild_index()
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

        for path, content, rationale in self._compile_students_and_timeline(
            class_id, diary_md, lesson_date, title
        ):
            proposals.append(
                WikiUpdateProposal(
                    wiki_path=self.rel_wiki(path),
                    current_content=self.read_text(path),
                    proposed_content=content,
                    rationale=rationale,
                )
            )

        return lesson_date, dedupe_wiki_proposals(proposals)

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

        raw_rel = self.rel_wiki(raw_path)
        if raw_rel not in applied:
            applied.insert(0, raw_rel)

        self._finalize_lesson_writes(class_id, diary_md, lesson_date, title, applied)
        log_id = self._append_log(class_id, lesson_date, title, applied, kind="ingest")
        self.rebuild_index()
        return raw_rel, applied, log_id

    def save_lesson_plan(self, class_id: str, lesson_date: str, content: str) -> str:
        path = self.lesson_dir(class_id, lesson_date) / "lesson_plan.md"
        self.lesson_dir(class_id, lesson_date).mkdir(parents=True, exist_ok=True)
        self.write_text(path, content)
        self.rebuild_index()
        return self.rel_wiki(path)

    def build_plan_context(self, class_id: str) -> str:
        """Memory pack for planning the *next* lesson — forward-looking rollups + last real lesson."""
        snapshot = self.get_snapshot(class_id)
        cls = self.get_class(class_id)
        timeline = self.get_timeline(class_id)
        parts = [
            f"# Session: Plan next lesson — {snapshot.label} ({class_id})",
            f"Subject: {cls.subject} | Current unit: {snapshot.current_unit}",
            f"Open loops (count): {snapshot.open_loop_count}",
            "",
            "Use this to propose activities, timing, and homework for the upcoming lesson.",
            "",
            "## Top misconceptions to address",
        ]
        if snapshot.top_misconceptions:
            parts.extend(f"- {m}" for m in snapshot.top_misconceptions)
        else:
            parts.append("- None listed")
        parts.append("")

        if snapshot.recent_lessons:
            parts.extend(["## Recent lessons (titles)", *[f"- {line}" for line in snapshot.recent_lessons], ""])

        if snapshot.last_committed_date:
            try:
                detail = self.get_lesson_detail(class_id, snapshot.last_committed_date)
                parts.extend(
                    [
                        f"## Last committed lesson ({snapshot.last_committed_date})",
                        detail.diary_markdown[:5000],
                        "",
                    ]
                )
                if detail.lesson_plan_markdown:
                    parts.extend(
                        [
                            f"## Existing plan on file ({snapshot.last_committed_date})",
                            detail.lesson_plan_markdown[:3000],
                            "",
                        ]
                    )
            except KeyError:
                pass

        for key in ("course_state", "open_loops", "misconceptions"):
            path = self.roll_up_paths(class_id)[key]
            label = ROLLUP_LABELS.get(key, key)
            parts.extend([f"## {label}", self.read_text(path)[:2500], ""])

        planned = [e for e in timeline.entries if e.has_plan][:3]
        if planned:
            parts.append("## Lessons that already have a saved plan")
            for e in planned:
                parts.append(f"- {e.date} — {e.title}")
            parts.append("")

        parts.extend(
            [
                "## Teacher profile (excerpt)",
                self.read_text(self.root / "wiki" / "teacher_profile.md")[:1200],
                "",
                f"## Subject guide: {cls.subject} (excerpt)",
                self.read_text(self.root / "wiki" / "subjects" / f"{cls.subject}.md")[:1200],
            ]
        )
        return "\n".join(parts)

    def build_ingest_context(self, class_id: str) -> str:
        """Memory pack for logging today's lesson — student IDs, prior lesson, light rollups."""
        snapshot = self.get_snapshot(class_id)
        cls = self.get_class(class_id)
        parts = [
            f"# Session: Update lesson notes — {snapshot.label} ({class_id})",
            f"Subject: {cls.subject} | Current unit: {snapshot.current_unit}",
            "",
            "Help the teacher record what happened today. Use only what they say; use context for IDs and continuity.",
            "",
            "## Student notes (use S-xxx pseudonyms from here)",
            self.read_text(self.roll_up_paths(class_id)["student_notes"])[:4500],
            "",
            "## Course state",
            self.read_text(self.roll_up_paths(class_id)["course_state"])[:2000],
            "",
        ]

        if snapshot.last_committed_date:
            try:
                detail = self.get_lesson_detail(class_id, snapshot.last_committed_date)
                parts.extend(
                    [
                        f"## Previous lesson ({snapshot.last_committed_date}) — continuity only",
                        detail.diary_markdown[:3500],
                        "",
                    ]
                )
            except KeyError:
                pass

        parts.extend(
            [
                "## Open loops (teacher may close or add while logging)",
                self.read_text(self.roll_up_paths(class_id)["open_loops"])[:1500],
                "",
                "## Misconceptions (brief — note new ones if the teacher reports them)",
            ]
        )
        if snapshot.top_misconceptions:
            parts.extend(f"- {m}" for m in snapshot.top_misconceptions[:5])
        else:
            parts.append("- None listed yet")
        parts.extend(
            [
                "",
                "## Wiki logging conventions (excerpt)",
                self.read_text(self.root / "AGENTS.md")[:1200],
            ]
        )
        return "\n".join(parts)

    def empty_plan_template(self, lesson_date: Optional[str] = None) -> str:
        d = lesson_date or date.today().isoformat()
        return (
            f"# Lesson Plan — Next lesson\n\n"
            f"> Duration: 45 min | Target date: {d}\n\n"
            "## Learning goals\n\n\n"
            "## Lesson flow\n\n"
            "- **Opening** (5 min):\n\n"
            "- **Main teaching** (25 min):\n\n"
            "- **Practice** (10 min):\n\n"
            "- **Close** (5 min):\n\n"
            "## Warmup\n\n\n"
            "## Practice tasks\n\n-\n\n"
            "## Homework\n\n\n"
            "## Teacher notes\n\n"
        )

    def is_plan_ready(self, plan_md: str) -> bool:
        required = ("## Learning goals", "## Lesson flow", "## Warmup")
        text = plan_md.lower()
        return all(h.lower() in text for h in required) and len(plan_md.strip()) > 200

    def load_index_context(
        self, class_id: str, max_chars: int = 4000, *, for_tool_loop: bool = False
    ) -> str:
        """Index-first context bundled into chat prompts."""
        cls = self.get_class(class_id)
        index_hint = (
            "read pages via tools as needed"
            if for_tool_loop
            else "see sections below for detail"
        )
        parts = [
            f"# Wiki index ({index_hint})",
            f"Class: {cls.label} ({class_id})",
            "",
            self.read_wiki_index(class_id)[:max_chars],
            "",
            "## Roll-up excerpts",
            self.read_text(self.roll_up_paths(class_id)["course_state"])[:1500],
            "",
            self.read_text(self.roll_up_paths(class_id)["open_loops"])[:1000],
        ]
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

        # student_notes: built in _compile_students_and_timeline (with lesson previews)

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

    def _parse_student_observations(self, students_block: str) -> dict[str, list[str]]:
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
        self, class_id: str, student_id: str, lesson_date: str, bullets: list[str]
    ) -> Path:
        path = self.student_path(class_id, student_id)
        existing = self.read_text(path)
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
        self.write_text(path, "\n".join(lines))
        return path

    def _rebuild_student_notes_index(
        self, class_id: str, previews: Optional[dict[str, str]] = None
    ) -> str:
        lines = [
            "# Student Notes",
            "",
            "> Index of student entity pages. Details live in `students/S-###.md`.",
            "",
        ]
        previews = previews or {}
        sdir = self.students_dir(class_id)
        ids: set[str] = set(previews.keys())
        if sdir.exists():
            ids.update(p.stem.upper() for p in sdir.glob("S-*.md"))
        for sid in sorted(ids):
            text = previews.get(sid) or self.read_text(self.student_path(class_id, sid))
            if not text.strip():
                continue
            p = self.student_path(class_id, sid)
            one_liner = ""
            for ln in text.splitlines():
                if ln.strip().startswith("- "):
                    one_liner = ln.strip().lstrip("- ")[:120]
                    break
            rel = f"students/{sid}.md"
            lines.append(f"## {sid}")
            if one_liner:
                lines.append(f"- {one_liner}")
            lines.append(f"- Page: [{sid}]({rel})")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def _compile_timeline_entry(
        self,
        class_id: str,
        lesson_date: str,
        title: str,
        diary_md: str,
    ) -> str:
        results_path = self.lesson_dir(class_id, lesson_date) / "lesson_results.md"
        lesson_results = self.read_text(results_path)
        if not lesson_results.strip():
            lesson_results = self._format_lesson_results(
                class_id,
                self.get_class(class_id).subject,
                diary_md,
                lesson_date,
                title,
            )
        summary, highlights, _, _ = self._build_timeline_summary(lesson_results)
        lesson_link = f"lessons/{lesson_date}/lesson_results.md"
        block = (
            f"## {lesson_date} — {title}\n"
            f"- [{title}]({lesson_link})\n"
            f"- {summary}\n"
        )
        if highlights:
            block += f"- Highlight: {highlights[0]}\n"
        return block

    def _upsert_timeline_md(
        self, class_id: str, lesson_date: str, title: str, diary_md: str
    ) -> str:
        path = self.timeline_path(class_id)
        existing = self.read_text(path)
        if not existing.strip():
            existing = f"# Lesson Timeline\n\n> Class: {class_id}\n\n"
        new_block = self._compile_timeline_entry(class_id, lesson_date, title, diary_md)
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
        self,
        class_id: str,
        diary_md: str,
        lesson_date: str,
        title: str,
    ) -> list[tuple[Path, str, str]]:
        students_block = self._extract_section_body(diary_md, "Student observations")
        by_student = self._parse_student_observations(students_block)
        outputs: list[tuple[Path, str, str]] = []

        for sid, bullets in by_student.items():
            path = self.student_path(class_id, sid)
            proposed_path = path
            content = self.read_text(path)
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

        notes_path = self.roll_up_paths(class_id)["student_notes"]
        previews: dict[str, str] = {}
        for sid, bullets in by_student.items():
            path = self.student_path(class_id, sid)
            content = self.read_text(path)
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
        index_content = self._rebuild_student_notes_index(class_id, previews=previews)
        outputs.append(
            (
                notes_path,
                index_content,
                "Rebuild student index linking to entity pages.",
            )
        )

        timeline_path = self.timeline_path(class_id)
        timeline_content = self._upsert_timeline_md(class_id, lesson_date, title, diary_md)
        outputs.append(
            (
                timeline_path,
                timeline_content,
                "Update chronological lesson timeline.",
            )
        )
        return outputs

    def _finalize_lesson_writes(
        self,
        class_id: str,
        diary_md: str,
        lesson_date: str,
        title: str,
        applied: list[str],
    ) -> None:
        """Apply student entities, index, and timeline after lesson commit/revise."""
        students_block = self._extract_section_body(diary_md, "Student observations")
        by_student = self._parse_student_observations(students_block)
        for sid, bullets in by_student.items():
            path = self._upsert_student_entity(class_id, sid, lesson_date, bullets)
            rel = self.rel_wiki(path)
            if rel not in applied:
                applied.append(rel)

        notes_path = self.roll_up_paths(class_id)["student_notes"]
        self.write_text(notes_path, self._rebuild_student_notes_index(class_id))
        rel_notes = self.rel_wiki(notes_path)
        if rel_notes not in applied:
            applied.append(rel_notes)

        timeline_path = self.timeline_path(class_id)
        self.write_text(
            timeline_path,
            self._upsert_timeline_md(class_id, lesson_date, title, diary_md),
        )
        rel_tl = self.rel_wiki(timeline_path)
        if rel_tl not in applied:
            applied.append(rel_tl)

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

    def _parse_log_entry(self, header: str, block: str) -> Optional[dict]:
        lesson_date = ""
        title = ""
        entry_id = ""
        m = LOG_HEADER_RE.match(header.strip())
        if m:
            _ts, _kind, lesson_date, title, entry_id = m.groups()
            lesson_date = (lesson_date or "").strip()
        else:
            m = LOG_HEADER_LEGACY_RE.match(header.strip())
            if not m:
                return None
            lesson_date, _kind, title, entry_id = m.groups()
        paths = re.findall(r"- Updated:\s*(.+)", block)
        meta_m = re.search(r"> Lesson date:\s*(\d{4}-\d{2}-\d{2})", block)
        if meta_m:
            lesson_date = meta_m.group(1)
        elif not lesson_date:
            bracket_m = re.search(r"\[(\d{4}-\d{2}-\d{2})\]", header)
            if bracket_m:
                lesson_date = bracket_m.group(1)
            else:
                return None
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", lesson_date):
            return None
        ts_m = re.match(r"##\s*\[([^\]]+)\]", header.strip())
        committed_at = ts_m.group(1) if ts_m else lesson_date
        return {
            "lesson_date": lesson_date,
            "title": title.strip(),
            "entry_id": entry_id,
            "wiki_paths": [p.strip() for p in paths],
            "committed_at": committed_at,
        }

    def _parse_log_by_date(self) -> dict[str, dict]:
        """Map lesson_date -> latest log metadata."""
        log_text = self.read_text(self.log_path)
        by_date: dict[str, dict] = {}
        headers = list(re.finditer(r"^##\s*\[", log_text, re.M))
        for i, hm in enumerate(headers):
            start = hm.start()
            end = headers[i + 1].start() if i + 1 < len(headers) else len(log_text)
            block = log_text[start:end]
            header_line = block.split("\n", 1)[0]
            meta = self._parse_log_entry(header_line, block)
            if meta and meta["lesson_date"]:
                by_date[meta["lesson_date"]] = meta
        return by_date

    def _latest_log_commit(self) -> dict[str, str]:
        """Newest log entry with a valid YYYY-MM-DD lesson date (skip malformed headers)."""
        log_text = self.read_text(self.log_path)
        headers = list(re.finditer(r"^##\s*\[", log_text, re.M))
        for i in range(len(headers) - 1, -1, -1):
            start = headers[i].start()
            end = headers[i + 1].start() if i + 1 < len(headers) else len(log_text)
            block = log_text[start:end]
            header_line = block.split("\n", 1)[0]
            meta = self._parse_log_entry(header_line, block)
            if meta and meta.get("lesson_date"):
                return {
                    "lesson_date": meta["lesson_date"],
                    "committed_at": meta["committed_at"],
                    "title": meta["title"],
                }
        return {}

    def _append_log(
        self,
        class_id: str,
        lesson_date: str,
        title: str,
        applied: list[str],
        kind: str = "ingest",
    ) -> str:
        log_path = self.log_path
        entry_id = str(uuid.uuid4())[:8]
        ts = datetime.now().isoformat(timespec="seconds")
        lines = [
            f"\n## [{ts}] {kind} | {lesson_date} — {title} (id:{entry_id})",
            f"> Class: {class_id}",
            f"> Lesson date: {lesson_date}",
        ]
        for path in applied:
            lines.append(f"- Updated: {path}")
        existing = self.read_text(log_path)
        if not existing.strip():
            existing = "# Wiki Log\n"
        self.write_text(log_path, existing.rstrip() + "\n" + "\n".join(lines) + "\n")
        return entry_id

    def rebuild_index(self, class_id: Optional[str] = None) -> None:
        """Regenerate index.md for all classes (or verify one class exists)."""
        if class_id:
            self.get_class(class_id)
        classes = [self.get_class(c.id) for c in self.list_classes()]
        lines = [
            "# KlassenPilot Wiki Index",
            "",
            "> Read this file first when querying the wiki.",
            "",
            "## Classes",
        ]
        for cls in classes:
            lines.append(f"- **{cls.label}** (`{cls.id}`) — subject: {cls.subject}")
        lines.append("")

        for cls in classes:
            cid = cls.id
            timeline = self.get_timeline(cid)
            lines.extend(
                [
                    f"## Class: {cid} — {cls.label}",
                    "",
                    "### Roll-ups",
                ]
            )
            for key, path in self.roll_up_paths(cid).items():
                lines.append(f"- [{ROLLUP_LABELS.get(key, key)}]({self.rel_wiki(path)})")
            tl = self.timeline_path(cid)
            if tl.exists():
                lines.append(f"- [Lesson timeline]({self.rel_wiki(tl)})")
            lines.extend(["", "### Lessons", ""])
            if timeline.entries:
                lines.append("| Date | Title | Summary | Plan | Path |")
                lines.append("|------|-------|---------|------|------|")
                for e in timeline.entries:
                    results_path = self.lesson_dir(cid, e.date) / "lesson_results.md"
                    summary = self._one_line(e.summary, 80)
                    lines.append(
                        f"| {e.date} | {e.title} | {summary} | "
                        f"{'yes' if e.has_plan else 'no'} | {self.rel_wiki(results_path)} |"
                    )
            else:
                lines.append("_No lessons yet._")
            lines.extend(["", "### Students", ""])
            sdir = self.students_dir(cid)
            if sdir.exists() and list(sdir.glob("S-*.md")):
                for p in sorted(sdir.glob("S-*.md")):
                    sid = p.stem.upper()
                    text = self.read_text(p)
                    one = ""
                    for ln in text.splitlines():
                        if ln.strip().startswith("- "):
                            one = self._one_line(ln.lstrip("- "), 60)
                            break
                    lines.append(
                        f"- [{sid}]({self.rel_wiki(p)})" + (f" — {one}" if one else "")
                    )
            else:
                lines.append("_No student entity pages yet._")
            lines.extend(["", "### Raw sources", ""])
            raw_root = self.root / "raw" / "classes" / cid
            if raw_root.exists():
                for p in sorted(raw_root.glob("*.md")):
                    lines.append(f"- [{p.name}]({self.rel_wiki(p)})")
            else:
                lines.append("_No raw diaries yet._")
            lines.append("")

        self.write_text(self.index_path, "\n".join(lines))

    def _update_index(self, class_id: str) -> None:
        self.rebuild_index(class_id)
