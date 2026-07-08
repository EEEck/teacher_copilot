"""Mem V3 Phase 4 goldens: single-call sweep contract (docs/mem_v3/design.md lane 3).

xfail until app/services/memory_sweep.py gains the mem0-style consolidation
contract:

- ConsolidationOp: {claim_ids, operation: add|update|delete|none,
  memory_id?, new_text?, target, section, rationale}
- validate_consolidation_ops(ops, memory_index, claim_ids) -> list[ConsolidationOp]
  Structural checks ONLY (restores docs/2sweep_idea.md §7): every claim id
  accounted for exactly once; referenced memory ids must exist in the
  enumerated index; update/delete must reference a memory id; update must
  carry new_text. No lexical token-overlap semantics.
- consolidation_failure_notice(reason, claim_count) -> single plain-language
  notice (no raw internal ids), replacing per-candidate zombie cards.
"""

from __future__ import annotations

import pytest

from app.services import memory_sweep as sweep


def _require(name: str):
    fn = getattr(sweep, name, None)
    if fn is None:
        pytest.xfail(f"mem_v3 phase 4: {name} not implemented yet")
    return fn


MEMORY_INDEX = {
    "M1": "**Current Unit:** Practicing redox half equations with peer checking.",
    "M2": "Feedback and planning language: English for this prototype.",
}


def _op(**kwargs):
    base = {
        "claim_ids": ["c1"],
        "operation": "add",
        "memory_id": None,
        "new_text": "New durable note.",
        "target": "planning_brief.md",
        "section": "current_unit",
        "rationale": "test",
    }
    base.update(kwargs)
    return base


def test_valid_transition_update_passes_without_lexical_overlap():
    validate = _require("validate_consolidation_ops")
    # The V2 catch-22 case: new topic shares no tokens with the old bullet.
    ops = [
        _op(
            operation="update",
            memory_id="M1",
            new_text=(
                "**Current Unit:** First organic chemistry lessons; keep redox "
                "review brief."
            ),
        )
    ]
    validated = validate(ops, MEMORY_INDEX, {"c1"})
    assert len(validated) == 1


def test_unknown_memory_id_is_rejected():
    validate = _require("validate_consolidation_ops")
    with pytest.raises(ValueError, match="memory"):
        validate([_op(operation="update", memory_id="M99")], MEMORY_INDEX, {"c1"})


def test_every_claim_must_be_accounted_for_exactly_once():
    validate = _require("validate_consolidation_ops")
    with pytest.raises(ValueError, match="claim"):
        validate([_op(claim_ids=["c1"])], MEMORY_INDEX, {"c1", "c2"})
    with pytest.raises(ValueError, match="claim"):
        validate(
            [_op(claim_ids=["c1"]), _op(claim_ids=["c1"], operation="none")],
            MEMORY_INDEX,
            {"c1"},
        )


def test_no_change_update_is_demoted_to_none():
    validate = _require("validate_consolidation_ops")
    ops = validate(
        [
            _op(
                operation="update",
                memory_id="M2",
                new_text="Feedback and planning language:  english for this prototype.",
            )
        ],
        MEMORY_INDEX,
        {"c1"},
    )
    assert ops[0].operation == "none"
    assert ops[0].memory_id is None


def test_update_requires_new_text():
    validate = _require("validate_consolidation_ops")
    with pytest.raises(ValueError):
        validate(
            [_op(operation="update", memory_id="M1", new_text="")],
            MEMORY_INDEX,
            {"c1"},
        )


def test_failure_produces_one_plain_language_notice():
    notice_fn = _require("consolidation_failure_notice")
    notice = notice_fn("validator said: sweep_card_deadbeef exploded", 7)
    text = str(getattr(notice, "message", notice))
    assert "sweep_card_" not in text, "raw internal ids must not reach teachers"
    assert "7" in text
