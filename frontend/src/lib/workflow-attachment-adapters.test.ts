import { describe, expect, it } from "vitest";

import { composerHasRunningAttachments } from "@/lib/workflow-attachment-adapters";

describe("composerHasRunningAttachments", () => {
  it("is false when empty or ready", () => {
    expect(composerHasRunningAttachments([])).toBe(false);
    expect(
      composerHasRunningAttachments([
        { status: { type: "requires-action" } },
        { status: { type: "complete" } },
      ]),
    ).toBe(false);
  });

  it("is true when any attachment is running", () => {
    expect(
      composerHasRunningAttachments([
        { status: { type: "requires-action" } },
        { status: { type: "running" } },
      ]),
    ).toBe(true);
  });

  it("does not block on failed incomplete tiles", () => {
    expect(
      composerHasRunningAttachments([
        { status: { type: "incomplete" } },
      ]),
    ).toBe(false);
  });
});
