import type { MemorySweepReviewResponse } from "@/lib/api";

/** Default cadence for class-home Memory Sweep nudge. */
export const MEMORY_SWEEP_DUE_AFTER_DAYS = 5;

function openCandidateCount(review: MemorySweepReviewResponse | null): number {
  if (!review?.queues) return 0;
  return Object.values(review.queues).reduce(
    (sum, queue) => sum + (queue?.length ?? 0),
    0,
  );
}

/** Empty ready/stale review — same UI as Memory Sweep "All caught up." */
export function memorySweepIsAllCaughtUp(
  review: MemorySweepReviewResponse | null,
): boolean {
  if (!review) return false;
  if (review.status !== "ready" && review.status !== "stale") return false;
  return openCandidateCount(review) === 0;
}

export function memorySweepReviewBadge(
  review: MemorySweepReviewResponse | null,
): string {
  if (!review || review.status === "none") return "";
  if (review.status === "generating" || review.status === "applying") {
    return review.status === "applying" ? "Applying..." : "Generating...";
  }
  // Only alarm when teacher edits are at risk. Unedited fingerprint drift is
  // normal (ledger/wiki moved on) — class home keeps "Draft saved"; opening
  // sweep can refresh without discarding teacher work.
  if (
    (review.status === "stale" || review.is_stale) &&
    review.has_teacher_edits
  ) {
    return "Stale draft";
  }
  if (review.status === "failed") return "Failed";
  if (review.status !== "ready" && review.status !== "stale") return "";
  // Empty sweep is "all caught up", not an open draft to finish.
  if (memorySweepIsAllCaughtUp(review)) return "";
  const date = shortDate(review.updated_at ?? review.generated_at);
  return date ? `Draft saved ${date}` : "Draft saved";
}

/**
 * Attention chip on class-home Memory Sweep (generating / stale / failed).
 * Quiet "Draft saved…" is a subtitle instead — see usefulSubtitle.
 */
export function memorySweepReviewAttentionBadge(
  review: MemorySweepReviewResponse | null,
): string {
  const badge = memorySweepReviewBadge(review);
  if (!badge) return "";
  if (badge.startsWith("Draft saved") || badge === "Draft saved") {
    return "";
  }
  return badge;
}

/** Subtitle when useful (option 2): draft saved + attention states. */
export function memorySweepUsefulSubtitle(
  review: MemorySweepReviewResponse | null,
): string {
  return memorySweepReviewBadge(review);
}

function parseTimestamp(value?: string | null): Date | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function lastAppliedTimestamp(
  review: MemorySweepReviewResponse | null,
): Date | null {
  return parseTimestamp(review?.completed_at);
}

/** Last successful apply, or last empty "all caught up" sweep. */
function cadenceResetTimestamp(
  review: MemorySweepReviewResponse | null,
): Date | null {
  const applied = lastAppliedTimestamp(review);
  const caughtUpAt = memorySweepIsAllCaughtUp(review)
    ? parseTimestamp(review?.updated_at ?? review?.generated_at)
    : null;
  if (applied && caughtUpAt) {
    return applied.getTime() >= caughtUpAt.getTime() ? applied : caughtUpAt;
  }
  return applied ?? caughtUpAt;
}

export function memorySweepDaysSinceActivity(
  review: MemorySweepReviewResponse | null,
  now: Date = new Date(),
): number | null {
  // Cadence resets on wiki apply *or* an empty "all caught up" sweep — not on
  // opening/saving a draft that still has pending suggestions.
  const at = cadenceResetTimestamp(review);
  if (!at) return null;
  const ms = now.getTime() - at.getTime();
  if (ms < 0) return 0;
  return Math.floor(ms / (24 * 60 * 60 * 1000));
}

/**
 * Weekly cadence nudge: never applied/caught-up, or last reset ≥ dueAfterDays.
 * Abandoned drafts with open candidates do not reset this.
 */
export function memorySweepIsDue(
  review: MemorySweepReviewResponse | null,
  opts?: { dueAfterDays?: number; now?: Date },
): boolean {
  if (review?.status === "generating" || review?.status === "applying") {
    return false;
  }
  const dueAfterDays = opts?.dueAfterDays ?? MEMORY_SWEEP_DUE_AFTER_DAYS;
  const days = memorySweepDaysSinceActivity(review, opts?.now);
  if (days === null) return true;
  return days >= dueAfterDays;
}

/** Corner chip when due; empty when apply or all-caught-up reset is fresh. */
export function memorySweepDueBadge(
  review: MemorySweepReviewResponse | null,
  opts?: { dueAfterDays?: number; now?: Date },
): string {
  if (!memorySweepIsDue(review, opts)) return "";
  const days = memorySweepDaysSinceActivity(review, opts?.now);
  if (days === null) return "Due · weekly";
  return `Due · ${opts?.dueAfterDays ?? MEMORY_SWEEP_DUE_AFTER_DAYS}+ days`;
}

/** Short open/load of an existing review (usually a few seconds). */
export function memorySweepLoadingSavedText(): string {
  return "Loading saved Memory Sweep results… Usually a few seconds.";
}

/** Durable backend generation while status is generating. */
export function memorySweepProgressText(
  review: MemorySweepReviewResponse | null,
): string {
  return review?.status === "generating"
    ? "Generating updated memory candidates… This can take 1–2 minutes."
    : "";
}

function shortDate(value?: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
