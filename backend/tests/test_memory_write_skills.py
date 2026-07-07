"""PR3: typed memory write-skill contracts + B2 canonical-aware folding.

The typed interface (`app/services/memory_skills.py`) puts one declared contract
in front of every memory write. These tests assert each skill's declared
`{targets, ledger_effect, hitl, dedup_scope}` matches its routing, and that B2
(dedup_scope=ledger+canonical) folds a re-capture of a fact already written to a
curated target. See docs/mem_v3/next_implementation.md.
"""

from __future__ import annotations

from pathlib import Path

from app.services.memory_candidate_ledger import (
    MemoryCandidateLedger,
    MemoryCandidateRow,
    insert_with_folding,
)
from app.services.memory_skills import (
    APPLY_CURATED_MEMORY,
    COMMIT_LESSON_RECORD,
    write_skill_for_target,
)
from tests.conftest import CLASS_ID

_LESSON = f"wiki/classes/{CLASS_ID}/lessons/2026-05-29/lesson_results.md"


def test_curated_targets_route_to_the_curated_skill():
    for target in (
        "teacher_profile.md",
        "user.md",
        "copilot_profile.md",
        "copilot.md",
        "teaching_patterns.md",
        "planning_brief.md",
        "wiki/subjects/chemie.md",
        "students/S-046.md",
    ):
        assert write_skill_for_target(target) is APPLY_CURATED_MEMORY, target
        assert APPLY_CURATED_MEMORY.allowed(target)
    assert APPLY_CURATED_MEMORY.ledger_effect == "close_candidates"
    assert APPLY_CURATED_MEMORY.hitl == "requires_approval"
    assert APPLY_CURATED_MEMORY.dedup_scope == "ledger+canonical"


def test_lesson_record_targets_route_to_the_commit_skill():
    for target in (
        "canonical_wiki",
        _LESSON,
        f"wiki/classes/{CLASS_ID}/course_state.md",
        f"wiki/classes/{CLASS_ID}/timeline.md",
    ):
        assert write_skill_for_target(target) is COMMIT_LESSON_RECORD, target
    assert COMMIT_LESSON_RECORD.ledger_effect == "none"
    assert COMMIT_LESSON_RECORD.hitl == "at_review"
    assert COMMIT_LESSON_RECORD.dedup_scope == "none"


def test_allowlists_do_not_cross():
    # A curated skill may not touch the raw lesson record, and vice versa.
    assert not APPLY_CURATED_MEMORY.allowed(_LESSON)
    assert not COMMIT_LESSON_RECORD.allowed("teacher_profile.md")


def test_retired_targets_have_no_write_skill():
    for target in ("class_state.md", "taught_so_far.md"):
        assert write_skill_for_target(target) is None, target


def _curated_row(candidate_id: str, text: str) -> MemoryCandidateRow:
    now = "2026-07-06T09:00:00Z"
    return MemoryCandidateRow(
        id=candidate_id,
        created_at=now,
        updated_at=now,
        class_id=CLASS_ID,
        subject="chemie",
        workflow="ingest",
        session_id="sess-b2",
        turn_index=1,
        channel="class_learning_pattern",
        target="teaching_patterns.md",
        section="what_worked_well",
        candidate_update=text,
        evidence_summary="",
    )


def test_b2_folds_a_capture_already_present_in_the_target_file(tmp_path: Path):
    ledger = MemoryCandidateLedger(tmp_path / "ledger.sqlite")
    ledger.initialize()

    # The fact is already written to teaching_patterns.md (e.g. by compaction),
    # so a fresh capture of it must fold to already_covered, not re-propose.
    present = ["Peer checking helps reduce balancing errors."]
    stored = insert_with_folding(
        ledger,
        _curated_row("cand-b2-1", "Peer checking reduces balancing errors."),
        canonical_bullets=present,
    )
    assert stored.status == "already_covered"
    assert "already present" in (stored.rejection_reason or "")


def test_b2_leaves_a_genuinely_new_capture_open(tmp_path: Path):
    ledger = MemoryCandidateLedger(tmp_path / "ledger.sqlite")
    ledger.initialize()

    present = ["Peer checking helps reduce balancing errors."]
    stored = insert_with_folding(
        ledger,
        _curated_row("cand-b2-2", "Molecule kits before formal terminology work well."),
        canonical_bullets=present,
    )
    assert stored.status == "captured"
