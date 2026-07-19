"""Deterministic, provenance-aware trusted source registry for teacher workflows.

Source records live as Markdown under ``wiki/sources``. They are deliberately
separate from class memory: source pages inform curriculum claims, while class
pages remain the authority for what a particular class has learned.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*(?:\n|\Z)", re.S)
_HEADING_RE = re.compile(
    r"^##\s+Section:\s*(?P<id>[^—-]+?)(?:\s+[—-]\s+(?P<title>.*))?$", re.M
)
_FIRST_HEADING_RE = re.compile(r"^#\s+(?P<title>.+?)\s*$", re.M)


@dataclass(frozen=True)
class SourceSection:
    id: str
    title: str
    body: str


@dataclass(frozen=True)
class TrustedSource:
    source_id: str
    title: str
    authority: str
    jurisdiction: str
    subject: str
    school_type: str
    branch: str
    grade: str
    canonical_url: str
    retrieved_at: str
    version_label: str
    content_hash: str
    path: str
    summary: str
    sections: tuple[SourceSection, ...]
    source_format: str = ""
    ingestion_method: str = ""
    review_status: str = ""
    artifact_path: str = ""
    extracted_markdown_path: str = ""
    source_language: str = ""


@dataclass(frozen=True)
class CurriculumProfile:
    state: str
    school_type: str
    branch: str
    grade: str
    subject: str
    source_ids: tuple[str, ...]


def _frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    values: dict[str, str] = {}
    for line in match.group("body").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"\'')
    return values, text[match.end() :]


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "section"


def _sections(body: str) -> tuple[SourceSection, ...]:
    matches = list(_HEADING_RE.finditer(body))
    sections: list[SourceSection] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        section_id = match.group("id").strip()
        title = (match.group("title") or section_id).strip()
        sections.append(SourceSection(section_id, title, body[start:end].strip()))
    if sections:
        return tuple(sections)

    heading_matches = list(re.finditer(r"^##\s+(?P<title>.+?)\s*$", body, re.M))
    fallback: list[SourceSection] = []
    for index, match in enumerate(heading_matches):
        start = match.end()
        end = heading_matches[index + 1].start() if index + 1 < len(heading_matches) else len(body)
        title = match.group("title").strip()
        fallback.append(SourceSection(_slug(title), title, body[start:end].strip()))
    return tuple(fallback)


def _summary(body: str) -> str:
    match = re.search(r"^##\s+Summary\s*$([\s\S]*?)(?=^##\s+|\Z)", body, re.M | re.I)
    if match:
        return " ".join(match.group(1).split())[:700]
    return " ".join(body.split())[:700]


def _source_from_path(path: Path, wiki_root: Path) -> TrustedSource | None:
    text = path.read_text(encoding="utf-8")
    metadata, body = _frontmatter(text)
    title_match = _FIRST_HEADING_RE.search(body)
    source_id = metadata.get("source_id", "").strip()
    if not source_id or not title_match:
        return None
    if any(not metadata.get(key, "").strip() for key in ("authority", "canonical_url")):
        return None
    content_hash = metadata.get("content_hash") or hashlib.sha256(text.encode("utf-8")).hexdigest()
    return TrustedSource(
        source_id=source_id,
        title=metadata.get("title") or title_match.group("title").strip(),
        authority=metadata.get("authority", "external_evidence"),
        jurisdiction=metadata.get("jurisdiction", ""),
        subject=metadata.get("subject", ""),
        school_type=metadata.get("school_type", ""),
        branch=metadata.get("branch", ""),
        grade=metadata.get("grade", ""),
        canonical_url=metadata["canonical_url"],
        retrieved_at=metadata.get("retrieved_at", ""),
        version_label=metadata.get("version_label", ""),
        content_hash=content_hash,
        path=path.relative_to(wiki_root).as_posix(),
        summary=_summary(body),
        sections=_sections(body),
        source_format=metadata.get("source_format", ""),
        ingestion_method=metadata.get("ingestion_method", ""),
        review_status=metadata.get("review_status", ""),
        artifact_path=metadata.get("artifact_path", ""),
        extracted_markdown_path=metadata.get("extracted_markdown_path", ""),
        source_language=metadata.get("source_language", ""),
    )


def load_trusted_sources(wiki_root: Path) -> dict[str, TrustedSource]:
    source_root = Path(wiki_root) / "wiki" / "sources"
    records: dict[str, TrustedSource] = {}
    if not source_root.exists():
        return records
    for path in sorted(source_root.rglob("*.md")):
        source = _source_from_path(path, Path(wiki_root))
        if source is not None:
            records[source.source_id] = source
    return records


def _metadata_for_page(wiki_root: Path, class_id: str, filename: str) -> dict[str, str]:
    path = Path(wiki_root) / "wiki" / "classes" / class_id / filename
    if not path.exists():
        return {}
    metadata, _ = _frontmatter(path.read_text(encoding="utf-8"))
    return metadata


def linked_source_ids(wiki_root: Path, class_id: str) -> tuple[str, ...]:
    raw = _metadata_for_page(wiki_root, class_id, "trusted_sources.md").get("source_ids", "")
    return tuple(dict.fromkeys(item.strip() for item in raw.split(",") if item.strip()))


def load_curriculum_profile(wiki_root: Path, class_id: str) -> CurriculumProfile:
    metadata = _metadata_for_page(wiki_root, class_id, "curriculum_profile.md")
    return CurriculumProfile(
        state=metadata.get("state", ""),
        school_type=metadata.get("school_type", ""),
        branch=metadata.get("branch", ""),
        grade=metadata.get("grade", ""),
        subject=metadata.get("subject", ""),
        source_ids=linked_source_ids(wiki_root, class_id),
    )


def _grade_number(value: str) -> int | None:
    match = re.search(r"\d+", value or "")
    return int(match.group(0)) if match else None


def _matches_scope(source: TrustedSource, profile: CurriculumProfile, scope: str) -> bool:
    scope = (scope or "all").strip().lower()
    if scope in {"official", "official_curriculum", "official_standard"} and not source.authority.startswith("official"):
        return False
    source_grade = _grade_number(source.grade)
    profile_grade = _grade_number(profile.grade)
    if scope == "active" and source_grade is not None and profile_grade is not None and source_grade != profile_grade:
        return False
    if scope == "prior" and source_grade is not None and profile_grade is not None and source_grade >= profile_grade:
        return False
    return True


def list_sources_for_class(wiki_root: Path, class_id: str, scope: str = "all") -> list[TrustedSource]:
    profile = load_curriculum_profile(wiki_root, class_id)
    records = load_trusted_sources(wiki_root)
    return [
        records[source_id]
        for source_id in profile.source_ids
        if source_id in records and _matches_scope(records[source_id], profile, scope)
    ]


def _terms(text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(re.findall(r"[a-z0-9äöüß]+", text.lower())))


def _snippet(text: str, terms: Iterable[str], max_chars: int = 260) -> str:
    normalized = " ".join(text.split())
    lower = normalized.lower()
    indexes = [lower.find(term) for term in terms if lower.find(term) >= 0]
    index = min(indexes) if indexes else 0
    return normalized[max(0, index - 80) : max(0, index - 80) + max_chars]


def search_sources_for_class(
    wiki_root: Path, class_id: str, query: str, scope: str = "all", max_results: int = 8
) -> list[dict[str, object]]:
    query_terms = _terms(query)
    if not query_terms:
        return []
    hits: list[dict[str, object]] = []
    for source in list_sources_for_class(wiki_root, class_id, scope):
        for section in source.sections:
            haystack = " ".join((source.source_id, source.title, section.id, section.title, source.summary, section.body)).lower()
            matched = [term for term in query_terms if term in haystack]
            if not matched:
                continue
            score = len(matched) + (2 if source.source_id.lower() in query.lower() else 0)
            hits.append(
                {
                    "source_id": source.source_id,
                    "title": source.title,
                    "authority": source.authority,
                    "section_id": section.id,
                    "section_title": section.title,
                    "matched_terms": matched,
                    "snippet": _snippet(section.body, matched),
                    "canonical_url": source.canonical_url,
                    "path": source.path,
                    "score": score,
                }
            )
    hits.sort(key=lambda item: (-int(item["score"]), str(item["source_id"]), str(item["section_id"])))
    return hits[: max(1, min(max_results, 20))]


def read_source_for_class(
    wiki_root: Path, class_id: str, source_id: str, section_id: str = "", max_chars: int = 12000
) -> dict[str, object]:
    linked = {source.source_id: source for source in list_sources_for_class(wiki_root, class_id, "all")}
    source = linked.get(source_id)
    if source is None:
        raise ValueError(f"trusted source '{source_id}' is not linked to active class '{class_id}'")
    section = None
    if section_id:
        section = next((item for item in source.sections if item.id == section_id), None)
        if section is None:
            raise ValueError(f"unknown section '{section_id}' for trusted source '{source_id}'")
    body = section.body if section else source.summary
    if len(body) > max_chars:
        body = body[: max_chars - 32] + "\n\n… [source section truncated]"
    return {
        "source_id": source.source_id,
        "title": source.title,
        "authority": source.authority,
        "jurisdiction": source.jurisdiction,
        "branch": source.branch,
        "grade": source.grade,
        "canonical_url": source.canonical_url,
        "retrieved_at": source.retrieved_at,
        "version_label": source.version_label,
        "content_hash": source.content_hash,
        "section_id": section.id if section else "summary",
        "section_title": section.title if section else "Summary",
        "content": body,
        "citation": f"{source.title}, {section.title if section else 'Summary'} ({source.canonical_url})",
        "path": source.path,
    }
