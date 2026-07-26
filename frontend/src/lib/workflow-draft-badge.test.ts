import { describe, expect, it } from "vitest";

import { workflowDraftCornerBadge } from "@/lib/workflow-draft-badge";

describe("workflowDraftCornerBadge", () => {
  it("returns empty when there is no draft", () => {
    expect(workflowDraftCornerBadge(null)).toBe("");
    expect(workflowDraftCornerBadge(undefined)).toBe("");
    expect(workflowDraftCornerBadge({ draft_id: "", mode: "plan" })).toBe("");
  });

  it("returns Draft when a draft id is present", () => {
    expect(
      workflowDraftCornerBadge({ draft_id: "d1", mode: "ingest" }),
    ).toBe("Draft");
    expect(
      workflowDraftCornerBadge({
        draft_id: "d1",
        mode: "plan",
        updated_at: "2026-07-25T12:00:00Z",
      }),
    ).toBe("Draft");
  });
});
