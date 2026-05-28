import type { CompletenessChecklist } from "@/lib/api";

/** True when no required diary sections have content yet. */
export function isDiaryEmpty(
  diaryMarkdown: string,
  checklist: CompletenessChecklist | null,
): boolean {
  if (!checklist?.items.length) return !diaryMarkdown.trim();
  return !checklist.items.some((item) => item.complete);
}
