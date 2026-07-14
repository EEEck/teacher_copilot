import { describe, expect, it } from "vitest";
import { timelineStatusBadges } from "./timeline-status-badges";

const now = new Date("2026-07-13T12:00:00Z");

describe("timelineStatusBadges", () => {
  it("marks future plans as black Upcoming", () => {
    expect(
      timelineStatusBadges({ status: "planned", date: "2026-07-20" }, now),
    ).toMatchObject([
      {
        label: "Upcoming",
        className: expect.stringContaining("bg-foreground"),
      },
    ]);
  });

  it("marks past/today plans as amber Add results", () => {
    expect(
      timelineStatusBadges({ status: "planned", date: "2026-07-10" }, now),
    ).toMatchObject([
      {
        label: "Add results",
        className: expect.stringContaining("bg-amber-50"),
      },
    ]);
  });

  it("marks taught lessons as dark green Done", () => {
    expect(
      timelineStatusBadges({ status: "taught", date: "2026-07-01" }, now),
    ).toEqual([{ label: "Done", variant: "default" }]);
  });
});
