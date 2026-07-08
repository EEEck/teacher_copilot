"""Mem V3 promotion gate: which ledger clusters may enter the Memory Sweep.

docs/mem_v3/design.md lane 2. Inspired by OpenClaw's dreaming promotion
thresholds (ref_repos/openclaw/src/memory-host-sdk/dreaming.ts, MIT):
signals must demonstrate persistence before they earn teacher attention.

Rules:
- explicit teacher asks are eligible only via the verified fast-lane verdict
  (persisted ``fast_lane`` flag, or the quote token on conduct files); they
  get the pinned "Explicitly requested changes" section;
- inferred claims need captures on >= 2 distinct OCCASIONS — an occasion is
  the artifact the session was about (``occasion_key``, e.g. one lesson),
  falling back to 6-hour time buckets for unanchored sessions, so retries
  and same-evening bursts about one lesson count once;
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
from app.teacher_agent.memory_capture import is_fast_lane_row

GATE_MIN_DISTINCT_OCCASIONS = 2
OCCASION_FALLBACK_BUCKET_HOURS = 6
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


def _occasion(row: MemoryCandidateRow) -> str:
    """The independence unit for reinforcement (docs/mem_v3 lane 2).

    Anchored captures use the artifact they were about (one lesson = one
    occasion no matter how many sessions touched it). Unanchored captures
    fall back to 6-hour time buckets so retries and reloads collapse.
    """
    if row.occasion_key:
        return row.occasion_key
    bucket = int(_parse_utc(row.created_at).timestamp()) // (
        OCCASION_FALLBACK_BUCKET_HOURS * 3600
    )
    return f"t:{bucket}"


def distinct_occasions(cluster: list[MemoryCandidateRow]) -> int:
    return len({_occasion(row) for row in cluster})


def _is_explicit(cluster: list[MemoryCandidateRow]) -> bool:
    return any(
        is_fast_lane_row(
            row.target, row.source, row.evidence_summary, row.fast_lane
        )
        for row in cluster
    )


def cluster_score(cluster: list[MemoryCandidateRow], now: datetime) -> float:
    """Frequency+recency ordering score in [0, 1]; explicit clusters get 1."""
    if _is_explicit(cluster):
        return 1.0
    frequency = min(distinct_occasions(cluster) / 3.0, 1.0)
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
        if (
            _is_explicit(cluster)
            or distinct_occasions(cluster) >= GATE_MIN_DISTINCT_OCCASIONS
        ):
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
