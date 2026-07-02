export function isMemoryReviewSaveDisabled({
  saving,
  isUpdating,
  hasLessonResultsApproved,
}: {
  saving: boolean;
  isUpdating: boolean;
  hasLessonResultsApproved: boolean;
}) {
  return saving || isUpdating || !hasLessonResultsApproved;
}
