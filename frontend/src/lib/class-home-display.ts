/** Class-home display helpers (title, track, compact unit). */

const STEM_SUBJECTS = new Set([
  "chemie",
  "chemistry",
  "physik",
  "physics",
  "biologie",
  "bio",
  "biology",
  "mathe",
  "mathematik",
  "math",
  "informatik",
  "nawi",
]);

const LANGUAGE_SUBJECTS = new Set([
  "deutsch",
  "english",
  "englisch",
  "franzoesisch",
  "französisch",
  "franzosisch",
  "latein",
  "spanisch",
  "italienisch",
  "russisch",
]);

export type ClassHomeHeading = {
  title: string;
  year: string | null;
  track: "STEM track" | "Language track" | null;
};

function capitalizeWord(word: string): string {
  if (!word) return word;
  return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
}

/**
 * Parse `chemie_9b_2026_27` → title Chemie 9b, year 2026/27, STEM track.
 * Falls back to cleaning snapshot.label when the id shape is unknown.
 */
export function formatClassHomeHeading(
  classId: string,
  label?: string,
): ClassHomeHeading {
  const idMatch = classId.match(
    /^([a-z][a-z0-9_]*)_(\d+[a-z]?)_(\d{4})_(\d{2})$/i,
  );
  if (idMatch) {
    const subjectKey = idMatch[1].split("_")[0].toLowerCase();
    const subject = idMatch[1]
      .split("_")
      .map(capitalizeWord)
      .join(" ");
    return {
      title: `${subject} ${idMatch[2].toLowerCase()}`,
      year: `${idMatch[3]}/${idMatch[4]}`,
      track: classTrackFromSubject(subjectKey),
    };
  }

  const cleaned = (label || classId)
    .replace(/^Class Config\s*[—–-]\s*/i, "")
    .replace(/_/g, " ")
    .trim();
  return { title: cleaned || classId, year: null, track: null };
}

export function classTrackFromSubject(
  subject: string,
): "STEM track" | "Language track" | null {
  const key = subject.trim().toLowerCase();
  if (STEM_SUBJECTS.has(key)) return "STEM track";
  if (LANGUAGE_SUBJECTS.has(key)) return "Language track";
  return null;
}

/** Compact At a glance unit: a few words, prefer the latest list clause. */
export function shortenUnitLabel(unit: string, maxWords = 3): string {
  const cleaned = unit.trim();
  if (!cleaned || cleaned === "-" || /^not set$/i.test(cleaned)) {
    return "Not set";
  }
  const parts = cleaned
    .split(/,\s*|\s+and\s+/i)
    .map((part) => part.trim())
    .filter(Boolean);
  const focus = parts.length > 1 ? parts[parts.length - 1]! : parts[0]!;
  const words = focus.replace(/^(with|and)\s+/i, "").split(/\s+/).filter(Boolean);
  const short = words.slice(0, maxWords).join(" ");
  return short ? capitalizeWord(short) : "Not set";
}

/** Hover copy for class-home workflows (teacher ICP, executive-assistant tone). */
export const CLASS_HOME_HOVER = {
  plan:
    "Your private planning agent drafts the next lesson from everything this class has already lived: what you taught, what stuck, and what still needs work.",
  memory:
    "Teach your personal class agent what happened today. Every approved update makes it sharper for the next plan, the next question, the next decision.",
  discuss:
    "Ask your class executive assistant anything: open loops, what to watch, what to do next. It already knows this class.",
  timeline:
    "The living record of this class: planned and taught lessons, ready when you need to step back into any day.",
  wiki:
    "Open the living notebook for this class: lesson notes, plans, and everything your assistant remembers.",
  sweep:
    "While you teach, your assistant quietly gathers insights from this class and how you like to work. Open this to review how it wants to get more personal for you. Nothing changes until you approve.",
} as const;
