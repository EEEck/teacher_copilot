import type { TimelineEntry } from "@/lib/api";

export type TimelineStatusTone = "done" | "upcoming" | "add_results";

function todayKey(now = new Date()): string {
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/** Shared status for timeline badges and matching row CTAs. */
export function timelineStatusTone(
  entry: Pick<TimelineEntry, "status" | "date">,
  now = new Date(),
): TimelineStatusTone {
  if (entry.status === "taught") return "done";
  if (entry.date > todayKey(now)) return "upcoming";
  return "add_results";
}

/** Badge classNames for tones outside default primary green. */
export const TIMELINE_STATUS_BADGE_CLASS = {
  upcoming: "border-transparent bg-foreground text-background",
  add_results:
    "border-amber-200 bg-amber-50 text-amber-950 hover:bg-amber-50",
} as const;
