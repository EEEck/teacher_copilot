"""Wiki search operations (delegated from WikiStore)."""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.teacher_agent.wiki.constants import INDEX_WIKI_PATH_RE

_SEARCH_STOPWORDS = {
    "about",
    "after",
    "and",
    "auf",
    "based",
    "build",
    "class",
    "der",
    "die",
    "das",
    "for",
    "from",
    "gymnasium",
    "include",
    "into",
    "level",
    "lesson",
    "lessons",
    "minute",
    "minutes",
    "next",
    "our",
    "plan",
    "the",
    "und",
    "use",
    "wiki",
    "with",
}
_SEARCH_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9.+/_-]*")

ReferenceKind = Literal["class", "student", "lesson"]
ReferenceScope = Literal["active_class", "workspace"]
ResolutionStatus = Literal[
    "active_class_match", "cross_class_match", "ambiguous", "unresolved"
]


class ReferenceQuery(BaseModel):
    kind: ReferenceKind
    value: str


class ReferenceMatch(BaseModel):
    class_id: str
    canonical_value: str
    label: str
    evidence_path: str


class ResolvedReference(BaseModel):
    query: ReferenceQuery
    status: ResolutionStatus
    matches: list[ReferenceMatch] = Field(default_factory=list)


class ReferenceResolution(BaseModel):
    active_class_id: str
    items: list[ResolvedReference] = Field(default_factory=list)


def _normalized_reference(value: str) -> str:
    return " ".join((value or "").casefold().split())


def _normalized_student_id(value: str) -> str:
    match = re.fullmatch(r"s[\s-]*0*(\d{1,3})", value.strip(), re.I)
    if not match:
        return ""
    return f"S-{int(match.group(1)):03d}"


def _student_matches(store, class_id: str, value: str) -> list[ReferenceMatch]:
    path = store.roll_up_paths(class_id)["students"]
    text = store.read_text(path)
    requested_id = _normalized_student_id(value)
    requested_name = _normalized_reference(value)
    matches: list[ReferenceMatch] = []
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        student_id = _normalized_student_id(cells[0])
        name = cells[1].strip()
        if not student_id:
            continue
        if requested_id == student_id or requested_name == _normalized_reference(name):
            matches.append(
                ReferenceMatch(
                    class_id=class_id,
                    canonical_value=student_id,
                    label=name or student_id,
                    evidence_path=store.rel_wiki(path),
                )
            )
    return matches


def _class_matches(store, class_id: str, value: str) -> list[ReferenceMatch]:
    cls = store.get_class(class_id)
    requested = _normalized_reference(value)
    if requested not in {
        _normalized_reference(cls.id),
        _normalized_reference(cls.label),
    }:
        return []
    return [
        ReferenceMatch(
            class_id=class_id,
            canonical_value=cls.id,
            label=cls.label,
            evidence_path=store.rel_wiki(store.class_config_path(class_id)),
        )
    ]


def _lesson_matches(store, class_id: str, value: str) -> list[ReferenceMatch]:
    requested = _normalized_reference(value)
    path = store.timeline_path(class_id)
    matches: list[ReferenceMatch] = []
    for entry in store.get_timeline(class_id).entries:
        if requested not in {
            _normalized_reference(entry.date),
            _normalized_reference(entry.title),
        }:
            continue
        matches.append(
            ReferenceMatch(
                class_id=class_id,
                canonical_value=entry.date,
                label=entry.title,
                evidence_path=store.rel_wiki(path),
            )
        )
    return matches


def resolve_wiki_references(
    store,
    *,
    active_class_id: str,
    references: list[ReferenceQuery],
    scope: ReferenceScope = "active_class",
) -> ReferenceResolution:
    class_ids = [active_class_id]
    if scope == "workspace":
        class_ids.extend(
            cls.id for cls in store.list_classes() if cls.id != active_class_id
        )
    resolvers = {
        "class": _class_matches,
        "student": _student_matches,
        "lesson": _lesson_matches,
    }
    resolved: list[ResolvedReference] = []
    for query in references:
        matches: list[ReferenceMatch] = []
        for class_id in class_ids:
            matches.extend(resolvers[query.kind](store, class_id, query.value))
        active_matches = [
            match for match in matches if match.class_id == active_class_id
        ]
        if len(matches) > 1:
            status: ResolutionStatus = "ambiguous"
        elif active_matches:
            status = "active_class_match"
        elif matches:
            status = "cross_class_match"
        else:
            status = "unresolved"
        resolved.append(
            ResolvedReference(query=query, status=status, matches=matches)
        )
    return ReferenceResolution(active_class_id=active_class_id, items=resolved)


def _query_terms(query: str) -> list[str]:
    terms = _SEARCH_TOKEN_RE.findall(query.lower())
    unique_terms = []
    seen = set()
    for term in terms:
        term = term.strip("._/+ -")
        if len(term) < 3 or term.isdigit() or term in _SEARCH_STOPWORDS:
            continue
        if term not in seen:
            seen.add(term)
            unique_terms.append(term)
    return unique_terms


def _weighted_counts(text: str, weight: float) -> Counter[str]:
    counts: Counter[str] = Counter()
    for term in _query_terms(text):
        counts[term] += weight
    return counts


def _first_heading(text: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+)$", text, flags=re.M)
    if match:
        return match.group(1).strip()[:120]
    return fallback.replace("_", " ").replace("-", " ").strip()[:120]


def _doc_kind_boost(kind: str) -> float:
    return {
        "memory": 2.0,
        "lesson": 1.5,
        "rollup": 1.2,
        "meta": 1.0,
        "student": 0.5,
        "course_network": 1.2,
        "raw": -2.0,
    }.get(kind, 0.0)


def _page_title_for_path(path: str) -> str:
    if path.endswith("/"):
        return path.rstrip("/").split("/")[-1]
    return Path(path).stem


def _line_snippet(line: str, terms: list[str], *, max_chars: int = 240) -> str:
    lower = line.lower()
    idx = -1
    for term in terms:
        idx = lower.find(term)
        if idx >= 0:
            break
    if idx < 0:
        return " ".join(line.split())[:max_chars]
    start = max(0, idx - 90)
    return " ".join(line[start : idx + 120].split())[:max_chars]


def _text_snippet(text: str, terms: list[str], *, max_chars: int = 260) -> str:
    lower = text.lower()
    idx = -1
    for term in terms:
        idx = lower.find(term)
        if idx >= 0:
            break
    if idx < 0:
        idx = 0
    start = max(0, idx - 90)
    return " ".join(text[start : idx + 140].split())[:max_chars]


def build_class_relevance_corpus(store, class_id: str) -> dict[str, Any]:
    """Build an AutoSci-style deterministic weighted corpus for one class wiki."""
    store.get_class(class_id)
    docs: list[dict[str, Any]] = []
    postings: dict[str, list[tuple[int, float]]] = {}
    df: Counter[str] = Counter()

    def add_doc(
        *,
        path: str,
        kind: str,
        title: str,
        body: str,
        source: str,
        title_weight: float,
        body_weight: float,
    ) -> None:
        counts = Counter()
        counts.update(_weighted_counts(title, title_weight))
        counts.update(_weighted_counts(path, 2.0))
        counts.update(_weighted_counts(body, body_weight))
        if not counts:
            return
        doc_idx = len(docs)
        length = float(sum(counts.values()))
        docs.append(
            {
                "path": path,
                "kind": kind,
                "title": title,
                "body": body,
                "source": source,
                "length": length,
            }
        )
        for term, tf in counts.items():
            postings.setdefault(term, []).append((doc_idx, float(tf)))
        df.update(set(counts))

    index_text = store.read_wiki_index(class_id)
    for line in index_text.splitlines():
        for match in INDEX_WIKI_PATH_RE.finditer(line):
            path = match.group(1)
            if not path.startswith(f"wiki/classes/{class_id}/"):
                continue
            kind = (
                "lesson"
                if "/lessons/" in path
                else "memory"
                if "/memory/" in path
                else "index"
            )
            add_doc(
                path=path,
                kind=kind,
                title=_page_title_for_path(path),
                body=line,
                source="index",
                title_weight=3.0,
                body_weight=2.0,
            )

    for page in store.list_class_pages(class_id):
        kind = page["kind"]
        if kind == "raw":
            continue
        path = page["path"]
        if not path.startswith(f"wiki/classes/{class_id}/"):
            continue
        try:
            text = store.read_text(store.resolve_path(path))
        except ValueError:
            continue
        title = _first_heading(text, _page_title_for_path(path))
        title_weight = 5.0 if kind in {"lesson", "memory"} else 3.0
        body_weight = 1.4 if kind == "memory" else 1.0
        add_doc(
            path=path,
            kind=kind,
            title=title,
            body=text,
            source="body",
            title_weight=title_weight,
            body_weight=body_weight,
        )

    avg_len = sum(float(doc["length"]) for doc in docs) / len(docs) if docs else 0.0
    return {"docs": docs, "postings": postings, "df": df, "avg_len": avg_len}


def list_class_pages(
    store, class_id: str, kind: Optional[str] = None
) -> list[dict[str, str]]:
    store.get_class(class_id)
    pages: list[dict[str, str]] = []
    base = store.class_dir(class_id)
    kinds = (
        {kind}
        if kind
        else {
            "rollups",
            "lessons",
            "students",
            "timeline",
            "memory",
            "course_network",
            "raw",
        }
    )

    if "rollups" in kinds:
        for key, path in store.roll_up_paths(class_id).items():
            pages.append({"kind": "rollup", "id": key, "path": store.rel_wiki(path)})
        for name in (
            "timeline.md",
            "class_config.md",
            "curriculum_profile.md",
            "trusted_sources.md",
        ):
            p = base / name
            if p.exists():
                pages.append({"kind": "meta", "id": name, "path": store.rel_wiki(p)})

    if "lessons" in kinds:
        lessons_root = base / "lessons"
        if lessons_root.exists():
            for day_dir in sorted(lessons_root.iterdir()):
                if not day_dir.is_dir():
                    continue
                for fname in ("lesson_results.md", "lesson_plan.md"):
                    p = day_dir / fname
                    if p.exists():
                        pages.append(
                            {
                                "kind": "lesson",
                                "id": day_dir.name,
                                "path": store.rel_wiki(p),
                            }
                        )

    if "students" in kinds:
        sdir = store.students_dir(class_id)
        if sdir.exists():
            for p in sorted(sdir.glob("S-*.md")):
                pages.append(
                    {
                        "kind": "student",
                        "id": p.stem,
                        "path": store.rel_wiki(p),
                    }
                )

    if "memory" in kinds:
        memory_root = base / "memory"
        if memory_root.exists():
            for p in sorted(memory_root.glob("*.md")):
                pages.append(
                    {
                        "kind": "memory",
                        "id": p.stem,
                        "path": store.rel_wiki(p),
                    }
                )

    if "course_network" in kinds:
        from app.teacher_agent.wiki import course_network

        pages.extend(course_network.list_course_network_pages(store, class_id))

    if "raw" in kinds:
        raw_root = store.root / "raw" / "classes" / class_id
        if raw_root.exists():
            for p in sorted(raw_root.glob("*.md")):
                pages.append({"kind": "raw", "id": p.stem, "path": store.rel_wiki(p)})
    return pages


def find_in_memory(
    store, class_id: str, query: str, max_results: int = 5
) -> list[dict[str, str]]:
    """Deterministic BM25-style search over class index, memory, and wiki pages."""
    store.get_class(class_id)
    q = query.lower().strip()
    if not q:
        return []
    terms = _query_terms(q)
    if not terms:
        return []

    corpus = build_class_relevance_corpus(store, class_id)
    docs = corpus["docs"]
    postings = corpus["postings"]
    df = corpus["df"]
    avg_len = float(corpus["avg_len"] or 0.0)
    if not docs or avg_len <= 0:
        return []

    k1 = 1.2
    b = 0.75
    doc_scores: Counter[int] = Counter()
    doc_terms: dict[int, set[str]] = {}
    n_docs = len(docs)
    for term in terms:
        term_postings = postings.get(term)
        if not term_postings:
            continue
        term_df = int(df.get(term, 0))
        idf = math.log(1.0 + (n_docs - term_df + 0.5) / (term_df + 0.5))
        for doc_idx, tf in term_postings:
            doc_len = float(docs[doc_idx]["length"])
            norm = tf + k1 * (1.0 - b + b * doc_len / avg_len)
            doc_scores[doc_idx] += idf * ((tf * (k1 + 1.0)) / norm)
            doc_terms.setdefault(doc_idx, set()).add(term)

    best_by_path: dict[str, dict[str, Any]] = {}
    for doc_idx, score in doc_scores.items():
        doc = docs[doc_idx]
        final_score = float(score) + _doc_kind_boost(doc["kind"])
        terms_matched = sorted(doc_terms.get(doc_idx, set()))
        snippet = (
            _line_snippet(doc["body"], terms, max_chars=240)
            if doc["source"] == "index"
            else _text_snippet(doc["body"], terms, max_chars=260)
        )
        hit = {
            "path": doc["path"],
            "kind": doc["kind"],
            "title": doc["title"],
            "snippet": snippet,
            "score": round(final_score, 3),
            "matched_terms": terms_matched,
            "source": doc["source"],
        }
        existing = best_by_path.get(doc["path"])
        if not existing or final_score > float(existing["score"]):
            best_by_path[doc["path"]] = hit

    ranked = sorted(
        best_by_path.values(),
        key=lambda h: (-float(h["score"]), h["kind"], h["path"]),
    )
    return ranked[: max(1, min(max_results or 5, 20))]


def search_wiki(
    store, class_id: str, query: str, max_results: int = 15
) -> list[dict[str, str]]:
    """Backward-compatible search; delegates to find_in_memory."""
    return [
        {"path": h["path"], "snippet": h["snippet"]}
        for h in store.find_in_memory(class_id, query, max_results)
    ]


def is_class_memory_path(store, class_id: str, relative_path: str) -> bool:
    """True if path is readable class-scoped wiki (chat read_memory_page guard)."""
    rel = relative_path.strip().lstrip("/").replace("\\", "/")
    if ".." in rel.split("/"):
        return False
    prefix = f"wiki/classes/{class_id}/"
    return rel.startswith(prefix)
