"""Wiki indexing operations (delegated from WikiStore)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Optional

from app.teacher_agent.wiki import parsing
from app.teacher_agent.wiki.constants import ROLLUP_LABELS


def _parse_log_by_date(store) -> dict[str, dict]:
    """Map lesson_date -> latest log metadata."""
    log_text = store.read_text(store.log_path)
    by_date: dict[str, dict] = {}
    headers = list(re.finditer(r"^##\s*\[", log_text, re.M))
    for i, hm in enumerate(headers):
        start = hm.start()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(log_text)
        block = log_text[start:end]
        header_line = block.split("\n", 1)[0]
        meta = parsing.parse_log_entry(header_line, block)
        if meta and meta["lesson_date"]:
            by_date[meta["lesson_date"]] = meta
    return by_date


def _latest_log_commit(store, class_id: Optional[str] = None) -> dict[str, str]:
    """Newest valid log entry, optionally limited to one class."""
    log_text = store.read_text(store.log_path)
    headers = list(re.finditer(r"^##\s*\[", log_text, re.M))
    for i in range(len(headers) - 1, -1, -1):
        start = headers[i].start()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(log_text)
        block = log_text[start:end]
        header_line = block.split("\n", 1)[0]
        meta = parsing.parse_log_entry(header_line, block)
        if (
            meta
            and meta.get("lesson_date")
            and (class_id is None or meta.get("class_id") == class_id)
        ):
            return {
                "lesson_date": meta["lesson_date"],
                "committed_at": meta["committed_at"],
                "title": meta["title"],
            }
    return {}


def _append_log(
    store,
    class_id: str,
    lesson_date: str,
    title: str,
    applied: list[str],
    kind: str = "ingest",
) -> str:
    log_path = store.log_path
    entry_id = str(uuid.uuid4())[:8]
    ts = datetime.now().isoformat(timespec="seconds")
    lines = [
        f"\n## [{ts}] {kind} | {lesson_date} — {title} (id:{entry_id})",
        f"> Class: {class_id}",
        f"> Lesson date: {lesson_date}",
    ]
    for path in applied:
        lines.append(f"- Updated: {path}")
    existing = store.read_text(log_path)
    if not existing.strip():
        existing = "# Wiki Log\n"
    store.write_text(log_path, existing.rstrip() + "\n" + "\n".join(lines) + "\n")
    return entry_id


def rebuild_index(store, class_id: Optional[str] = None) -> None:
    """Regenerate index.md for all classes (or verify one class exists)."""
    if class_id:
        store.get_class(class_id)
    classes = [store.get_class(c.id) for c in store.list_classes()]
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

    subject_root = store.root / "wiki" / "subjects"
    framework_links = []
    if subject_root.exists():
        for guide_path in sorted(subject_root.glob("*.md")):
            framework_index = (
                subject_root / guide_path.stem / "teaching_frameworks" / "index.md"
            )
            if framework_index.exists():
                label = (
                    parsing.extract_title(store.read_text(framework_index))
                    or f"{guide_path.stem.title()} teaching frameworks"
                )
                framework_links.append((label, framework_index))
    if framework_links:
        lines.extend(["## Shared subject frameworks", ""])
        for label, framework_index in framework_links:
            lines.append(f"- [{label}]({store.rel_wiki(framework_index)})")
        lines.append("")

    for cls in classes:
        cid = cls.id
        timeline = store.get_timeline(cid)
        lines.extend(
            [
                f"## Class: {cid} — {cls.label}",
                "",
                "### Roll-ups",
            ]
        )
        for key, path in store.roll_up_paths(cid).items():
            lines.append(f"- [{ROLLUP_LABELS.get(key, key)}]({store.rel_wiki(path)})")
        tl = store.timeline_path(cid)
        if tl.exists():
            lines.append(f"- [Lesson timeline]({store.rel_wiki(tl)})")
        memory_pages = []
        try:
            memory_pages = [
                path for path in store.memory_paths(cid).values() if path.exists()
            ]
        except KeyError:
            memory_pages = []
        if memory_pages:
            lines.extend(["", "### Compact memory"])
            for path in memory_pages:
                title = parsing.extract_title(store.read_text(path)) or path.stem
                lines.append(f"- [{title}]({store.rel_wiki(path)})")
        profile_path = store.class_dir(cid) / "curriculum_profile.md"
        sources_path = store.class_dir(cid) / "trusted_sources.md"
        if profile_path.exists() or sources_path.exists():
            lines.extend(["", "### Curriculum & trusted sources"])
            if profile_path.exists():
                lines.append(f"- [Curriculum profile]({store.rel_wiki(profile_path)})")
            if sources_path.exists():
                lines.append(
                    f"- [Trusted source index]({store.rel_wiki(sources_path)})"
                )
        overview_path = store.class_dir(cid) / "course_network" / "overview.md"
        if overview_path.exists():
            lines.extend(["", "### Course network"])
            lines.append(
                f"- [Course network overview]({store.rel_wiki(overview_path)})"
            )
        lines.extend(["", "### Lessons", ""])
        if timeline.entries:
            lines.append("| Date | Title | Summary | Plan | Path |")
            lines.append("|------|-------|---------|------|------|")
            for e in timeline.entries:
                results_path = store.lesson_dir(cid, e.date) / "lesson_results.md"
                summary = parsing.one_line(e.summary, 80)
                lines.append(
                    f"| {e.date} | {e.title} | {summary} | "
                    f"{'yes' if e.has_plan else 'no'} | {store.rel_wiki(results_path)} |"
                )
        else:
            lines.append("_No lessons yet._")
        lines.extend(["", "### Students", ""])
        sdir = store.students_dir(cid)
        if sdir.exists() and list(sdir.glob("S-*.md")):
            for p in sorted(sdir.glob("S-*.md")):
                sid = p.stem.upper()
                text = store.read_text(p)
                one = ""
                for ln in text.splitlines():
                    if ln.strip().startswith("- "):
                        one = parsing.one_line(ln.lstrip("- "), 60)
                        break
                lines.append(
                    f"- [{sid}]({store.rel_wiki(p)})" + (f" — {one}" if one else "")
                )
        else:
            lines.append("_No student entity pages yet._")
        lines.extend(["", "### Raw sources", ""])
        raw_root = store.root / "raw" / "classes" / cid
        if raw_root.exists():
            for p in sorted(raw_root.glob("*.md")):
                lines.append(f"- [{p.name}]({store.rel_wiki(p)})")
        else:
            lines.append("_No raw diaries yet._")
        lines.append("")

    content = "\n".join(lines)
    temporary = store.index_path.with_name(
        f".{store.index_path.name}.{uuid.uuid4().hex}.tmp"
    )
    try:
        store.write_text(temporary, content)
        temporary.replace(store.index_path)
    finally:
        temporary.unlink(missing_ok=True)


def _update_index(store, class_id: str) -> None:
    store.rebuild_index(class_id)
