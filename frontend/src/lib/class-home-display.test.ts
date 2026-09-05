import { describe, expect, it } from "vitest";
import {
  formatClassHomeHeading,
  shortenUnitLabel,
  classHomeLessonProgress,
} from "./class-home-display";

describe("classHomeLessonProgress", () => {
  it("does not count an empty class or a saved future plan as taught", () => {
    expect(classHomeLessonProgress([])).toEqual({ lastTaught: "Not set", lessonsLogged: 0 });
    expect(classHomeLessonProgress([{ date: "2030-09-05", status: "planned" }])).toEqual({ lastTaught: "Not set", lessonsLogged: 0 });
  });

  it("uses the latest taught date while preserving planned lessons in the timeline", () => {
    expect(classHomeLessonProgress([
      { date: "2030-09-12", status: "planned" },
      { date: "2030-09-05", status: "taught" },
      { date: "2030-09-07", status: "taught" },
    ])).toEqual({ lastTaught: "2030-09-07", lessonsLogged: 2 });
  });
});

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
