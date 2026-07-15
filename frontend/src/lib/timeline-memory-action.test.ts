import { describe, expect, it } from "vitest";

import { timelineMemoryAction } from "./timeline-memory-action";

const now = new Date("2026-07-13T12:00:00Z");

describe("timelineMemoryAction", () => {
  it("offers amber Add results for a past planned lesson", () => {
    expect(
      timelineMemoryAction(
        {
          status: "planned",
          date: "2026-07-10",
          memory_draft_id: null,
        },
        now,
      ),
    ).toMatchObject({
      label: "Add results",
      intent: "update_missing_results",
      targetKind: "planned_lesson",
      variant: "attention",
    });
  });

  it("offers black Add results for an upcoming planned lesson", () => {
    expect(
      timelineMemoryAction(
        {
          status: "planned",
          date: "2026-07-20",
          memory_draft_id: null,
        },
        now,
      ),
    ).toMatchObject({
      label: "Add results",
      variant: "inverse",
    });
  });

  it("offers Edit memory draft whenever a matching draft is active", () => {
    expect(
      timelineMemoryAction(
        {
          status: "planned",
          date: "2026-07-10",
          memory_draft_id: "draft-1",
        },
        now,
      ),
    ).toMatchObject({
      label: "Edit memory draft",
      intent: "update_missing_results",
      targetKind: "planned_lesson",
      variant: "attention",
    });
  });

  it("offers outline Correct with agent after results are saved", () => {
    expect(
      timelineMemoryAction(
        {
          status: "taught",
          date: "2026-07-01",
          memory_draft_id: null,
        },
        now,
      ),
    ).toMatchObject({
      label: "Correct with agent",
      intent: "correct_existing_results",
      targetKind: "taught_lesson",
      variant: "outline",
    });
  });
});
