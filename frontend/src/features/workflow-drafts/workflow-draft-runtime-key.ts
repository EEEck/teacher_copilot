export function workflowDraftRuntimeKey(
  draftId: string | undefined,
  sessionId: string,
): string {
  return draftId || sessionId;
}
