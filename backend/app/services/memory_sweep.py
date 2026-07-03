"""Memory Sweep review grouping and consolidation helpers.

This module is the slow review layer between the candidate ledger and curated
wiki memory. The ledger preserves every evidence row; sweep turns related rows
into teacher-reviewable cards without writing memory.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from app.services.memory_candidate_ledger import (
    MemoryCandidateLedger,
    MemoryCandidateRow,
    OPEN_STATUSES,
)
from app.teacher_agent.memory_targets import (
    canonical_memory_target,
    compact_key_for_target,
    is_supported_runtime_target,
    is_student_page_target,
    is_subject_guide_target,
    memory_channel_for_target,
    student_id_from_target,
)
from app.teacher_agent.wiki_store import WikiStore


QUEUE_BY_CHANNEL = {
    "teacher_behavior": "Teacher/Copilot Preferences",
    "class_evolution": "Class Evolution",
    "class_learning_pattern": "Class Evolution",
    "subject_concept": "Subject Concepts",
    "student_memory": "Student Memory",
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
SYNTHETIC_STUDENT_SUMMARY_PREFIX = "student_summary:"
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
    surface_labels: list[str] = field(default_factory=list)
    shared_attributes: list[str] = field(default_factory=list)
    distinguishing_attributes: list[str] = field(default_factory=list)
    merge_test: str = ""
    public_rationale: str = ""
    operation: str = "add"
    replaces_content: str = ""
    status_recommendation: str = "promote"
    why_now: str = ""
    current_memory_excerpt: str = ""
    signal_count: int = 1
    can_apply: bool = False
    review_only_reason: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MemorySweepPacket:
    packet_id: str
    target: str
    section: str
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
    surface_labels: list[str] = field(default_factory=list)
    shared_attributes: list[str] = field(default_factory=list)
    distinguishing_attributes: list[str] = field(default_factory=list)
    merge_test: str = ""
    public_rationale: str = ""


@dataclass(frozen=True)
class MemorySweepResult:
    class_id: str
    subject: str
    cards_by_queue: dict[str, list[MemorySweepReviewCard]]
    warnings: list[str] = field(default_factory=list)


async def propose_memory_sweep_review(
    *,
    wiki: WikiStore,
    ledger: MemoryCandidateLedger,
    agents: Any,
    class_id: str,
    include_student_summaries: bool = False,
    queue: str | None = None,
) -> MemorySweepResult:
    """Run the two-pass Memory Sweep proposal lifecycle.

    Failures after retry become unresolved review cards. This function never
    falls back to direct row-to-add-card promotion because normalization is a
    required contract of the sweep.
    """
    cls = wiki.get_class(class_id)
    candidates = ledger.list_candidates(
        class_id=class_id,
        subject=cls.subject,
        statuses=OPEN_STATUSES,
        include_global=True,
    )
    grouped = build_sweep_proposals(candidates)
    if include_student_summaries:
        for student_queue, proposals in build_student_summary_sweep_proposals(
            wiki, class_id
        ).items():
            grouped.setdefault(student_queue, []).extend(proposals)
    if queue:
        grouped = {
            review_queue: proposals
            for review_queue, proposals in grouped.items()
            if review_queue == queue
        }
    if not grouped:
        return MemorySweepResult(
            class_id=class_id, subject=cls.subject, cards_by_queue={}
        )

    target_excerpts = memory_sweep_target_excerpts(
        wiki, class_id, sweep_targets(grouped)
    )
    packets = build_sweep_packets(grouped, target_excerpts)
    all_cards: list[MemorySweepReviewCard] = []
    warnings: list[str] = []
    for packet in packets:
        packet_payload = sweep_packet_payloads([packet])
        packet_excerpts = {packet.target: packet.current_memory_excerpt}
        validation_error = ""
        for attempt in range(2):
            try:
                alignment = await agents.align_memory_sweep_candidates(
                    class_id,
                    cls.subject,
                    packet_payload,
                    packet_excerpts,
                    validation_error=validation_error,
                )
                alignment_groups = validate_alignment_output(packet, alignment)
            except Exception as exc:
                validation_error = str(exc)
                if attempt == 1:
                    warning = (
                        f"Memory Sweep alignment unresolved for {packet.packet_id}: "
                        f"{validation_error}"
                    )
                    warnings.append(warning)
                    all_cards.extend(
                        unresolved_cards_from_packet(
                            packet,
                            target_excerpts,
                            validation_error,
                            warnings=[warning],
                        )
                    )
                continue

            try:
                packet_out = await agents.propose_memory_sweep_cards(
                    class_id,
                    cls.subject,
                    packet_payload,
                    packet_excerpts,
                    alignment_groups=alignment_groups_payload(alignment_groups),
                    validation_error=validation_error,
                )
                packet_cards, packet_warnings = validate_cards_against_alignment(
                    packet,
                    packet_out,
                    alignment_groups,
                    target_excerpts,
                )
                all_cards.extend(packet_cards)
                warnings.extend(alignment.warnings)
                warnings.extend(packet_warnings)
                break
            except Exception as exc:
                validation_error = str(exc)
                if attempt == 1:
                    warning = (
                        "Memory Sweep card generation unresolved for "
                        f"{packet.packet_id}: {validation_error}"
                    )
                    warnings.append(warning)
                    all_cards.extend(
                        unresolved_cards_from_packet(
                            packet,
                            target_excerpts,
                            validation_error,
                            warnings=[warning],
                        )
                    )

    return MemorySweepResult(
        class_id=class_id,
        subject=cls.subject,
        cards_by_queue=grouped_review_cards(all_cards),
        warnings=warnings,
    )


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


def build_sweep_packets(
    grouped: dict[str, list[MemorySweepProposal]],
    target_excerpts: dict[str, str],
) -> list[MemorySweepPacket]:
    """Build bounded target/scope packets for the isolated proposer.

    Packets are grouped by hard target and queue. Semantic grouping remains an
    LLM responsibility; this step is only token control and context selection.
    """
    by_key: dict[tuple[str, str, str], list[MemorySweepProposal]] = {}
    for proposals in grouped.values():
        for proposal in proposals:
            by_key.setdefault(
                (proposal.review_queue, proposal.target, proposal.section),
                [],
            ).append(proposal)
    packets: list[MemorySweepPacket] = []
    for (queue, target, section), proposals in sorted(by_key.items()):
        excerpt = _current_excerpt(target_excerpts, target)
        for index, chunk in enumerate(_chunks(proposals, SWEEP_PACKET_PROPOSAL_LIMIT)):
            packet_id = _card_id(
                f"packet-{index}-{section}",
                target,
                [p.candidate_id for p in chunk],
            )
            packets.append(
                MemorySweepPacket(
                    packet_id=packet_id,
                    target=target,
                    section=section,
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


def build_student_summary_sweep_proposals(
    wiki: WikiStore,
    class_id: str,
) -> dict[str, list[MemorySweepProposal]]:
    """Build read-only weekly review proposals from dated student observations."""
    proposals: list[MemorySweepProposal] = []
    sdir = wiki.students_dir(class_id)
    if not sdir.exists():
        return {}
    for path in sorted(sdir.glob("S-*.md")):
        student_id = path.stem.upper()
        excerpt = wiki._student_sweep_excerpt(class_id, student_id)
        dates = sorted(
            set(re.findall(r"^##\s+(\d{4}-\d{2}-\d{2})\s*$", excerpt, re.M))
        )
        if not dates:
            continue
        target = f"students/{student_id}.md"
        candidate_id = synthetic_student_summary_candidate_id(class_id, student_id)
        recent_dates = dates[-4:]
        proposals.append(
            MemorySweepProposal(
                candidate_id=candidate_id,
                candidate_ids=[candidate_id],
                review_queue="Student Memory",
                channel="student_memory",
                target=target,
                section="Student Summary",
                content=(
                    "Review the dated observations and propose one neutral "
                    "Student Summary sentence using balanced trajectory with "
                    "recency bias."
                ),
                evidence_summary=(
                    f"{student_id} has dated observations through {recent_dates[-1]}; "
                    f"recent dates: {', '.join(recent_dates)}."
                ),
                evidence_refs=[wiki.rel_wiki(path)],
                confidence="medium",
                basis="repeated_behavior" if len(dates) > 1 else "inferred",
                status="captured",
                signal_count=len(dates),
                current_memory_excerpt=excerpt,
            )
        )
    return {"Student Memory": proposals} if proposals else {}


def synthetic_student_summary_candidate_id(class_id: str, student_id: str) -> str:
    return f"{SYNTHETIC_STUDENT_SUMMARY_PREFIX}{class_id}:{student_id.upper()}"


def synthetic_student_summary_candidate_ids(
    wiki: WikiStore,
    class_id: str,
) -> set[str]:
    return {
        proposal.candidate_id
        for proposals in build_student_summary_sweep_proposals(wiki, class_id).values()
        for proposal in proposals
    }


def is_synthetic_student_summary_candidate_id(candidate_id: str) -> bool:
    return (candidate_id or "").startswith(SYNTHETIC_STUDENT_SUMMARY_PREFIX)


def memory_sweep_target_excerpts(
    wiki: WikiStore,
    class_id: str,
    targets: set[str],
) -> dict[str, str]:
    excerpts: dict[str, str] = {}
    for raw_target in sorted(targets):
        target = canonical_memory_target(raw_target)
        if target == "teacher_profile.md":
            excerpts[target] = wiki.read_user_profile()[:1600]
        elif target == "copilot_profile.md":
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
        elif is_student_page_target(target):
            student_id = student_id_from_target(target)
            if student_id:
                excerpts[target] = wiki._student_sweep_excerpt(class_id, student_id)
        elif target == "canonical_wiki":
            excerpts[target] = "(review-only canonical wiki issue)"
    return excerpts


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
        group_id = str(
            getattr(raw_group, "group_id", "") or f"group_{index + 1}"
        ).strip()
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
            raise ValueError(
                f"alignment group {group_id} assigned duplicate candidate ids"
            )
        ids = _unique(raw_ids)
        if not ids:
            raise ValueError(f"alignment group {group_id} has no ledger_candidate_ids")
        unknown = sorted(set(ids) - input_ids)
        if unknown:
            raise ValueError(
                f"alignment group {group_id} used unknown candidate ids: {unknown}"
            )

        target = canonical_memory_target(
            str(getattr(raw_group, "target", "") or packet.target).strip()
        )
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
            raise ValueError(
                f"alignment group {group_id} used unsupported target: {target}"
            )
        if target != packet.target:
            raise ValueError(
                f"alignment group {group_id} changed packet target from {packet.target} to {target}"
            )
        if section != packet.section:
            raise ValueError(
                f"alignment group {group_id} changed packet section from {packet.section} to {section}"
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

        surface_labels = _clean_string_list(
            getattr(raw_group, "surface_labels", []) or []
        )
        if decision in {"already_covered", "adjust_existing"} and not surface_labels:
            raise ValueError(
                f"alignment group {group_id} marked {decision} but has no surface_labels"
            )
        if (
            decision == "merge"
            and surface_labels
            and _current_memory_has_surface_label_bullet(
                packet.current_memory_excerpt,
                surface_labels,
            )
        ):
            raise ValueError(
                f"alignment group {group_id} marked merge but current memory has "
                "a bullet overlapping its surface_labels"
            )
        if decision == "already_covered" and surface_labels:
            if not _current_memory_covers_surface_labels(
                packet.current_memory_excerpt,
                surface_labels,
            ):
                raise ValueError(
                    f"alignment group {group_id} marked already_covered but current "
                    "memory does not cover all surface_labels"
                )
        if (
            decision == "adjust_existing"
            and surface_labels
            and not _current_memory_has_surface_label_bullet(
                packet.current_memory_excerpt,
                surface_labels,
            )
        ):
            raise ValueError(
                f"alignment group {group_id} marked adjust_existing but current "
                "memory has no bullet overlapping its surface_labels"
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
                    for value in (
                        getattr(raw_group, "matched_memory_item_ids", []) or []
                    )
                    if str(value).strip()
                ],
                relationship=relationship,
                decision=decision,
                group_label=str(getattr(raw_group, "group_label", "") or "").strip(),
                surface_labels=surface_labels,
                shared_attributes=_clean_string_list(
                    getattr(raw_group, "shared_attributes", []) or []
                ),
                distinguishing_attributes=_clean_string_list(
                    getattr(raw_group, "distinguishing_attributes", []) or []
                ),
                merge_test=str(getattr(raw_group, "merge_test", "") or "").strip(),
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
        raise ValueError(
            f"invalid alignment coverage: missing={missing}, extra={extra}"
        )
    return groups


def alignment_groups_payload(
    groups: list[MemorySweepAlignmentGroup],
) -> list[dict[str, Any]]:
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
            "surface_labels": list(group.surface_labels),
            "shared_attributes": list(group.shared_attributes),
            "distinguishing_attributes": list(group.distinguishing_attributes),
            "merge_test": group.merge_test,
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
            raise ValueError(
                "card missing source_group_id or exact group candidate_ids"
            )
        if group.group_id not in remaining_group_ids:
            raise ValueError(
                f"duplicate or unknown card source_group_id: {group.group_id}"
            )
        remaining_group_ids.remove(group.group_id)

        card_ids = _card_candidate_ids(raw_card)
        if set(card_ids) != set(group.ledger_candidate_ids):
            raise ValueError(
                f"card {group.group_id} candidate_ids do not match alignment group"
            )
        target = _card_target(raw_card, group.target, warnings)
        section = (getattr(raw_card, "section", "") or group.section).strip()
        if target != group.target:
            raise ValueError(
                f"card {group.group_id} target does not match alignment group"
            )
        if section != group.section:
            raise ValueError(
                f"card {group.group_id} section does not match alignment group"
            )

        expected_operation = DECISION_TO_OPERATION[group.decision]
        operation = _card_operation(raw_card, warnings)
        if operation != expected_operation:
            raise ValueError(
                f"card {group.group_id} operation {operation} does not match decision {group.decision}"
            )
        if operation == "add":
            overlapping_bullet = _existing_named_label_bullet(
                _current_excerpt(target_excerpts, group.target),
                group,
            )
            if overlapping_bullet:
                raise ValueError(
                    "add card overlaps an existing current-memory bullet; "
                    "use adjust_existing or already_covered instead: "
                    f"{overlapping_bullet}"
                )
        replaces_content = (getattr(raw_card, "replaces_content", "") or "").strip()
        if operation == "adjust":
            if not replaces_content:
                raise ValueError(
                    f"card {group.group_id} adjust missing replaces_content"
                )
            if not _excerpt_has_bullet(
                _current_excerpt(target_excerpts, group.target),
                replaces_content,
            ):
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
                surface_labels=group.surface_labels,
                shared_attributes=group.shared_attributes,
                distinguishing_attributes=group.distinguishing_attributes,
                merge_test=group.merge_test,
                public_rationale=group.public_rationale,
                operation=operation,
                replaces_content=replaces_content if operation == "adjust" else "",
                status_recommendation=OPERATION_TO_STATUS_RECOMMENDATION[operation],
                why_now=(
                    getattr(raw_card, "why_now", "") or group.public_rationale
                ).strip(),
            )
        )

    if remaining_group_ids:
        raise ValueError(
            f"missing cards for alignment groups: {sorted(remaining_group_ids)}"
        )
    return cards, warnings


def unresolved_cards_from_packet(
    packet: MemorySweepPacket,
    target_excerpts: dict[str, str],
    reason: str,
    warnings: list[str] | None = None,
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
                warnings=warnings or [],
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
    surface_labels: list[str] | None = None,
    shared_attributes: list[str] | None = None,
    distinguishing_attributes: list[str] | None = None,
    merge_test: str = "",
    public_rationale: str = "",
    operation: str = "add",
    replaces_content: str = "",
    status_recommendation: str = "promote",
    why_now: str = "",
    warnings: list[str] | None = None,
) -> MemorySweepReviewCard:
    candidate_ids = list(proposal.candidate_ids)
    final_target = target or proposal.target
    can_apply, review_only_reason = memory_sweep_apply_policy(final_target, operation)
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
        surface_labels=list(surface_labels or []),
        shared_attributes=list(shared_attributes or []),
        distinguishing_attributes=list(distinguishing_attributes or []),
        merge_test=merge_test,
        public_rationale=public_rationale,
        operation=operation,
        replaces_content=replaces_content,
        status_recommendation=status_recommendation,
        why_now=why_now,
        current_memory_excerpt=_current_excerpt(target_excerpts, final_target),
        signal_count=proposal.signal_count,
        can_apply=can_apply,
        review_only_reason=review_only_reason,
        warnings=warnings or [],
    )


def queue_for_channel(channel: str) -> str:
    return QUEUE_BY_CHANNEL.get(channel, "Memory Sweep")


def memory_sweep_apply_policy(target: str, operation: str) -> tuple[bool, str]:
    if operation not in {"add", "adjust"}:
        return False, "non-writing operation"
    normalized = canonical_memory_target(target)
    if normalized == "canonical_wiki":
        return False, "canonical wiki findings are review-only"
    if normalized in {"teacher_profile.md", "copilot_profile.md"}:
        return True, ""
    if compact_key_for_target(normalized):
        return True, ""
    if is_subject_guide_target(normalized):
        return True, ""
    if is_student_page_target(normalized):
        return True, ""
    return False, f"unsupported target: {target}"


def _proposal_from_rows(rows: list[MemoryCandidateRow]) -> MemorySweepProposal:
    primary = _primary_sweep_row(rows)
    candidate_ids = _candidate_ids(primary, rows)
    return MemorySweepProposal(
        candidate_id=primary.id,
        candidate_ids=candidate_ids,
        review_queue=queue_for_channel(primary.channel),
        channel=primary.channel,
        target=canonical_memory_target(primary.target),
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


def _candidate_ids(
    primary: MemoryCandidateRow, rows: list[MemoryCandidateRow]
) -> list[str]:
    ordered = [primary.id]
    ordered.extend(row.id for row in rows if row.id != primary.id)
    return ordered


def _packet_proposal_lookup(
    packet: MemorySweepPacket,
) -> dict[str, MemorySweepProposal]:
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


def _existing_named_label_bullet(
    excerpt: str,
    group: MemorySweepAlignmentGroup,
) -> str:
    labels = [*group.surface_labels, *group.shared_attributes]
    for line in (excerpt or "").splitlines():
        if not line.strip().startswith("-"):
            continue
        bullet = _normalize_bullet_text(line)
        if any(_named_label_overlaps_bullet(label, bullet) for label in labels):
            return bullet
    return ""


def _current_memory_covers_surface_labels(excerpt: str, labels: list[str]) -> bool:
    labels_with_tokens = [label for label in labels if _label_tokens(label)]
    if not labels_with_tokens:
        return True
    for line in (excerpt or "").splitlines():
        if not line.strip().startswith("-"):
            continue
        bullet = _normalize_bullet_text(line)
        if all(
            _named_label_overlaps_bullet(label, bullet) for label in labels_with_tokens
        ):
            return True
    return False


def _current_memory_has_surface_label_bullet(excerpt: str, labels: list[str]) -> bool:
    labels_with_tokens = [label for label in labels if _label_tokens(label)]
    if not labels_with_tokens:
        return True
    for line in (excerpt or "").splitlines():
        if not line.strip().startswith("-"):
            continue
        bullet = _normalize_bullet_text(line)
        if any(
            _named_label_overlaps_bullet(label, bullet) for label in labels_with_tokens
        ):
            return True
    return False


_LABEL_STOPWORDS = {
    "and",
    "for",
    "the",
    "this",
    "that",
    "with",
    "use",
    "uses",
    "using",
    "teacher",
    "prefers",
    "preference",
}


def _named_label_overlaps_bullet(label: str, bullet: str) -> bool:
    label_tokens = _label_tokens(label)
    if not label_tokens:
        return False
    bullet_tokens = _label_tokens(bullet)
    if not bullet_tokens:
        return False
    return len(label_tokens & bullet_tokens) >= 2


def _label_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (value or "").lower())
        if len(token) >= 3 and token not in _LABEL_STOPWORDS
    }


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


def _card_target(card: Any, fallback: str, warnings: list[str]) -> str:
    target = canonical_memory_target(
        str(getattr(card, "target", "") or fallback).strip()
    )
    if is_supported_runtime_target(target):
        return target
    warnings.append(f"ignored unsupported Memory Sweep target: {target}")
    return fallback


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
    canonical = canonical_memory_target(target)
    for key in (canonical, target):
        if key in target_excerpts:
            return (target_excerpts.get(key, "") or "").strip()[:800]
    for key, value in target_excerpts.items():
        if canonical_memory_target(key) == canonical:
            return (value or "").strip()[:800]
    return ""


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


def _clean_string_list(values: Iterable[Any]) -> list[str]:
    return _unique(str(value).strip() for value in values if str(value).strip())


def _chunks(
    values: list[MemorySweepProposal], size: int
) -> Iterable[list[MemorySweepProposal]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]
