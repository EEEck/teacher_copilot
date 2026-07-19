import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const threadSource = readFileSync(
  fileURLToPath(new URL("./thread.tsx", import.meta.url)),
  "utf8",
);

describe("Thread action-bar contract", () => {
  it("does not expose reload without an external-store reload handler", () => {
    expect(threadSource).not.toContain("ActionBarPrimitive.Reload");
  });
});
