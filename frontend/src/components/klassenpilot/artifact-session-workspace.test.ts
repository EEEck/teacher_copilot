import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const workspaceSource = readFileSync(
  fileURLToPath(new URL("./artifact-session-workspace.tsx", import.meta.url)),
  "utf8",
);

describe("ArtifactSessionWorkspace review layout", () => {
  it("pins the selected diff in most of the workspace while preserving transcript space", () => {
    // Assert the durable layout intent (diff pinned to ~70%, shrink-0, bottom
    // border) rather than an exact className string, so class-list tweaks don't
    // break the test while a real layout regression still would.
    expect(workspaceSource).toContain("h-[70%]");
    expect(workspaceSource).toContain("shrink-0");
    expect(workspaceSource).toContain("border-b border-border");
    expect(workspaceSource).not.toContain("max-h-[42%]");
  });
});
