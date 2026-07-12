export type WorkflowTurnActivityInput = {
  localStreamActive: boolean;
  backendTurnInProgress: boolean;
};

/**
 * Separates the current tab's SSE lifecycle from the durable backend turn.
 * assistant-ui owns the former; the workflow draft owns the latter.
 */
export function workflowTurnActivity({
  localStreamActive,
  backendTurnInProgress,
}: WorkflowTurnActivityInput) {
  return {
    runtimeIsRunning: localStreamActive,
    showResumedTurnStatus: backendTurnInProgress && !localStreamActive,
  };
}
