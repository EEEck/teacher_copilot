import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const editorSource = readFileSync(
  fileURLToPath(new URL("./markdown-editor-panel.tsx", import.meta.url)),
  "utf8",
);
const artifactSource = readFileSync(
  fileURLToPath(new URL("./artifact-draft-panel.tsx", import.meta.url)),
  "utf8",
);
const diarySource = readFileSync(
  fileURLToPath(new URL("./diary-draft-panel.tsx", import.meta.url)),
  "utf8",
);

describe("plan Context tab wiring", () => {
  it("lets MarkdownEditorPanel add a Context extra view", () => {
    expect(editorSource).toContain("extraViews");
    expect(editorSource).toContain("Preview");
    expect(editorSource).toContain("Edit");
  });

  it("exposes Context on artifact drafts only when a contextPanel is passed", () => {
    expect(artifactSource).toContain("contextPanel");
    expect(artifactSource).toContain('label: "Context"');
    expect(diarySource).not.toContain("contextPanel");
  });
});
