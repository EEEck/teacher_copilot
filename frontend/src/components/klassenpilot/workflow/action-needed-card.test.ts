import React, { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

describe("WorkflowActionNeededCard", () => {
  it("renders action-needed copy with respond CTA by default", async () => {
    Object.assign(globalThis, { React });
    const { WorkflowActionNeededCard } = await import("./action-needed-card");
    const html = renderToStaticMarkup(
      createElement(WorkflowActionNeededCard, {
        message: "I didn't save this yet; one detail needs your call.",
      }),
    );

    expect(html).toContain("Couldn");
    expect(html).toContain("Respond in chat");
    expect(html).toContain("needs your call");
    expect(html).toContain("bg-[var(--error-bg)]");
  });

  it("can omit the respond CTA", async () => {
    Object.assign(globalThis, { React });
    const { WorkflowActionNeededCard } = await import("./action-needed-card");
    const html = renderToStaticMarkup(
      createElement(WorkflowActionNeededCard, {
        message: "Needs a decision.",
        respondInChat: false,
      }),
    );

    expect(html).not.toContain("Respond in chat");
  });
});
