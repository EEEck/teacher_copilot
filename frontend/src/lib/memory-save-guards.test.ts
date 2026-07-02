import { describe, expect, it } from "vitest";

import { isMemoryReviewSaveDisabled } from "./memory-save-guards";

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
