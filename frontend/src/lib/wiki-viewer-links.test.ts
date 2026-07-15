import { describe, expect, it } from "vitest";

import {
  normalizeClassWikiPath,
  resolveWikiMarkdownHref,
  wikiViewerHref,
} from "./wiki-viewer-links";

describe("wiki viewer links", () => {
  const classId = "chemie_9b_2026_27";

  it("rewrites retired memory/course_state paths", () => {
    expect(
      normalizeClassWikiPath(
        classId,
        `wiki/classes/${classId}/memory/course_state.md`,
      ),
    ).toBe(`wiki/classes/${classId}/course_state.md`);
  });

  it("resolves roster links relative to students.md", () => {
    const path = resolveWikiMarkdownHref(
      classId,
      "students/S-014.md",
      `wiki/classes/${classId}/students.md`,
    );
    expect(path).toBe(`wiki/classes/${classId}/students/S-014.md`);
    expect(wikiViewerHref(classId, path!)).toContain(
      encodeURIComponent(`wiki/classes/${classId}/students/S-014.md`),
    );
  });

  it("leaves external links alone", () => {
    expect(
      resolveWikiMarkdownHref(
        classId,
        "https://example.com",
        `wiki/classes/${classId}/students.md`,
      ),
    ).toBeNull();
  });
});
