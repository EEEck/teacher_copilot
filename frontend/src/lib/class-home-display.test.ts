import { describe, expect, it } from "vitest";
import {
  formatClassHomeHeading,
  shortenUnitLabel,
} from "./class-home-display";

describe("formatClassHomeHeading", () => {
  it("formats chemie_9b_2026_27 as Chemie 9b with year and STEM track", () => {
    expect(formatClassHomeHeading("chemie_9b_2026_27")).toEqual({
      title: "Chemie 9b",
      year: "2026/27",
      track: "STEM track",
    });
  });

  it("maps language subjects to Language track", () => {
    expect(formatClassHomeHeading("englisch_8a_2025_26").track).toBe(
      "Language track",
    );
  });
});

describe("shortenUnitLabel", () => {
  it("prefers a short late clause from a long unit list", () => {
    expect(
      shortenUnitLabel(
        "Reaction writing, balancing equations, oxidation numbers, and redox with ion follow-up.",
      ),
    ).toMatch(/redox/i);
  });

  it("returns Not set for empty placeholders", () => {
    expect(shortenUnitLabel("-")).toBe("Not set");
    expect(shortenUnitLabel("Not set")).toBe("Not set");
  });
});
