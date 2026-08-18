import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { groupPlanMaterials } from "@/lib/plan-context-groups";

const source = readFileSync(
  fileURLToPath(new URL("./plan-context-panel.tsx", import.meta.url)),
  "utf8",
);

describe("PlanContextPanel", () => {
  it("groups uploaded materials by textbook then personal", () => {
    const grouped = groupPlanMaterials([
      {
        material_id: "mat_p",
        arm: "personal",
        title: "Worksheet",
        summary: "",
        page_count: 1,
      },
      {
        material_id: "mat_t",
        arm: "textbook",
        title: "Chapter",
        summary: "",
        page_count: 2,
      },
    ]);
    expect(grouped.textbook.map((item) => item.material_id)).toEqual(["mat_t"]);
    expect(grouped.personal.map((item) => item.material_id)).toEqual(["mat_p"]);
  });

  it("keeps uploaded materials, class memory, and always-in-context as separate categories", () => {
    expect(source).toContain("Uploaded materials");
    expect(source).toContain("Textbook");
    expect(source).toContain("Personal");
    expect(source).toContain("Class memory");
    expect(source).toContain("Always in context");
    expect(source).toContain("Remove");
  });
});
