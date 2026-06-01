"""Wiki search operations (delegated from WikiStore)."""

from __future__ import annotations

import re
import uuid
import math
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from app.schemas.api import (
    ApprovedWikiUpdate,
    ClassMemorySnapshot,
    ClassSummary,
    ClassTimeline,
    CompletenessChecklist,
    CompletenessItem,
    LessonDetail,
    RollupExcerpt,
    TimelineEntry,
    WikiUpdateProposal,
)

from app.teacher_agent.wiki.constants import (
    CLASS_REGISTRY,
    DIARY_SECTION_HEADINGS,
    INDEX_WIKI_PATH_RE,
    LESSON_RESULTS_SECTIONS,
    LOG_HEADER_LEGACY_RE,
    LOG_HEADER_RE,
    ROLLUP_LABELS,
    STUDENT_ID_RE,
    dedupe_wiki_proposals,
)

from app.teacher_agent.wiki import parsing


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
            kind = "lesson" if "/lessons/" in path else "memory" if "/memory/" in path else "index"
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
        else {"rollups", "lessons", "students", "timeline", "memory", "raw"}
    )

    if "rollups" in kinds:
        for key, path in store.roll_up_paths(class_id).items():
            pages.append(
                {"kind": "rollup", "id": key, "path": store.rel_wiki(path)}
            )
        for name in ("timeline.md", "class_config.md"):
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

    if "raw" in kinds:
        raw_root = store.root / "raw" / "classes" / class_id
        if raw_root.exists():
            for p in sorted(raw_root.glob("*.md")):
                pages.append(
                    {"kind": "raw", "id": p.stem, "path": store.rel_wiki(p)}
                )
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
