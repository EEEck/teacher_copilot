/** Mock upcoming dates for class home (not wiki-backed). */

export type ClassHomeMockDate = {
  label: string;
  date: string;
};

const DEFAULT_MOCK: ClassHomeMockDate[] = [
  { label: "Next large exam", date: "2026-07-20" },
  { label: "Class excursion", date: "2026-07-28" },
];

const BY_CLASS: Record<string, ClassHomeMockDate[]> = {
  chemie_9b_2026_27: [
    { label: "Next large exam", date: "2026-07-20" },
    { label: "Class excursion", date: "2026-07-28" },
  ],
};

export function classHomeMockUpcoming(classId: string): ClassHomeMockDate[] {
  return BY_CLASS[classId] ?? DEFAULT_MOCK;
}
