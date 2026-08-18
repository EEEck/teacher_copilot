"""Match OCR document_annotation.subject to the class Fach.

Empty or unknown labels are accepted so messy scans are not false-rejected.
A *known other* school subject (e.g. ESL on Chemie) is rejected.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# Canonical family -> accepted aliases (lowercase).
_SUBJECT_FAMILIES: dict[str, frozenset[str]] = {
    "chemie": frozenset({"chemie", "chemistry", "chem", "chemical"}),
    "physik": frozenset({"physik", "physics", "phy"}),
    "biologie": frozenset({"biologie", "biology", "bio"}),
    "mathe": frozenset({"mathe", "mathematik", "mathematics", "math", "maths"}),
    "esl": frozenset({"esl", "english", "englisch", "efl", "engl"}),
    "deutsch": frozenset({"deutsch", "german", "daZ", "daz"}),
    "informatik": frozenset({"informatik", "inf", "cs", "computer science"}),
}

_ALIAS_TO_FAMILY: dict[str, str] = {
    alias: family
    for family, aliases in _SUBJECT_FAMILIES.items()
    for alias in aliases
}


def normalize_subject_family(label: str) -> str | None:
    """Return a canonical family or None when the label is empty/unknown."""
    raw = " ".join((label or "").strip().lower().replace("_", " ").split())
    if not raw or raw in {"(unknown)", "unknown", "unclear", "n/a", "none"}:
        return None
    if raw in _ALIAS_TO_FAMILY:
        return _ALIAS_TO_FAMILY[raw]
    # First token: "english as a second language", "chemie ntg"
    first = raw.split()[0]
    if first in _ALIAS_TO_FAMILY:
        return _ALIAS_TO_FAMILY[first]
    return None


def is_known_subject_mismatch(class_subject: str, annotation_subject: str) -> bool:
    class_family = normalize_subject_family(class_subject)
    ann_family = normalize_subject_family(annotation_subject)
    if class_family is None or ann_family is None:
        return False
    return class_family != ann_family


def read_package_annotation_subject(root: Path) -> str:
    """Read OCR subject from scratch/wiki package files."""
    ann_path = Path(root) / "document_annotation.json"
    if ann_path.is_file():
        try:
            data = json.loads(ann_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
        if isinstance(data, dict):
            subject = str(data.get("subject") or "").strip()
            if subject:
                return subject
    summary = Path(root) / "summary.md"
    if summary.is_file():
        match = re.search(
            r"^-\s*Subject:\s*(.+)$",
            summary.read_text(encoding="utf-8"),
            re.M | re.I,
        )
        if match:
            value = match.group(1).strip()
            if value and value.lower() != "(unknown)":
                return value
    return ""


def raise_if_off_subject(*, class_subject: str, annotation_subject: str) -> None:
    if not is_known_subject_mismatch(class_subject, annotation_subject):
        return
    class_label = (class_subject or "").strip() or "this class"
    ann_label = (annotation_subject or "").strip() or "another subject"
    raise ValueError(
        f"This PDF looks like {ann_label}, not {class_label}. "
        "Upload a matching chapter or drop the file."
    )
