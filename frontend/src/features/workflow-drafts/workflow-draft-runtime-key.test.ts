import { describe, expect, it } from "vitest";

import { workflowDraftRuntimeKey } from "./workflow-draft-runtime-key";

describe("workflowDraftRuntimeKey", () => {
  it("changes only when a fresh durable draft replaces the current session", () => {
    expect(workflowDraftRuntimeKey("draft-1", "session-1")).toBe("draft-1");
    expect(workflowDraftRuntimeKey("draft-2", "session-2")).toBe("draft-2");
    expect(workflowDraftRuntimeKey(undefined, "session-1")).toBe("session-1");
  });
});
