import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { splitDocsMarkdown } from "./markdown";
import { slugify } from "./registry";

const here = dirname(fileURLToPath(import.meta.url));
const startHere = readFileSync(join(here, "../../content/docs/en/start-here.md"), "utf8");

describe("splitDocsMarkdown", () => {
  it("extracts important callout from start-here with CRLF line endings", () => {
    const blocks = splitDocsMarkdown(startHere);
    const callouts = blocks.filter((b) => b.kind === "callout");
    expect(callouts.length).toBeGreaterThanOrEqual(3);
    const important = callouts.find(
      (b) => b.kind === "callout" && b.calloutType === "important",
    );
    expect(important).toBeDefined();
    if (important?.kind === "callout") {
      expect(important.content).toContain("never saves class memory");
      expect(important.content).not.toContain("[!important]");
    }
  });

  it("keeps regular blockquotes in markdown blocks", () => {
    const blocks = splitDocsMarkdown(startHere);
    const betaSection = blocks.find(
      (b) => b.kind === "markdown" && b.content.includes("What the beta tests"),
    );
    expect(betaSection?.kind).toBe("markdown");
    if (betaSection?.kind === "markdown") {
      expect(betaSection.content).toContain("> Can you update class memory");
    }
  });

  it("falls back unknown callout types to note", () => {
    const blocks = splitDocsMarkdown("> [!unknown]\n> Body");
    expect(blocks).toEqual([{ kind: "callout", calloutType: "note", content: "Body" }]);
  });
});

describe("slugify", () => {
  it("normalizes accented headings for stable anchor ids", () => {
    expect(slugify("\u00dcberblick f\u00fcr Lehrkr\u00e4fte")).toBe(
      "uberblick-fur-lehrkrafte",
    );
  });
});
