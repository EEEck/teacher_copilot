import { describe, expect, it } from "vitest";
import type { MemorySweepReviewResponse } from "@/lib/api";
import {
  memorySweepLoadingSavedText,
  memorySweepProgressText,
  memorySweepReviewBadge,
} from "./memory-sweep-review-status";

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
    stale_reasons: [],
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

  it("shows stale draft only when teacher edits are at risk", () => {
    expect(
      memorySweepReviewBadge(
        review({
          status: "ready",
          is_stale: true,
          has_teacher_edits: true,
        }),
      ),
    ).toBe("Stale draft");
    expect(
      memorySweepReviewBadge(
        review({ status: "stale", is_stale: true, has_teacher_edits: true }),
      ),
    ).toBe("Stale draft");
  });

  it("keeps Draft saved for unedited fingerprint drift", () => {
    expect(
      memorySweepReviewBadge(
        review({ status: "ready", is_stale: true, has_teacher_edits: false }),
      ),
    ).toMatch(/^Draft saved/);
    expect(
      memorySweepReviewBadge(
        review({ status: "stale", is_stale: true, has_teacher_edits: false }),
      ),
    ).toMatch(/^Draft saved/);
  });

  it("hides completed and missing reviews", () => {
    expect(memorySweepReviewBadge(null)).toBe("");
    expect(memorySweepReviewBadge(review({ status: "completed" }))).toBe("");
  });

  it("keeps the class-home badge short while generation is durable", () => {
    expect(memorySweepReviewBadge(review({ status: "generating" }))).toBe(
      "Generating...",
    );
  });

  it("separates short saved-results open from long generation copy", () => {
    expect(memorySweepLoadingSavedText()).toBe(
      "Loading saved Memory Sweep results… Usually a few seconds.",
    );
    expect(memorySweepProgressText(review({ status: "generating" }))).toBe(
      "Generating updated memory candidates… This can take 1–2 minutes.",
    );
    expect(memorySweepProgressText(review({ status: "ready" }))).toBe("");
  });
});
