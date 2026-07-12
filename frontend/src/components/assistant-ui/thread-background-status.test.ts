import React, { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

describe("ThreadRunningIndicator", () => {
  it(
    "reserves the fallback for a resumed backend turn",
    async () => {
      const { shouldShowResumedTurnStatus } = await import("./thread");

      expect(shouldShowResumedTurnStatus(true, false)).toBe(true);
      expect(shouldShowResumedTurnStatus(true, true)).toBe(false);
      expect(shouldShowResumedTurnStatus(false, true)).toBe(false);
    },
    15_000,
  );

  it(
    "shows backend-owned work after the local runtime remounts",
    async () => {
      Object.assign(globalThis, { React });
      const { WorkingStatus } = await import("./thread");

      const html = renderToStaticMarkup(createElement(WorkingStatus));

      expect(html).toContain("Still working on your response");
      expect(html).toContain("animate-spin");
      expect(html).toContain('role="status"');
    },
    15_000,
  );
});
