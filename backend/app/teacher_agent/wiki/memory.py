"""Class-scoped compact memory and local copilot profile helpers."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

COMPACT_MEMORY_FILES: dict[str, str] = {
    "taught_so_far": "taught_so_far.md",
    "planning_brief": "planning_brief.md",
    "teaching_patterns": "teaching_patterns.md",
    "copilot_profile": "copilot_profile.md",
    "class_state": "class_state.md",
    "session_summaries": "session_summaries.md",
}

PROFILE_SECTION_LIMIT = 12
PROFILE_ENTRY_LIMIT = 280

# Global, cross-class teacher profile ("user.md"). Single file per teacher.
USER_PROFILE_REL = "wiki/teacher_profile.md"
USER_PROFILE_SECTION_LIMIT = 8
USER_PROFILE_ENTRY_LIMIT = 240
SUBJECT_GUIDE_SECTION_LIMIT = 8

# Hermes-style hard size budgets (chars). Enforced at write time (clamp on
# every compaction/profile write) AND at inject time (slim context slice), so
# durable memory never grows unbounded or pollutes the prompt.
MEMORY_PAGE_BUDGETS: dict[str, int] = {
    "user": 1500,
    "copilot_profile": 1500,
    "teaching_patterns": 2200,
    "class_state": 1800,
    "taught_so_far": 1500,
    "planning_brief": 1200,
    "session_summaries": 1200,
    "subject_guide": 1400,
}
_DEFAULT_PAGE_BUDGET = 1800


def memory_budget(key: str) -> int:
    return MEMORY_PAGE_BUDGETS.get(key, _DEFAULT_PAGE_BUDGET)


def clamp_memory_page(key: str, text: str) -> str:
    """Trim a memory page to its budget on a line boundary, marking truncation.

    Keeps pages small so they stay high-signal and never flood the context.
    """
    budget = memory_budget(key)
    text = (text or "").rstrip()
    if len(text) <= budget:
        return text + ("\n" if text else "")
    marker = "\n\n_… trimmed to size budget._\n"
    keep = max(0, budget - len(marker))
    clipped = text[:keep]
    nl = clipped.rfind("\n")
    if nl > keep * 0.5:
        clipped = clipped[:nl]
    return clipped.rstrip() + marker


def memory_dir(store, class_id: str):
    store.get_class(class_id)
    return store.class_dir(class_id) / "memory"


def memory_paths(store, class_id: str) -> dict[str, Any]:
    base = memory_dir(store, class_id)
    return {key: base / filename for key, filename in COMPACT_MEMORY_FILES.items()}


def compact_memory_excerpts(store, class_id: str, max_chars: int = 1600) -> list[tuple[str, str]]:
    excerpts: list[tuple[str, str]] = []
    for key, path in memory_paths(store, class_id).items():
        text = store.read_text(path).strip()
        if text:
            excerpts.append((store.rel_wiki(path), text[:max_chars]))
    return excerpts


def read_copilot_profile(store, class_id: str) -> str:
    return store.read_text(memory_paths(store, class_id)["copilot_profile"])


def user_profile_path(store):
    return store.root / "wiki" / "teacher_profile.md"


def read_user_profile(store) -> str:
    """Global, cross-class teacher profile ("user.md")."""
    return store.read_text(user_profile_path(store))


def _normalize_profile_section(section: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9 &/_-]+", "", section).strip()
    return cleaned[:80] or "General"


def _ensure_profile_header(text: str, class_id: str) -> str:
    if text.strip():
        return text.rstrip() + "\n"
    return (
        f"# Class Copilot Profile\n\n"
        f"> Class: {class_id}\n"
        "> Bounded local profile for stable teacher/class preferences and reusable planning patterns.\n\n"
    )


def add_profile_conclusion(
    store,
    class_id: str,
    section: str,
    content: str,
    *,
    source_path: str | None = None,
) -> str:
    """Deterministically add/replace one small profile conclusion.

    This mirrors Hermes' bounded memory-tool discipline: the model/user may
    propose a fact, but persistence is a fixed append/replace operation with
    size and scope checks.
    """
    clean = " ".join(content.strip().split())
    if not clean:
        raise ValueError("profile conclusion cannot be empty")
    if len(clean) > PROFILE_ENTRY_LIMIT:
        raise ValueError(f"profile conclusion must be <= {PROFILE_ENTRY_LIMIT} chars")
    if source_path and not store.is_class_memory_path(class_id, source_path):
        raise ValueError(f"source_path must be under wiki/classes/{class_id}/")

    sec = _normalize_profile_section(section)
    path = memory_paths(store, class_id)["copilot_profile"]
    text = _ensure_profile_header(store.read_text(path), class_id)
    heading = f"## {sec}"
    entry = f"- {clean}" + (f" (source: `{source_path}`)" if source_path else "")

    if entry in text:
        return store.rel_wiki(path)

    if heading not in text:
        text = text.rstrip() + f"\n\n{heading}\n{entry}\n"
    else:
        pattern = rf"(^##\s+{re.escape(sec)}\s*\n)(.*?)(?=^##\s+|\Z)"
        match = re.search(pattern, text, flags=re.M | re.S)
        if not match:
            text = text.rstrip() + f"\n\n{heading}\n{entry}\n"
        else:
            existing_lines = [
                ln for ln in match.group(2).splitlines() if ln.strip().startswith("-")
            ]
            existing_lines = [ln for ln in existing_lines if clean not in ln]
            existing_lines.append(entry)
            if len(existing_lines) > PROFILE_SECTION_LIMIT:
                existing_lines = existing_lines[-PROFILE_SECTION_LIMIT:]
            replacement = match.group(1) + "\n".join(existing_lines).rstrip() + "\n\n"
            text = text[: match.start()] + replacement + text[match.end() :]

    store.write_text(path, clamp_memory_page("copilot_profile", text))
    return store.rel_wiki(path)


def _ensure_user_profile_header(text: str) -> str:
    if text.strip():
        return text.rstrip() + "\n"
    return (
        "# Teacher Profile\n\n"
        "> Global, cross-class teacher profile (communication style, stable "
        "preferences, default lesson structure). Bounded local memory.\n\n"
    )


def add_user_profile_conclusion(
    store,
    section: str,
    content: str,
) -> str:
    """Add/replace one small conclusion in the global teacher profile (user.md).

    Bounded mirror of ``add_profile_conclusion`` for the cross-class profile.
    """
    clean = " ".join(content.strip().split())
    if not clean:
        raise ValueError("user profile conclusion cannot be empty")
    if len(clean) > USER_PROFILE_ENTRY_LIMIT:
        raise ValueError(
            f"user profile conclusion must be <= {USER_PROFILE_ENTRY_LIMIT} chars"
        )

    sec = _normalize_profile_section(section)
    path = user_profile_path(store)
    text = _ensure_user_profile_header(store.read_text(path))
    heading = f"## {sec}"
    entry = f"- {clean}"

    if entry in text:
        return store.rel_wiki(path)

    if heading not in text:
        text = text.rstrip() + f"\n\n{heading}\n{entry}\n"
    else:
        pattern = rf"(^##\s+{re.escape(sec)}\s*\n)(.*?)(?=^##\s+|\Z)"
        match = re.search(pattern, text, flags=re.M | re.S)
        if not match:
            text = text.rstrip() + f"\n\n{heading}\n{entry}\n"
        else:
            existing_lines = [
                ln for ln in match.group(2).splitlines() if ln.strip().startswith("-")
            ]
            existing_lines = [ln for ln in existing_lines if clean not in ln]
            existing_lines.append(entry)
            if len(existing_lines) > USER_PROFILE_SECTION_LIMIT:
                existing_lines = existing_lines[-USER_PROFILE_SECTION_LIMIT:]
            replacement = match.group(1) + "\n".join(existing_lines).rstrip() + "\n\n"
            text = text[: match.start()] + replacement + text[match.end() :]

    store.write_text(path, clamp_memory_page("user", text))
    return store.rel_wiki(path)


def add_subject_guide_conclusion(
    store,
    class_id: str,
    section: str,
    content: str,
) -> str:
    """Add one teacher-approved subject-wide conclusion for this class subject."""
    cls = store.get_class(class_id)
    subject = re.sub(r"[^a-z0-9_-]+", "", cls.subject.lower())
    if not subject:
        raise ValueError("class subject is missing")
    clean = " ".join(content.strip().split())
    if not clean:
        raise ValueError("subject guide conclusion cannot be empty")
    if len(clean) > PROFILE_ENTRY_LIMIT:
        raise ValueError(
            f"subject guide conclusion must be <= {PROFILE_ENTRY_LIMIT} chars"
        )

    path = store.root / "wiki" / "subjects" / f"{subject}.md"
    text = store.read_text(path)
    if not text.strip():
        text = f"# {subject.title()} Subject Notes\n"
    else:
        text = text.rstrip() + "\n"

    sec = _normalize_profile_section(section)
    heading = f"## {sec}"
    entry = f"- {clean}"
    if entry in text:
        return store.rel_wiki(path)

    if heading not in text:
        text = text.rstrip() + f"\n\n{heading}\n{entry}\n"
    else:
        pattern = rf"(^##\s+{re.escape(sec)}\s*\n)(.*?)(?=^##\s+|\Z)"
        match = re.search(pattern, text, flags=re.M | re.S)
        if not match:
            text = text.rstrip() + f"\n\n{heading}\n{entry}\n"
        else:
            existing_lines = [
                ln for ln in match.group(2).splitlines() if ln.strip().startswith("-")
            ]
            existing_lines = [ln for ln in existing_lines if clean not in ln]
            existing_lines.append(entry)
            if len(existing_lines) > SUBJECT_GUIDE_SECTION_LIMIT:
                existing_lines = existing_lines[-SUBJECT_GUIDE_SECTION_LIMIT:]
            replacement = match.group(1) + "\n".join(existing_lines).rstrip() + "\n\n"
            text = text[: match.start()] + replacement + text[match.end() :]

    store.write_text(path, clamp_memory_page("subject_guide", text))
    return store.rel_wiki(path)


def add_compact_memory_conclusion(
    store,
    class_id: str,
    key: str,
    section: str,
    content: str,
    *,
    source_path: str | None = None,
) -> str:
    """Add one teacher-approved conclusion to a compact class memory page."""
    if key not in {
        "class_state",
        "planning_brief",
        "taught_so_far",
        "teaching_patterns",
    }:
        raise ValueError(f"unsupported compact memory target: {key}")
    clean = " ".join(content.strip().split())
    if not clean:
        raise ValueError("compact memory conclusion cannot be empty")
    if len(clean) > PROFILE_ENTRY_LIMIT:
        raise ValueError(
            f"compact memory conclusion must be <= {PROFILE_ENTRY_LIMIT} chars"
        )
    if source_path and not store.is_class_memory_path(class_id, source_path):
        raise ValueError(f"source_path must be under wiki/classes/{class_id}/")

    titles = {
        "class_state": "Class State",
        "planning_brief": "Planning Brief",
        "taught_so_far": "Taught So Far",
        "teaching_patterns": "Teaching Patterns",
    }
    path = memory_paths(store, class_id)[key]
    text = store.read_text(path)
    if not text.strip():
        text = _page_with_fallback(titles[key], "", class_id)
    else:
        text = text.rstrip() + "\n"

    sec = _normalize_profile_section(section)
    heading = f"## {sec}"
    entry = f"- {clean}" + (f" (source: `{source_path}`)" if source_path else "")
    if entry in text:
        return store.rel_wiki(path)

    if heading not in text:
        text = text.rstrip() + f"\n\n{heading}\n{entry}\n"
    else:
        pattern = rf"(^##\s+{re.escape(sec)}\s*\n)(.*?)(?=^##\s+|\Z)"
        match = re.search(pattern, text, flags=re.M | re.S)
        if not match:
            text = text.rstrip() + f"\n\n{heading}\n{entry}\n"
        else:
            existing_lines = [
                ln for ln in match.group(2).splitlines() if ln.strip().startswith("-")
            ]
            existing_lines = [ln for ln in existing_lines if clean not in ln]
            existing_lines.append(entry)
            if len(existing_lines) > PROFILE_SECTION_LIMIT:
                existing_lines = existing_lines[-PROFILE_SECTION_LIMIT:]
            replacement = match.group(1) + "\n".join(existing_lines).rstrip() + "\n\n"
            text = text[: match.start()] + replacement + text[match.end() :]

    store.write_text(path, clamp_memory_page(key, text))
    return store.rel_wiki(path)


def search_personal_memory(
    store, class_id: str, query: str, max_results: int = 5
) -> list[dict[str, str]]:
    q = query.strip().lower()
    if not q:
        return []
    limit = max(1, min(max_results or 5, 20))
    hits: list[dict[str, str]] = []
    paths = memory_paths(store, class_id)
    ordered_keys = [
        "copilot_profile",
        "teaching_patterns",
        "planning_brief",
        "taught_so_far",
        "session_summaries",
    ]
    for key in ordered_keys:
        path = paths[key]
        text = store.read_text(path)
        low = text.lower()
        if q not in low:
            continue
        idx = low.index(q)
        start = max(0, idx - 120)
        snippet = " ".join(text[start : idx + 160].split())
        hits.append(
            {
                "kind": key,
                "path": store.rel_wiki(path),
                "snippet": snippet[:260],
            }
        )
        if len(hits) >= limit:
            break
    return hits


def build_memory_compaction_source_packet(
    store,
    class_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    cls = store.get_class(class_id)
    timeline = store.get_timeline(class_id)
    source_paths: list[str] = []
    warnings: list[str] = []

    if start_date and end_date and start_date > end_date:
        warnings.append("start_date is after end_date; no lesson range filter applied.")
        start_date = None
        end_date = None

    def in_range(lesson_date: str) -> bool:
        if start_date and lesson_date < start_date.isoformat():
            return False
        if end_date and lesson_date > end_date.isoformat():
            return False
        return True

    lesson_entries = [
        e for e in sorted(timeline.entries, key=lambda entry: entry.date)
        if e.status == "taught" and in_range(e.date)
    ]
    if not lesson_entries:
        warnings.append("No taught lessons found for compaction range.")

    parts = [
        "# Memory Compaction Source Packet",
        f"Class: {cls.label} ({class_id})",
        f"Subject: {cls.subject}",
        "",
        "## Current rollups",
    ]
    for key, path in store.roll_up_paths(class_id).items():
        rel = store.rel_wiki(path)
        source_paths.append(rel)
        parts.extend([f"### {rel}", store.read_text(path)[:3000], ""])

    subject_path = store.root / "wiki" / "subjects" / f"{cls.subject}.md"
    if subject_path.exists():
        rel = store.rel_wiki(subject_path)
        source_paths.append(rel)
        parts.extend([f"## Subject guide ({rel})", store.read_text(subject_path)[:2000], ""])

    existing = compact_memory_excerpts(store, class_id, max_chars=2200)
    if existing:
        parts.append("## Existing compact memory")
        for rel, text in existing:
            source_paths.append(rel)
            parts.extend([f"### {rel}", text, ""])

    parts.append("## Approved lessons and plans")
    for entry in lesson_entries:
        try:
            detail = store.get_lesson_detail(class_id, entry.date)
        except KeyError:
            continue
        result_path = f"wiki/classes/{class_id}/lessons/{entry.date}/lesson_results.md"
        source_paths.append(result_path)
        parts.extend(
            [
                f"### {entry.date} - {entry.title}",
                f"Source: {result_path}",
                detail.primary_markdown[:5000],
                "",
            ]
        )
        if detail.lesson_plan_markdown:
            plan_path = f"wiki/classes/{class_id}/lessons/{entry.date}/lesson_plan.md"
            source_paths.append(plan_path)
            parts.extend(
                [
                    f"#### Saved plan ({plan_path})",
                    detail.lesson_plan_markdown[:2500],
                    "",
                ]
            )

    unique_paths = list(dict.fromkeys(source_paths))
    return {
        "packet": "\n".join(parts),
        "source_paths": unique_paths,
        "warnings": warnings,
    }


def _page_with_fallback(title: str, content: str, class_id: str) -> str:
    header = f"# {title}\n\n> Class: {class_id}\n\n"
    body = content.strip()
    if not body:
        return header + "- No compact memory generated yet.\n"
    if body.startswith("# "):
        page = body
    else:
        page = header + body

    class_line = f"> Class: {class_id}"
    lines = page.splitlines()
    normalized: list[str] = []
    class_seen = False
    for line in lines:
        if line.strip() == class_line:
            if class_seen:
                continue
            class_seen = True
        normalized.append(line)

    if not class_seen:
        insert_at = 1 if normalized and normalized[0].startswith("#") else 0
        normalized[insert_at:insert_at] = ["", class_line]

    return "\n".join(normalized).rstrip() + "\n"


def commit_memory_compaction(
    store,
    class_id: str,
    pages: dict[str, str],
    *,
    source_paths: list[str] | None = None,
) -> tuple[list[str], str]:
    store.get_class(class_id)
    allowed = memory_paths(store, class_id)
    titles = {
        "taught_so_far": "Taught So Far",
        "planning_brief": "Planning Brief",
        "teaching_patterns": "Teaching Patterns",
        "copilot_profile": "Class Copilot Profile",
        "class_state": "Class State",
        "session_summaries": "Session Summaries",
    }
    applied: list[str] = []
    for key, content in pages.items():
        if key not in allowed:
            raise ValueError(f"Unsupported compact memory page: {key}")
        path = allowed[key]
        rel = store.rel_wiki(path)
        if not rel.startswith(f"wiki/classes/{class_id}/memory/"):
            raise ValueError(f"Compact memory path outside class memory: {rel}")
        page = _page_with_fallback(titles[key], content, class_id)
        store.write_text(path, clamp_memory_page(key, page))
        applied.append(rel)

    log_id = store._append_log(
        class_id,
        date.today().isoformat(),
        "Compact class memory",
        applied,
        kind="compact",
    )
    store.rebuild_index(class_id)
    return applied, log_id
