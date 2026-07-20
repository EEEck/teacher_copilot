import React, { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ThreadActivity } from "./thread-activity";

describe("ThreadActivity", () => {
  it("renders runtime-owned content outside the message list", () => {
    const html = renderToStaticMarkup(
      createElement(
        ThreadActivity,
        null,
        createElement("p", null, "Review ready"),
      ),
    );

    expect(html).toContain('data-slot="thread-activity"');
    expect(html).toContain("Review ready");
  });
});
