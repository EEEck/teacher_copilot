import React, { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { PlanSaveConfirm } from "./plan-save-confirm";

Object.assign(globalThis, { React });

describe("PlanSaveConfirm", () => {
  it("shows a footer amber confirm with date control and save CTA", () => {
    const html = renderToStaticMarkup(
      createElement(PlanSaveConfirm, {
        lessonDate: "2026-07-25",
        onLessonDateChange: vi.fn(),
        onConfirm: vi.fn(),
        onCancel: vi.fn(),
      }),
    );

    expect(html).toContain("Confirm save");
    expect(html).toContain("Save plan");
    expect(html).toContain("Cancel");
    expect(html).toContain("lesson-date-confirm");
    expect(html).toContain("bg-amber-50");
    expect(html).toMatch(/Jul(?:y)?\s+25/);
  });

  it("disables actions and shows a spinner while saving", () => {
    const html = renderToStaticMarkup(
      createElement(PlanSaveConfirm, {
        lessonDate: "2026-07-25",
        onLessonDateChange: vi.fn(),
        onConfirm: vi.fn(),
        onCancel: vi.fn(),
        saving: true,
      }),
    );

    expect(html).toContain("disabled");
    expect(html).toContain("Saving");
    expect(html).toContain("animate-spin");
  });
});
