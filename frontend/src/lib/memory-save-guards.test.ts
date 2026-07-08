import { describe, expect, it } from "vitest";

import {
  isMemoryReCommitBlocked,
  isMemoryReviewSaveDisabled,
  shouldShowReviewBrief,
} from "./memory-save-guards";

describe("isMemoryReviewSaveDisabled", () => {
  it("blocks review save while chat is updating", () => {
    expect(
      isMemoryReviewSaveDisabled({
        saving: false,
        isUpdating: true,
        hasLessonResultsApproved: true,
      }),
    ).toBe(true);
  });

  it("allows review save only when idle and lesson results are approved", () => {
    expect(
      isMemoryReviewSaveDisabled({
        saving: false,
        isUpdating: false,
        hasLessonResultsApproved: true,
      }),
    ).toBe(false);
  });
});

describe("shouldShowReviewBrief", () => {
  it("shows the brief during an open review with items", () => {
    expect(
      shouldShowReviewBrief({ inReview: true, alreadyCommitted: false, itemCount: 7 }),
    ).toBe(true);
  });

  it("hides the brief once the review has committed (no re-save)", () => {
    expect(
      shouldShowReviewBrief({ inReview: true, alreadyCommitted: true, itemCount: 7 }),
    ).toBe(false);
  });

  it("hides the brief when there are no items", () => {
    expect(
      shouldShowReviewBrief({ inReview: true, alreadyCommitted: false, itemCount: 0 }),
    ).toBe(false);
  });
});

describe("isMemoryReCommitBlocked", () => {
  it("blocks a repeat commit once the review has committed", () => {
    expect(isMemoryReCommitBlocked({ saving: false, alreadyCommitted: true })).toBe(true);
  });

  it("blocks a commit already in flight", () => {
    expect(isMemoryReCommitBlocked({ saving: true, alreadyCommitted: false })).toBe(true);
  });

  it("allows the first commit of an open review", () => {
    expect(isMemoryReCommitBlocked({ saving: false, alreadyCommitted: false })).toBe(false);
  });
});
