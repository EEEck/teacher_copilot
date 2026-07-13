import type { MemorySweepReviewResponse } from "@/lib/api";

/** Default cadence for class-home Memory Sweep nudge. */
export const MEMORY_SWEEP_DUE_AFTER_DAYS = 5;

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

function lastAppliedTimestamp(
  review: MemorySweepReviewResponse | null,
): Date | null {
  if (!review?.completed_at) return null;
  const date = new Date(review.completed_at);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function memorySweepDaysSinceActivity(
  review: MemorySweepReviewResponse | null,
  now: Date = new Date(),
): number | null {
  // Weekly cadence is last *apply*, not last draft open/save — otherwise an
  // abandoned ready draft would silence the due chip for days.
  const at = lastAppliedTimestamp(review);
  if (!at) return null;
  const ms = now.getTime() - at.getTime();
  if (ms < 0) return 0;
  return Math.floor(ms / (24 * 60 * 60 * 1000));
}

/**
 * Weekly cadence nudge: never applied to wiki, or last apply ≥ dueAfterDays ago.
 * Draft generate/save does not reset this. Suppressed while generate/apply runs.
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

/** Corner chip when due (option 4); empty when caught up on apply cadence. */
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
