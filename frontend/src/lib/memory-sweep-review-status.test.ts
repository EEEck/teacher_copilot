import { describe, expect, it } from "vitest";
import type { MemorySweepReviewResponse } from "@/lib/api";
import { memorySweepReviewBadge } from "./memory-sweep-review-status";

function review(
  overrides: Partial<MemorySweepReviewResponse>,
): MemorySweepReviewResponse {
  return {
    review_id: "review_1",
    class_id: "chemie_9b_2026_27",
    status: "ready",
    source_fingerprint: "fp",
    generated_at: "2026-07-09T08:00:00Z",
    updated_at: "2026-07-09T08:00:00Z",
    completed_at: null,
    is_stale: false,
    has_teacher_edits: false,
    queues: {},
    decisions: [],
    warnings: [],
    error: "",
    ...overrides,
  };
}

describe("memorySweepReviewBadge", () => {
  it("shows saved draft date for ready reviews", () => {
    expect(memorySweepReviewBadge(review({ status: "ready" }))).toMatch(
      /^Draft saved /,
    );
  });

  it("shows stale draft before ready state", () => {
    expect(
      memorySweepReviewBadge(review({ status: "ready", is_stale: true })),
    ).toBe("Stale draft");
  });

  it("hides completed and missing reviews", () => {
    expect(memorySweepReviewBadge(null)).toBe("");
    expect(memorySweepReviewBadge(review({ status: "completed" }))).toBe("");
  });
});

