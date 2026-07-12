import { describe, expect, it } from "vitest";

import { memoryDiscardRedirectHref } from "./memory-discard-routing";

describe("memoryDiscardRedirectHref", () => {
  it("returns to class home after discarding a timeline-hinted draft", () => {
    expect(
      memoryDiscardRedirectHref({
        classId: "chemie_9b_2026_27",
        hasTimelineHint: true,
      }),
    ).toBe("/classes/chemie_9b_2026_27");
  });

  it("keeps general update memory on the page after discard", () => {
    expect(
      memoryDiscardRedirectHref({
        classId: "chemie_9b_2026_27",
        hasTimelineHint: false,
      }),
    ).toBeNull();
  });
});
