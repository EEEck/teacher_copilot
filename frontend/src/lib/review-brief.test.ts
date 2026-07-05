import { describe, expect, it } from "vitest";

import type { FileChange } from "@/components/klassenpilot/review/types";
import { briefFromChanges, briefLessonDate } from "./review-brief";

const CLASS = "wiki/classes/chemie_9b_2026_27";

function change(path: string, overrides: Partial<FileChange> = {}): FileChange {
  return {
    path,
    before: "# Page\n\n- existing note\n",
    after: "# Page\n\n- existing note\n- another note\n",
    approved: true,
    ...overrides,
  };
}

describe("briefFromChanges", () => {
  it("categorizes new, updated, and removed changes", () => {
    const entries = briefFromChanges([
      change(`${CLASS}/students/S-046.md`, { before: "" }),
      change(`${CLASS}/misconceptions.md`),
      change(`${CLASS}/open_loops.md`, {
        before: "# Notes\n\n- one\n- two\n- three\n",
        after: "# Notes\n\n- one\n",
      }),
    ]);
    const byPath = Object.fromEntries(entries.map((e) => [e.path, e]));
    expect(byPath[`${CLASS}/students/S-046.md`].category).toBe("new");
    expect(byPath[`${CLASS}/misconceptions.md`].category).toBe("updated");
    expect(byPath[`${CLASS}/open_loops.md`].category).toBe("removed");
  });

  it("pairs the raw archive copy into the lesson-results entry", () => {
    const entries = briefFromChanges([
      change(`${CLASS}/lessons/2026-07-02/lesson_results.md`, { before: "", required: true }),
      change("raw/classes/chemie_9b_2026_27/2026-07-02-redox.md", { before: "" }),
      change(`${CLASS}/timeline.md`),
    ]);
    expect(entries).toHaveLength(2);
    const lesson = entries.find((e) => e.path.endsWith("lesson_results.md"));
    expect(lesson?.paths).toContain("raw/classes/chemie_9b_2026_27/2026-07-02-redox.md");
    expect(lesson?.label).toBe("Lesson results for 2026-07-02 (incl. archive copy)");
    expect(lesson?.required).toBe(true);
  });

  it("uses friendly labels and teacher-facing summaries", () => {
    const entries = briefFromChanges([
      change(`${CLASS}/timeline.md`),
      change(`${CLASS}/course_state.md`),
      change(`${CLASS}/misconceptions.md`, {
        before: "# Misconceptions\n",
        after: "# Misconceptions\n\n## 2026-07-02\n- charge vs oxidation number\n- phosphate confusion\n",
      }),
    ]);
    const byPath = Object.fromEntries(entries.map((e) => [e.path, e]));
    expect(byPath[`${CLASS}/timeline.md`].label).toBe("Lesson timeline");
    expect(byPath[`${CLASS}/timeline.md`].summary).toBe("entry for this lesson");
    expect(byPath[`${CLASS}/course_state.md`].summary).toBe(
      "current unit & next focus refreshed",
    );
    expect(byPath[`${CLASS}/misconceptions.md`].summary).toContain("notes added");
  });

  it("resolves student display names from the overview table", () => {
    const entries = briefFromChanges([
      change(`${CLASS}/students/S-046.md`, { before: "" }),
      change(`${CLASS}/students.md`, {
        after: "| ID | Name | Note | Page |\n|---|---|---|---|\n| S-046 | Mira Lange | quiet | [x](y) |\n",
      }),
    ]);
    const student = entries.find((e) => e.path.endsWith("S-046.md"));
    expect(student?.label).toBe("Student Mira Lange (S-046)");
  });

  it("keeps IDs when the overview has no real name", () => {
    const entries = briefFromChanges([
      change(`${CLASS}/students/S-033.md`),
      change(`${CLASS}/students.md`, {
        after: "| ID | Name | Note | Page |\n|---|---|---|---|\n| S-033 | S-033 | note | [x](y) |\n",
      }),
    ]);
    const student = entries.find((e) => e.path.endsWith("S-033.md"));
    expect(student?.label).toBe("Student S-033");
  });

  it("an entry is only approved when all covered paths are approved", () => {
    const entries = briefFromChanges([
      change(`${CLASS}/lessons/2026-07-02/lesson_results.md`, { before: "" }),
      change("raw/classes/chemie_9b_2026_27/2026-07-02-redox.md", {
        before: "",
        approved: false,
      }),
    ]);
    expect(entries[0].approved).toBe(false);
  });

  it("orders lesson results before student pages before rollups", () => {
    const entries = briefFromChanges([
      change(`${CLASS}/open_loops.md`),
      change(`${CLASS}/students/S-014.md`),
      change(`${CLASS}/lessons/2026-07-02/lesson_results.md`, { before: "" }),
    ]);
    expect(entries.map((e) => e.path)).toEqual([
      `${CLASS}/lessons/2026-07-02/lesson_results.md`,
      `${CLASS}/students/S-014.md`,
      `${CLASS}/open_loops.md`,
    ]);
  });
});

describe("briefLessonDate", () => {
  it("extracts the lesson date from the results path", () => {
    expect(
      briefLessonDate([change(`${CLASS}/lessons/2026-07-02/lesson_results.md`)]),
    ).toBe("2026-07-02");
    expect(briefLessonDate([change(`${CLASS}/timeline.md`)])).toBeNull();
  });
});
