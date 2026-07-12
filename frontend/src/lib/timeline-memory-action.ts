export type TimelineMemoryActionInput = {
  status: "taught" | "planned";
  memory_draft_id?: string | null;
};

export type TimelineMemoryAction = {
  label: "Add results" | "Edit memory draft" | "Correct with agent";
  intent: "update_missing_results" | "correct_existing_results";
  targetKind: "planned_lesson" | "taught_lesson";
  variant: "default" | "outline";
};

export function timelineMemoryAction(
  entry: TimelineMemoryActionInput,
): TimelineMemoryAction {
  const planned = entry.status === "planned";
  return {
    label: entry.memory_draft_id
      ? "Edit memory draft"
      : planned
        ? "Add results"
        : "Correct with agent",
    intent: planned ? "update_missing_results" : "correct_existing_results",
    targetKind: planned ? "planned_lesson" : "taught_lesson",
    variant: planned || Boolean(entry.memory_draft_id) ? "default" : "outline",
  };
}
