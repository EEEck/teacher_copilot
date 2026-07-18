"""Deterministic guards and rubric loaders for trusted lesson workflows.

These checks are deliberately narrow: they catch provenance and structural
mistakes without pretending a heuristic can grade pedagogical quality.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path


SOURCE_CITATION_RE = re.compile(
    r"(?:source|quelle)\s*:\s*`?([a-z0-9][a-z0-9-]*)(?:#([a-z0-9_-]+))?`?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RubricCriterion:
    criterion_id: str
    bucket: str
    criterion: str
    pass_requires: str
    notes: str
    conditional: str


def load_rubric(path: Path) -> list[RubricCriterion]:
    """Load a P/R/O/M rubric without coupling it to an LLM evaluator."""
    with path.open(encoding="utf-8", newline="") as handle:
        rows = csv.DictReader(handle)
        required = {"ID", "Bucket", "Criterion", "What pass requires"}
        if not required <= set(rows.fieldnames or []):
            raise ValueError(f"Rubric {path} is missing required P/R/O/M columns")
        return [
            RubricCriterion(
                criterion_id=(row.get("ID") or "").strip(),
                bucket=(row.get("Bucket") or "").strip(),
                criterion=(row.get("Criterion") or "").strip(),
                pass_requires=(row.get("What pass requires") or "").strip(),
                notes=(row.get("Notes") or "").strip(),
                conditional=(row.get("Conditional") or "").strip(),
            )
            for row in rows
            if (row.get("ID") or "").strip()
        ]


def validate_source_citations(
    markdown: str, consulted_sources: list[dict[str, str]], *, require: bool = False
) -> list[str]:
    """Reject citations which have not been read through the trusted-source tool."""
    cited = [(source, section or "summary") for source, section in SOURCE_CITATION_RE.findall(markdown or "")]
    if require and not cited:
        return ["A source citation is required but no `Source: source-id#section-id` was found."]
    consulted = {
        (str(item.get("source_id", "")).strip(), str(item.get("section_id", "summary")).strip() or "summary")
        for item in consulted_sources
    }
    errors: list[str] = []
    for citation in cited:
        if citation not in consulted:
            errors.append(
                f"Citation `{citation[0]}#{citation[1]}` was not read in this session."
            )
    return errors


def validate_lesson_duration(markdown: str) -> list[str]:
    """Catch a plainly impossible phase total when a duration header is supplied."""
    total_match = re.search(r">\s*Duration\s*:\s*(\d+)\s*min", markdown or "", re.I)
    if not total_match:
        return []
    phase_minutes = [int(value) for value in re.findall(r"\((\d+)\s*min\)", markdown)]
    if phase_minutes and sum(phase_minutes) != int(total_match.group(1)):
        return [
            f"Lesson-flow phases total {sum(phase_minutes)} min, but the duration is {total_match.group(1)} min."
        ]
    return []
