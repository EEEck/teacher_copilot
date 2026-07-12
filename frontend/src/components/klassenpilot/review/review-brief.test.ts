import React, { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

describe("ReviewBrief", () => {
  it("keeps the save action disabled and shows a spinner while saving", async () => {
    Object.assign(globalThis, { React });
    const { ReviewBrief } = await import("./review-brief");
    const html = renderToStaticMarkup(
      createElement(ReviewBrief, {
        items: [
          {
            path: "wiki/classes/c1/lessons/2026-07-09/lesson_plan.md",
            before: "",
            after: "# Plan",
            approved: true,
            required: true,
          },
        ],
        selectedPath: null,
        onSetApproved: vi.fn(),
        onUndoAll: vi.fn(),
        onKeepAll: vi.fn(),
        onSave: vi.fn(),
        saving: true,
      }),
    );

    expect(html).toContain("disabled");
    expect(html).toContain("Saving");
    expect(html).toContain("animate-spin");
  });
});
