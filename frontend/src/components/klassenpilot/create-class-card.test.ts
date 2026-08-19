import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const source = readFileSync(
  fileURLToPath(new URL("./create-class-card.tsx", import.meta.url)),
  "utf8",
);

describe("CreateClassCard", () => {
  it("uses reviewed routes, the shared API client, and design-system fields", () => {
    expect(source).toContain("getCurriculumRoutes");
    expect(source).toContain("createClass");
    expect(source).toContain("NativeSelect");
    expect(source).toContain("FieldLabel");
    expect(source).not.toContain("fetch(");
    expect(source).not.toContain("physik");
  });
});
