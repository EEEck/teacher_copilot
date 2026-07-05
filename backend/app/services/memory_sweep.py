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
    """Mem V3 single-call sweep (docs/mem_v3/design.md lane 3).

    Deterministic backend work first (silent decay, cluster grouping, the
    promotion gate), then ONE high-reasoning consolidation call over all
    gate-passing claims and the enumerated current memory, validated
    structurally. A failed run yields one plain-language notice, never
    per-candidate fallback cards.
    """
    from datetime import datetime, timezone

    from app.services.memory_gate import expire_stale_candidates, gate_clusters

    cls = wiki.get_class(class_id)
    now = datetime.now(timezone.utc)
    expire_stale_candidates(ledger, now)

    candidates = ledger.list_review_candidates(
        class_id=class_id,
        subject=cls.subject,
        include_global=True,
    )
    clusters: dict[str, list[MemoryCandidateRow]] = {}
    for row in candidates:
        clusters.setdefault(row.cluster_key or row.id, []).append(row)
    gate = gate_clusters(list(clusters.values()), now)
    claims = claims_from_clusters(gate.eligible, now)

    if include_student_summaries and queue in (None, "Student Memory"):
        claims.extend(_student_summary_claims(wiki, class_id, start=len(claims)))

    if queue:
        # Scope the consolidation call itself, not just the returned cards —
        # per-queue refreshes must not pay for the whole ledger.
        claims = [
            claim
            for claim in claims
            if QUEUE_BY_CHANNEL.get(
                memory_channel_for_target(claim["target"]), "Memory Sweep"
            )
            == queue
        ]

    if not claims:
        return MemorySweepResult(
            class_id=class_id, subject=cls.subject, cards_by_queue={}
        )

    targets = sorted({claim["target"] for claim in claims})
    target_excerpts = memory_sweep_target_excerpts(wiki, class_id, set(targets))
    memory_indexes: dict[str, dict[str, str]] = {}
    flat_index: dict[str, str] = {}
    for position, target in enumerate(targets, start=1):
        index = enumerate_memory_bullets(
            target_excerpts.get(target, ""), prefix=f"M{position}_"
        )
        memory_indexes[target] = index
        flat_index.update(index)

    warnings: list[str] = []
    all_cards: list[MemorySweepReviewCard] = []
    claim_ids = {claim["claim_id"] for claim in claims}
    validation_error = ""
    ops: list[ConsolidationOp] | None = None
    for attempt in range(2):
        try:
            output = await agents.consolidate_memory_sweep(
                class_id,
                cls.subject,
                claims,
                memory_indexes,
                applied_history=_history_texts(ledger, targets, status="applied"),
                rejected_history=_history_texts(ledger, targets, status="rejected"),
                budget_usage=_budget_usage(targets, target_excerpts),
                today=now.date().isoformat(),
                validation_error=validation_error,
            )
            ops = validate_consolidation_ops(output.operations, flat_index, claim_ids)
            warnings.extend(output.warnings)
            break
        except Exception as exc:
            validation_error = str(exc)
            ops = None

    if ops is None:
        notice = consolidation_failure_notice(validation_error, len(claims))
        warnings.append(notice.message)
    else:
        all_cards.extend(
            cards_from_consolidation_ops(ops, claims, flat_index, target_excerpts)
        )

    cards_by_queue = grouped_review_cards(all_cards)
    if queue:
        cards_by_queue = {
            review_queue: cards
            for review_queue, cards in cards_by_queue.items()
            if review_queue == queue
        }
    return MemorySweepResult(
        class_id=class_id,
        subject=cls.subject,
        cards_by_queue=cards_by_queue,
        warnings=warnings,
    )


def _student_summary_claims(
    wiki: WikiStore, class_id: str, *, start: int
) -> list[dict[str, Any]]:
    """Student-summary refresh requests as claims for the consolidation call."""
    claims: list[dict[str, Any]] = []
    position = start
    for proposals in build_student_summary_sweep_proposals(wiki, class_id).values():
        for proposal in proposals:
            position += 1
            claims.append(
                {
                    "claim_id": f"C{position}",
                    "cluster_key": proposal.candidate_id,
                    "target": proposal.target,
                    "section": proposal.section,
                    "text": proposal.content,
                    "evidence_summary": proposal.evidence_summary,
                    "observations_excerpt": proposal.current_memory_excerpt,
                    "signal_count": proposal.signal_count,
                    "session_count": proposal.signal_count,
                    "first_seen": "",
                    "last_seen": "",
                    "explicit": False,
                    "score": 0.5,
                    "candidate_ids": list(proposal.candidate_ids),
                }
            )
    return claims


def _budget_usage(
    targets: list[str], target_excerpts: dict[str, str]
) -> dict[str, str]:
    """Per-target character usage against the hermes-style page budgets.

    Fed into the consolidation call so the model prefers update/delete over
    add when a memory file is near its budget (letta's error-on-exceed idea,
    applied one step earlier: pressure becomes compaction proposals).
    """
    from app.teacher_agent.wiki.memory import memory_budget

    usage: dict[str, str] = {}
    for target in targets:
        canonical = canonical_memory_target(target)
        if canonical == "teacher_profile.md":
            key = "user"
        elif canonical == "copilot_profile.md":
            key = "copilot_profile"
        elif is_subject_guide_target(canonical):
            key = "subject_guide"
        else:
            key = compact_key_for_target(canonical) or ""
        if not key:
            continue
        usage[canonical] = (
            f"{len(target_excerpts.get(canonical, ''))}/{memory_budget(key)} chars"
        )
    return usage


def _history_texts(
    ledger: MemoryCandidateLedger,
    targets: list[str],
    *,
    status: str,
    limit: int = 20,
) -> dict[str, list[str]]:
    """Recently applied/rejected candidate texts per target for the call."""
    rows = ledger.list_candidates(statuses=(status,))
    by_target: dict[str, list[str]] = {}
    for row in sorted(rows, key=lambda r: r.updated_at, reverse=True):
        target = canonical_memory_target(row.target)
        if target not in targets:
            continue
        bucket = by_target.setdefault(target, [])
        if len(bucket) < limit:
            bucket.append(row.candidate_update)
    return by_target


def cards_from_consolidation_ops(
    ops: list["ConsolidationOp"],
    claims: list[dict[str, Any]],
    memory_index: dict[str, str],
    target_excerpts: dict[str, str],
) -> list[MemorySweepReviewCard]:
    """Map validated consolidation operations onto teacher review cards.

    add -> add (can_apply), update -> adjust with the referenced bullet as
    replaces_content (can_apply), delete -> review-only needs_decision
    describing the removal, none -> already_covered (teacher confirms via
    "Already in memory", which retires the ledger rows).
    """
    claims_by_id = {claim["claim_id"]: claim for claim in claims}
    cards: list[MemorySweepReviewCard] = []
    for op in ops:
        op_claims = [claims_by_id[cid] for cid in op.claim_ids if cid in claims_by_id]
        if not op_claims:
            continue
        primary = op_claims[0]
        target = canonical_memory_target(op.target or primary["target"])
        section = op.section or primary["section"]
        candidate_ids = _unique(
            cid for claim in op_claims for cid in claim["candidate_ids"]
        )
        channel = memory_channel_for_target(target)
        review_queue = QUEUE_BY_CHANNEL.get(channel, "Memory Sweep")
        signal_count = sum(int(claim.get("signal_count") or 1) for claim in op_claims)
        explicit = any(claim.get("explicit") for claim in op_claims)
        evidence_summary = "; ".join(
            _unique(
                str(claim.get("evidence_summary") or "").strip()
                for claim in op_claims
            )
        )[:600]
        base = {
            "card_id": _card_id(target, section, candidate_ids),
            "source_group_id": _card_id(target, section, candidate_ids),
            "candidate_id": candidate_ids[0],
            "candidate_ids": candidate_ids,
            "review_queue": review_queue,
            "channel": channel,
            "target": target,
            "section": section,
            "evidence_summary": evidence_summary,
            "confidence": "high" if explicit else "medium",
            "basis": "explicit" if explicit else "inferred",
            "status": "proposed",
            "group_label": "explicit_ask" if explicit else "",
            "public_rationale": op.rationale,
            "why_now": (
                f"Seen {signal_count}x across "
                f"{max(int(claim.get('session_count') or 1) for claim in op_claims)} "
                "session(s)."
            ),
            "current_memory_excerpt": target_excerpts.get(target, "")[:800],
            "signal_count": signal_count,
        }
        if op.operation == "add":
            cards.append(
                MemorySweepReviewCard(
                    **base,
                    content=op.new_text,
                    operation="add",
                    status_recommendation="promote",
                    can_apply=True,
                )
            )
        elif op.operation == "update":
            cards.append(
                MemorySweepReviewCard(
                    **base,
                    content=op.new_text,
                    operation="adjust",
                    replaces_content=memory_index.get(op.memory_id or "", ""),
                    status_recommendation="promote",
                    can_apply=True,
                )
            )
        elif op.operation == "delete":
            removed = memory_index.get(op.memory_id or "", "")
            cards.append(
                MemorySweepReviewCard(
                    **base,
                    content=primary["text"],
                    operation="needs_decision",
                    status_recommendation="needs_decision",
                    can_apply=False,
                    review_only_reason=(
                        "The sweep suggests removing an outdated note: "
                        f"“{removed[:160]}”. Decide in the detail card."
                    ),
                )
            )
        else:  # none
            cards.append(
                MemorySweepReviewCard(
                    **base,
                    content=primary["text"],
                    operation="already_covered",
                    status_recommendation="already_covered",
                    can_apply=False,
                    review_only_reason=(
                        op.rationale
                        or "Current memory already covers this suggestion."
                    ),
                )
            )
    return cards


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


def grouped_review_cards(
    cards: Iterable[MemorySweepReviewCard],
) -> dict[str, list[MemorySweepReviewCard]]:
    grouped: dict[str, list[MemorySweepReviewCard]] = {}
    for card in cards:
        grouped.setdefault(card.review_queue, []).append(card)
    return grouped


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


# --- Mem V3 single-call consolidation contract (docs/mem_v3/design.md lane 3)
#
# The sweep's one high-reasoning call returns ID-referenced operations
# against the enumerated current-memory bullets (mem0-style
# ADD/UPDATE/DELETE/NONE, Apache-2.0 pattern). Validation here is
# STRUCTURAL ONLY, restoring the docs/2sweep_idea.md §7 contract: no
# lexical token-overlap second-guessing of the model's semantics — the
# teacher review is the safety net.

CONSOLIDATION_OPERATIONS = {"add", "update", "delete", "none"}


@dataclass(frozen=True)
class ConsolidationOp:
    """One validated consolidation decision from the sweep call."""

    claim_ids: list[str]
    operation: str  # add | update | delete | none
    target: str
    section: str
    memory_id: str | None = None
    new_text: str = ""
    rationale: str = ""


@dataclass(frozen=True)
class ConsolidationFailureNotice:
    """Single teacher-facing notice replacing per-candidate zombie cards."""

    message: str
    claim_count: int


def _op_field(op: Any, name: str, default: Any = None) -> Any:
    if isinstance(op, dict):
        return op.get(name, default)
    return getattr(op, name, default)


def validate_consolidation_ops(
    ops: Iterable[Any],
    memory_index: dict[str, str],
    claim_ids: set[str],
) -> list[ConsolidationOp]:
    """Structurally validate the single-call sweep output.

    Checks: known operations; update/delete reference an existing memory id
    from the enumerated index; update/add carry new_text; every input claim
    id is accounted for exactly once across operations. Raises ValueError
    with an actionable message (fed back to the model for one retry).
    """
    validated: list[ConsolidationOp] = []
    assigned: list[str] = []
    for op in ops or []:
        operation = str(_op_field(op, "operation", "") or "").strip().lower()
        if operation not in CONSOLIDATION_OPERATIONS:
            raise ValueError(f"unsupported consolidation operation: {operation!r}")
        op_claims = [
            str(cid).strip()
            for cid in (_op_field(op, "claim_ids", []) or [])
            if str(cid).strip()
        ]
        if not op_claims:
            raise ValueError(f"{operation} operation lists no claim_ids")
        memory_id_raw = _op_field(op, "memory_id")
        memory_id = str(memory_id_raw).strip() if memory_id_raw else None
        new_text = str(_op_field(op, "new_text", "") or "").strip()

        if operation in {"update", "delete"}:
            if not memory_id:
                raise ValueError(f"{operation} operation requires a memory_id")
            if memory_id not in memory_index:
                raise ValueError(
                    f"unknown memory id {memory_id}: reference input memory ids only"
                )
        if operation in {"update", "add"} and not new_text:
            raise ValueError(f"{operation} operation requires new_text")

        assigned.extend(op_claims)
        validated.append(
            ConsolidationOp(
                claim_ids=op_claims,
                operation=operation,
                target=str(_op_field(op, "target", "") or "").strip(),
                section=str(_op_field(op, "section", "") or "").strip(),
                memory_id=memory_id,
                new_text=new_text,
                rationale=str(_op_field(op, "rationale", "") or "").strip(),
            )
        )

    if len(assigned) != len(set(assigned)):
        raise ValueError("a claim id was assigned to more than one operation")
    assigned_set = set(assigned)
    if assigned_set != set(claim_ids):
        missing = sorted(set(claim_ids) - assigned_set)
        extra = sorted(assigned_set - set(claim_ids))
        raise ValueError(
            f"invalid claim coverage: missing={missing}, extra={extra}"
        )
    return validated


def consolidation_failure_notice(
    reason: str, claim_count: int
) -> ConsolidationFailureNotice:
    """One plain-language notice for a failed consolidation run.

    Raw internal reasons (validator errors, card ids) go to logs, never to
    the teacher-facing payload.
    """
    import logging

    logging.getLogger(__name__).warning(
        "Memory Sweep consolidation unresolved (%d claims): %s", claim_count, reason
    )
    return ConsolidationFailureNotice(
        message=(
            f"The sweep could not consolidate {claim_count} suggestions in "
            "this run. Nothing was lost — run the sweep again, or review "
            "them later once more evidence has accumulated."
        ),
        claim_count=claim_count,
    )


def enumerate_memory_bullets(markdown: str, *, prefix: str = "M") -> dict[str, str]:
    """Enumerate a memory file's bullets with ephemeral call-time ids.

    No file-format change: ids exist only for one consolidation call so the
    model can reference bullets precisely (UPDATE/DELETE by id) and the
    backend can validate references mechanically.
    """
    index: dict[str, str] = {}
    counter = 0
    for line in (markdown or "").splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        text = stripped[2:].strip()
        if not text:
            continue
        counter += 1
        index[f"{prefix}{counter}"] = text
    return index


def claims_from_clusters(
    clusters: list[list[MemoryCandidateRow]],
    now: Any,
) -> list[dict[str, Any]]:
    """Turn gate-passing ledger clusters into the sweep call's claim payload.

    One claim per cluster: the most recent phrasing represents the claim,
    reinforcement metadata (signal/session counts, first/last seen) gives the
    model the evidence weight, and candidate ids keep apply/status updates
    traceable back to ledger rows.
    """
    from app.services.memory_gate import cluster_score

    claims: list[dict[str, Any]] = []
    for position, cluster in enumerate(clusters, start=1):
        if not cluster:
            continue
        newest = max(cluster, key=lambda row: row.created_at)
        claims.append(
            {
                "claim_id": f"C{position}",
                "cluster_key": newest.cluster_key or newest.id,
                "target": canonical_memory_target(newest.target),
                "section": newest.section,
                "text": newest.candidate_update,
                "evidence_summary": newest.evidence_summary,
                "signal_count": len(cluster),
                "session_count": len(
                    {row.session_id for row in cluster if row.session_id}
                ),
                "first_seen": min(row.created_at for row in cluster),
                "last_seen": newest.created_at,
                "explicit": any(
                    row.source == "teacher_explicit" for row in cluster
                ),
                "score": round(cluster_score(cluster, now), 3),
                "candidate_ids": [row.id for row in cluster],
            }
        )
    return claims
