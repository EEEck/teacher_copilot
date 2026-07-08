import { diffLineStats, shortWikiPath } from "@/lib/markdown-diff";
import type { FileChange } from "@/components/klassenpilot/review/types";

export type BriefCategory = "new" | "updated" | "removed";

export type BriefEntry = {
  /** Primary wiki path (used as stable key and for [view]/edit). */
  path: string;
  /** All wiki paths this decision covers (includes the paired raw/ copy). */
  paths: string[];
  category: BriefCategory;
  label: string;
  summary: string;
  approved: boolean;
  required?: boolean;
};

const LESSON_RESULTS_RE = /lessons\/(\d{4}-\d{2}-\d{2})\/lesson_results\.md$/;
const LESSON_PLAN_RE = /lessons\/(\d{4}-\d{2}-\d{2})\/lesson_plan\.md$/;
const STUDENT_PAGE_RE = /students\/(S-\d{3})\.md$/i;

/** Order teachers care about: the lesson itself, then students, then rollups. */
function typeRank(path: string): number {
  if (LESSON_RESULTS_RE.test(path)) return 0;
  if (LESSON_PLAN_RE.test(path)) return 1;
  if (STUDENT_PAGE_RE.test(path)) return 2;
  if (path.endsWith("students.md")) return 3;
  if (path.endsWith("timeline.md")) return 4;
  if (path.endsWith("course_state.md")) return 5;
  if (path.endsWith("misconceptions.md")) return 6;
  if (path.endsWith("open_loops.md")) return 7;
  return 8;
}

/** Parse "| S-014 | Anna M. | …" rows from the students overview table. */
function studentNamesFromOverview(items: FileChange[]): Record<string, string> {
  const overview = items.find((i) => i.path.endsWith("students.md"));
  const names: Record<string, string> = {};
  if (!overview) return names;
  for (const line of overview.after.split("\n")) {
    const m = /^\|\s*(S-\d{3})\s*\|\s*([^|]+?)\s*\|/i.exec(line);
    if (!m) continue;
    const id = m[1].toUpperCase();
    const name = m[2].trim();
    if (name && name.toUpperCase() !== id) names[id] = name;
  }
  return names;
}

function friendlyLabel(path: string, studentNames: Record<string, string>): string {
  const lessonResults = LESSON_RESULTS_RE.exec(path);
  if (lessonResults) return `Lesson results for ${lessonResults[1]}`;
  const lessonPlan = LESSON_PLAN_RE.exec(path);
  if (lessonPlan) return `Lesson plan for ${lessonPlan[1]}`;
  const student = STUDENT_PAGE_RE.exec(path);
  if (student) {
    const id = student[1].toUpperCase();
    const name = studentNames[id];
    return name ? `Student ${name} (${id})` : `Student ${id}`;
  }
  if (path.endsWith("students.md")) return "Student overview";
  if (path.endsWith("timeline.md")) return "Lesson timeline";
  if (path.endsWith("course_state.md")) return "Course state";
  if (path.endsWith("misconceptions.md")) return "Misconceptions";
  if (path.endsWith("open_loops.md")) return "Open follow-ups";
  if (path.endsWith("teacher_profile.md")) return "Teacher profile";
  if (path.includes("/memory/")) {
    const stem = shortWikiPath(path).replace(/\.md$/, "").replace(/_/g, " ");
    return stem.charAt(0).toUpperCase() + stem.slice(1);
  }
  return shortWikiPath(path);
}

function countNoun(path: string): [singular: string, plural: string] {
  if (STUDENT_PAGE_RE.test(path)) return ["observation", "observations"];
  if (path.endsWith("misconceptions.md") || path.endsWith("open_loops.md")) {
    return ["note", "notes"];
  }
  return ["line", "lines"];
}

function summarize(item: FileChange, category: BriefCategory): string {
  const path = item.path;
  if (category === "new") {
    if (LESSON_RESULTS_RE.test(path)) return "full lesson diary";
    if (STUDENT_PAGE_RE.test(path)) return "new student page";
    return "new page";
  }
  if (path.endsWith("timeline.md")) return "entry for this lesson";
  if (path.endsWith("course_state.md")) return "current unit & next focus refreshed";
  if (path.endsWith("students.md")) return "overview refreshed";
  if (LESSON_RESULTS_RE.test(path)) return "lesson notes updated";

  const { added, removed } = diffLineStats(item.before, item.after);
  const [singular, plural] = countNoun(path);
  const parts: string[] = [];
  if (added > 0) parts.push(`${added} ${added === 1 ? singular : plural} added`);
  if (removed > 0) parts.push(`${removed} removed`);
  if (parts.length === 0) return "updated";
  return parts.join(" · ");
}

function categorize(item: FileChange): BriefCategory {
  if (!item.before.trim()) return "new";
  const { added, removed } = diffLineStats(item.before, item.after);
  if (removed > added) return "removed";
  return "updated";
}

/**
 * Turn raw file-change items into a teacher-readable brief.
 *
 * The `raw/` archive copy of the diary is folded into the lesson-results
 * entry: one decision covers both paths, and teachers never see the raw
 * layer as a separate line.
 */
export function briefFromChanges(items: FileChange[]): BriefEntry[] {
  const studentNames = studentNamesFromOverview(items);
  const rawItems = items.filter((i) => i.path.startsWith("raw/"));
  const wikiItems = items.filter((i) => !i.path.startsWith("raw/"));

  const entries: BriefEntry[] = wikiItems.map((item) => {
    const category = categorize(item);
    const isLessonResults = LESSON_RESULTS_RE.test(item.path);
    const paired = isLessonResults ? rawItems : [];
    return {
      path: item.path,
      paths: [item.path, ...paired.map((r) => r.path)],
      category,
      label:
        friendlyLabel(item.path, studentNames) +
        (paired.length > 0 ? " (incl. archive copy)" : ""),
      summary: summarize(item, category),
      approved: item.approved && paired.every((r) => r.approved),
      required: item.required,
    };
  });

  // Raw items without a lesson-results sibling (shouldn't happen) stay visible.
  const covered = new Set(entries.flatMap((e) => e.paths));
  for (const raw of rawItems) {
    if (covered.has(raw.path)) continue;
    entries.push({
      path: raw.path,
      paths: [raw.path],
      category: categorize(raw),
      label: "Archive copy of the diary",
      summary: "saved for reference",
      approved: raw.approved,
    });
  }

  entries.sort((a, b) => typeRank(a.path) - typeRank(b.path));
  return entries;
}

/** Lesson date for the brief heading, from the results or plan path. */
export function briefLessonDate(items: FileChange[]): string | null {
  for (const item of items) {
    const m = LESSON_RESULTS_RE.exec(item.path) ?? LESSON_PLAN_RE.exec(item.path);
    if (m) return m[1];
  }
  return null;
}
