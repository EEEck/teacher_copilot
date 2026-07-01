"""Wiki commit operations (delegated from WikiStore)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from app.schemas.api import (
    ApprovedWikiUpdate,
    WikiUpdateProposal,
)

from app.teacher_agent.wiki.constants import (
    dedupe_wiki_proposals,
)

from app.teacher_agent.wiki import parsing


def compile_from_diary(
    store, class_id: str, diary_md: str, lesson_date: Optional[str] = None
) -> tuple[str, list[WikiUpdateProposal]]:
    """Return (lesson_date, wiki proposals)."""
    lesson_date = (
        lesson_date
        or parsing.extract_date_from_diary(diary_md)
        or date.today().isoformat()
    )
    title = parsing.extract_title(diary_md) or "Lesson"
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
    lesson_date = parsing.extract_date_from_diary(diary_md) or date.today().isoformat()
    title = parsing.extract_title(diary_md) or "lesson"
    slug = parsing.slugify(title)
    raw_path = store.root / "raw" / "classes" / class_id / f"{lesson_date}-{slug}.md"
    raw_rel = store.rel_wiki(raw_path)

    approved_writes = [u for u in approved if u.approved]
    if not approved_writes:
        raise ValueError("At least one wiki update must be approved to commit.")
    if not any("lesson_results.md" in u.wiki_path for u in approved_writes):
        raise ValueError("lesson_results.md must be approved to commit.")

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
