const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8010";

export type ClassSummary = { id: string; label: string; subject: string };
export type TimelineEntry = {
  date: string;
  title: string;
  month_key: string;
  summary: string;
  highlights: string[];
  issues: string[];
  follow_ups: string[];
  covered: string[];
  homework?: string | null;
  raw_path?: string | null;
  has_plan: boolean;
  status: "taught" | "planned";
  committed_at?: string | null;
  wiki_paths: string[];
};
export type ClassTimeline = {
  class_id: string;
  entries: TimelineEntry[];
  months: string[];
};
export type ClassMemorySnapshot = {
  class_id: string;
  label: string;
  current_unit: string;
  last_lesson_date?: string | null;
  last_committed_date?: string | null;
  last_committed_at?: string | null;
  last_committed_title?: string | null;
  open_loop_count: number;
  top_misconceptions: string[];
  recent_lessons: string[];
};
export type RollupExcerpt = { wiki_path: string; label: string; markdown: string };
export type LessonDetail = {
  class_id: string;
  date: string;
  title: string;
  primary_markdown: string;
  diary_markdown: string;
  raw_markdown: string;
  lesson_plan_markdown?: string | null;
  rollup_excerpts: RollupExcerpt[];
};
export type ReviseLessonResponse = {
  entry: TimelineEntry;
  applied_wiki_paths: string[];
};
export type CompletenessItem = {
  field: string;
  label: string;
  complete: boolean;
  required: boolean;
};
export type CompletenessChecklist = { items: CompletenessItem[] };
export type ChatMessage = { role: string; content: string };
export type IngestSession = {
  session_id: string;
  class_id: string;
  status: string;
  messages: ChatMessage[];
  completeness: CompletenessChecklist;
};
export type WikiUpdateProposal = {
  wiki_path: string;
  current_content: string;
  proposed_content: string;
  rationale: string;
};

/** One card per wiki path — guards against duplicate proposals from the API. */
export function uniqueWikiProposals(proposals: WikiUpdateProposal[]): WikiUpdateProposal[] {
  const byPath = new Map<string, WikiUpdateProposal>();
  for (const p of proposals) {
    if (!byPath.has(p.wiki_path)) byPath.set(p.wiki_path, p);
  }
  return [...byPath.values()];
}
export type IngestDraft = {
  diary_markdown: string;
  wiki_proposals: WikiUpdateProposal[];
  completeness: CompletenessChecklist;
};
export type ApprovedWikiUpdate = {
  wiki_path: string;
  content: string;
  approved: boolean;
};
export type ChatAttachment = { filename: string; content: string };
export type ChatResponse = {
  reply: string;
  diary_markdown: string;
  completeness: CompletenessChecklist;
  ready_to_propose: boolean;
};
export type PlanSession = {
  session_id: string;
  class_id: string;
  status: string;
  messages: ChatMessage[];
  opening_message: string;
};
export type PlanDraft = { plan_markdown: string };
export type PlanChatResponse = {
  reply: string;
  plan_markdown: string;
  ready_to_save: boolean;
};
export type SavePlanResponse = {
  lesson_date: string;
  title: string;
  plan_path: string;
};
export type LessonFlowPhase = { phase: string; minutes: number; description: string };
export type LessonPlan = {
  title: string;
  lesson_date?: string | null;
  duration_minutes: number;
  learning_goals: string[];
  lesson_flow: LessonFlowPhase[];
  warmup: string;
  practice_tasks: string[];
  homework: string;
  teacher_notes: string;
  addresses_open_loops: string[];
  addresses_misconceptions: string[];
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
    });
  } catch {
    throw new Error(
      `Cannot reach API at ${API_BASE}. Start the backend with: ./scripts/restart-dev.ps1 -NoNewWindow`,
    );
  }
  if (!res.ok) {
    const text = await res.text();
    let message = text || res.statusText;
    try {
      const body = JSON.parse(text) as {
        error?: { message?: string };
        detail?: string;
      };
      // Typed envelope { error: { message } }, with fallback to legacy { detail }.
      message = body.error?.message ?? body.detail ?? message;
    } catch {
      /* use raw text */
    }
    throw new Error(`API ${res.status}: ${message}`);
  }
  return res.json() as Promise<T>;
}

/** Backfill fields when an older API instance is still bound to port 8001. */
function normalizeTimelineEntry(raw: Partial<TimelineEntry> & Pick<TimelineEntry, "date" | "title">): TimelineEntry {
  const month_key = raw.month_key ?? raw.date.slice(0, 7);
  const covered = raw.covered ?? [];
  const status = raw.status === "planned" ? "planned" : "taught";
  const summary =
    raw.summary?.trim() ||
    (status === "planned"
      ? "Planned — not taught yet."
      : covered.length > 0
        ? `Covered: ${covered[0]}`
        : `Lesson: ${raw.title}`);
  return {
    date: raw.date,
    title: raw.title,
    month_key,
    summary,
    highlights: raw.highlights ?? (covered[0] ? [covered[0]] : []),
    issues: raw.issues ?? [],
    follow_ups: raw.follow_ups ?? [],
    covered,
    homework: raw.homework ?? null,
    raw_path: raw.raw_path ?? null,
    has_plan: raw.has_plan ?? false,
    status,
    committed_at: raw.committed_at ?? null,
    wiki_paths: raw.wiki_paths ?? [],
  };
}

function normalizeTimeline(raw: Partial<ClassTimeline> & { class_id: string }): ClassTimeline {
  const entries = (raw.entries ?? []).map((e) =>
    normalizeTimelineEntry(e as Partial<TimelineEntry> & Pick<TimelineEntry, "date" | "title">),
  );
  const months =
    raw.months && raw.months.length > 0
      ? raw.months
      : [...new Set(entries.map((e) => e.month_key))].sort().reverse();
  return { class_id: raw.class_id, entries, months };
}

export const client = {
  getClasses: () => api<{ classes: ClassSummary[] }>("/api/classes"),
  getTimeline: async (classId: string) => {
    const raw = await api<Partial<ClassTimeline> & { class_id: string }>(
      `/api/classes/${classId}/timeline`,
    );
    return normalizeTimeline(raw);
  },
  getSnapshot: (classId: string) => api<ClassMemorySnapshot>(`/api/classes/${classId}/snapshot`),
  getLessonDetail: (classId: string, lessonDate: string) =>
    api<LessonDetail>(`/api/classes/${classId}/lessons/${lessonDate}`),
  reviseLesson: (classId: string, lessonDate: string, diaryMarkdown: string) =>
    api<ReviseLessonResponse>(`/api/classes/${classId}/lessons/${lessonDate}`, {
      method: "PATCH",
      body: JSON.stringify({ diary_markdown: diaryMarkdown }),
    }),
  startIngestSession: (classId: string) =>
    api<IngestSession>(`/api/classes/${classId}/ingest/sessions`, { method: "POST" }),
  ingestChat: (
    classId: string,
    sessionId: string,
    message: string,
    diaryMarkdown?: string,
    attachments?: ChatAttachment[],
  ) =>
    api<ChatResponse>(`/api/classes/${classId}/ingest/sessions/${sessionId}/chat`, {
      method: "POST",
      body: JSON.stringify({
        message,
        diary_markdown: diaryMarkdown ?? null,
        attachments: attachments ?? [],
      }),
    }),
  ingestGetDraft: (classId: string, sessionId: string) =>
    api<IngestDraft>(`/api/classes/${classId}/ingest/sessions/${sessionId}/draft`),
  ingestUpdateDraft: (classId: string, sessionId: string, diaryMarkdown: string) =>
    api<IngestDraft>(`/api/classes/${classId}/ingest/sessions/${sessionId}/draft`, {
      method: "PATCH",
      body: JSON.stringify({ diary_markdown: diaryMarkdown }),
    }),
  ingestPropose: (classId: string, sessionId: string) =>
    api<IngestDraft>(`/api/classes/${classId}/ingest/sessions/${sessionId}/propose`, {
      method: "POST",
    }),
  ingestCommit: (
    classId: string,
    sessionId: string,
    diaryMarkdown: string,
    approvedUpdates: ApprovedWikiUpdate[],
  ) =>
    api<{
      raw_diary_path: string;
      applied_wiki_paths: string[];
      log_entry_id: string;
      lesson_date: string;
      title: string;
    }>(
      `/api/classes/${classId}/ingest/commit`,
      {
        method: "POST",
        body: JSON.stringify({
          session_id: sessionId,
          diary_markdown: diaryMarkdown,
          approved_updates: approvedUpdates,
        }),
      },
    ),
  startPlanSession: (classId: string) =>
    api<PlanSession>(`/api/classes/${classId}/plan/sessions`, { method: "POST" }),
  planChat: (
    classId: string,
    sessionId: string,
    message: string,
    planMarkdown?: string,
    attachments?: ChatAttachment[],
  ) =>
    api<PlanChatResponse>(`/api/classes/${classId}/plan/sessions/${sessionId}/chat`, {
      method: "POST",
      body: JSON.stringify({
        message,
        plan_markdown: planMarkdown ?? null,
        attachments: attachments ?? [],
      }),
    }),
  planGetDraft: (classId: string, sessionId: string) =>
    api<PlanDraft>(`/api/classes/${classId}/plan/sessions/${sessionId}/draft`),
  planUpdateDraft: (classId: string, sessionId: string, planMarkdown: string) =>
    api<PlanDraft>(`/api/classes/${classId}/plan/sessions/${sessionId}/draft`, {
      method: "PATCH",
      body: JSON.stringify({ plan_markdown: planMarkdown }),
    }),
  planSave: (
    classId: string,
    sessionId: string,
    lessonDate: string,
    planMarkdown: string,
  ) =>
    api<SavePlanResponse>(`/api/classes/${classId}/plan/save`, {
      method: "POST",
      body: JSON.stringify({
        session_id: sessionId,
        lesson_date: lessonDate,
        plan_markdown: planMarkdown,
      }),
    }),
};
