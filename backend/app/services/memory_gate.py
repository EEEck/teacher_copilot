"""Mem V3 promotion gate: which ledger clusters may enter the Memory Sweep.

docs/mem_v3/design.md lane 2. Inspired by OpenClaw's dreaming promotion
thresholds (ref_repos/openclaw/src/memory-host-sdk/dreaming.ts, MIT):
signals must demonstrate persistence before they earn teacher attention.

Rules:
- explicit teacher asks (``source == "teacher_explicit"``) are always
  eligible — they get the pinned "Explicitly requested changes" section;
- inferred claims need captures in >= 2 distinct sessions;
- eligible clusters are ordered by a frequency+recency score;
- stale unreinforced singletons expire silently (the ledger is invisible;
  wiki artifacts remain the durable evidence).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.services.memory_candidate_ledger import (
    MemoryCandidateLedger,
    MemoryCandidateRow,
)

GATE_MIN_DISTINCT_SESSIONS = 2
STALE_SINGLETON_DAYS = 42

# OpenClaw dreaming weights (frequency 0.24 / relevance 0.30 / recency 0.15,
# rescaled to the two signals we can measure — capture frequency and
# recency). Used for ordering eligible clusters, not for eligibility.
FREQUENCY_WEIGHT = 0.6
RECENCY_WEIGHT = 0.4
RECENCY_HALF_LIFE_DAYS = 14.0


@dataclass(frozen=True)
class GateResult:
    eligible: list[list[MemoryCandidateRow]] = field(default_factory=list)
    held: list[list[MemoryCandidateRow]] = field(default_factory=list)


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat((value or "").replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _distinct_sessions(cluster: list[MemoryCandidateRow]) -> int:
    return len({row.session_id for row in cluster if row.session_id})


def _is_explicit(cluster: list[MemoryCandidateRow]) -> bool:
    return any(row.source == "teacher_explicit" for row in cluster)


def cluster_score(cluster: list[MemoryCandidateRow], now: datetime) -> float:
    """Frequency+recency ordering score in [0, 1]; explicit clusters get 1."""
    if _is_explicit(cluster):
        return 1.0
    frequency = min(_distinct_sessions(cluster) / 3.0, 1.0)
    newest = max(_parse_utc(row.created_at) for row in cluster)
    age_days = max((now - newest).total_seconds() / 86400.0, 0.0)
    recency = 0.5 ** (age_days / RECENCY_HALF_LIFE_DAYS)
    return FREQUENCY_WEIGHT * frequency + RECENCY_WEIGHT * recency


def gate_clusters(
    clusters: list[list[MemoryCandidateRow]], now: datetime
) -> GateResult:
    eligible: list[list[MemoryCandidateRow]] = []
    held: list[list[MemoryCandidateRow]] = []
    for cluster in clusters:
        if not cluster:
            continue
        if _is_explicit(cluster) or _distinct_sessions(cluster) >= GATE_MIN_DISTINCT_SESSIONS:
            eligible.append(cluster)
        else:
            held.append(cluster)
    eligible.sort(key=lambda cluster: cluster_score(cluster, now), reverse=True)
    return GateResult(eligible=eligible, held=held)


def expire_stale_candidates(ledger: MemoryCandidateLedger, now: datetime) -> int:
    """Silently expire unreinforced singleton claims older than the window.

    Only plain ``captured`` singletons expire; explicit asks and reinforced
    clusters (>1 open row sharing a cluster_key) never do.
    """
    rows = ledger.list_candidates(statuses=("captured",))
    by_cluster: dict[str, list[MemoryCandidateRow]] = {}
    for row in rows:
        by_cluster.setdefault(row.cluster_key or row.id, []).append(row)

    now_iso = now.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    now_iso = now_iso.replace("+00:00", "Z")
    expired = 0
    for cluster in by_cluster.values():
        if len(cluster) > 1 or _is_explicit(cluster):
            continue
        row = cluster[0]
        age_days = (now - _parse_utc(row.created_at)).total_seconds() / 86400.0
        if age_days > STALE_SINGLETON_DAYS:
            ledger.update_status(
                row.id,
                "expired",
                updated_at=now_iso,
                rejection_reason="auto: stale unreinforced signal",
            )
            expired += 1
    return expired
