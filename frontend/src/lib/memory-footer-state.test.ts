import { describe, expect, it } from "vitest";

import { getReadyToSaveButtonLabel } from "./memory-footer-state";

describe("memory footer state", () => {
  it("does not label draft discard as memory compilation", () => {
    expect(getReadyToSaveButtonLabel("idle")).toBe("Ready to save memory");
    expect(getReadyToSaveButtonLabel("compiling")).toBe("Compiling wiki updates...");
    expect(getReadyToSaveButtonLabel("discarding")).toBe("Ready to save memory");
  });
});
