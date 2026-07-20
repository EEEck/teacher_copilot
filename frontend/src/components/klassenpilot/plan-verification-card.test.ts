import React, { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { PlanVerificationReportCard } from "./plan-verification-card";

describe("PlanVerificationReportCard", () => {
  it("shows a compact advisory activity with optional details", () => {
    const html = renderToStaticMarkup(
      createElement(PlanVerificationReportCard, {
        report: {
          overall_status: "advisory",
          summary: "Confirm the intentional local scope extension.",
          review_state: "complete",
          rows: [
            {
              row_id: "curriculum_scope",
              label: "Curriculum grounding and scope",
              status: "needs_teacher_decision",
              summary: "Organic chemistry is a local extension here.",
            },
          ],
        },
      }),
    );

    expect(html).toContain("Plan review ready");
    expect(html).toContain("Show details");
    expect(html).toContain("Teacher decision");
    expect(html).toContain("Organic chemistry is a local extension here.");
    expect(html).not.toContain("Blocked");
  });

  it("shows progress as a single chat activity while the review runs", () => {
    const html = renderToStaticMarkup(
      createElement(PlanVerificationReportCard, {
        report: {
          overall_status: "clear",
          summary: "",
          review_state: "pending",
          rows: [],
        },
      }),
    );

    expect(html).toContain("Reviewing plan against curriculum, class context, and safety");
    expect(html).not.toContain("Show details");
  });
});
