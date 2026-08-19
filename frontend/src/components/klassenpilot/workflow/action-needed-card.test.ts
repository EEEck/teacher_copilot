import React, { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { WorkflowActionNeededCard } from "./action-needed-card";

Object.assign(globalThis, { React });

describe("WorkflowActionNeededCard", () => {
  it("renders action-needed copy with respond CTA by default", () => {
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

  it("can omit the respond CTA", () => {
    const html = renderToStaticMarkup(
      createElement(WorkflowActionNeededCard, {
        message: "Needs a decision.",
        respondInChat: false,
      }),
    );

    expect(html).not.toContain("Respond in chat");
  });
});
