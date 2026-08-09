import { describe, expect, it } from "vitest";

import {
  parseMaterialAssetFilename,
  resolveMaterialAssetSrc,
} from "@/lib/material-asset-urls";

describe("material-asset-urls", () => {
  it("parses bare and path-tailed assets filenames", () => {
    expect(parseMaterialAssetFilename("assets/img-0.jpeg")).toBe("img-0.jpeg");
    expect(parseMaterialAssetFilename("./assets/img-8.jpg")).toBe("img-8.jpg");
    expect(parseMaterialAssetFilename("foo/assets/tbl-1.png")).toBe("tbl-1.png");
    expect(parseMaterialAssetFilename("https://example.com/x.png")).toBeNull();
    expect(parseMaterialAssetFilename("assets/../secret.jpeg")).toBeNull();
  });

  it("rewrites relative assets src when session materials exist", () => {
    const src = resolveMaterialAssetSrc("assets/img-0.jpeg", {
      classId: "chemie_9b_2026_27",
      sessionId: "sess_1",
      materialIds: ["mat_abc"],
    });
    expect(src).toContain("/api/classes/chemie_9b_2026_27/plan/sessions/sess_1/");
    expect(src).toContain("/materials/mat_abc/assets/img-0.jpeg");
  });

  it("leaves src unchanged without materials context", () => {
    expect(resolveMaterialAssetSrc("assets/img-0.jpeg", null)).toBe(
      "assets/img-0.jpeg",
    );
  });
});
