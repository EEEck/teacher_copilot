export type DocPage = {
  slug: string;
  title: string;
  description: string;
  outcome: string;
  group: "Start" | "Use" | "Trust" | "Help";
};

export const DEFAULT_LOCALE = "en";

export const docsPages: DocPage[] = [
  {
    slug: "start-here",
    title: "Start here",
    description: "What KlassenPilot remembers, what the beta tests, and where to begin.",
    outcome: "Understand the beta loop and open the mock class.",
    group: "Start",
  },
  {
    slug: "first-session",
    title: "Your first session",
    description: "A 20-minute Chemie 9b walkthrough with expected outcomes at each step.",
    outcome: "Complete one full plan -> teach -> memory cycle.",
    group: "Start",
  },
  {
    slug: "weekly-loop",
    title: "The weekly loop",
    description: "Update memory, review changes, and plan the next lesson - every week.",
    outcome: "Run the repeatable teach -> log -> plan rhythm.",
    group: "Use",
  },
  {
    slug: "how-it-works",
    title: "How the copilot works",
    description: "Memory layers, drafts vs saves, and what the agent will not do.",
    outcome: "Trust the copilot without treating it like a blank chatbot.",
    group: "Trust",
  },
  {
    slug: "help",
    title: "Help and FAQ",
    description: "Common questions, troubleshooting, and what to report during beta.",
    outcome: "Fix issues quickly and give useful feedback.",
    group: "Help",
  },
];

export function getDocPage(slug: string) {
  return docsPages.find((page) => page.slug === slug) ?? null;
}

export function getDocStepIndex(slug: string) {
  const index = docsPages.findIndex((page) => page.slug === slug);
  return index < 0 ? null : index + 1;
}

export function getNextDoc(slug: string) {
  const index = docsPages.findIndex((page) => page.slug === slug);
  if (index < 0) return null;
  return docsPages[index + 1] ?? null;
}

export function getPreviousDoc(slug: string) {
  const index = docsPages.findIndex((page) => page.slug === slug);
  if (index < 0) return null;
  return docsPages[index - 1] ?? null;
}

export function slugify(value: string) {
  return value
    .normalize("NFKD")
    .replace(/ß/g, "ss")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-");
}

export function collectHeadings(markdown: string) {
  return markdown
    .split(/\r?\n/)
    .map((line) => line.match(/^##\s+(.+)$/)?.[1])
    .filter((value): value is string => Boolean(value))
    .map((label) => ({ id: slugify(label), label }));
}
