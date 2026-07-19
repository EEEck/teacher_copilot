import { describe, expect, it } from "vitest";

import {
  applyBackendDraftFlags,
  flagsForPhase,
  resolveClientStreamEnd,
} from "./workflow-turn-state";
import { workflowTurnActivity } from "./workflow-turn-activity";

describe("workflow turn state", () => {
  it("maps streaming to local running without resumed spinner", () => {
    const flags = flagsForPhase("streaming");
    expect(
      workflowTurnActivity({
        localStreamActive: flags.localStreamActive,
        backendTurnInProgress: flags.turnInProgress,
      }),
    ).toEqual({
      runtimeIsRunning: true,
      showResumedTurnStatus: false,
    });
  });

  it("maps backend_running to Still working spinner", () => {
    const flags = flagsForPhase("backend_running");
    expect(
      workflowTurnActivity({
        localStreamActive: flags.localStreamActive,
        backendTurnInProgress: flags.turnInProgress,
      }),
    ).toEqual({
      runtimeIsRunning: false,
      showResumedTurnStatus: true,
    });
  });

  it("maps complete and failed to spinner off", () => {
    for (const phase of ["complete", "failed"] as const) {
      const flags = flagsForPhase(phase);
      expect(
        workflowTurnActivity({
          localStreamActive: flags.localStreamActive,
          backendTurnInProgress: flags.turnInProgress,
        }),
      ).toEqual({
        runtimeIsRunning: false,
        showResumedTurnStatus: false,
      });
    }
  });

  it("resolves client stream end into the correct phase", () => {
    expect(
      resolveClientStreamEnd({ gotFinal: true, hadStreamedContent: true }),
    ).toBe("complete");
    expect(
      resolveClientStreamEnd({ gotFinal: false, hadStreamedContent: true }),
    ).toBe("backend_running");
    expect(
      resolveClientStreamEnd({ gotFinal: false, hadStreamedContent: false }),
    ).toBe("failed");
    expect(
      resolveClientStreamEnd({
        gotFinal: false,
        hadStreamedContent: true,
        terminalError: true,
      }),
    ).toBe("failed");
  });

  it("maps draft poll flags into phases", () => {
    expect(
      applyBackendDraftFlags({
        turnInProgress: true,
        latestTurnComplete: false,
      }),
    ).toBe("backend_running");
    expect(
      applyBackendDraftFlags({
        turnInProgress: false,
        latestTurnComplete: true,
      }),
    ).toBe("complete");
  });
});
