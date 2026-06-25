"""Memory Sweep review grouping and consolidation helpers.

This module is the slow review layer between the candidate ledger and curated
wiki memory. The ledger preserves every evidence row; sweep turns related rows
into teacher-reviewable cards without writing memory.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Iterable

from app.services.memory_candidate_ledger import MemoryCandidateRow
from app.teacher_agent.memory_targets import (
    is_supported_runtime_target,
    memory_channel_for_target,
)
from app.teacher_agent.wiki_store import WikiStore


QUEUE_BY_CHANNEL = {
    "teacher_behavior": "Teacher/Copilot Preferences",
    "class_evolution": "Class Evolution",
    "class_learning_pattern": "Class Evolution",
    "subject_concept": "Subject Concepts",
    "wiki_lint": "Wiki Review",
    "memory_sweep": "Memory Sweep",
}

SWEEP_PACKET_PROPOSAL_LIMIT = 40
SWEEP_OPERATIONS = {
    "add",
    "adjust",
    "already_covered",
    "reject_low_signal",
    "needs_decision",
}
SWEEP_STATUS_RECOMMENDATIONS = {
    "promote",
    "already_covered",
    "reject_low_signal",
    "needs_decision",
}
OPERATION_TO_STATUS_RECOMMENDATION = {
    "add": "promote",
    "adjust": "promote",
    "already_covered": "already_covered",
    "reject_low_signal": "reject_low_signal",
    "needs_decision": "needs_decision",
}
STATUS_RECOMMENDATION_TO_OPERATION = {
    "promote": "add",
    "already_covered": "already_covered",
    "reject_low_signal": "reject_low_signal",
    "needs_decision": "needs_decision",
}
ALIGNMENT_RELATIONSHIPS = {
    "new_semantic_claim",
    "broadens_existing_memory",
    "already_covered",
    "possible_conflict",
    "one_off_or_low_signal",
    "scoped_exception",
}
ALIGNMENT_DECISIONS = {
    "merge",
    "adjust_existing",
    "already_covered",
    "needs_decision",
    "reject_low_signal",
}
DECISION_TO_OPERATION = {
    "merge": "add",
    "adjust_existing": "adjust",
    "already_covered": "already_covered",
    "needs_decision": "needs_decision",
    "reject_low_signal": "reject_low_signal",
}


@dataclass(frozen=True)
class MemorySweepProposal:
    candidate_id: str
    candidate_ids: list[str]
    review_queue: str
    channel: str
    target: str
    section: str
    content: str
    evidence_summary: str
    evidence_refs: list[str]
    confidence: str
    basis: str
    status: str
    signal_count: int = 1
    current_memory_excerpt: str = ""


@dataclass(frozen=True)
class MemorySweepReviewCard:
    card_id: str
    source_group_id: str
    candidate_id: str
    candidate_ids: list[str]
    review_queue: str
    channel: str
    target: str
    section: str
    content: str
    evidence_summary: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    confidence: str = "low"
    basis: str = "inferred"
    status: str = "captured"
    relationship: str = ""
    group_label: str = ""
    public_rationale: str = ""
    operation: str = "add"
    replaces_content: str = ""
    status_recommendation: str = "promote"
    why_now: str = ""
    current_memory_excerpt: str = ""
    signal_count: int = 1


@dataclass(frozen=True)
class MemorySweepPacket:
    packet_id: str
    target: str
    review_queue: str
    proposals: list[MemorySweepProposal]
    current_memory_excerpt: str


@dataclass(frozen=True)
class MemorySweepAlignmentGroup:
    group_id: str
    target: str
    section: str
    ledger_candidate_ids: list[str]
    matched_memory_item_ids: list[str] = field(default_factory=list)
    relationship: str = "new_semantic_claim"
    decision: str = "merge"
    group_label: str = ""
    public_rationale: str = ""


def build_sweep_proposals(
    candidates: Iterable[MemoryCandidateRow],
) -> dict[str, list[MemorySweepProposal]]:
    """Group open ledger rows into review proposals.

    Matching cluster keys mean the backend already knows these rows are the same
    semantic thread. Rows without a cluster key stay separate and can still be
    consolidated by the isolated weekly proposer.
    """
    clusters: dict[tuple[str, str, str, str, str], list[MemoryCandidateRow]] = {}
    singles: list[list[MemoryCandidateRow]] = []
    for candidate in candidates:
        queue = queue_for_channel(candidate.channel)
        if candidate.cluster_key:
            key = (
                queue,
                candidate.channel,
                candidate.target,
                candidate.section,
                candidate.cluster_key,
            )
            clusters.setdefault(key, []).append(candidate)
        else:
            singles.append([candidate])

    grouped: dict[str, list[MemorySweepProposal]] = {}
    for rows in list(clusters.values()) + singles:
        proposal = _proposal_from_rows(rows)
        grouped.setdefault(proposal.review_queue, []).append(proposal)
    return grouped


def sweep_proposer_payload(
    grouped: dict[str, list[MemorySweepProposal]],
) -> dict[str, list[dict[str, Any]]]:
    return {
        queue: [
            {
                "candidate_id": p.candidate_id,
                "candidate_ids": list(p.candidate_ids),
                "signal_count": p.signal_count,
                "review_queue": p.review_queue,
                "channel": p.channel,
                "target": p.target,
                "section": p.section,
                "content": p.content,
                "evidence_summary": p.evidence_summary,
                "evidence_refs": list(p.evidence_refs),
                "confidence": p.confidence,
                "basis": p.basis,
                "status": p.status,
            }
            for p in proposals
        ]
        for queue, proposals in grouped.items()
    }


def build_sweep_packets(
    grouped: dict[str, list[MemorySweepProposal]],
    target_excerpts: dict[str, str],
) -> list[MemorySweepPacket]:
    """Build bounded target/scope packets for the isolated proposer.

    Packets are grouped by hard target and queue. Semantic grouping remains an
    LLM responsibility; this step is only token control and context selection.
    """
    by_key: dict[tuple[str, str], list[MemorySweepProposal]] = {}
    for proposals in grouped.values():
        for proposal in proposals:
            by_key.setdefault((proposal.review_queue, proposal.target), []).append(proposal)
    packets: list[MemorySweepPacket] = []
    for (queue, target), proposals in sorted(by_key.items()):
        excerpt = _current_excerpt(target_excerpts, target)
        for index, chunk in enumerate(_chunks(proposals, SWEEP_PACKET_PROPOSAL_LIMIT)):
            packet_id = _card_id(
                f"packet-{index}",
                target,
                [p.candidate_id for p in chunk],
            )
            packets.append(
                MemorySweepPacket(
                    packet_id=packet_id,
                    target=target,
                    review_queue=queue,
                    proposals=[
                        MemorySweepProposal(
                            candidate_id=p.candidate_id,
                            candidate_ids=list(p.candidate_ids),
                            review_queue=p.review_queue,
                            channel=p.channel,
                            target=p.target,
                            section=p.section,
                            content=p.content,
                            evidence_summary=p.evidence_summary,
                            evidence_refs=list(p.evidence_refs),
                            confidence=p.confidence,
                            basis=p.basis,
                            status=p.status,
                            signal_count=p.signal_count,
                            current_memory_excerpt=excerpt,
                        )
                        for p in chunk
                    ],
                    current_memory_excerpt=excerpt,
                )
            )
    return packets


def sweep_packet_payloads(
    packets: list[MemorySweepPacket],
) -> dict[str, list[dict[str, Any]]]:
    """Return the existing proposer payload shape, now packeted by target."""
    return {
        packet.packet_id: [
            {
                "candidate_id": p.candidate_id,
                "candidate_ids": list(p.candidate_ids),
                "signal_count": p.signal_count,
                "review_queue": p.review_queue,
                "channel": p.channel,
                "target": p.target,
                "section": p.section,
                "content": p.content,
                "evidence_summary": p.evidence_summary,
                "evidence_refs": list(p.evidence_refs),
                "confidence": p.confidence,
                "basis": p.basis,
                "status": p.status,
                "current_memory_excerpt": p.current_memory_excerpt,
                "allowed_operations": [
                    "add",
                    "adjust",
                    "already_covered",
                    "reject_low_signal",
                    "needs_decision",
                ],
                "allowed_status_recommendations": [
                    "promote",
                    "already_covered",
                    "needs_decision",
                    "reject_low_signal",
                ],
            }
            for p in packet.proposals
        ]
        for packet in packets
    }


def sweep_targets(grouped: dict[str, list[MemorySweepProposal]]) -> set[str]:
    return {p.target for proposals in grouped.values() for p in proposals}


def memory_sweep_target_excerpts(
    wiki: WikiStore,
    class_id: str,
    targets: set[str],
) -> dict[str, str]:
    excerpts: dict[str, str] = {}
    for target in sorted(targets):
        if target in {"user.md", "teacher_profile.md"}:
            excerpts[target] = wiki.read_user_profile()[:1600]
        elif target in {"copilot.md", "copilot_profile.md"}:
            excerpts[target] = wiki.read_copilot_profile(class_id)[:1600]
        elif target in {
            "class_state.md",
            "planning_brief.md",
            "taught_so_far.md",
            "teaching_patterns.md",
        }:
            key = target.removesuffix(".md")
            path = wiki.memory_paths(class_id).get(key)
            if path:
                excerpts[target] = wiki.read_text(path)[:1600]
        elif target.startswith("wiki/subjects/"):
            excerpts[target] = wiki.read_wiki_page(target, max_chars=1600)
        elif target == "canonical_wiki":
            excerpts[target] = "(review-only canonical wiki issue)"
    return excerpts


def fallback_review_cards(
    grouped: dict[str, list[MemorySweepProposal]],
    *,
    target_excerpts: dict[str, str] | None = None,
    why_now: str = "",
) -> dict[str, list[MemorySweepReviewCard]]:
    return {
        queue: [
            review_card_from_proposal(
                p,
                target_excerpts=target_excerpts or {},
                why_now=why_now,
            )
            for p in proposals
        ]
        for queue, proposals in grouped.items()
    }


def sanitize_sweep_output(
    grouped: dict[str, list[MemorySweepProposal]],
    output: Any,
    target_excerpts: dict[str, str],
) -> tuple[dict[str, list[MemorySweepReviewCard]], list[str]]:
    """Accept model-polished cards while preserving ledger ownership.

    The proposer may consolidate several proposals by returning multiple known
    candidate IDs. Unknown IDs and cross-target merges are ignored with warnings.
    Any proposal not represented by a returned card is preserved as a fallback.
    """
    proposal_by_id = _proposal_lookup(grouped)
    cards_by_queue: dict[str, list[MemorySweepReviewCard]] = {}
    warnings = list(getattr(output, "warnings", []) or [])
    represented_ids: set[str] = set()
    seen_card_ids: set[str] = set()

    for card in getattr(output, "cards", []) or []:
        raw_ids = _card_candidate_ids(card)
        known_ids = [candidate_id for candidate_id in raw_ids if candidate_id in proposal_by_id]
        for candidate_id in raw_ids:
            if candidate_id not in proposal_by_id:
                warnings.append(f"ignored unknown Memory Sweep candidate id: {candidate_id}")
        if not known_ids:
            continue

        base = proposal_by_id[known_ids[0]]
        compatible_ids = [
            candidate_id
            for candidate_id in known_ids
            if _is_compatible_merge(base, proposal_by_id[candidate_id])
        ]
        ignored_ids = set(known_ids) - set(compatible_ids)
        for candidate_id in sorted(ignored_ids):
            warnings.append(
                "ignored incompatible Memory Sweep consolidation id: "
                f"{candidate_id}"
            )
        if not compatible_ids:
            continue

        supporting_ids = _expanded_supporting_ids(base, compatible_ids, proposal_by_id)
        target = _card_target(card, base.target, warnings)
        operation = _card_operation(card, warnings)
        replaces_content = (getattr(card, "replaces_content", "") or "").strip()
        if operation == "adjust" and not replaces_content:
            warnings.append(
                "downgraded Memory Sweep adjust card without replaces_content "
                f"for candidate id: {base.candidate_id}"
            )
            operation = "needs_decision"
        status_recommendation = _status_recommendation(card, operation)
        card_id = (getattr(card, "card_id", "") or "").strip() or _card_id(
            target,
            (getattr(card, "section", "") or base.section).strip() or base.section,
            supporting_ids,
        )
        if card_id in seen_card_ids:
            continue
        seen_card_ids.add(card_id)
        represented_ids.update(supporting_ids)

        queue = queue_for_channel(memory_channel_for_target(target))
        cards_by_queue.setdefault(queue, []).append(
            review_card_from_proposal(
                _merged_proposal(base, supporting_ids, proposal_by_id),
                target_excerpts=target_excerpts,
                card_id=card_id,
                target=target,
                review_queue=queue,
                content=(getattr(card, "content", "") or "").strip(),
                section=(getattr(card, "section", "") or "").strip(),
                operation=operation,
                replaces_content=replaces_content if operation == "adjust" else "",
                status_recommendation=status_recommendation,
                why_now=(getattr(card, "why_now", "") or "").strip(),
            )
        )

    for queue, proposals in grouped.items():
        for proposal in proposals:
            if represented_ids.isdisjoint(proposal.candidate_ids):
                cards_by_queue.setdefault(queue, []).append(
                    review_card_from_proposal(
                        proposal,
                        target_excerpts=target_excerpts,
                        why_now="Included from deterministic ledger grouping.",
                    )
                )
                represented_ids.update(proposal.candidate_ids)
    return cards_by_queue, warnings


def validate_alignment_output(
    packet: MemorySweepPacket,
    output: Any,
) -> list[MemorySweepAlignmentGroup]:
    """Validate complete one-time candidate coverage for a packet."""
    proposal_by_id = _packet_proposal_lookup(packet)
    input_ids = set(proposal_by_id)
    groups: list[MemorySweepAlignmentGroup] = []
    assigned_ids: list[str] = []
    seen_group_ids: set[str] = set()

    raw_groups = list(getattr(output, "alignment_groups", []) or [])
    if not raw_groups:
        raise ValueError("alignment output contained no groups")

    for index, raw_group in enumerate(raw_groups):
        group_id = str(getattr(raw_group, "group_id", "") or f"group_{index + 1}").strip()
        if not group_id:
            raise ValueError("alignment group is missing group_id")
        if group_id in seen_group_ids:
            raise ValueError(f"duplicate alignment group_id: {group_id}")
        seen_group_ids.add(group_id)

        raw_ids = [
            str(candidate_id).strip()
            for candidate_id in (getattr(raw_group, "ledger_candidate_ids", []) or [])
            if str(candidate_id).strip()
        ]
        if len(raw_ids) != len(set(raw_ids)):
            raise ValueError(f"alignment group {group_id} assigned duplicate candidate ids")
        ids = _unique(raw_ids)
        if not ids:
            raise ValueError(f"alignment group {group_id} has no ledger_candidate_ids")
        unknown = sorted(set(ids) - input_ids)
        if unknown:
            raise ValueError(
                f"alignment group {group_id} used unknown candidate ids: {unknown}"
            )

        target = str(getattr(raw_group, "target", "") or packet.target).strip()
        section = str(getattr(raw_group, "section", "") or "").strip()
        relationship = str(
            getattr(raw_group, "relationship", "") or "new_semantic_claim"
        ).strip()
        decision = str(getattr(raw_group, "decision", "") or "merge").strip()
        if relationship not in ALIGNMENT_RELATIONSHIPS:
            raise ValueError(
                f"alignment group {group_id} used unsupported relationship: {relationship}"
            )
        if decision not in ALIGNMENT_DECISIONS:
            raise ValueError(
                f"alignment group {group_id} used unsupported decision: {decision}"
            )
        if not is_supported_runtime_target(target):
            raise ValueError(f"alignment group {group_id} used unsupported target: {target}")
        if target != packet.target:
            raise ValueError(
                f"alignment group {group_id} changed packet target from {packet.target} to {target}"
            )
        for candidate_id in ids:
            proposal = proposal_by_id[candidate_id]
            if proposal.target != target:
                raise ValueError(
                    f"alignment group {group_id} target does not match candidate {candidate_id}"
                )
            if proposal.section != section:
                raise ValueError(
                    f"alignment group {group_id} section does not match candidate {candidate_id}"
                )

        assigned_ids.extend(ids)
        groups.append(
            MemorySweepAlignmentGroup(
                group_id=group_id,
                target=target,
                section=section,
                ledger_candidate_ids=ids,
                matched_memory_item_ids=[
                    str(value).strip()
                    for value in (getattr(raw_group, "matched_memory_item_ids", []) or [])
                    if str(value).strip()
                ],
                relationship=relationship,
                decision=decision,
                group_label=str(getattr(raw_group, "group_label", "") or "").strip(),
                public_rationale=str(
                    getattr(raw_group, "public_rationale", "") or ""
                ).strip(),
            )
        )

    if len(assigned_ids) != len(set(assigned_ids)):
        raise ValueError("alignment assigned a candidate_id more than once")
    assigned_set = set(assigned_ids)
    if assigned_set != input_ids:
        missing = sorted(input_ids - assigned_set)
        extra = sorted(assigned_set - input_ids)
        raise ValueError(f"invalid alignment coverage: missing={missing}, extra={extra}")
    return groups


def alignment_groups_payload(groups: list[MemorySweepAlignmentGroup]) -> list[dict[str, Any]]:
    return [
        {
            "group_id": group.group_id,
            "target": group.target,
            "section": group.section,
            "ledger_candidate_ids": list(group.ledger_candidate_ids),
            "matched_memory_item_ids": list(group.matched_memory_item_ids),
            "relationship": group.relationship,
            "decision": group.decision,
            "group_label": group.group_label,
            "public_rationale": group.public_rationale,
        }
        for group in groups
    ]


def validate_cards_against_alignment(
    packet: MemorySweepPacket,
    output: Any,
    alignment_groups: list[MemorySweepAlignmentGroup],
    target_excerpts: dict[str, str],
) -> tuple[list[MemorySweepReviewCard], list[str]]:
    """Validate card output against already-validated alignment groups."""
    proposal_by_id = _packet_proposal_lookup(packet)
    group_by_id = {group.group_id: group for group in alignment_groups}
    remaining_group_ids = set(group_by_id)
    warnings = list(getattr(output, "warnings", []) or [])
    cards: list[MemorySweepReviewCard] = []
    seen_card_ids: set[str] = set()

    for raw_card in getattr(output, "cards", []) or []:
        group = _card_alignment_group(raw_card, alignment_groups)
        if group is None:
            raise ValueError("card missing source_group_id or exact group candidate_ids")
        if group.group_id not in remaining_group_ids:
            raise ValueError(f"duplicate or unknown card source_group_id: {group.group_id}")
        remaining_group_ids.remove(group.group_id)

        card_ids = _card_candidate_ids(raw_card)
        if set(card_ids) != set(group.ledger_candidate_ids):
            raise ValueError(
                f"card {group.group_id} candidate_ids do not match alignment group"
            )
        target = _card_target(raw_card, group.target, warnings)
        section = (getattr(raw_card, "section", "") or group.section).strip()
        if target != group.target:
            raise ValueError(f"card {group.group_id} target does not match alignment group")
        if section != group.section:
            raise ValueError(f"card {group.group_id} section does not match alignment group")

        expected_operation = DECISION_TO_OPERATION[group.decision]
        operation = _card_operation(raw_card, warnings)
        if operation != expected_operation:
            raise ValueError(
                f"card {group.group_id} operation {operation} does not match decision {group.decision}"
            )
        replaces_content = (getattr(raw_card, "replaces_content", "") or "").strip()
        if operation == "adjust":
            if not replaces_content:
                raise ValueError(f"card {group.group_id} adjust missing replaces_content")
            if not _excerpt_has_bullet(target_excerpts.get(group.target, ""), replaces_content):
                raise ValueError(
                    f"card {group.group_id} replaces_content not found in current memory excerpt"
                )

        card_id = (getattr(raw_card, "card_id", "") or "").strip() or _card_id(
            group.target,
            group.section,
            group.ledger_candidate_ids,
        )
        if card_id in seen_card_ids:
            raise ValueError(f"duplicate card_id: {card_id}")
        seen_card_ids.add(card_id)
        proposal = _merged_proposal(
            proposal_by_id[group.ledger_candidate_ids[0]],
            group.ledger_candidate_ids,
            proposal_by_id,
        )
        cards.append(
            review_card_from_proposal(
                proposal,
                target_excerpts=target_excerpts,
                card_id=card_id,
                source_group_id=group.group_id,
                target=group.target,
                review_queue=queue_for_channel(memory_channel_for_target(group.target)),
                content=(getattr(raw_card, "content", "") or "").strip(),
                section=group.section,
                relationship=group.relationship,
                group_label=group.group_label,
                public_rationale=group.public_rationale,
                operation=operation,
                replaces_content=replaces_content if operation == "adjust" else "",
                status_recommendation=OPERATION_TO_STATUS_RECOMMENDATION[operation],
                why_now=(getattr(raw_card, "why_now", "") or group.public_rationale).strip(),
            )
        )

    if remaining_group_ids:
        raise ValueError(f"missing cards for alignment groups: {sorted(remaining_group_ids)}")
    return cards, warnings


def unresolved_cards_from_packet(
    packet: MemorySweepPacket,
    target_excerpts: dict[str, str],
    reason: str,
) -> list[MemorySweepReviewCard]:
    cards: list[MemorySweepReviewCard] = []
    for proposal in packet.proposals:
        cards.append(
            review_card_from_proposal(
                proposal,
                target_excerpts=target_excerpts,
                source_group_id=f"unresolved_{proposal.candidate_id}",
                operation="needs_decision",
                status_recommendation="needs_decision",
                relationship="possible_conflict",
                group_label="unresolved_alignment",
                public_rationale="Memory Sweep alignment could not be validated.",
                why_now=f"Unresolved Memory Sweep alignment: {reason}",
            )
        )
    return cards


def grouped_review_cards(
    cards: Iterable[MemorySweepReviewCard],
) -> dict[str, list[MemorySweepReviewCard]]:
    grouped: dict[str, list[MemorySweepReviewCard]] = {}
    for card in cards:
        grouped.setdefault(card.review_queue, []).append(card)
    return grouped


def review_card_from_proposal(
    proposal: MemorySweepProposal,
    *,
    target_excerpts: dict[str, str],
    card_id: str = "",
    source_group_id: str = "",
    target: str = "",
    review_queue: str = "",
    content: str = "",
    section: str = "",
    relationship: str = "",
    group_label: str = "",
    public_rationale: str = "",
    operation: str = "add",
    replaces_content: str = "",
    status_recommendation: str = "promote",
    why_now: str = "",
) -> MemorySweepReviewCard:
    candidate_ids = list(proposal.candidate_ids)
    final_target = target or proposal.target
    return MemorySweepReviewCard(
        card_id=card_id or _card_id(final_target, proposal.section, candidate_ids),
        source_group_id=source_group_id,
        candidate_id=proposal.candidate_id,
        candidate_ids=candidate_ids,
        review_queue=review_queue or proposal.review_queue,
        channel=memory_channel_for_target(final_target),
        target=final_target,
        section=section or proposal.section,
        content=content or proposal.content,
        evidence_summary=proposal.evidence_summary,
        evidence_refs=list(proposal.evidence_refs),
        confidence=proposal.confidence,
        basis=proposal.basis,
        status=proposal.status,
        relationship=relationship,
        group_label=group_label,
        public_rationale=public_rationale,
        operation=operation,
        replaces_content=replaces_content,
        status_recommendation=status_recommendation,
        why_now=why_now,
        current_memory_excerpt=_current_excerpt(target_excerpts, final_target),
        signal_count=proposal.signal_count,
    )


def queue_for_channel(channel: str) -> str:
    return QUEUE_BY_CHANNEL.get(channel, "Memory Sweep")


def _proposal_from_rows(rows: list[MemoryCandidateRow]) -> MemorySweepProposal:
    primary = _primary_sweep_row(rows)
    candidate_ids = _candidate_ids(primary, rows)
    return MemorySweepProposal(
        candidate_id=primary.id,
        candidate_ids=candidate_ids,
        review_queue=queue_for_channel(primary.channel),
        channel=primary.channel,
        target=primary.target,
        section=primary.section,
        content=primary.candidate_update,
        evidence_summary=_merged_row_evidence_summary(rows),
        evidence_refs=_merged_row_evidence_refs(rows),
        confidence=primary.confidence,
        basis=primary.basis,
        status=primary.status,
        signal_count=len(candidate_ids),
    )


def _primary_sweep_row(rows: list[MemoryCandidateRow]) -> MemoryCandidateRow:
    return max(
        rows,
        key=lambda row: (
            _confidence_rank(row.confidence),
            _basis_rank(row.basis),
            len(row.evidence_refs),
            row.created_at,
            row.id,
        ),
    )


def _candidate_ids(primary: MemoryCandidateRow, rows: list[MemoryCandidateRow]) -> list[str]:
    ordered = [primary.id]
    ordered.extend(row.id for row in rows if row.id != primary.id)
    return ordered


def _proposal_lookup(
    grouped: dict[str, list[MemorySweepProposal]],
) -> dict[str, MemorySweepProposal]:
    lookup: dict[str, MemorySweepProposal] = {}
    for proposals in grouped.values():
        for proposal in proposals:
            for candidate_id in proposal.candidate_ids:
                lookup[candidate_id] = proposal
    return lookup


def _packet_proposal_lookup(packet: MemorySweepPacket) -> dict[str, MemorySweepProposal]:
    lookup: dict[str, MemorySweepProposal] = {}
    for proposal in packet.proposals:
        for candidate_id in proposal.candidate_ids:
            lookup[candidate_id] = proposal
    return lookup


def _card_alignment_group(
    card: Any,
    groups: list[MemorySweepAlignmentGroup],
) -> MemorySweepAlignmentGroup | None:
    source_group_id = str(getattr(card, "source_group_id", "") or "").strip()
    if source_group_id:
        for group in groups:
            if group.group_id == source_group_id:
                return group
        return None
    card_ids = set(_card_candidate_ids(card))
    for group in groups:
        if card_ids == set(group.ledger_candidate_ids):
            return group
    return None


def _card_candidate_ids(card: Any) -> list[str]:
    ids: list[str] = []
    candidate_id = str(getattr(card, "candidate_id", "") or "").strip()
    if candidate_id:
        ids.append(candidate_id)
    extra_ids = getattr(card, "candidate_ids", []) or []
    if isinstance(extra_ids, list):
        ids.extend(str(candidate_id).strip() for candidate_id in extra_ids)
    return _unique([candidate_id for candidate_id in ids if candidate_id])


def _excerpt_has_bullet(excerpt: str, bullet_content: str) -> bool:
    wanted = _normalize_bullet_text(bullet_content)
    for line in (excerpt or "").splitlines():
        if not line.strip().startswith("-"):
            continue
        if _normalize_bullet_text(line) == wanted:
            return True
    return False


def _normalize_bullet_text(value: str) -> str:
    text = " ".join((value or "").strip().split())
    if text.startswith("- "):
        text = " ".join(text[2:].strip().split())
    return text


def _card_operation(card: Any, warnings: list[str]) -> str:
    value = str(getattr(card, "operation", "") or "").strip()
    if value == "add" and not _field_was_provided(card, "operation"):
        value = ""
    if value:
        if value in SWEEP_OPERATIONS:
            return value
        warnings.append(f"ignored unsupported Memory Sweep operation: {value}")
        return "needs_decision"
    status = str(getattr(card, "status_recommendation", "") or "promote").strip()
    return STATUS_RECOMMENDATION_TO_OPERATION.get(status, "needs_decision")


def _field_was_provided(card: Any, field_name: str) -> bool:
    fields_set = getattr(card, "model_fields_set", None)
    if fields_set is None:
        fields_set = getattr(card, "__fields_set__", set())
    return field_name in fields_set


def _status_recommendation(card: Any, operation: str) -> str:
    value = str(getattr(card, "status_recommendation", "") or "").strip()
    if operation not in {"add", "adjust"} and value == "promote":
        return OPERATION_TO_STATUS_RECOMMENDATION.get(operation, "needs_decision")
    if value in SWEEP_STATUS_RECOMMENDATIONS:
        return value
    return OPERATION_TO_STATUS_RECOMMENDATION.get(operation, "needs_decision")


def _card_target(card: Any, fallback: str, warnings: list[str]) -> str:
    target = str(getattr(card, "target", "") or fallback).strip()
    if is_supported_runtime_target(target):
        return target
    warnings.append(f"ignored unsupported Memory Sweep target: {target}")
    return fallback


def _is_compatible_merge(
    base: MemorySweepProposal,
    other: MemorySweepProposal,
) -> bool:
    return (
        base.review_queue == other.review_queue
        and base.channel == other.channel
        and base.target == other.target
    )


def _expanded_supporting_ids(
    base: MemorySweepProposal,
    compatible_ids: list[str],
    proposal_by_id: dict[str, MemorySweepProposal],
) -> list[str]:
    ids: list[str] = []
    for candidate_id in [base.candidate_id, *compatible_ids]:
        proposal = proposal_by_id[candidate_id]
        ids.extend(proposal.candidate_ids)
    return _unique(ids)


def _merged_proposal(
    base: MemorySweepProposal,
    supporting_ids: list[str],
    proposal_by_id: dict[str, MemorySweepProposal],
) -> MemorySweepProposal:
    proposals = _unique_proposals(supporting_ids, proposal_by_id)
    primary = _primary_proposal(base, proposals)
    return MemorySweepProposal(
        candidate_id=primary.candidate_id,
        candidate_ids=supporting_ids,
        review_queue=primary.review_queue,
        channel=primary.channel,
        target=primary.target,
        section=primary.section,
        content=primary.content,
        evidence_summary=_merged_proposal_evidence_summary(proposals),
        evidence_refs=_merged_proposal_evidence_refs(proposals),
        confidence=primary.confidence,
        basis=primary.basis,
        status=primary.status,
        signal_count=len(supporting_ids),
    )


def _unique_proposals(
    supporting_ids: list[str],
    proposal_by_id: dict[str, MemorySweepProposal],
) -> list[MemorySweepProposal]:
    proposals: list[MemorySweepProposal] = []
    seen: set[str] = set()
    for candidate_id in supporting_ids:
        proposal = proposal_by_id[candidate_id]
        if proposal.candidate_id not in seen:
            proposals.append(proposal)
            seen.add(proposal.candidate_id)
    return proposals


def _primary_proposal(
    base: MemorySweepProposal,
    proposals: list[MemorySweepProposal],
) -> MemorySweepProposal:
    return max(
        proposals or [base],
        key=lambda proposal: (
            _confidence_rank(proposal.confidence),
            _basis_rank(proposal.basis),
            proposal.signal_count,
            proposal.candidate_id,
        ),
    )


def _merged_row_evidence_summary(rows: list[MemoryCandidateRow]) -> str:
    summaries = _unique(" ".join(row.evidence_summary.split()) for row in rows)
    if len(rows) == 1:
        return summaries[0] if summaries else ""
    return _bounded_evidence(f"{len(rows)} related signals", summaries)


def _merged_row_evidence_refs(rows: list[MemoryCandidateRow]) -> list[str]:
    return _unique(ref for row in rows for ref in row.evidence_refs)[:12]


def _merged_proposal_evidence_summary(proposals: list[MemorySweepProposal]) -> str:
    summaries = _unique(
        " ".join(proposal.evidence_summary.split()) for proposal in proposals
    )
    signal_count = sum(proposal.signal_count for proposal in proposals)
    if signal_count <= 1:
        return summaries[0] if summaries else ""
    return _bounded_evidence(f"{signal_count} related signals", summaries)


def _merged_proposal_evidence_refs(proposals: list[MemorySweepProposal]) -> list[str]:
    return _unique(ref for proposal in proposals for ref in proposal.evidence_refs)[:12]


def _bounded_evidence(prefix: str, summaries: list[str]) -> str:
    text = f"{prefix}: " + "; ".join(summaries[:4])
    return text[:700]


def _current_excerpt(target_excerpts: dict[str, str], target: str) -> str:
    return (target_excerpts.get(target, "") or "").strip()[:800]


def _card_id(target: str, section: str, candidate_ids: list[str]) -> str:
    raw = "|".join([target, section, *sorted(candidate_ids)])
    return "sweep_card_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _confidence_rank(value: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(value, 0)


def _basis_rank(value: str) -> int:
    return {"explicit": 3, "repeated_behavior": 2, "inferred": 1}.get(value, 0)


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _chunks(values: list[MemorySweepProposal], size: int) -> Iterable[list[MemorySweepProposal]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]
