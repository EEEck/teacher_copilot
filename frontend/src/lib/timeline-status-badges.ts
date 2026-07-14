import type { TimelineEntry } from "@/lib/api";
import {
  TIMELINE_STATUS_BADGE_CLASS,
  timelineStatusTone,
} from "@/lib/timeline-status-tone";

export type TimelineStatusBadge = {
  label: string;
  variant: "default" | "secondary" | "outline";
  /** Extra classes for tones outside Badge variants (black / amber). */
  className?: string;
};

/**
 * Simple teacher-facing status (one chip):
 * - Upcoming (black): plan only, date still ahead
 * - Add results (amber): plan only, date today/past — action owed
 * - Done (dark green): lesson results exist
 */
export function timelineStatusBadges(
  entry: Pick<TimelineEntry, "status" | "date">,
  now = new Date(),
): TimelineStatusBadge[] {
  const tone = timelineStatusTone(entry, now);
  if (tone === "done") {
    return [{ label: "Done", variant: "default" }];
  }
  if (tone === "upcoming") {
    return [
      {
        label: "Upcoming",
        variant: "outline",
        className: TIMELINE_STATUS_BADGE_CLASS.upcoming,
      },
    ];
  }
  return [
    {
      label: "Add results",
      variant: "outline",
      className: TIMELINE_STATUS_BADGE_CLASS.add_results,
    },
  ];
}
