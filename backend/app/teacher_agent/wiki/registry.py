"""Wiki registry operations (delegated from WikiStore)."""

from __future__ import annotations

import re

from app.schemas.api import (
    ClassSummary,
)


def list_classes(store) -> list[ClassSummary]:
    """Classes are exactly the directories under `wiki/classes/`.

    An empty workspace reports no classes; there is deliberately no seeded
    fallback, or a teacher who has not created a class yet would be shown one
    that does not exist in their wiki.
    """
    discovered: list[ClassSummary] = []
    classes_root = store.root / "wiki" / "classes"
    if classes_root.exists():
        for class_dir in sorted(classes_root.iterdir()):
            if not class_dir.is_dir():
                continue
            class_id = class_dir.name
            label, subject = store._read_class_meta(class_id)
            discovered.append(ClassSummary(id=class_id, label=label, subject=subject))
    return discovered


def _read_class_meta(store, class_id: str) -> tuple[str, str]:
    config = store.read_text(store.class_config_path(class_id))
    label = class_id.replace("_", " ")
    subject = "general"
    m = re.search(r"^#\s+(.+)$", config, re.M)
    if m:
        # Older pages (including the seeded class every beta workspace copied)
        # title the file rather than the class: "# Class Config — Chemie 9b".
        label = re.sub(r"^class config\s*[—-]\s*", "", m.group(1).strip(), flags=re.I)
    m = re.search(r"^subject:\s*(\S+)", config, re.M | re.I)
    if m:
        subject = m.group(1).strip().lower()
    return label, subject


def get_class(store, class_id: str) -> ClassSummary:
    for c in store.list_classes():
        if c.id == class_id:
            return c
    raise KeyError(f"Unknown class: {class_id}")
