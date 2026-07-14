import { timelineStatusTone } from "@/lib/timeline-status-tone";

export type TimelineMemoryActionInput = {
  status: "taught" | "planned";
  date: string;
  memory_draft_id?: string | null;
};

export type TimelineMemoryAction = {
  label: "Add results" | "Edit memory draft" | "Correct with agent";
  intent: "update_missing_results" | "correct_existing_results";
  targetKind: "planned_lesson" | "taught_lesson";
  /** Matches timeline status badge tones. */
  variant: "outline" | "attention" | "inverse";
};

/**
 * Row CTA styled like the status badge:
 * - Add results (past/today plan) → amber attention
 * - Upcoming (future plan) → black inverse
 * - Done (taught) → outline (badge already carries dark green)
 */
export function timelineMemoryAction(
  entry: TimelineMemoryActionInput,
  now = new Date(),
): TimelineMemoryAction {
  const planned = entry.status === "planned";
  const tone = timelineStatusTone(entry, now);
  const variant: TimelineMemoryAction["variant"] =
    tone === "add_results"
      ? "attention"
      : tone === "upcoming"
        ? "inverse"
        : "outline";

  return {
    label: entry.memory_draft_id
      ? "Edit memory draft"
      : planned
        ? "Add results"
        : "Correct with agent",
    intent: planned ? "update_missing_results" : "correct_existing_results",
    targetKind: planned ? "planned_lesson" : "taught_lesson",
    variant,
  };
}
