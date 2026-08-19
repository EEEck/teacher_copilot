import React, { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { shouldShowResumedTurnStatus, WorkingStatus } from "./thread";

Object.assign(globalThis, { React });

describe("ThreadRunningIndicator", () => {
  it("reserves the fallback for a resumed backend turn", () => {
    expect(shouldShowResumedTurnStatus(true, false)).toBe(true);
    expect(shouldShowResumedTurnStatus(true, true)).toBe(false);
    expect(shouldShowResumedTurnStatus(false, true)).toBe(false);
  });

  it("shows backend-owned work after the local runtime remounts", () => {
    const html = renderToStaticMarkup(createElement(WorkingStatus));

    expect(html).toContain("Still working on your response");
    expect(html).toContain("animate-spin");
    expect(html).toContain('role="status"');
  });
});
