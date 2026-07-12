import type { MemorySweepReviewResponse } from "@/lib/api";

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
