"""Backend-only contract tests for Memory Sweep storage and write boundaries."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from app.services.memory_apply import apply_memory_items, apply_memory_sweep_decisions
from app.services.memory_candidate_ledger import (
    MemoryCandidateLedger,
    MemoryCandidateRow,
    rows_from_runtime_candidates,
)
from app.services.memory_sweep import (
    build_sweep_packets,
    build_sweep_proposals,
    validate_alignment_output,
    validate_cards_against_alignment,
    memory_sweep_target_excerpts,
)
from app.services.ingest_service import IngestService
from app.services.plan_service import PlanService
from app.teacher_agent.models import (
    MemorySweepAlignmentGroupOutput,
    MemorySweepAlignmentOutput,
    MemorySweepCardOutput,
    MemorySweepProposalOutput,
)
from app.teacher_agent.planning_state import MemoryCandidate
from app.teacher_agent.wiki_store import WikiStore
from tests.conftest import CLASS_ID, StubAgentRunner


@dataclass(frozen=True)
class _ApplyItem:
    target: str
    section: str
    content: str


@dataclass(frozen=True)
class _SweepDecision:
    action: str
    target: str
    section: str
    content: str
    candidate_ids: list[str]
    operation: str = "add"
    replaces_content: str = ""


def _seed_memory_sweep_examples(ledger: MemoryCandidateLedger) -> None:
    ledger.add_many(
        [
            MemoryCandidateRow(
                id="cand_teacher_mbb_1",
                created_at="2026-06-22T09:00:00Z",
                updated_at="2026-06-22T09:00:00Z",
                class_id=None,
                subject=None,
                workflow="plan",
                session_id="sess_plan_001",
                turn_index=3,
                channel="teacher_behavior",
                target="teacher_profile.md",
                section="Communication",
                candidate_update="Prefers concise MBB-style planning summaries.",
                evidence_summary=(
                    "Teacher asked for MBB-style communication in multiple "
                    "planning sessions."
                ),
                evidence_refs=["trace:sess_plan_001:turn3", "trace:sess_plan_002:turn2"],
                source="inferred_from_session",
                basis="repeated_behavior",
                confidence="medium",
                cluster_key="teacher.communication.mbb_concise",
            ),
            MemoryCandidateRow(
                id="cand_class_redox_examples_1",
                created_at="2026-06-22T09:05:00Z",
                updated_at="2026-06-22T09:05:00Z",
                class_id=CLASS_ID,
                subject="chemie",
                workflow="ingest",
                session_id="sess_ingest_010",
                turn_index=4,
                channel="class_learning_pattern",
                target="teaching_patterns.md",
                section="What Worked Well",
                candidate_update=(
                    "Concrete metal-displacement examples helped this class "
                    "understand redox as electron transfer."
                ),
                evidence_summary=(
                    "Approved lesson memory says students understood redox "
                    "better after concrete examples."
                ),
                evidence_refs=[
                    f"wiki/classes/{CLASS_ID}/lessons/2026-05-25/lesson_results.md"
                ],
                source="approved_wiki",
                basis="explicit",
                confidence="high",
                cluster_key="class.redox.concrete_examples",
            ),
            MemoryCandidateRow(
                id="cand_subject_oxidation_sequence_1",
                created_at="2026-06-22T09:10:00Z",
                updated_at="2026-06-22T09:10:00Z",
                class_id=CLASS_ID,
                subject="chemie",
                workflow="plan",
                session_id="sess_plan_020",
                turn_index=2,
                channel="subject_concept",
                target="wiki/subjects/chemie.md",
                section="Common lesson patterns",
                candidate_update=(
                    "For chemistry classes, introduce oxidation numbers after "
                    "electron-transfer redox examples."
                ),
                evidence_summary=(
                    "Teacher explicitly framed this as a reusable chemistry "
                    "teaching sequence."
                ),
                evidence_refs=["trace:sess_plan_020:turn2"],
                source="teacher_explicit",
                basis="explicit",
                confidence="high",
                cluster_key="subject.chemie.oxidation_after_electron_transfer",
            ),
            MemoryCandidateRow(
                id="cand_lint_stale_class_state_1",
                created_at="2026-06-22T09:15:00Z",
                updated_at="2026-06-22T09:15:00Z",
                class_id=CLASS_ID,
                subject="chemie",
                workflow="memory_sweep",
                session_id="sweep_001",
                turn_index=0,
                channel="wiki_lint",
                target="class_state.md",
                section="Current State",
                candidate_update=(
                    "Class state should say the class is now applying redox "
                    "vocabulary, not merely preparing oxidation numbers."
                ),
                evidence_summary=(
                    "Last three approved lessons show the unit moved from "
                    "oxidation numbers to redox applications."
                ),
                evidence_refs=[
                    f"wiki/classes/{CLASS_ID}/lessons/2026-05-21/lesson_results.md",
                    f"wiki/classes/{CLASS_ID}/lessons/2026-05-29/lesson_results.md",
                ],
                source="approved_wiki",
                basis="explicit",
                confidence="high",
                cluster_key="lint.class_state.redox_progression",
            ),
        ]
    )


def _proposal_by_id(grouped, candidate_id: str):
    for proposals in grouped.values():
        for proposal in proposals:
            if candidate_id in proposal.candidate_ids:
                return proposal
    raise AssertionError(f"missing proposal: {candidate_id}")


def _teacher_behavior_row(
    candidate_id: str,
    *,
    update: str,
    evidence: str,
    created_at: str,
) -> MemoryCandidateRow:
    return MemoryCandidateRow(
        id=candidate_id,
        created_at=created_at,
        updated_at=created_at,
        class_id=None,
        subject=None,
        workflow="plan",
        session_id=candidate_id,
        turn_index=1,
        channel="teacher_behavior",
        target="user.md",
        section="Communication",
        candidate_update=update,
        evidence_summary=evidence,
        evidence_refs=[f"trace:{candidate_id}"],
        source="teacher_explicit",
        basis="explicit",
        confidence="high",
    )


def test_memory_sweep_sqlite_groups_applies_and_preserves_boundaries(tmp_path, wiki: WikiStore):
    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    _seed_memory_sweep_examples(ledger)

    grouped = ledger.propose_for_sweep(class_id=CLASS_ID, subject="chemie")

    assert "Teacher/Copilot Preferences" in grouped
    assert "Class Evolution" in grouped
    assert "Subject Concepts" in grouped
    assert "Wiki Review" in grouped
    assert grouped["Teacher/Copilot Preferences"][0].target == "teacher_profile.md"
    assert grouped["Class Evolution"][0].target == "teaching_patterns.md"
    assert grouped["Subject Concepts"][0].target == "wiki/subjects/chemie.md"
    assert grouped["Wiki Review"][0].target == "class_state.md"

    teacher_before = wiki.read_user_profile()
    subject_before = wiki.read_wiki_page("wiki/subjects/chemie.md")
    lesson_before = wiki.read_wiki_page(
        f"wiki/classes/{CLASS_ID}/lessons/2026-05-29/lesson_results.md"
    )

    redox = _proposal_by_id(grouped, "cand_class_redox_examples_1")
    stale_state = _proposal_by_id(grouped, "cand_lint_stale_class_state_1")
    applied, skipped, warnings = apply_memory_items(
        wiki,
        CLASS_ID,
        [
            _ApplyItem(redox.target, redox.section, redox.content),
            _ApplyItem(stale_state.target, stale_state.section, stale_state.content),
        ],
    )

    assert warnings == []
    assert skipped == []
    assert f"wiki/classes/{CLASS_ID}/memory/teaching_patterns.md" in applied
    assert f"wiki/classes/{CLASS_ID}/memory/class_state.md" in applied

    ledger.update_status(
        "cand_class_redox_examples_1",
        "applied",
        updated_at="2026-06-22T10:00:00Z",
        review_batch_id="sweep_001",
        promoted_at="2026-06-22T10:00:00Z",
    )
    ledger.update_status(
        "cand_lint_stale_class_state_1",
        "applied",
        updated_at="2026-06-22T10:00:00Z",
        review_batch_id="sweep_001",
        promoted_at="2026-06-22T10:00:00Z",
    )
    ledger.update_status(
        "cand_teacher_mbb_1",
        "rejected",
        updated_at="2026-06-22T10:00:00Z",
        rejection_reason="Teacher did not want this saved as a durable preference.",
        review_batch_id="sweep_001",
    )

    teaching_patterns = wiki.read_wiki_page(
        f"wiki/classes/{CLASS_ID}/memory/teaching_patterns.md"
    )
    class_state = wiki.read_wiki_page(f"wiki/classes/{CLASS_ID}/memory/class_state.md")

    assert "Concrete metal-displacement examples helped this class" in teaching_patterns
    assert "now applying redox vocabulary" in class_state
    assert wiki.read_user_profile() == teacher_before
    assert wiki.read_wiki_page("wiki/subjects/chemie.md") == subject_before
    assert (
        wiki.read_wiki_page(f"wiki/classes/{CLASS_ID}/lessons/2026-05-29/lesson_results.md")
        == lesson_before
    )

    next_grouped = ledger.propose_for_sweep(class_id=CLASS_ID, subject="chemie")
    next_ids = {
        proposal.candidate_id
        for proposals in next_grouped.values()
        for proposal in proposals
    }
    assert "cand_teacher_mbb_1" not in next_ids
    assert "cand_class_redox_examples_1" not in next_ids
    assert "cand_lint_stale_class_state_1" not in next_ids
    assert "cand_subject_oxidation_sequence_1" in next_ids


def test_memory_sweep_consolidates_matching_cluster_key(tmp_path):
    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    rows = [
        MemoryCandidateRow(
            id="group_roles_1",
            created_at="2026-06-22T09:00:00Z",
            updated_at="2026-06-22T09:00:00Z",
            class_id=CLASS_ID,
            subject="chemie",
            workflow="plan",
            session_id="sess_1",
            turn_index=1,
            channel="class_learning_pattern",
            target="teaching_patterns.md",
            section="Class Learning Profile",
            candidate_update=(
                "Structured group roles helped Chemie 9b start symbolic redox tasks."
            ),
            evidence_summary="Planning note said group roles made redox notation smoother.",
            evidence_refs=["trace:group_roles:1"],
            source="inferred_from_session",
            basis="inferred",
            confidence="medium",
            cluster_key=f"{CLASS_ID}.teaching_patterns.group_roles_symbolic_redox",
        ),
        MemoryCandidateRow(
            id="group_roles_2",
            created_at="2026-06-22T09:05:00Z",
            updated_at="2026-06-22T09:05:00Z",
            class_id=CLASS_ID,
            subject="chemie",
            workflow="ingest",
            session_id="sess_2",
            turn_index=2,
            channel="class_learning_pattern",
            target="teaching_patterns.md",
            section="Class Learning Profile",
            candidate_update=(
                "Assigned group roles kept students oriented before redox notation."
            ),
            evidence_summary="Lesson reflection repeated that assigned roles helped.",
            evidence_refs=["trace:group_roles:2"],
            source="inferred_from_session",
            basis="inferred",
            confidence="medium",
            cluster_key=f"{CLASS_ID}.teaching_patterns.group_roles_symbolic_redox",
        ),
        MemoryCandidateRow(
            id="group_roles_3",
            created_at="2026-06-22T09:10:00Z",
            updated_at="2026-06-22T09:10:00Z",
            class_id=CLASS_ID,
            subject="chemie",
            workflow="plan",
            session_id="sess_3",
            turn_index=3,
            channel="class_learning_pattern",
            target="teaching_patterns.md",
            section="Class Learning Profile",
            candidate_update=(
                "Use structured group roles before symbolic chemistry tasks."
            ),
            evidence_summary="Teacher explicitly repeated the group-role pattern.",
            evidence_refs=["trace:group_roles:3"],
            source="teacher_explicit",
            basis="explicit",
            confidence="high",
            cluster_key=f"{CLASS_ID}.teaching_patterns.group_roles_symbolic_redox",
        ),
    ]
    ledger.add_many(rows)

    grouped = ledger.propose_for_sweep(class_id=CLASS_ID, subject="chemie")

    proposals = grouped["Class Evolution"]
    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.candidate_id == "group_roles_3"
    assert proposal.candidate_ids == ["group_roles_3", "group_roles_1", "group_roles_2"]
    assert proposal.signal_count == 3
    assert proposal.confidence == "high"
    assert "3 related signals" in proposal.evidence_summary
    assert proposal.evidence_refs == [
        "trace:group_roles:1",
        "trace:group_roles:2",
        "trace:group_roles:3",
    ]


def test_memory_sweep_packets_by_target_scope(tmp_path, wiki: WikiStore):
    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    _seed_memory_sweep_examples(ledger)

    grouped = ledger.propose_for_sweep(class_id=CLASS_ID, subject="chemie")
    target_excerpts = memory_sweep_target_excerpts(
        wiki,
        CLASS_ID,
        {p.target for proposals in grouped.values() for p in proposals},
    )
    packets = build_sweep_packets(grouped, target_excerpts)

    packet_targets = {packet.target for packet in packets}
    assert {
        "teacher_profile.md",
        "teaching_patterns.md",
        "wiki/subjects/chemie.md",
        "class_state.md",
    } <= packet_targets
    for packet in packets:
        assert packet.proposals
        assert all(proposal.target == packet.target for proposal in packet.proposals)
        if packet.target != "canonical_wiki":
            assert isinstance(packet.current_memory_excerpt, str)


def test_memory_sweep_packets_enforce_candidate_cap(tmp_path, wiki: WikiStore):
    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    profile_path = wiki.root / "wiki" / "teacher_profile.md"
    profile = wiki.read_text(profile_path)
    profile = "\n".join(
        line
        for line in profile.splitlines()
        if "executive-style communication" not in line and "MBB" not in line
    )
    wiki.write_text(profile_path, profile)
    ledger.add_many(
        [
            MemoryCandidateRow(
                id=f"bulk_teacher_pref_{index}",
                created_at=f"2026-06-22T09:{index:02d}:00Z",
                updated_at=f"2026-06-22T09:{index:02d}:00Z",
                class_id=None,
                subject=None,
                workflow="plan",
                session_id=f"bulk_{index}",
                turn_index=1,
                channel="teacher_behavior",
                target="user.md",
                section="Communication",
                candidate_update=f"Teacher communication signal {index}.",
                evidence_summary=f"Evidence {index}.",
                evidence_refs=[f"trace:bulk:{index}"],
                source="teacher_explicit",
                basis="explicit",
                confidence="high",
            )
            for index in range(45)
        ]
    )

    grouped = ledger.propose_for_sweep(class_id=CLASS_ID, subject="chemie")
    packets = build_sweep_packets(
        grouped,
        memory_sweep_target_excerpts(wiki, CLASS_ID, {"user.md"}),
    )

    assert len(packets) == 2
    assert [len(packet.proposals) for packet in packets] == [40, 5]


def test_memory_sweep_alignment_validation_requires_exact_coverage(tmp_path, wiki: WikiStore):
    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    ledger.add_many(
        [
            _teacher_behavior_row(
                "align_mbb_1",
                update="Use MBB-style communication.",
                evidence="Teacher asked for MBB style.",
                created_at="2026-06-22T09:00:00Z",
            ),
            _teacher_behavior_row(
                "align_exec_1",
                update="Use executive-style communication.",
                evidence="Teacher asked for executive style.",
                created_at="2026-06-22T09:05:00Z",
            ),
        ]
    )
    grouped = build_sweep_proposals(ledger.list_candidates(class_id=CLASS_ID, subject="chemie"))
    packet = build_sweep_packets(grouped, memory_sweep_target_excerpts(wiki, CLASS_ID, {"user.md"}))[0]

    output = MemorySweepAlignmentOutput(
        alignment_groups=[
            MemorySweepAlignmentGroupOutput(
                group_id="g1",
                target="user.md",
                section="Communication",
                ledger_candidate_ids=["align_mbb_1"],
                relationship="new_semantic_claim",
                decision="merge",
                surface_labels=["recommendation first", "answer-first"],
                shared_attributes=["concise", "recommendation-oriented"],
                distinguishing_attributes=[],
                merge_test="Can be written as one coherent preference.",
            )
        ]
    )

    with pytest.raises(ValueError, match="invalid alignment coverage"):
        validate_alignment_output(packet, output)


def test_memory_sweep_alignment_validation_has_no_backend_synonym_split_guard(
    tmp_path,
    wiki: WikiStore,
):
    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    ledger.add_many(
        [
            _teacher_behavior_row(
                "split_mbb_1",
                update="Use MBB-style communication for lesson plans.",
                evidence="Teacher asked for MBB style.",
                created_at="2026-06-22T09:00:00Z",
            ),
            _teacher_behavior_row(
                "split_exec_1",
                update="Use executive-style communication with concise framing.",
                evidence="Teacher asked for executive style.",
                created_at="2026-06-22T09:05:00Z",
            ),
        ]
    )
    grouped = build_sweep_proposals(ledger.list_candidates(class_id=CLASS_ID, subject="chemie"))
    packet = build_sweep_packets(grouped, {"user.md": ""})[0]
    output = MemorySweepAlignmentOutput(
        alignment_groups=[
            MemorySweepAlignmentGroupOutput(
                group_id="mbb_only",
                target="user.md",
                section="Communication",
                ledger_candidate_ids=["split_mbb_1"],
                relationship="new_semantic_claim",
                decision="merge",
            ),
            MemorySweepAlignmentGroupOutput(
                group_id="exec_only",
                target="user.md",
                section="Communication",
                ledger_candidate_ids=["split_exec_1"],
                relationship="new_semantic_claim",
                decision="merge",
            ),
        ]
    )

    groups = validate_alignment_output(packet, output)

    assert [group.group_id for group in groups] == ["mbb_only", "exec_only"]
    assert groups[0].surface_labels == []


def test_memory_sweep_alignment_validation_has_no_backend_synonym_conflict_guard(
    tmp_path,
    wiki: WikiStore,
):
    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    ledger.add_many(
        [
            _teacher_behavior_row(
                "conflict_mbb_1",
                update="Use MBB-style communication for lesson plans.",
                evidence="Teacher asked for MBB style.",
                created_at="2026-06-22T09:00:00Z",
            ),
            _teacher_behavior_row(
                "conflict_exec_1",
                update="Use executive-style communication with concise framing.",
                evidence="Teacher asked for executive style.",
                created_at="2026-06-22T09:05:00Z",
            ),
        ]
    )
    grouped = build_sweep_proposals(ledger.list_candidates(class_id=CLASS_ID, subject="chemie"))
    packet = build_sweep_packets(
        grouped,
        {"user.md": "## Communication\n- Teacher prefers MBB-style framing.\n"},
    )[0]
    output = MemorySweepAlignmentOutput(
        alignment_groups=[
            MemorySweepAlignmentGroupOutput(
                group_id="mbb_exec_conflict",
                target="user.md",
                section="Communication",
                ledger_candidate_ids=["conflict_mbb_1", "conflict_exec_1"],
                relationship="possible_conflict",
                decision="needs_decision",
                group_label="MBB and executive communication",
                public_rationale="Teacher has expressed dual preferences.",
            )
        ]
    )

    groups = validate_alignment_output(packet, output)

    assert groups[0].relationship == "possible_conflict"
    assert groups[0].decision == "needs_decision"
    assert groups[0].merge_test == ""


def test_memory_sweep_alignment_validation_rejects_duplicates_unknowns_and_bad_labels(
    tmp_path,
    wiki: WikiStore,
):
    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    ledger.add(
        _teacher_behavior_row(
            "align_bad_1",
            update="Use executive-style communication.",
            evidence="Teacher asked for executive style.",
            created_at="2026-06-22T09:00:00Z",
        )
    )
    grouped = build_sweep_proposals(ledger.list_candidates(class_id=CLASS_ID, subject="chemie"))
    packet = build_sweep_packets(grouped, memory_sweep_target_excerpts(wiki, CLASS_ID, {"user.md"}))[0]

    unknown = MemorySweepAlignmentOutput(
        alignment_groups=[
            MemorySweepAlignmentGroupOutput(
                group_id="g1",
                target="user.md",
                section="Communication",
                ledger_candidate_ids=["align_bad_1", "missing"],
            )
        ]
    )
    with pytest.raises(ValueError, match="unknown candidate"):
        validate_alignment_output(packet, unknown)

    duplicate = MemorySweepAlignmentOutput(
        alignment_groups=[
            MemorySweepAlignmentGroupOutput(
                group_id="g1",
                target="user.md",
                section="Communication",
                ledger_candidate_ids=["align_bad_1", "align_bad_1"],
            )
        ]
    )
    with pytest.raises(ValueError, match="duplicate candidate"):
        validate_alignment_output(packet, duplicate)

    bad_label = MemorySweepAlignmentOutput(
        alignment_groups=[
            MemorySweepAlignmentGroupOutput(
                group_id="g1",
                target="user.md",
                section="Communication",
                ledger_candidate_ids=["align_bad_1"],
                relationship="magic",
            )
        ]
    )
    with pytest.raises(ValueError, match="unsupported relationship"):
        validate_alignment_output(packet, bad_label)


def test_memory_sweep_card_validation_requires_group_match(tmp_path, wiki: WikiStore):
    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    ledger.add_many(
        [
            _teacher_behavior_row(
                "card_group_mbb",
                update="Use MBB-style communication.",
                evidence="Teacher asked for MBB style.",
                created_at="2026-06-22T09:00:00Z",
            ),
            _teacher_behavior_row(
                "card_group_exec",
                update="Use executive-style communication.",
                evidence="Teacher asked for executive style.",
                created_at="2026-06-22T09:05:00Z",
            ),
        ]
    )
    grouped = build_sweep_proposals(ledger.list_candidates(class_id=CLASS_ID, subject="chemie"))
    target_excerpts = {"user.md": ""}
    packet = build_sweep_packets(grouped, target_excerpts)[0]
    alignment = validate_alignment_output(
        packet,
        MemorySweepAlignmentOutput(
            alignment_groups=[
                MemorySweepAlignmentGroupOutput(
                    group_id="g1",
                    target="user.md",
                    section="Communication",
                    ledger_candidate_ids=["card_group_mbb", "card_group_exec"],
                    decision="merge",
                )
            ]
        ),
    )
    bad_cards = MemorySweepProposalOutput(
        cards=[
            MemorySweepCardOutput(
                source_group_id="g1",
                candidate_id="card_group_mbb",
                candidate_ids=["card_group_mbb"],
                review_queue="Teacher/Copilot Preferences",
                channel="teacher_behavior",
                target="user.md",
                section="Communication",
                content="Teacher prefers concise executive-style communication.",
            )
        ]
    )

    with pytest.raises(ValueError, match="candidate_ids do not match"):
        validate_cards_against_alignment(packet, bad_cards, alignment, target_excerpts)


def test_memory_sweep_alignment_rejects_cross_target_reassignment(
    tmp_path,
    wiki: WikiStore,
):
    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    ledger.add(
        MemoryCandidateRow(
            id="cross_scope_fckw_mbb",
            created_at="2026-06-22T09:00:00Z",
            updated_at="2026-06-22T09:00:00Z",
            class_id=None,
            subject=None,
            workflow="plan",
            session_id="cross_scope",
            turn_index=1,
            channel="teacher_behavior",
            target="user.md",
            section="Communication",
            candidate_update=(
                "Use MBB-style summaries for FCKW lessons: core concept, "
                "experiment, then exam phrasing."
            ),
            evidence_summary="Teacher gave a cross-cutting communication and subject pattern.",
            evidence_refs=["trace:cross_scope:1"],
            source="teacher_explicit",
            basis="explicit",
            confidence="high",
        )
    )
    rows = ledger.list_candidates(class_id=CLASS_ID, subject="chemie")
    grouped = build_sweep_proposals(rows)
    target_excerpts = {"user.md": ""}
    packets = build_sweep_packets(grouped, target_excerpts)
    packet = packets[0]
    output = MemorySweepAlignmentOutput(
        alignment_groups=[
            MemorySweepAlignmentGroupOutput(
                group_id="bad_cross_target",
                target="wiki/subjects/chemie.md",
                section="Communication",
                ledger_candidate_ids=["cross_scope_fckw_mbb"],
                relationship="new_semantic_claim",
                decision="merge",
            )
        ]
    )

    with pytest.raises(ValueError, match="changed packet target"):
        validate_alignment_output(packet, output)


def test_memory_sweep_card_validation_preserves_adjust_operation(tmp_path, wiki: WikiStore):
    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    profile_path = wiki.root / "wiki" / "teacher_profile.md"
    profile = wiki.read_text(profile_path)
    profile = "\n".join(
        line
        for line in profile.splitlines()
        if "executive-style communication" not in line and "MBB" not in line
    )
    wiki.write_text(profile_path, profile)
    ledger.add_many(
        [
            _teacher_behavior_row(
                "adjust_mbb_1",
                update="Use MBB-style communication for plans.",
                evidence="Teacher asked for MBB style.",
                created_at="2026-06-22T09:00:00Z",
            ),
            _teacher_behavior_row(
                "adjust_exec_1",
                update="Use executive-style communication.",
                evidence="Teacher broadened the preference to executive style.",
                created_at="2026-06-22T09:05:00Z",
            ),
        ]
    )
    grouped = build_sweep_proposals(ledger.list_candidates(class_id=CLASS_ID, subject="chemie"))
    target_excerpts = {"user.md": "## Communication\n- Teacher prefers MBB-style framing.\n"}
    packet = build_sweep_packets(grouped, target_excerpts)[0]
    alignment = validate_alignment_output(
        packet,
        MemorySweepAlignmentOutput(
            alignment_groups=[
                MemorySweepAlignmentGroupOutput(
                    group_id="adjust_mbb_exec",
                    target="user.md",
                    section="Communication",
                    ledger_candidate_ids=["adjust_mbb_1", "adjust_exec_1"],
                    relationship="broadens_existing_memory",
                    decision="adjust_existing",
                )
            ]
        ),
    )
    output = MemorySweepProposalOutput(
        cards=[
            MemorySweepCardOutput(
                candidate_id="adjust_mbb_1",
                source_group_id="adjust_mbb_exec",
                candidate_ids=["adjust_mbb_1", "adjust_exec_1"],
                review_queue="Teacher/Copilot Preferences",
                channel="teacher_behavior",
                target="user.md",
                section="Communication",
                content=(
                    "Teacher prefers concise executive-style communication, "
                    "including MBB/McKinsey-style framing when useful."
                ),
                confidence="high",
                basis="explicit",
                operation="adjust",
                replaces_content="Teacher prefers MBB-style framing.",
                status_recommendation="promote",
                why_now="New evidence broadens the current narrow MBB wording.",
                signal_count=2,
            )
        ]
    )

    cards, warnings = validate_cards_against_alignment(
        packet, output, alignment, target_excerpts
    )

    assert warnings == []
    card = cards[0]
    assert card.operation == "adjust"
    assert card.status_recommendation == "promote"
    assert card.replaces_content == "Teacher prefers MBB-style framing."
    assert set(card.candidate_ids) == {"adjust_mbb_1", "adjust_exec_1"}
    assert card.can_apply is True


def test_memory_sweep_card_validation_rejects_invalid_operation_and_adjust_missing_replace(
    tmp_path,
):
    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    ledger.add(
        _teacher_behavior_row(
            "bad_operation_1",
            update="Use executive-style communication.",
            evidence="Teacher asked for executive style.",
            created_at="2026-06-22T09:00:00Z",
        )
    )
    grouped = build_sweep_proposals(ledger.list_candidates(class_id=CLASS_ID, subject="chemie"))
    target_excerpts = {"user.md": "## Communication\n- Teacher prefers MBB-style framing.\n"}
    packet = build_sweep_packets(grouped, target_excerpts)[0]
    alignment = validate_alignment_output(
        packet,
        MemorySweepAlignmentOutput(
            alignment_groups=[
                MemorySweepAlignmentGroupOutput(
                    group_id="bad_operation_group",
                    target="user.md",
                    section="Communication",
                    ledger_candidate_ids=["bad_operation_1"],
                    relationship="new_semantic_claim",
                    decision="merge",
                )
            ]
        ),
    )

    class BadOperationCard:
        candidate_id = "bad_operation_1"
        source_group_id = "bad_operation_group"
        candidate_ids = ["bad_operation_1"]
        target = "user.md"
        section = "Communication"
        content = "Teacher prefers concise executive-style communication."
        operation = "rewrite_file"
        status_recommendation = "promote"
        why_now = "Invalid operation should fail validation."
        model_fields_set = {"operation"}

    with pytest.raises(ValueError, match="operation needs_decision does not match"):
        validate_cards_against_alignment(
            packet,
            type("Output", (), {"cards": [BadOperationCard()], "warnings": []})(),
            alignment,
            target_excerpts,
        )

    adjust_alignment = validate_alignment_output(
        packet,
        MemorySweepAlignmentOutput(
            alignment_groups=[
                MemorySweepAlignmentGroupOutput(
                    group_id="missing_replace_group",
                    target="user.md",
                    section="Communication",
                    ledger_candidate_ids=["bad_operation_1"],
                    relationship="broadens_existing_memory",
                    decision="adjust_existing",
                )
            ]
        ),
    )
    output = MemorySweepProposalOutput(
        cards=[
            MemorySweepCardOutput(
                candidate_id="bad_operation_1",
                source_group_id="missing_replace_group",
                candidate_ids=["bad_operation_1"],
                review_queue="Teacher/Copilot Preferences",
                channel="teacher_behavior",
                target="user.md",
                section="Communication",
                content="Teacher prefers concise executive-style communication.",
                operation="adjust",
                status_recommendation="promote",
                why_now="Missing replacement should be downgraded.",
            )
        ]
    )

    with pytest.raises(ValueError, match="adjust missing replaces_content"):
        validate_cards_against_alignment(packet, output, adjust_alignment, target_excerpts)


def test_memory_candidate_ledger_rejects_invalid_status(tmp_path):
    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()

    try:
        ledger.update_status(
            "missing",
            "remembered_forever",
            updated_at="2026-06-22T10:00:00Z",
        )
    except ValueError as exc:
        assert "unsupported memory candidate status" in str(exc)
    else:
        raise AssertionError("expected invalid status to fail")


def test_memory_apply_supports_bounded_active_subject_guide_updates(wiki: WikiStore):
    subject_before = wiki.read_wiki_page("wiki/subjects/chemie.md")
    update = (
        "Introduce oxidation numbers after concrete electron-transfer examples "
        "when generalizing redox sequences."
    )

    applied, skipped, warnings = apply_memory_items(
        wiki,
        CLASS_ID,
        [
            _ApplyItem("wiki/subjects/chemie.md", "Common lesson patterns", update),
            _ApplyItem("wiki/subjects/physik.md", "Common lesson patterns", "Skip me."),
            _ApplyItem("canonical_wiki", "General", "Skip me too."),
        ],
    )

    assert warnings == []
    assert skipped == [
        "unsupported target: wiki/subjects/physik.md",
        "unsupported target: canonical_wiki",
    ]
    assert applied == ["wiki/subjects/chemie.md"]
    subject_after = wiki.read_wiki_page("wiki/subjects/chemie.md")
    assert subject_before != subject_after
    assert update in subject_after

    applied_again, skipped_again, warnings_again = apply_memory_items(
        wiki,
        CLASS_ID,
        [_ApplyItem("wiki/subjects/chemie.md", "Common lesson patterns", update)],
    )

    assert warnings_again == []
    assert skipped_again == []
    assert applied_again == ["wiki/subjects/chemie.md"]
    assert wiki.read_wiki_page("wiki/subjects/chemie.md").count(update) == 1


def test_memory_sweep_apply_adjust_replaces_exact_existing_bullet(wiki: WikiStore):
    old = "Teacher prefers MBB-style framing."
    new = (
        "Teacher prefers concise executive-style communication, including "
        "MBB/McKinsey-style framing when useful."
    )
    wiki.add_user_profile_conclusion("Communication", old)

    applied, skipped, warnings, successful = apply_memory_sweep_decisions(
        wiki,
        CLASS_ID,
        [
            _SweepDecision(
                action="apply",
                target="user.md",
                section="Communication",
                content=new,
                operation="adjust",
                replaces_content=old,
                candidate_ids=["adjust_success_1"],
            )
        ],
    )

    user_profile = wiki.read_user_profile()
    assert applied == ["wiki/teacher_profile.md"]
    assert skipped == []
    assert warnings == []
    assert successful == [0]
    assert old not in user_profile
    assert new in user_profile
    assert user_profile.count(new) == 1


def test_memory_sweep_apply_failed_adjust_reports_no_success(wiki: WikiStore):
    wiki.add_user_profile_conclusion("Communication", "Teacher prefers MBB-style framing.")

    applied, skipped, warnings, successful = apply_memory_sweep_decisions(
        wiki,
        CLASS_ID,
        [
            _SweepDecision(
                action="apply",
                target="user.md",
                section="Communication",
                content="Teacher prefers concise executive-style communication.",
                operation="adjust",
                replaces_content="Teacher prefers a missing bullet.",
                candidate_ids=["adjust_fail_1"],
            )
        ],
    )

    user_profile = wiki.read_user_profile()
    assert applied == []
    assert skipped == []
    assert successful == []
    assert any("replaces_content was not found" in warning for warning in warnings)
    assert "Teacher prefers concise executive-style communication." not in user_profile


def test_memory_apply_api_writes_active_subject_guide_only(client: TestClient):
    update = (
        "Use particle-level sketches before symbolic redox notation when "
        "students struggle to locate electron transfer."
    )

    apply_res = client.post(
        f"/api/classes/{CLASS_ID}/memory/apply",
        json={
            "items": [
                {
                    "target": "wiki/subjects/chemie.md",
                    "section": "Common lesson patterns",
                    "content": update,
                },
                {
                    "target": "wiki/subjects/physik.md",
                    "section": "Common lesson patterns",
                    "content": "Should not be written.",
                },
            ]
        },
    )

    assert apply_res.status_code == 200, apply_res.text
    body = apply_res.json()
    assert body["applied_wiki_paths"] == ["wiki/subjects/chemie.md"]
    assert body["skipped"] == ["unsupported target: wiki/subjects/physik.md"]

    subject_file = client.get(
        f"/api/classes/{CLASS_ID}/wiki/file",
        params={"path": "wiki/subjects/chemie.md"},
    )
    assert subject_file.status_code == 200
    assert update in subject_file.json()["markdown"]


def test_runtime_candidate_capture_allows_safe_subject_guide_target():
    rows = rows_from_runtime_candidates(
        [
            MemoryCandidate(
                target="wiki/subjects/chemie.md",
                section="Common lesson patterns",
                candidate_update=(
                    "For chemistry classes, always introduce oxidation numbers "
                    "after electron transfer."
                ),
                evidence="Explicit teacher subject-wide guidance.",
                source="teacher_explicit",
                basis="explicit",
                confidence="high",
            ),
            MemoryCandidate(
                target="wiki/classes/chemie_9b_2026_27/timeline.md",
                section="General",
                candidate_update="Unsafe arbitrary wiki target should be dropped.",
                source="teacher_explicit",
                basis="explicit",
                confidence="high",
            ),
        ],
        class_id=CLASS_ID,
        subject="chemie",
        workflow="plan",
        session_id="subject-capture",
        turn_index=1,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row.target == "wiki/subjects/chemie.md"
    assert row.channel == "subject_concept"
    assert row.class_id == CLASS_ID
    assert row.subject == "chemie"


def test_memory_sweep_44_examples_route_and_apply_to_expected_files(
    tmp_path,
    wiki: WikiStore,
):
    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    examples = [
        MemoryCandidateRow(
            id="doc44_class_redox_demo",
            created_at="2026-06-22T11:00:00Z",
            updated_at="2026-06-22T11:00:00Z",
            class_id=CLASS_ID,
            subject="chemie",
            workflow="ingest",
            session_id="doc44",
            turn_index=1,
            channel="class_learning_pattern",
            target="teaching_patterns.md",
            section="What Worked Well",
            candidate_update=(
                "9b finally understood redox after metal-displacement demos."
            ),
            evidence_summary="Teacher framed this as class-specific evidence.",
            evidence_refs=["doc:4.4:row1"],
            source="approved_wiki",
            basis="explicit",
            confidence="high",
        ),
        MemoryCandidateRow(
            id="doc44_subject_redox_sequence",
            created_at="2026-06-22T11:01:00Z",
            updated_at="2026-06-22T11:01:00Z",
            class_id=CLASS_ID,
            subject="chemie",
            workflow="plan",
            session_id="doc44",
            turn_index=2,
            channel="subject_concept",
            target="wiki/subjects/chemie.md",
            section="Common lesson patterns",
            candidate_update=(
                "For chemistry classes, always introduce oxidation numbers after "
                "electron transfer."
            ),
            evidence_summary="Teacher stated this as reusable chemistry guidance.",
            evidence_refs=["doc:4.4:row2"],
            source="teacher_explicit",
            basis="explicit",
            confidence="high",
        ),
        MemoryCandidateRow(
            id="doc44_teacher_mbb",
            created_at="2026-06-22T11:02:00Z",
            updated_at="2026-06-22T11:02:00Z",
            class_id=None,
            subject=None,
            workflow="plan",
            session_id="doc44",
            turn_index=3,
            channel="teacher_behavior",
            target="user.md",
            section="Communication",
            candidate_update="This teacher wants all plan summaries in MBB style.",
            evidence_summary="Explicit cross-class teacher communication preference.",
            evidence_refs=["doc:4.4:row3"],
            source="teacher_explicit",
            basis="explicit",
            confidence="high",
        ),
        MemoryCandidateRow(
            id="doc44_friday_discovery",
            created_at="2026-06-22T11:03:00Z",
            updated_at="2026-06-22T11:03:00Z",
            class_id=CLASS_ID,
            subject="chemie",
            workflow="plan",
            session_id="doc44",
            turn_index=4,
            channel="teacher_behavior",
            target="copilot.md",
            section="Planning Patterns",
            candidate_update=(
                "For this class, avoid long discovery phases on Fridays."
            ),
            evidence_summary="Class-scoped copilot working agreement.",
            evidence_refs=["doc:4.4:row4"],
            source="teacher_explicit",
            basis="explicit",
            confidence="high",
        ),
    ]
    ledger.add_many(examples)

    grouped = ledger.propose_for_sweep(class_id=CLASS_ID, subject="chemie")
    by_id = {
        proposal.candidate_id: proposal
        for proposals in grouped.values()
        for proposal in proposals
    }

    assert by_id["doc44_class_redox_demo"].review_queue == "Class Evolution"
    assert by_id["doc44_class_redox_demo"].target == "teaching_patterns.md"
    assert by_id["doc44_subject_redox_sequence"].review_queue == "Subject Concepts"
    assert by_id["doc44_subject_redox_sequence"].target == "wiki/subjects/chemie.md"
    assert by_id["doc44_teacher_mbb"].review_queue == "Teacher/Copilot Preferences"
    assert by_id["doc44_teacher_mbb"].target == "teacher_profile.md"
    assert by_id["doc44_friday_discovery"].review_queue == "Teacher/Copilot Preferences"
    assert by_id["doc44_friday_discovery"].target == "copilot_profile.md"

    before_lesson = wiki.read_wiki_page(
        f"wiki/classes/{CLASS_ID}/lessons/2026-05-29/lesson_results.md"
    )
    before_subject = wiki.read_wiki_page("wiki/subjects/chemie.md")
    before_user = wiki.read_user_profile()

    applied, skipped, warnings = apply_memory_items(
        wiki,
        CLASS_ID,
        [
            _ApplyItem(p.target, p.section, p.content)
            for p in [
                by_id["doc44_class_redox_demo"],
                by_id["doc44_subject_redox_sequence"],
                by_id["doc44_teacher_mbb"],
                by_id["doc44_friday_discovery"],
            ]
        ],
    )

    assert skipped == []
    assert warnings == []
    assert f"wiki/classes/{CLASS_ID}/memory/teaching_patterns.md" in applied
    assert "wiki/subjects/chemie.md" in applied
    assert "wiki/teacher_profile.md" in applied
    assert f"wiki/classes/{CLASS_ID}/memory/copilot_profile.md" in applied

    teaching_patterns = wiki.read_wiki_page(
        f"wiki/classes/{CLASS_ID}/memory/teaching_patterns.md"
    )
    subject = wiki.read_wiki_page("wiki/subjects/chemie.md")
    user = wiki.read_user_profile()
    copilot = wiki.read_wiki_page(
        f"wiki/classes/{CLASS_ID}/memory/copilot_profile.md"
    )

    assert "9b finally understood redox after metal-displacement demos." in teaching_patterns
    assert subject != before_subject
    assert "always introduce oxidation numbers after electron transfer" in subject
    assert user != before_user
    assert "MBB style" in user
    assert "avoid long discovery phases on Fridays" in copilot
    assert (
        wiki.read_wiki_page(f"wiki/classes/{CLASS_ID}/lessons/2026-05-29/lesson_results.md")
        == before_lesson
    )


def test_memory_sweep_api_proposes_and_updates_candidate_status(client: TestClient):
    plan_base = f"/api/classes/{CLASS_ID}/plan"

    start = client.post(f"{plan_base}/sessions")
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]

    chat = client.post(
        f"{plan_base}/sessions/{session_id}/chat",
        json={"message": "Please draft a concise redox lesson plan."},
    )
    assert chat.status_code == 200, chat.text

    propose = client.post(f"/api/classes/{CLASS_ID}/memory/sweep/propose")
    assert propose.status_code == 200, propose.text
    queues = propose.json()["queues"]
    prefs = queues["Teacher/Copilot Preferences"]
    assert len(prefs) == 1
    candidate = prefs[0]
    assert candidate["target"] == "copilot_profile.md"
    assert candidate["channel"] == "teacher_behavior"
    assert candidate["why_now"] == "Stub isolated sweep review."
    assert isinstance(candidate["current_memory_excerpt"], str)
    assert len(candidate["current_memory_excerpt"]) <= 800

    reject = client.post(
        f"/api/classes/{CLASS_ID}/memory/candidates/{candidate['candidate_id']}/status",
        json={
            "status": "rejected",
            "rejection_reason": "Do not save this copilot preference.",
            "review_batch_id": "sweep_api_test",
        },
    )
    assert reject.status_code == 200, reject.text
    assert reject.json()["status"] == "rejected"

    propose_again = client.post(f"/api/classes/{CLASS_ID}/memory/sweep/propose")
    assert propose_again.status_code == 200, propose_again.text
    next_ids = {
        item["candidate_id"]
        for items in propose_again.json()["queues"].values()
        for item in items
    }
    assert candidate["candidate_id"] not in next_ids


def test_memory_sweep_api_falls_back_when_isolated_proposer_unavailable(
    tmp_path,
    wiki: WikiStore,
):
    from app.api import deps
    from app.main import app

    class FailingSweepAgent(StubAgentRunner):
        async def propose_memory_sweep_cards(
            self,
            class_id: str,
            subject: str,
            grouped_candidates,
            target_excerpts,
            alignment_groups=None,
            validation_error: str = "",
        ):
            raise RuntimeError("offline proposer")

    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    _seed_memory_sweep_examples(ledger)
    agents = FailingSweepAgent(wiki)

    app.dependency_overrides[deps.get_wiki] = lambda: wiki
    app.dependency_overrides[deps.get_agents] = lambda: agents
    app.dependency_overrides[deps.get_memory_candidate_ledger] = lambda: ledger
    try:
        with TestClient(app, raise_server_exceptions=False) as local_client:
            res = local_client.post(f"/api/classes/{CLASS_ID}/memory/sweep/propose")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200, res.text
    body = res.json()
    assert "Memory Sweep card generation unresolved" in body["warnings"][0]
    assert body["queues"]["Class Evolution"][0]["target"] == "teaching_patterns.md"
    assert body["queues"]["Class Evolution"][0]["operation"] == "needs_decision"


def test_memory_sweep_api_accepts_model_consolidated_card(
    tmp_path,
    wiki: WikiStore,
):
    from app.api import deps
    from app.main import app
    class MergingSweepAgent(StubAgentRunner):
        async def align_memory_sweep_candidates(
            self,
            class_id: str,
            subject: str,
            grouped_candidates,
            target_excerpts,
            validation_error: str = "",
        ):
            class_cards = [
                item
                for items in grouped_candidates.values()
                for item in items
                if item["target"] == "teaching_patterns.md"
            ]
            ids = [item["candidate_id"] for item in class_cards]
            return MemorySweepAlignmentOutput(
                alignment_groups=[
                    MemorySweepAlignmentGroupOutput(
                        group_id="group_roles",
                        target="teaching_patterns.md",
                        section="What Worked Well",
                        ledger_candidate_ids=ids,
                        relationship="new_semantic_claim",
                        decision="merge",
                        group_label="structured_group_roles",
                        public_rationale="Two class-learning signals describe the same pattern.",
                    )
                ]
            )

        async def propose_memory_sweep_cards(
            self,
            class_id: str,
            subject: str,
            grouped_candidates,
            target_excerpts,
            alignment_groups=None,
            validation_error: str = "",
        ):
            class_cards = [
                item
                for items in grouped_candidates.values()
                for item in items
                if item["target"] == "teaching_patterns.md"
            ]
            ids = [item["candidate_id"] for item in class_cards]
            first = class_cards[0]
            return MemorySweepProposalOutput(
                cards=[
                    MemorySweepCardOutput(
                        candidate_id=ids[0],
                        source_group_id="group_roles",
                        candidate_ids=ids,
                        signal_count=len(ids),
                        review_queue=first["review_queue"],
                        channel=first["channel"],
                        target=first["target"],
                        section="What Worked Well",
                        content=(
                            "Structured group roles help Chemie 9b handle symbolic "
                            "redox work."
                        ),
                        evidence_summary="Merged repeated group-role signals.",
                        evidence_refs=[],
                        confidence="high",
                        basis="explicit",
                        status="captured",
                        why_now="Two related signals point to the same class pattern.",
                    )
                ],
                warnings=[],
            )

    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    ledger.add_many(
        [
            MemoryCandidateRow(
                id="semantic_group_roles_1",
                created_at="2026-06-22T09:00:00Z",
                updated_at="2026-06-22T09:00:00Z",
                class_id=CLASS_ID,
                subject="chemie",
                workflow="plan",
                session_id="sess_semantic_1",
                turn_index=1,
                channel="class_learning_pattern",
                target="teaching_patterns.md",
                section="What Worked Well",
                candidate_update="Group roles made symbolic redox entry smoother.",
                evidence_summary="Planning session noted group roles helped.",
                evidence_refs=["trace:semantic:1"],
                source="inferred_from_session",
                basis="inferred",
                confidence="medium",
            ),
            MemoryCandidateRow(
                id="semantic_group_roles_2",
                created_at="2026-06-22T09:05:00Z",
                updated_at="2026-06-22T09:05:00Z",
                class_id=CLASS_ID,
                subject="chemie",
                workflow="ingest",
                session_id="sess_semantic_2",
                turn_index=2,
                channel="class_learning_pattern",
                target="teaching_patterns.md",
                section="What Worked Well",
                candidate_update="Assigned roles kept Chemie 9b oriented in notation work.",
                evidence_summary="Lesson reflection repeated the role pattern.",
                evidence_refs=["trace:semantic:2"],
                source="teacher_explicit",
                basis="explicit",
                confidence="high",
            ),
        ]
    )
    agents = MergingSweepAgent(wiki)

    app.dependency_overrides[deps.get_wiki] = lambda: wiki
    app.dependency_overrides[deps.get_agents] = lambda: agents
    app.dependency_overrides[deps.get_memory_candidate_ledger] = lambda: ledger
    try:
        with TestClient(app, raise_server_exceptions=False) as local_client:
            res = local_client.post(f"/api/classes/{CLASS_ID}/memory/sweep/propose")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200, res.text
    cards = res.json()["queues"]["Class Evolution"]
    assert len(cards) == 1
    card = cards[0]
    assert card["candidate_id"] in {
        "semantic_group_roles_1",
        "semantic_group_roles_2",
    }
    assert set(card["candidate_ids"]) == {
        "semantic_group_roles_1",
        "semantic_group_roles_2",
    }
    assert card["signal_count"] == 2
    assert card["target"] == "teaching_patterns.md"
    assert "Structured group roles help" in card["content"]


def test_memory_sweep_api_merges_mbb_and_executive_communication(
    tmp_path,
    wiki: WikiStore,
):
    from app.api import deps
    from app.main import app

    class ExecutiveCommunicationSweepAgent(StubAgentRunner):
        async def align_memory_sweep_candidates(
            self,
            class_id: str,
            subject: str,
            grouped_candidates,
            target_excerpts,
            validation_error: str = "",
        ):
            rows = [
                item
                for items in grouped_candidates.values()
                for item in items
                if item["target"] == "teacher_profile.md"
            ]
            ids = [item["candidate_id"] for item in rows]
            return MemorySweepAlignmentOutput(
                alignment_groups=[
                    MemorySweepAlignmentGroupOutput(
                        group_id="executive_structured_communication",
                            target="teacher_profile.md",
                        section="Communication",
                        ledger_candidate_ids=ids,
                        relationship="new_semantic_claim",
                        decision="merge",
                        group_label="executive_structured_communication",
                        public_rationale="MBB and executive style point to concise structured communication.",
                    )
                ]
            )

        async def propose_memory_sweep_cards(
            self,
            class_id: str,
            subject: str,
            grouped_candidates,
            target_excerpts,
            alignment_groups=None,
            validation_error: str = "",
        ):
            rows = [
                item
                for items in grouped_candidates.values()
                for item in items
                if item["target"] == "teacher_profile.md"
            ]
            ids = [item["candidate_id"] for item in rows]
            first = rows[0]
            return MemorySweepProposalOutput(
                cards=[
                    MemorySweepCardOutput(
                        candidate_id=ids[0],
                        source_group_id="executive_structured_communication",
                        candidate_ids=ids,
                        signal_count=len(ids),
                        review_queue=first["review_queue"],
                        channel=first["channel"],
                            target="teacher_profile.md",
                        section="Communication",
                        content=(
                            "Teacher prefers concise executive-style communication, "
                            "including MBB-style framing when useful."
                        ),
                        evidence_summary=(
                            "Two MBB-style requests and one executive-communication "
                            "request point to the same broader preference."
                        ),
                        evidence_refs=[],
                        confidence="high",
                        basis="explicit",
                        status="captured",
                        status_recommendation="promote",
                        why_now="Repeated communication-style signals are semantically aligned.",
                    )
                ],
                warnings=[],
            )

    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    profile_path = wiki.root / "wiki" / "teacher_profile.md"
    profile = wiki.read_text(profile_path)
    profile = "\n".join(
        line
        for line in profile.splitlines()
        if "executive-style communication" not in line and "MBB" not in line
    )
    wiki.write_text(profile_path, profile)
    ledger.add_many(
        [
            _teacher_behavior_row(
                "mbb_style_1",
                update="Use MBB-style communication for lesson plans.",
                evidence="Teacher asked for MBB-style summaries.",
                created_at="2026-06-22T09:00:00Z",
            ),
            _teacher_behavior_row(
                "mbb_style_2",
                update="Please keep using MBB-style planning summaries.",
                evidence="Teacher repeated the MBB-style preference.",
                created_at="2026-06-22T09:05:00Z",
            ),
            _teacher_behavior_row(
                "executive_style_1",
                update="Use executive-style communication as the standard.",
                evidence="Teacher asked for executive-style communication.",
                created_at="2026-06-22T09:10:00Z",
            ),
        ]
    )
    agents = ExecutiveCommunicationSweepAgent(wiki)

    app.dependency_overrides[deps.get_wiki] = lambda: wiki
    app.dependency_overrides[deps.get_agents] = lambda: agents
    app.dependency_overrides[deps.get_memory_candidate_ledger] = lambda: ledger
    try:
        with TestClient(app, raise_server_exceptions=False) as local_client:
            res = local_client.post(f"/api/classes/{CLASS_ID}/memory/sweep/propose")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200, res.text
    cards = res.json()["queues"]["Teacher/Copilot Preferences"]
    assert len(cards) == 1
    card = cards[0]
    assert card["target"] == "teacher_profile.md"
    assert card["section"] == "Communication"
    assert card["operation"] == "add"
    assert card["status_recommendation"] == "promote"
    assert card["signal_count"] == 3
    assert set(card["candidate_ids"]) == {
        "mbb_style_1",
        "mbb_style_2",
        "executive_style_1",
    }
    assert "executive-style communication" in card["content"]
    assert "MBB-style framing" in card["content"]


def test_memory_sweep_api_repeated_mbb_preamble_is_already_covered(
    tmp_path,
    wiki: WikiStore,
):
    from app.api import deps
    from app.main import app

    wiki.add_user_profile_conclusion(
        "Communication",
        "Teacher prefers concise executive-style communication, including MBB-style framing when useful.",
    )

    class AlreadyCoveredSweepAgent(StubAgentRunner):
        async def align_memory_sweep_candidates(
            self,
            class_id: str,
            subject: str,
            grouped_candidates,
            target_excerpts,
            validation_error: str = "",
        ):
            rows = [
                item
                for items in grouped_candidates.values()
                for item in items
                if item["target"] == "teacher_profile.md"
            ]
            ids = [item["candidate_id"] for item in rows]
            return MemorySweepAlignmentOutput(
                alignment_groups=[
                    MemorySweepAlignmentGroupOutput(
                        group_id="covered_executive_structured_communication",
                            target="teacher_profile.md",
                        section="Communication",
                        ledger_candidate_ids=ids,
                        relationship="already_covered",
                        decision="already_covered",
                        group_label="executive_structured_communication",
                        public_rationale="Current memory already captures the preference.",
                    )
                ]
            )

        async def propose_memory_sweep_cards(
            self,
            class_id: str,
            subject: str,
            grouped_candidates,
            target_excerpts,
            alignment_groups=None,
            validation_error: str = "",
        ):
            assert "executive-style communication" in target_excerpts["teacher_profile.md"]
            rows = [
                item
                for items in grouped_candidates.values()
                for item in items
                if item["target"] == "teacher_profile.md"
            ]
            ids = [item["candidate_id"] for item in rows]
            first = rows[0]
            return MemorySweepProposalOutput(
                cards=[
                    MemorySweepCardOutput(
                        candidate_id=ids[0],
                        source_group_id="covered_executive_structured_communication",
                        candidate_ids=ids,
                        signal_count=len(ids),
                        review_queue=first["review_queue"],
                        channel=first["channel"],
                            target="teacher_profile.md",
                        section="Communication",
                        content=(
                            "Teacher prefers concise executive-style communication, "
                            "including MBB-style framing when useful."
                        ),
                        evidence_summary=(
                            "Repeated prompt preambles match existing profile memory."
                        ),
                        confidence="high",
                        basis="explicit",
                        status="captured",
                        operation="already_covered",
                        status_recommendation="already_covered",
                        why_now="Current teacher_profile.md already contains this communication preference.",
                    )
                ],
                warnings=[],
            )

    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    ledger.add_many(
        [
            _teacher_behavior_row(
                "covered_mbb_preamble_1",
                update="MBB style please.",
                evidence="Teacher used an MBB preamble.",
                created_at="2026-06-22T09:00:00Z",
            ),
            _teacher_behavior_row(
                "covered_mbb_preamble_2",
                update="Use MBB style again for this plan.",
                evidence="Teacher repeated an MBB preamble.",
                created_at="2026-06-22T09:05:00Z",
            ),
        ]
    )
    agents = AlreadyCoveredSweepAgent(wiki)

    app.dependency_overrides[deps.get_wiki] = lambda: wiki
    app.dependency_overrides[deps.get_agents] = lambda: agents
    app.dependency_overrides[deps.get_memory_candidate_ledger] = lambda: ledger
    try:
        with TestClient(app, raise_server_exceptions=False) as local_client:
            propose = local_client.post(f"/api/classes/{CLASS_ID}/memory/sweep/propose")
            assert propose.status_code == 200, propose.text
            card = propose.json()["queues"]["Teacher/Copilot Preferences"][0]
            assert card["operation"] == "already_covered"
            assert card["status_recommendation"] == "already_covered"
            assert set(card["candidate_ids"]) == {
                "covered_mbb_preamble_1",
                "covered_mbb_preamble_2",
            }

            apply = local_client.post(
                f"/api/classes/{CLASS_ID}/memory/sweep/apply",
                json={
                    "review_batch_id": "already_covered_mbb_test",
                    "decisions": [
                        {
                            "card_id": card["card_id"],
                            "action": "already_covered",
                            "target": card["target"],
                            "section": card["section"],
                            "content": card["content"],
                            "candidate_ids": card["candidate_ids"],
                        }
                    ],
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert apply.status_code == 200, apply.text
    body = apply.json()
    assert body["applied_wiki_paths"] == []
    assert set(body["updated_candidate_ids"]) == {
        "covered_mbb_preamble_1",
        "covered_mbb_preamble_2",
    }
    rows = {
        row.id: row.status
        for row in ledger.list_candidates(
            class_id=CLASS_ID,
            subject="chemie",
            statuses=("applied",),
        )
    }
    assert rows == {
        "covered_mbb_preamble_1": "applied",
        "covered_mbb_preamble_2": "applied",
    }


def test_memory_sweep_apply_updates_status_after_successful_write(
    tmp_path,
    wiki: WikiStore,
):
    from app.api import deps
    from app.main import app

    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    ledger.add_many(
        [
            MemoryCandidateRow(
                id="batch_apply_group_roles",
                created_at="2026-06-22T09:00:00Z",
                updated_at="2026-06-22T09:00:00Z",
                class_id=CLASS_ID,
                subject="chemie",
                workflow="ingest",
                session_id="batch_apply_1",
                turn_index=1,
                channel="class_learning_pattern",
                target="teaching_patterns.md",
                section="What Worked Well",
                candidate_update="Group roles helped symbolic redox work.",
                evidence_summary="Approved lesson reflection.",
                evidence_refs=["trace:batch:1"],
                source="teacher_explicit",
                basis="explicit",
                confidence="high",
            ),
            MemoryCandidateRow(
                id="batch_already_covered_mbb",
                created_at="2026-06-22T09:05:00Z",
                updated_at="2026-06-22T09:05:00Z",
                class_id=None,
                subject=None,
                workflow="plan",
                session_id="batch_apply_2",
                turn_index=2,
                channel="teacher_behavior",
                target="user.md",
                section="Communication",
                candidate_update="Teacher repeated MBB style.",
                evidence_summary="Prompt preamble repeated an existing preference.",
                evidence_refs=["trace:batch:2"],
                source="teacher_explicit",
                basis="explicit",
                confidence="high",
            ),
        ]
    )

    app.dependency_overrides[deps.get_wiki] = lambda: wiki
    app.dependency_overrides[deps.get_agents] = lambda: StubAgentRunner(wiki)
    app.dependency_overrides[deps.get_memory_candidate_ledger] = lambda: ledger
    try:
        with TestClient(app, raise_server_exceptions=False) as local_client:
            propose = local_client.post(f"/api/classes/{CLASS_ID}/memory/sweep/propose")
            assert propose.status_code == 200, propose.text
            before_rows = {
                row.id: row.status
                for row in ledger.list_candidates(class_id=CLASS_ID, subject="chemie")
            }
            assert before_rows["batch_apply_group_roles"] == "captured"
            assert before_rows["batch_already_covered_mbb"] == "captured"

            res = local_client.post(
                f"/api/classes/{CLASS_ID}/memory/sweep/apply",
                json={
                    "review_batch_id": "batch_apply_test",
                    "decisions": [
                        {
                            "card_id": "card_group_roles",
                            "action": "apply",
                            "target": "teaching_patterns.md",
                            "section": "What Worked Well",
                            "content": "Group roles help Chemie 9b handle symbolic redox work.",
                            "candidate_ids": ["batch_apply_group_roles"],
                        },
                        {
                            "card_id": "card_mbb_covered",
                            "action": "already_covered",
                            "target": "user.md",
                            "section": "Communication",
                            "content": "",
                            "candidate_ids": ["batch_already_covered_mbb"],
                        },
                    ],
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200, res.text
    body = res.json()
    assert f"wiki/classes/{CLASS_ID}/memory/teaching_patterns.md" in body["applied_wiki_paths"]
    assert set(body["updated_candidate_ids"]) == {
        "batch_apply_group_roles",
        "batch_already_covered_mbb",
    }
    rows = {
        row.id: row
        for row in ledger.list_candidates(
            class_id=CLASS_ID,
            subject="chemie",
            statuses=("applied",),
        )
    }
    assert set(rows) == {"batch_apply_group_roles", "batch_already_covered_mbb"}
    teaching_patterns = wiki.read_wiki_page(
        f"wiki/classes/{CLASS_ID}/memory/teaching_patterns.md"
    )
    assert "Group roles help Chemie 9b handle symbolic redox work." in teaching_patterns


def test_memory_sweep_apply_unsupported_write_leaves_status_open(
    tmp_path,
    wiki: WikiStore,
):
    from app.api import deps
    from app.main import app

    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    ledger.add(
        MemoryCandidateRow(
            id="review_only_canonical",
            created_at="2026-06-22T09:00:00Z",
            updated_at="2026-06-22T09:00:00Z",
            class_id=CLASS_ID,
            subject="chemie",
            workflow="memory_sweep",
            session_id="review_only",
            turn_index=1,
            channel="wiki_lint",
            target="canonical_wiki",
            section="General",
            candidate_update="Canonical wiki issue should be reviewed only.",
            evidence_summary="Review-only finding.",
            evidence_refs=["trace:review_only:1"],
            source="approved_wiki",
            basis="explicit",
            confidence="high",
        )
    )

    app.dependency_overrides[deps.get_wiki] = lambda: wiki
    app.dependency_overrides[deps.get_memory_candidate_ledger] = lambda: ledger
    try:
        with TestClient(app, raise_server_exceptions=False) as local_client:
            res = local_client.post(
                f"/api/classes/{CLASS_ID}/memory/sweep/apply",
                json={
                    "decisions": [
                        {
                            "card_id": "card_review_only",
                            "action": "apply",
                            "target": "canonical_wiki",
                            "section": "General",
                            "content": "Should not be written.",
                            "candidate_ids": ["review_only_canonical"],
                        }
                    ],
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["applied_wiki_paths"] == []
    assert body["updated_candidate_ids"] == []
    assert body["skipped"] == ["unsupported target: canonical_wiki"]
    rows = ledger.list_candidates(class_id=CLASS_ID, subject="chemie")
    assert rows[0].status == "captured"


def test_memory_sweep_apply_failed_adjust_leaves_status_open(
    tmp_path,
    wiki: WikiStore,
):
    from app.api import deps
    from app.main import app

    wiki.add_user_profile_conclusion("Communication", "Teacher prefers MBB-style framing.")
    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    ledger.add(
        _teacher_behavior_row(
            "adjust_route_fail_1",
            update="Use executive-style communication.",
            evidence="Teacher asked to broaden a communication preference.",
            created_at="2026-06-22T09:00:00Z",
        )
    )

    app.dependency_overrides[deps.get_wiki] = lambda: wiki
    app.dependency_overrides[deps.get_memory_candidate_ledger] = lambda: ledger
    try:
        with TestClient(app, raise_server_exceptions=False) as local_client:
            res = local_client.post(
                f"/api/classes/{CLASS_ID}/memory/sweep/apply",
                json={
                    "decisions": [
                        {
                            "card_id": "card_adjust_fail",
                            "action": "apply",
                            "target": "user.md",
                            "section": "Communication",
                            "content": "Teacher prefers concise executive-style communication.",
                            "operation": "adjust",
                            "replaces_content": "Teacher prefers missing wording.",
                            "candidate_ids": ["adjust_route_fail_1"],
                        }
                    ],
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["applied_wiki_paths"] == []
    assert body["updated_candidate_ids"] == []
    assert any("replaces_content was not found" in warning for warning in body["warnings"])
    rows = ledger.list_candidates(class_id=CLASS_ID, subject="chemie")
    assert rows[0].status == "captured"


@pytest.mark.anyio
async def test_plan_chat_persists_runtime_candidates_to_sqlite(tmp_path, wiki: WikiStore):
    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    service = PlanService(
        wiki=wiki,
        agents=StubAgentRunner(wiki),
        memory_candidate_ledger=ledger,
    )

    session = await service.start_session(CLASS_ID)
    response = await service.chat(
        session.session_id,
        "Please draft a concise redox lesson plan.",
    )

    assert response.memory_candidates
    rows = ledger.list_candidates(class_id=CLASS_ID, subject="chemie")
    assert len(rows) == 1
    row = rows[0]
    assert row.workflow == "plan"
    assert row.session_id == session.session_id
    assert row.class_id == CLASS_ID
    assert row.channel == "teacher_behavior"
    assert row.target == "copilot_profile.md"
    assert "Draft early" in row.candidate_update


@pytest.mark.anyio
async def test_ingest_chat_persists_runtime_candidates_to_sqlite(tmp_path, wiki: WikiStore):
    ledger = MemoryCandidateLedger(tmp_path / "memory_candidates.sqlite")
    ledger.initialize()
    service = IngestService(
        wiki=wiki,
        agents=StubAgentRunner(wiki),
        memory_candidate_ledger=ledger,
    )

    session = await service.start_session(CLASS_ID)
    response = await service.chat(
        session.session_id,
        "We covered common anions today and misconceptions surfaced early.",
    )

    assert response.memory_candidates
    rows = ledger.list_candidates(class_id=CLASS_ID, subject="chemie")
    assert len(rows) == 1
    row = rows[0]
    assert row.workflow == "ingest"
    assert row.session_id == session.session_id
    assert row.class_id == CLASS_ID
    assert row.channel == "class_learning_pattern"
    assert row.target == "teaching_patterns.md"
    assert "Short diagnostic checks" in row.candidate_update
