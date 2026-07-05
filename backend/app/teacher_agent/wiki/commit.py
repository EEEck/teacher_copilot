"""Wiki commit operations (delegated from WikiStore)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from app.schemas.api import (
    ApprovedWikiUpdate,
    WikiUpdateProposal,
)

from app.teacher_agent.wiki.constants import (
    dedupe_wiki_proposals,
)

from app.teacher_agent.wiki import parsing

# Teachers plan a full school year ahead, so lesson dates up to a year out
# are legitimate. Anything beyond that is almost certainly a typo'd date that
# would pollute the timeline, course state, and planning context.
MAX_FUTURE_LESSON_DAYS = 365


def validate_lesson_date(lesson_date: str) -> None:
    """Raise ValueError for dates that cannot be a real lesson."""
    try:
        parsed = date.fromisoformat(lesson_date)
    except ValueError as e:
        raise ValueError(
            f"Lesson date '{lesson_date}' in the diary heading is not a valid "
            "date. Use the format YYYY-MM-DD."
        ) from e
    if parsed > date.today() + timedelta(days=MAX_FUTURE_LESSON_DAYS):
        raise ValueError(
            f"Lesson date {lesson_date} is more than a school year in the "
            "future — that looks like a typo. Fix the date in the diary "
            "heading ('# Lesson Results — YYYY-MM-DD — …') before saving."
        )


def compile_from_diary(
    store, class_id: str, diary_md: str, lesson_date: Optional[str] = None
) -> tuple[str, list[WikiUpdateProposal]]:
    """Return (lesson_date, wiki proposals)."""
    lesson_date = (
        lesson_date
        or parsing.extract_date_from_diary(diary_md)
        or date.today().isoformat()
    )
    # No date validation here: drafts are also compiled for planned future
    # lessons (draft preview). validate_lesson_date guards commit_ingest only.
    title = parsing.clean_results_title(parsing.extract_title(diary_md) or "") or "Lesson"
    cls = store.get_class(class_id)

    lesson_results_path = store.lesson_dir(class_id, lesson_date) / "lesson_results.md"
    lesson_results_content = store._format_lesson_results(
        class_id, cls.subject, diary_md, lesson_date, title
    )

    proposals: list[WikiUpdateProposal] = [
        WikiUpdateProposal(
            wiki_path=store.rel_wiki(lesson_results_path),
            current_content=store.read_text(lesson_results_path),
            proposed_content=lesson_results_content,
            rationale="Primary lesson results for this date.",
        )
    ]

    rollups = store._compile_rollups(class_id, diary_md, lesson_date, title)
    for key, content, rationale in rollups:
        path = store.roll_up_paths(class_id)[key]
        proposals.append(
            WikiUpdateProposal(
                wiki_path=store.rel_wiki(path),
                current_content=store.read_text(path),
                proposed_content=content,
                rationale=rationale,
            )
        )

    for path, content, rationale in store._compile_students_and_timeline(
        class_id, diary_md, lesson_date, title
    ):
        proposals.append(
            WikiUpdateProposal(
                wiki_path=store.rel_wiki(path),
                current_content=store.read_text(path),
                proposed_content=content,
                rationale=rationale,
            )
        )

    slug = parsing.slugify(title)
    raw_path = store.root / "raw" / "classes" / class_id / f"{lesson_date}-{slug}.md"
    proposals.append(
        WikiUpdateProposal(
            wiki_path=store.rel_wiki(raw_path),
            current_content=store.read_text(raw_path),
            proposed_content=f"{diary_md.strip()}\n",
            rationale="Immutable approved diary snapshot (raw layer).",
        )
    )

    return lesson_date, dedupe_wiki_proposals(proposals)


def commit_ingest(
    store,
    class_id: str,
    diary_md: str,
    approved: list[ApprovedWikiUpdate],
    session_id: str,
) -> tuple[str, list[str], str]:
    approved_writes = [u for u in approved if u.approved]
    if not approved_writes:
        raise ValueError("At least one wiki update must be approved to commit.")
    lesson_results_update = next(
        (u for u in approved_writes if "lesson_results.md" in u.wiki_path),
        None,
    )
    if lesson_results_update is None:
        raise ValueError("lesson_results.md must be approved to commit.")

    request_lesson_date = parsing.extract_date_from_diary(diary_md)
    if request_lesson_date:
        validate_lesson_date(request_lesson_date)
    canonical_diary = lesson_results_update.content or diary_md
    lesson_date = parsing.extract_date_from_diary(canonical_diary) or date.today().isoformat()
    validate_lesson_date(lesson_date)
    title = parsing.clean_results_title(parsing.extract_title(canonical_diary) or "") or "lesson"
    slug = parsing.slugify(title)
    raw_path = store.root / "raw" / "classes" / class_id / f"{lesson_date}-{slug}.md"
    raw_rel = store.rel_wiki(raw_path)
    approved_rels = [
        u.wiki_path.strip().lstrip("/").replace("\\", "/")
        for u in approved
    ]
    approved_write_rels = [
        u.wiki_path.strip().lstrip("/").replace("\\", "/")
        for u in approved_writes
    ]
    has_explicit_student_entity_update = any(
        f"/classes/{class_id}/students/S-" in f"/{rel}"
        for rel in approved_rels
    )
    has_approved_students_index = any(
        rel == f"wiki/classes/{class_id}/students.md"
        for rel in approved_write_rels
    )

    applied: list[str] = []
    for update in approved_writes:
        rel = update.wiki_path.strip().lstrip("/").replace("\\", "/")
        path = store.resolve_path(rel)
        if rel == raw_rel or rel.startswith("raw/"):
            body = (
                f"> Session: {session_id}\n"
                f"> Committed: {datetime.now().isoformat(timespec='seconds')}\n\n"
                f"{update.content.strip()}\n"
            )
            store.write_text(path, body)
        else:
            store.write_text(path, update.content)
        applied.append(update.wiki_path)

    if has_approved_students_index and not has_explicit_student_entity_update:
        store._finalize_lesson_writes(class_id, canonical_diary, lesson_date, title, applied)

    log_id = store._append_log(class_id, lesson_date, title, applied, kind="ingest")
    store.rebuild_index()
    return (
        raw_rel if raw_rel in applied else (applied[0] if applied else raw_rel),
        applied,
        log_id,
    )


def save_lesson_plan(store, class_id: str, lesson_date: str, content: str) -> str:
    path = store.lesson_dir(class_id, lesson_date) / "lesson_plan.md"
    store.lesson_dir(class_id, lesson_date).mkdir(parents=True, exist_ok=True)
    store.write_text(path, content)
    store.rebuild_index()
    return store.rel_wiki(path)
