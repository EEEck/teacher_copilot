import { describe, expect, it } from "vitest";

import { classHomeWatchItems } from "./class-home-watch";

describe("classHomeWatchItems", () => {
  it("prefers misconceptions and caps at three unique items", () => {
    expect(
      classHomeWatchItems(
        ["Charge vs oxidation number", "Subscripts vs coefficients", "Oxidation needs oxygen", "Extra"],
        ["Watch from brief"],
      ),
    ).toEqual([
      "Charge vs oxidation number",
      "Subscripts vs coefficients",
      "Oxidation needs oxygen",
    ]);
  });

  it("falls back to brief watch items when misconceptions are empty", () => {
    expect(classHomeWatchItems([], ["A", "B"])).toEqual(["A", "B"]);
  });

  it("dedupes case-insensitively across sources", () => {
    expect(
      classHomeWatchItems(["Same Item"], ["same item", "Other"]),
    ).toEqual(["Same Item", "Other"]);
  });
});
