import type { MemorySweepReviewResponse } from "@/lib/api";

export function memorySweepReviewBadge(
  review: MemorySweepReviewResponse | null,
): string {
  if (!review || review.status === "none") return "";
  if (review.status === "generating" || review.status === "applying") {
    return review.status === "applying" ? "Applying..." : "Generating...";
  }
  if (review.status === "stale" || review.is_stale) return "Stale draft";
  if (review.status === "failed") return "Failed";
  if (review.status !== "ready") return "";
  const date = shortDate(review.updated_at ?? review.generated_at);
  return date ? `Draft saved ${date}` : "Draft saved";
}

function shortDate(value?: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

