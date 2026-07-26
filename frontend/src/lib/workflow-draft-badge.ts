import type { ActiveWorkflowDraftHint } from "@/lib/api";

/**
 * Amber corner chip copy for an open Create lesson plan / Update memory draft.
 * Empty when there is no resumable draft.
 */
export function workflowDraftCornerBadge(
  draft: ActiveWorkflowDraftHint | null | undefined,
): string {
  return draft?.draft_id ? "Draft" : "";
}
