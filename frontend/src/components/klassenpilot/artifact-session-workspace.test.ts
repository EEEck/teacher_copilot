import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const workspaceSource = readFileSync(
  fileURLToPath(new URL("./artifact-session-workspace.tsx", import.meta.url)),
  "utf8",
);

describe("ArtifactSessionWorkspace review layout", () => {
  it("pins the selected diff in most of the workspace while preserving transcript space", () => {
    expect(workspaceSource).toContain('className="h-[70%] shrink-0 overflow-y-auto border-b border-border p-3"');
    expect(workspaceSource).not.toContain("max-h-[42%]");
  });
});
