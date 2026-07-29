"""Wiki paths io operations (delegated from WikiStore)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def class_dir(store, class_id: str) -> Path:
    return store.root / "wiki" / "classes" / class_id


def lesson_dir(store, class_id: str, lesson_date: str) -> Path:
    return store.class_dir(class_id) / "lessons" / lesson_date


def students_dir(store, class_id: str) -> Path:
    return store.class_dir(class_id) / "students"


def student_path(store, class_id: str, student_id: str) -> Path:
    sid = student_id.upper()
    return store.students_dir(class_id) / f"{sid}.md"


def timeline_path(store, class_id: str) -> Path:
    return store.class_dir(class_id) / "timeline.md"


def class_config_path(store, class_id: str) -> Path:
    return store.class_dir(class_id) / "class_config.md"


def index_path(store) -> Path:
    return store.root / "index.md"


def log_path(store) -> Path:
    return store.root / "log.md"


def roll_up_paths(store, class_id: str) -> dict[str, Path]:
    base = store.class_dir(class_id)
    return {
        "course_state": base / "course_state.md",
        "students": base / "students.md",
        "misconceptions": base / "misconceptions.md",
        "open_loops": base / "open_loops.md",
    }


def rel_wiki(store, path: Path) -> str:
    try:
        return path.relative_to(store.root).as_posix()
    except ValueError:
        return path.as_posix()


def read_text(store, path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def write_text(store, path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def resolve_path(store, relative_path: str) -> Path:
    """Resolve a wiki-relative path; reject escapes outside root."""
    rel = relative_path.strip().lstrip("/").replace("\\", "/")
    if ".." in rel.split("/"):
        raise ValueError(f"Invalid path: {relative_path}")
    full = (store.root / rel).resolve()
    root_resolved = store.root.resolve()
    if not str(full).startswith(str(root_resolved)):
        raise ValueError(f"Path outside wiki root: {relative_path}")
    return full


def read_wiki_page(store, relative_path: str, max_chars: int = 12000) -> str:
    path = store.resolve_path(relative_path)
    text = store.read_text(path)
    if len(text) > max_chars:
        return text[: max_chars - 20] + "\n\n… [truncated]"
    return text


def read_wiki_index(store, class_id: Optional[str] = None) -> str:
    text = store.read_text(store.index_path)
    if not class_id:
        return text
    marker = f"## Class: {class_id}"
    if marker in text:
        start = text.index(marker)
        rest = text[start + len(marker) :]
        next_class = rest.find("\n## Class")
        section = text[
            start : start + len(marker) + (next_class if next_class >= 0 else len(rest))
        ]
        if next_class >= 0:
            section = text[start : start + len(marker) + next_class]
        return section
    cls = store.get_class(class_id)
    if cls.label in text:
        start = text.find(f"## Class — {cls.label}")
        if start >= 0:
            rest = text[start + 10 :]
            next_class = rest.find("\n## Class")
            end = start + 10 + (next_class if next_class >= 0 else len(rest))
            return text[start:end]
    # No section for this class (e.g. created but not yet indexed). Returning the
    # whole file here would inject every other class's index into the prompt.
    return ""
