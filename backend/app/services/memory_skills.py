"""Typed memory read/write skills (mem_v3 PR3).

One declared contract in front of every memory write, and the reads those write
paths depend on. Each write skill declares `{targets, ledger_effect, hitl,
dedup_scope}` so the seam rules are explicit and uniform instead of implicit and
duplicated across `commit_ingest` / `apply_memory_items` /
`apply_memory_sweep_decisions` — the shape that let B1 leak (a write that forgot
to close its ledger rows). The executors are thin: no behavior change over the
functions they wrap. The `dedup_scope` declaration is not decoration — it drives
B2 (insert-time folding consults the current curated target content), and it is
the substrate for handing narrow, auditable capabilities to subagents (PR5).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Literal

from app.services.memory_apply import apply_memory_items, apply_memory_sweep_decisions
from app.teacher_agent.memory_targets import (
    canonical_memory_target,
    is_supported_runtime_target,
)

LedgerEffect = Literal["none", "close_candidates"]
Hitl = Literal["at_review", "requires_approval"]
DedupScope = Literal["none", "ledger", "ledger+canonical"]


@dataclass(frozen=True)
class MemoryWriteSkill:
    """A declared memory-write capability.

    - ``allows`` is the target allowlist predicate — the only files this skill
      may touch.
    - ``ledger_effect``: whether applying closes the originating ledger rows.
    - ``hitl``: ``requires_approval`` (curated memory, teacher approves each) vs
      ``at_review`` (the lesson record, approved once at the save review).
    - ``dedup_scope``: what a capture folds against. ``ledger+canonical`` also
      consults the current target file (B2).
    """

    name: str
    allows: Callable[[str], bool]
    ledger_effect: LedgerEffect
    hitl: Hitl
    dedup_scope: DedupScope

    def allowed(self, target: str) -> bool:
        return self.allows(target)


def _is_curated_target(target: str) -> bool:
    """Curated, sweep/apply-managed memory: profiles, compact pages, subject
    guides, student summaries — everything supported except review-only
    canonical_wiki."""
    canonical = canonical_memory_target(target)
    return is_supported_runtime_target(canonical) and canonical != "canonical_wiki"


def _is_canonical_lesson_target(target: str) -> bool:
    """Deterministic event record written by the ingest commit.

    Student *summaries* are curated (they route to APPLY_CURATED_MEMORY); the
    lesson record here is the dated diary, rollups, and review-only canonical
    candidates.
    """
    t = (target or "").strip().lower()
    if t == "canonical_wiki" or "/lessons/" in t:
        return True
    return t.endswith(
        (
            "course_state.md",
            "timeline.md",
            "misconceptions.md",
            "open_loops.md",
            "students.md",
        )
    )


COMMIT_LESSON_RECORD = MemoryWriteSkill(
    name="commit_lesson_record",
    allows=_is_canonical_lesson_target,
    ledger_effect="none",
    hitl="at_review",
    dedup_scope="none",
)

APPLY_CURATED_MEMORY = MemoryWriteSkill(
    name="apply_curated_memory",
    allows=_is_curated_target,
    ledger_effect="close_candidates",
    hitl="requires_approval",
    dedup_scope="ledger+canonical",
)

WRITE_SKILLS = (APPLY_CURATED_MEMORY, COMMIT_LESSON_RECORD)


def write_skill_for_target(target: str) -> MemoryWriteSkill | None:
    """The one write skill that governs a target (curated wins on overlap)."""
    for skill in WRITE_SKILLS:
        if skill.allowed(target):
            return skill
    return None


# --- write executors (thin; no behavior change over the wrapped functions) ---


def apply_curated_memory(wiki, class_id, items):
    """Write teacher-approved curated bullets via the bounded helper.

    Ledger-close is contract-driven (`APPLY_CURATED_MEMORY.ledger_effect ==
    "close_candidates"`) and performed by the caller for the successfully
    applied items (see routes.apply_memory / apply_memory_sweep).
    """
    return apply_memory_items(wiki, class_id, items)


def apply_curated_sweep_decisions(wiki, class_id, decisions):
    """Apply teacher-reviewed sweep decisions via the bounded helper."""
    return apply_memory_sweep_decisions(wiki, class_id, decisions)


# --- reads the write paths depend on (declared, for B2 + the subagent set) ---

_BULLET_RE = re.compile(r"^\s*[-*]\s+(.*\S)\s*$")
_SOURCE_SUFFIX_RE = re.compile(r"\s*\(source:\s*`[^`]+`\)\s*$")


def _bullets_from_markdown(text: str) -> list[str]:
    bullets: list[str] = []
    for line in (text or "").splitlines():
        match = _BULLET_RE.match(line)
        if match:
            bullets.append(_SOURCE_SUFFIX_RE.sub("", match.group(1)).strip())
    return [b for b in bullets if b]


def read_curated_target_bullets(wiki, class_id: str, target: str) -> list[str]:
    """Current bullets already written to a curated target (the B2 dedup source).

    Only curated targets under `ledger+canonical` dedup scope are read; the
    canonical lesson record is out of scope (it is not a curated-memory twin).
    """
    if not _is_curated_target(target):
        return []
    # Local import avoids an import cycle (memory_sweep imports the ledger).
    from app.services.memory_sweep import memory_sweep_target_excerpts

    excerpts = memory_sweep_target_excerpts(wiki, class_id, {target})
    canonical = canonical_memory_target(target)
    return _bullets_from_markdown(excerpts.get(canonical, ""))
