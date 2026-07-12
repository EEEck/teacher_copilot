import { describe, expect, it } from "vitest";

import { workflowTurnActivity } from "./workflow-turn-activity";

describe("workflowTurnActivity", () => {
  it("keeps backend work distinct from the current tab's live stream", () => {
    expect(
      workflowTurnActivity({
        localStreamActive: false,
        backendTurnInProgress: true,
      }),
    ).toEqual({
      runtimeIsRunning: false,
      showResumedTurnStatus: true,
    });
  });

  it("uses the live stream instead of the resumed status in the active tab", () => {
    expect(
      workflowTurnActivity({
        localStreamActive: true,
        backendTurnInProgress: true,
      }),
    ).toEqual({
      runtimeIsRunning: true,
      showResumedTurnStatus: false,
    });
  });
});
