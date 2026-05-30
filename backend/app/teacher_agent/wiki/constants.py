"""Shared wiki constants and small helpers."""

from __future__ import annotations

import re

from app.schemas.api import ClassSummary, WikiUpdateProposal

ROLLUP_LABELS = {
    "course_state": "Course state",
    "open_loops": "Open loops",
    "misconceptions": "Misconceptions",
    "student_notes": "Student notes",
}

CLASS_REGISTRY: list[ClassSummary] = [
    ClassSummary(id="chemie_9b_2026_27", label="Chemie 9b — 2026/27", subject="chemie"),
]

LESSON_RESULTS_SECTIONS: list[tuple[str, str, bool]] = [
    ("what_was_covered", "What was covered", True),
    ("student_participation", "Student participation", True),
    ("what_went_well", "What went well", True),
    ("what_didnt_go_well", "What didn't go well", True),
    ("student_observations", "Student observations", True),
    ("homework_and_followups", "Homework & follow-ups", True),
]

DIARY_SECTION_HEADINGS = [label for _, label, _ in LESSON_RESULTS_SECTIONS]

STUDENT_ID_RE = re.compile(r"\b(S-\d{3})\b", re.I)

LOG_HEADER_RE = re.compile(
    r"##\s*\[([^\]]+)\]\s+(\w+)\s*\|\s*(?:([\d]{4}-[\d]{2}-[\d]{2})\s*[-—]\s*)?(.+?)\s*\(id:([a-f0-9]+)\)"
)
LOG_HEADER_LEGACY_RE = re.compile(
    r"##\s*\[(\d{4}-\d{2}-\d{2})\]\s+(\w+)\s*\|\s*(.+?)\s*\(id:([a-f0-9]+)\)"
)
INDEX_WIKI_PATH_RE = re.compile(r"(wiki/classes/[^\s|)]+?\.md)", re.I)


def dedupe_wiki_proposals(proposals: list[WikiUpdateProposal]) -> list[WikiUpdateProposal]:
    """Keep first proposal per wiki_path (compile used to emit student_notes twice)."""
    seen: set[str] = set()
    unique: list[WikiUpdateProposal] = []
    for proposal in proposals:
        if proposal.wiki_path in seen:
            continue
        seen.add(proposal.wiki_path)
        unique.append(proposal)
    return unique
