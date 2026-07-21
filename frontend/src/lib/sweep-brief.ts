import type { MemorySweepCandidate } from "@/lib/api";

/** Teacher-facing grouping of sweep cards (docs/mem_v3, M1b brief). */
export type SweepBriefSection =
  | "explicit"
  | "new"
  | "changed"
  | "removed"
  | "student_summary";

export type SweepBriefRow = {
  key: string;
  section: SweepBriefSection;
  label: string;
  summary: string;
  /** Distinct occasions (lessons/artifacts) this claim was mentioned on. */
  occasionCount: number;
  canApply: boolean;
  candidate: MemorySweepCandidate;
};

export const SWEEP_SECTION_TITLES: Record<SweepBriefSection, string> = {
  explicit: "Explicitly requested",
  new: "New memory",
  changed: "Changed (old → new)",
  removed: "Already covered / not worth keeping",
  student_summary: "Student summary updates",
};

export const SWEEP_SECTION_ORDER: SweepBriefSection[] = [
  "explicit",
  "new",
  "changed",
  "removed",
  "student_summary",
];

const STUDENT_TARGET_RE = /^students\/(s-\d{3})\.md$/i;
const SUBJECT_TARGET_RE = /^wiki\/subjects\/([a-z0-9_-]+)\.md$/i;

const TARGET_LABELS: Record<string, string> = {
  "teacher_profile.md": "Teacher profile",
  "user.md": "Teacher profile",
  "copilot_profile.md": "Class copilot profile",
  "copilot.md": "Class copilot profile",
  "teaching_patterns.md": "Teaching patterns",
  "planning_brief.md": "Planning brief",
  "session_summaries.md": "Session summaries",
};

export function sweepTargetLabel(target: string): string {
  const normalized = (target || "").trim().toLowerCase();
  const known = TARGET_LABELS[normalized];
  if (known) return known;
  const student = STUDENT_TARGET_RE.exec(normalized);
  if (student) return `Student ${student[1].toUpperCase()}`;
  const subject = SUBJECT_TARGET_RE.exec(normalized);
  if (subject) return `Subject guide (${subject[1]})`;
  return target;
}

export function sweepCardKey(candidate: MemorySweepCandidate): string {
  return candidate.card_id || candidate.candidate_id;
}

function isStudentSummaryCandidate(candidate: MemorySweepCandidate): boolean {
  if ((candidate.section || "").trim().toLowerCase() === "student summary") {
    return true;
  }
  const ids = [
    candidate.candidate_id,
    ...(candidate.candidate_ids ?? []),
  ];
  return ids.some((id) => (id || "").startsWith("student_summary:"));
}

function sectionFor(candidate: MemorySweepCandidate): SweepBriefSection {
  if (candidate.group_label === "explicit_ask") return "explicit";
  const operation = candidate.operation ?? "add";
  // Auto-refreshed student summary sentences belong in their own bucket,
  // not mixed into generic "Changed" / "New memory" rows.
  if (
    isStudentSummaryCandidate(candidate) &&
    (operation === "add" || operation === "adjust")
  ) {
    return "student_summary";
  }
  if (operation === "add") return "new";
  if (operation === "adjust") return "changed";
  return "removed"; // already_covered, needs_decision, reject_low_signal
}

function oneLine(text: string, maxLen = 130): string {
  const line = (text || "").replace(/\s+/g, " ").trim();
  return line.length > maxLen ? `${line.slice(0, maxLen - 1)}…` : line;
}

/**
 * Order sweep cards into the teacher brief: explicit asks pinned first, then
 * new / changed / retired, with student summary updates last — one row per
 * (already backend-consolidated) claim.
 */
export function sweepBriefRows(
  candidates: MemorySweepCandidate[],
): SweepBriefRow[] {
  const rows = candidates.map((candidate) => ({
    key: sweepCardKey(candidate),
    section: sectionFor(candidate),
    label: sweepTargetLabel(candidate.target),
    summary: oneLine(candidate.content),
    occasionCount: candidate.occasion_count ?? 1,
    canApply: Boolean(candidate.can_apply),
    candidate,
  }));
  const rank = new Map(SWEEP_SECTION_ORDER.map((section, i) => [section, i]));
  return rows.sort(
    (a, b) => (rank.get(a.section) ?? 9) - (rank.get(b.section) ?? 9),
  );
}
