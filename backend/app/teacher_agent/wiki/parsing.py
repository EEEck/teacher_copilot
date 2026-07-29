"""Pure markdown parsing helpers for diary, lesson results, and log entries."""

from __future__ import annotations

import re
from typing import Optional

from app.teacher_agent.wiki.constants import (
    LOG_HEADER_LEGACY_RE,
    LOG_HEADER_RE,
    STUDENT_ID_RE,
)


def lines_to_bullets(text: str) -> list[str]:
    bullets = []
    for line in text.splitlines():
        line = line.strip().lstrip("- ").strip()
        if line and line.lower() not in {"none", "n/a"}:
            bullets.append(line)
    return bullets


def extract_title(text: str) -> Optional[str]:
    m = re.search(r"^#\s+Lesson Results\s*—\s*[\d-]+\s*—\s*(.+)$", text, re.M)
    if m:
        return m.group(1).strip()
    m = re.search(r"^#\s+(.+)$", text, re.M)
    return m.group(1).strip() if m else None


_TITLE_PREFIX_RE = re.compile(
    r"^(Lesson\s+(Plan|Results)|\d{4}-\d{2}-\d{2})\s*[—–-]\s*", re.I
)


def clean_results_title(title: str) -> str:
    """Normalize a lesson-results title for headings, slugs, and the timeline.

    Titles often arrive prefixed from their source artifact ("Lesson Plan —
    Redox…" when results are logged against a planned lesson) or degenerate to
    the "Lesson Results" placeholder. Returns "" when nothing meaningful is
    left so callers can apply their own fallback.
    """
    cleaned = " ".join((title or "").split())
    while True:
        stripped = _TITLE_PREFIX_RE.sub("", cleaned)
        if stripped == cleaned:
            break
        cleaned = stripped
    if cleaned.lower() in {"lesson results", "lesson plan", "lesson"}:
        return ""
    return cleaned


# Stop at `|` so replacing the date can never eat a following ` | …` segment.
_PLAN_TARGET_DATE_RE = re.compile(r"(Target date:\s*)([^|\n]*?)(\s*(?:\||\n|$))")
_PLAN_DURATION_LINE_RE = re.compile(r"^(>\s*Duration:[^\n]*?)\s*$", re.M)


def normalize_plan_target_date(markdown: str, lesson_date: str) -> str:
    """Stamp the saved lesson date into the plan markdown.

    Drafts intentionally carry no target date (the prompt's plan structure has
    none; the date is chosen at save time). At the save boundary this appends
    ``| Target date: {lesson_date}`` to the ``> Duration`` line — matching the
    format of historically saved plans — or, as defense, replaces a date the
    model/teacher wrote into the draft (in-flight drafts predating this rule,
    or the model mimicking old saved plans it read as context). Idempotent;
    no-op when ``lesson_date`` is empty.
    """
    if not lesson_date:
        return markdown
    if _PLAN_TARGET_DATE_RE.search(markdown):
        return _PLAN_TARGET_DATE_RE.sub(
            lambda m: f"{m.group(1)}{lesson_date}{m.group(3)}", markdown, count=1
        )
    duration = _PLAN_DURATION_LINE_RE.search(markdown)
    if duration:
        line = duration.group(1)
        return (
            markdown[: duration.start(1)]
            + f"{line} | Target date: {lesson_date}"
            + markdown[duration.end(1) :]
        )
    lines = markdown.splitlines()
    for i, line in enumerate(lines):
        if line.lstrip().startswith("# "):
            lines.insert(i + 1, f"\n> Target date: {lesson_date}")
            return "\n".join(lines)
    return f"> Target date: {lesson_date}\n\n{markdown}"


def extract_date_from_diary(text: str) -> Optional[str]:
    m = re.search(r"Lesson Results\s*—\s*(\d{4}-\d{2}-\d{2})", text)
    if m:
        return m.group(1)
    m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    return m.group(1) if m else None


def extract_section_body(text: str, heading: str) -> str:
    pattern = rf"##\s*{re.escape(heading)}\s*\n(.*?)(?=\n##\s|\Z)"
    m = re.search(pattern, text, re.S | re.I)
    return m.group(1).strip() if m else ""


def extract_section_bullets(text: str, heading: str) -> list[str]:
    body = extract_section_body(text, heading)
    return [
        ln.lstrip("- ").strip()
        for ln in body.splitlines()
        if ln.strip().startswith("-")
    ]


def extract_homework(text: str) -> Optional[str]:
    body = extract_section_body(text, "Homework & follow-ups")
    for line in body.splitlines():
        if "homework" in line.lower():
            return line.strip().lstrip("- ")
    return None


def extract_raw_link(text: str) -> Optional[str]:
    m = re.search(r"\> Raw: \[.+?\]\((.+?)\)", text)
    return m.group(1) if m else None


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:60] or "lesson"


def one_line(text: str, max_len: int = 120) -> str:
    line = " ".join(text.replace("\n", " ").split()).strip()
    if len(line) > max_len:
        return line[: max_len - 1] + "…"
    return line


def parse_student_observations(students_block: str) -> dict[str, list[str]]:
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


def _section_one_line(text: str, heading: str, max_len: int = 120) -> str:
    """One readable line for a diary section: joined bullets, no '-' markers."""
    body = extract_section_body(text, heading)
    bullets = lines_to_bullets(body)
    return one_line("; ".join(bullets) if bullets else body, max_len)


def build_timeline_summary(
    lesson_results: str,
) -> tuple[str, list[str], list[str], list[str]]:
    covered = extract_section_bullets(lesson_results, "What was covered")
    participation = _section_one_line(lesson_results, "Student participation")
    went_well = _section_one_line(lesson_results, "What went well")
    didnt = extract_section_bullets(lesson_results, "What didn't go well")
    students = _section_one_line(lesson_results, "Student observations")
    followups = lines_to_bullets(
        extract_section_body(lesson_results, "Homework & follow-ups")
    )

    parts: list[str] = []
    if covered:
        parts.append(f"Covered: {one_line(covered[0], 80)}")
    if participation:
        parts.append(participation)
    if went_well:
        parts.append(f"Went well: {went_well}")
    if didnt:
        parts.append(f"Issues: {one_line(didnt[0], 80)}")
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


def diary_body_from_lesson_results(
    lesson_results: str, lesson_date: str, title: str
) -> str:
    body = lesson_results.strip()
    body = re.sub(r"^#\s+Lesson Results\s*—\s*[\d-]+\s*—\s*.+\n+", "", body, count=1)
    body = re.sub(r"^>\s+Class:.*\n", "", body, flags=re.M)
    body = re.sub(r"^>\s+Raw:.*\n+", "", body, flags=re.M)
    header = f"# Lesson Results — {lesson_date} — {title}\n\n"
    return header + body.strip() + "\n"


def extract_date_section(text: str, lesson_date: str) -> str:
    pattern = rf"##\s*{re.escape(lesson_date)}\s*\n(.*?)(?=\n##\s|\Z)"
    m = re.search(pattern, text, re.S)
    return m.group(1).strip() if m else ""


def remove_date_section(text: str, lesson_date: str) -> str:
    pattern = rf"\n?##\s*{re.escape(lesson_date)}\s*\n.*?(?=\n##\s|\Z)"
    cleaned = re.sub(pattern, "", text, flags=re.S).strip()
    if not cleaned:
        return (
            "# Notes\n\n"
            if "misconception" not in text.lower()
            else "# Misconceptions\n\n"
        )
    return cleaned + "\n"


def parse_log_entry(header: str, block: str) -> Optional[dict]:
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
    wiki_paths = [p.strip() for p in paths]
    return {
        "lesson_date": lesson_date,
        "title": title.strip(),
        "entry_id": entry_id,
        "wiki_paths": wiki_paths,
        "committed_at": committed_at,
        "class_id": log_entry_class_id(block, wiki_paths),
    }


def log_entry_class_id(block: str, wiki_paths: list[str]) -> str:
    """Attribute one log entry to a class.

    `_append_log` writes an explicit `> Class:` line, but older entries (including
    the seeded `log.md` that every beta workspace already holds a copy of) predate
    it. Fall back to the class segment of the written paths so those entries stay
    attributable without rewriting existing logs.
    """
    m = re.search(r"^>\s*Class:\s*(\S+)", block, re.M)
    if m:
        return m.group(1).strip()
    for path in wiki_paths:
        m = re.search(r"(?:wiki|raw)/classes/([^/]+)/", path)
        if m:
            return m.group(1)
    return ""
