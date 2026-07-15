/**
 * Single owner for plan / ingest / discuss chat turn lifecycle (MVP hybrid).
 * UI maps these flags via workflowTurnActivity — do not set competing clears.
 */

export type WorkflowTurnPhase =
  | "idle"
  | "streaming"
  | "backend_running"
  | "complete"
  | "failed";

export type WorkflowTurnFlags = {
  localStreamActive: boolean;
  turnInProgress: boolean;
  latestTurnComplete: boolean;
};

export function flagsForPhase(phase: WorkflowTurnPhase): WorkflowTurnFlags {
  switch (phase) {
    case "idle":
      return {
        localStreamActive: false,
        turnInProgress: false,
        latestTurnComplete: true,
      };
    case "streaming":
      return {
        localStreamActive: true,
        turnInProgress: true,
        latestTurnComplete: false,
      };
    case "backend_running":
      return {
        localStreamActive: false,
        turnInProgress: true,
        latestTurnComplete: false,
      };
    case "complete":
      return {
        localStreamActive: false,
        turnInProgress: false,
        latestTurnComplete: true,
      };
    case "failed":
      return {
        localStreamActive: false,
        turnInProgress: false,
        latestTurnComplete: true,
      };
  }
}

/**
 * After the browser SSE loop ends, decide the durable phase.
 * - final → complete (spinner off)
 * - partial streamed content, no final → backend may still run (spinner on)
 * - nothing useful streamed → failed
 */
export function resolveClientStreamEnd(args: {
  gotFinal: boolean;
  hadStreamedContent: boolean;
}): WorkflowTurnPhase {
  if (args.gotFinal) return "complete";
  if (args.hadStreamedContent) return "backend_running";
  return "failed";
}

export function applyBackendDraftFlags(args: {
  turnInProgress: boolean;
  latestTurnComplete: boolean;
}): WorkflowTurnPhase {
  if (args.turnInProgress) return "backend_running";
  if (args.latestTurnComplete) return "complete";
  return "idle";
}
