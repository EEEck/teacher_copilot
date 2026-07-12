import { describe, expect, it } from "vitest";

import { timelineMemoryAction } from "./timeline-memory-action";

describe("timelineMemoryAction", () => {
  it("offers Add results for a planned lesson without a draft", () => {
    expect(
      timelineMemoryAction({
        status: "planned",
        memory_draft_id: null,
      }),
    ).toMatchObject({
      label: "Add results",
      intent: "update_missing_results",
      targetKind: "planned_lesson",
    });
  });

  it("offers Edit memory draft whenever a matching draft is active", () => {
    expect(
      timelineMemoryAction({
        status: "planned",
        memory_draft_id: "draft-1",
      }),
    ).toMatchObject({
      label: "Edit memory draft",
      intent: "update_missing_results",
      targetKind: "planned_lesson",
    });
  });

  it("offers Correct with agent after results are saved", () => {
    expect(
      timelineMemoryAction({
        status: "taught",
        memory_draft_id: null,
      }),
    ).toMatchObject({
      label: "Correct with agent",
      intent: "correct_existing_results",
      targetKind: "taught_lesson",
    });
  });
});
