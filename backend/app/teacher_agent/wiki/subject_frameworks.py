"""Shared subject-framework selection and class-profile compilation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FrameworkSummary:
    subject: str
    grade: int
    branch: str
    path: str
    text: str
    source_refs: tuple[str, ...]
    version: str


@dataclass(frozen=True)
class FrameworkIndex:
    subject: str
    path: str
    entries: tuple[FrameworkSummary, ...]


def _frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    try:
        frontmatter, body = text[4:].split("\n---\n", 1)
    except ValueError:
        return {}, text
    values: dict[str, str] = {}
    for line in frontmatter.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"\'')
    return values, body


def _source_refs(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _framework_root(store, subject: str) -> Path:
    return store.root / "wiki" / "subjects" / subject / "teaching_frameworks"


def load_framework_index(store, subject: str) -> FrameworkIndex:
    """Read the shared, immutable framework summaries for one subject."""
    normalized = subject.strip().lower()
    root = _framework_root(store, normalized)
    entries: list[FrameworkSummary] = []
    for path in sorted(root.glob("*/key_summary.md")):
        metadata, body = _frontmatter(path.read_text(encoding="utf-8"))
        try:
            grade = int(metadata.get("grade", ""))
        except ValueError:
            continue
        branch = metadata.get("branch", "").upper()
        if not branch:
            continue
        entries.append(
            FrameworkSummary(
                subject=metadata.get("subject", normalized),
                grade=grade,
                branch=branch,
                path=store.rel_wiki(path),
                text=body.strip(),
                source_refs=_source_refs(metadata.get("source_refs", "")),
                version=metadata.get("version", ""),
            )
        )
    index_path = root / "index.md"
    return FrameworkIndex(
        subject=normalized,
        path=store.rel_wiki(index_path),
        entries=tuple(entries),
    )


def select_framework(store, subject: str, grade: int, branch: str | None) -> FrameworkSummary:
    """Return the exact shared framework for an active class route."""
    normalized_branch = (branch or "").strip().upper()
    for entry in load_framework_index(store, subject).entries:
        if entry.grade == grade and entry.branch == normalized_branch:
            return entry
    raise ValueError(
        f"No {subject} teaching framework for grade {grade} branch {normalized_branch or '<none>'}."
    )


def framework_for_class(store, class_id: str) -> FrameworkSummary:
    """Select one shared framework from the class's declared curriculum route."""
    class_config = store.get_class(class_id)
    curriculum = store.get_curriculum_profile(class_id)
    configured_subject = (class_config.subject or "").strip().lower()
    curriculum_subject = (curriculum.subject or configured_subject).strip().lower()
    if curriculum_subject != configured_subject:
        raise ValueError(
            "Curriculum profile subject does not match the class subject: "
            f"{curriculum_subject or '<none>'} != {configured_subject or '<none>'}."
        )
    try:
        grade = int(curriculum.grade)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Class {class_id} has no usable curriculum grade.") from exc
    return select_framework(store, configured_subject, grade, curriculum.branch)


def _active_framework_directory(store, class_id: str) -> tuple[Path, FrameworkSummary]:
    framework = framework_for_class(store, class_id)
    return _framework_root(store, framework.subject) / f"{framework.grade:02d}", framework


def _guidance_payload(store, path: Path) -> dict:
    metadata, body = _frontmatter(path.read_text(encoding="utf-8"))
    return {
        "path": store.rel_wiki(path),
        "grade": int(metadata.get("grade", "0") or 0),
        "page": path.stem,
        "section": "full_page",
        "source_refs": list(_source_refs(metadata.get("source_refs", ""))),
        "text": body.strip(),
    }


def search_subject_guidance(
    store, class_id: str, query: str, max_results: int = 8
) -> list[dict]:
    """Search detailed guidance only within the active class's grade/branch."""
    active_dir, framework = _active_framework_directory(store, class_id)
    terms = sorted({term for term in re.findall(r"[a-z0-9-]{3,}", query.lower())})
    if not terms:
        return []
    results: list[tuple[int, dict]] = []
    for path in sorted(active_dir.rglob("*.md")):
        payload = _guidance_payload(store, path)
        haystack = (payload["text"] + " " + path.name).lower()
        matched = [term for term in terms if term in haystack]
        if not matched:
            continue
        score = sum(haystack.count(term) for term in matched)
        lines = [line.strip() for line in payload["text"].splitlines() if line.strip()]
        snippet = next(
            (line for line in lines if any(term in line.lower() for term in matched)),
            payload["text"],
        )[:900]
        results.append(
            (
                score,
                {
                    "path": payload["path"],
                    "grade": framework.grade,
                    "branch": framework.branch,
                    "page": payload["page"],
                    "section": "full_page",
                    "source_refs": payload["source_refs"],
                    "matched_terms": matched,
                    "snippet": snippet,
                },
            )
        )
    results.sort(key=lambda item: (-item[0], item[1]["path"]))
    return [item for _, item in results[: max(1, min(max_results or 8, 20))]]


def read_subject_guidance(store, class_id: str, relative_path: str) -> dict:
    """Read one allowlisted active-grade guidance page with provenance metadata."""
    active_dir, framework = _active_framework_directory(store, class_id)
    requested = Path(relative_path)
    if requested.is_absolute() or requested.suffix.lower() != ".md":
        raise ValueError("Subject guidance path is not allowed.")
    candidate = (store.root / requested).resolve()
    allowed_root = active_dir.resolve()
    if candidate != allowed_root and allowed_root not in candidate.parents:
        raise ValueError("Subject guidance path is outside the active framework.")
    if not candidate.is_file():
        raise ValueError("Subject guidance page was not found.")
    payload = _guidance_payload(store, candidate)
    payload["grade"] = framework.grade
    payload["branch"] = framework.branch
    payload["text"] = payload["text"][:5000]
    return payload
