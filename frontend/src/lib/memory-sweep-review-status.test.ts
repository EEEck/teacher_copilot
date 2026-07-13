import { describe, expect, it } from "vitest";
import type { MemorySweepReviewResponse } from "@/lib/api";
import {
  memorySweepDueBadge,
  memorySweepIsDue,
  memorySweepLoadingSavedText,
  memorySweepProgressText,
  memorySweepReviewAttentionBadge,
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

describe("memorySweepReviewAttentionBadge", () => {
  it("hides quiet Draft saved on solid primary CTAs", () => {
    expect(memorySweepReviewAttentionBadge(review({ status: "ready" }))).toBe(
      "",
    );
    expect(
      memorySweepReviewAttentionBadge(
        review({ status: "ready", is_stale: true, has_teacher_edits: false }),
      ),
    ).toBe("");
  });

  it("keeps generating / stale / failed visible", () => {
    expect(
      memorySweepReviewAttentionBadge(review({ status: "generating" })),
    ).toBe("Generating...");
    expect(
      memorySweepReviewAttentionBadge(
        review({
          status: "stale",
          is_stale: true,
          has_teacher_edits: true,
        }),
      ),
    ).toBe("Stale draft");
    expect(memorySweepReviewAttentionBadge(review({ status: "failed" }))).toBe(
      "Failed",
    );
  });
});

describe("memorySweep due cadence", () => {
  const now = new Date("2026-07-12T12:00:00Z");

  it("is due when never applied (draft open does not count)", () => {
    expect(memorySweepIsDue(null, { now })).toBe(true);
    expect(memorySweepDueBadge(null, { now })).toBe("Due · weekly");
    expect(memorySweepIsDue(review({ status: "none" }), { now })).toBe(true);
    expect(
      memorySweepIsDue(
        review({
          status: "ready",
          updated_at: "2026-07-12T08:00:00Z",
          generated_at: "2026-07-12T08:00:00Z",
          completed_at: null,
        }),
        { now },
      ),
    ).toBe(true);
    expect(
      memorySweepDueBadge(
        review({
          status: "ready",
          updated_at: "2026-07-12T08:00:00Z",
          completed_at: null,
        }),
        { now },
      ),
    ).toBe("Due · weekly");
  });

  it("is due after 5+ days since last apply", () => {
    expect(
      memorySweepIsDue(
        review({
          status: "completed",
          completed_at: "2026-07-01T08:00:00Z",
          updated_at: "2026-07-12T08:00:00Z",
        }),
        { now },
      ),
    ).toBe(true);
    expect(
      memorySweepDueBadge(
        review({
          status: "completed",
          completed_at: "2026-07-01T08:00:00Z",
        }),
        { now },
      ),
    ).toBe("Due · 5+ days");
  });

  it("is caught up within 5 days of last apply even with a fresh draft", () => {
    expect(
      memorySweepIsDue(
        review({
          status: "ready",
          completed_at: "2026-07-10T08:00:00Z",
          updated_at: "2026-07-12T08:00:00Z",
          generated_at: "2026-07-12T08:00:00Z",
        }),
        { now },
      ),
    ).toBe(false);
    expect(
      memorySweepDueBadge(
        review({
          status: "ready",
          completed_at: "2026-07-10T08:00:00Z",
          updated_at: "2026-07-12T08:00:00Z",
        }),
        { now },
      ),
    ).toBe("");
  });

  it("suppresses due while generating", () => {
    expect(
      memorySweepIsDue(
        review({
          status: "generating",
          completed_at: null,
          updated_at: "2026-06-01T08:00:00Z",
        }),
        { now },
      ),
    ).toBe(false);
  });
});
