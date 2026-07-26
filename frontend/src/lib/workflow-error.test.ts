import { describe, expect, it, vi } from "vitest";

import { WriteVerificationBlockedError } from "@/lib/api";
import {
  classifyWorkflowError,
  routeWorkflowError,
} from "@/lib/workflow-error";

describe("classifyWorkflowError", () => {
  it("routes executive write-gate blocks to action_needed with chat CTA", () => {
    const err = new WriteVerificationBlockedError({
      code: "write_verification_blocked",
      action: "plan_save",
      artifact_fingerprint: "fp",
      executive_state: {
        open_findings: [
          {
            summary: "Date looks off.",
            question: "Keep 2026-07-25?",
            severity: "blocking",
          },
        ],
      },
      message: "I didn't save this yet; one detail needs your call.",
    });

    const classified = classifyWorkflowError(err, "Save failed");
    expect(classified.channel).toBe("action_needed");
    expect(classified.respondInChat).toBe(true);
    expect(classified.message).toContain("needs your call");
    expect(classified.message).toContain("Date looks off");
  });

  it("routes ordinary failures to the system banner channel", () => {
    const classified = classifyWorkflowError(
      new Error("Network down"),
      "Save failed",
    );
    expect(classified).toEqual({
      channel: "system",
      message: "Network down",
      respondInChat: false,
    });
  });
});

describe("routeWorkflowError", () => {
  it("dispatches to the matching channel handler", () => {
    const onActionNeeded = vi.fn();
    const onSystem = vi.fn();

    routeWorkflowError(
      {
        channel: "action_needed",
        message: "Decide this",
        respondInChat: true,
      },
      { onActionNeeded, onSystem },
    );
    expect(onActionNeeded).toHaveBeenCalledWith({
      message: "Decide this",
      respondInChat: true,
    });
    expect(onSystem).not.toHaveBeenCalled();

    routeWorkflowError(
      { channel: "system", message: "Offline", respondInChat: false },
      { onActionNeeded, onSystem },
    );
    expect(onSystem).toHaveBeenCalledWith("Offline");
  });
});
