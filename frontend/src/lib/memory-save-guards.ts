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

/**
 * The review brief must disappear once the current review has committed, until
 * a fresh review cycle is started (which clears `alreadyCommitted`). Beta
 * telemetry showed a teacher re-clicking Save after a successful commit gave no
 * visible transition, producing a duplicate memory commit; gating the brief on
 * `!alreadyCommitted` makes the second commit impossible.
 */
export function shouldShowReviewBrief({
  inReview,
  alreadyCommitted,
  itemCount,
}: {
  inReview: boolean;
  alreadyCommitted: boolean;
  itemCount: number;
}) {
  return inReview && !alreadyCommitted && itemCount > 0;
}

/** Block a repeat commit of a review that already committed (idempotency). */
export function isMemoryReCommitBlocked({
  saving,
  alreadyCommitted,
}: {
  saving: boolean;
  alreadyCommitted: boolean;
}) {
  return saving || alreadyCommitted;
}
