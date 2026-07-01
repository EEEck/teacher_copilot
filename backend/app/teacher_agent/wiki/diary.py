"""Wiki diary operations (delegated from WikiStore)."""

from __future__ import annotations


from app.schemas.api import (
    CompletenessChecklist,
    CompletenessItem,
)

from app.teacher_agent.wiki.constants import (
    LESSON_RESULTS_SECTIONS,
)

from app.teacher_agent.wiki import parsing


def checklist_from_diary(store, diary_md: str) -> CompletenessChecklist:
    items: list[CompletenessItem] = []
    for key, label, required in LESSON_RESULTS_SECTIONS:
        section = parsing.extract_section_body(diary_md, label)
        complete = bool(section.strip()) and section.strip().lower() not in {
            "none",
            "n/a",
            "tbd",
            "-",
        }
        items.append(
            CompletenessItem(
                field=key, label=label, complete=complete, required=required
            )
        )
    return CompletenessChecklist(items=items)


def is_diary_complete(store, diary_md: str) -> bool:
    checklist = store.checklist_from_diary(diary_md)
    return all(i.complete for i in checklist.items if i.required)
