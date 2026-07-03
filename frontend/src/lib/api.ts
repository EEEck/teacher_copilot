/** Browser uses localhost; SSR in Docker uses INTERNAL_API_BASE_URL (backend service). */
function getApiBase(): string {
  if (typeof window === "undefined") {
    return (
      process.env.INTERNAL_API_BASE_URL ??
      process.env.NEXT_PUBLIC_API_BASE_URL ??
      "http://localhost:8010"
    );
  }
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8010";
}

export type ClassSummary = { id: string; label: string; subject: string };
export type BetaIdentity = {
  tester_id: string;
  workspace_id: string;
  role: string;
};
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
export type IngestStartHint = {
  lesson_date?: string;
  lesson_title?: string;
  intent?: "log_new_results" | "update_missing_results" | "correct_existing_results";
  target_kind?: "new_lesson" | "planned_lesson" | "taught_lesson";
  source?: "teacher_explicit" | "timeline_hint" | "agent_inferred";
};
export type IngestSession = {
  session_id: string;
  class_id: string;
  status: string;
  messages: ChatMessage[];
  completeness: CompletenessChecklist;
  memory_state?: Record<string, unknown> | null;
  memory_candidates?: MemoryCandidate[];
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
  memory_state?: Record<string, unknown> | null;
  memory_candidates?: MemoryCandidate[];
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
  last_change_summary?: string;
  memory_state?: Record<string, unknown> | null;
  memory_candidates?: MemoryCandidate[];
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
  phase?: string | null;
  last_change_summary?: string;
  session_state?: Record<string, unknown> | null;
  lesson_planning_state?: Record<string, unknown> | null;
  memory_candidates?: MemoryCandidate[];
};
export type MemoryCandidate = {
  candidate_id?: string;
  target: string;
  section?: string;
  candidate_update: string;
  evidence?: string;
  evidence_refs?: string[];
  source?: string;
  basis?: string;
  confidence?: string;
  requires_teacher_approval?: boolean;
};
export type SavePlanResponse = {
  lesson_date: string;
  title: string;
  plan_path: string;
  session_state?: Record<string, unknown> | null;
  lesson_planning_state?: Record<string, unknown> | null;
  memory_candidates?: MemoryCandidate[];
};
export type PlanTraceResponse = {
  class_id: string;
  session_id: string;
  status: string;
  prompt_stack: Record<string, unknown>;
  runtime: Record<string, unknown>;
  messages: ChatMessage[];
  artifact_markdown: string;
  event_trace: Record<string, unknown>[];
  raw_evidence: Record<string, string>;
};
export type ProfileCandidate = {
  target: string;
  section: string;
  content: string;
  basis: string;
  confidence: string;
  evidence?: string;
};
export type ProfileProposalResponse = {
  class_id: string;
  candidates: ProfileCandidate[];
  warnings: string[];
};
export type MemoryApplyItem = {
  target: string;
  section?: string;
  content: string;
};
export type MemoryApplyResponse = {
  class_id: string;
  applied_wiki_paths: string[];
  skipped: string[];
  warnings: string[];
};
export type MemorySweepCandidate = {
  card_id: string;
  source_group_id: string;
  candidate_id: string;
  candidate_ids: string[];
  review_queue: string;
  channel: string;
  target: string;
  section: string;
  content: string;
  evidence_summary: string;
  evidence_refs: string[];
  confidence: string;
  basis: string;
  status: string;
  relationship: string;
  group_label: string;
  public_rationale: string;
  operation:
    | "add"
    | "adjust"
    | "already_covered"
    | "needs_decision"
    | "reject_low_signal";
  replaces_content: string;
  status_recommendation:
    | "promote"
    | "already_covered"
    | "needs_decision"
    | "reject_low_signal";
  why_now: string;
  current_memory_excerpt: string;
  signal_count: number;
  can_apply: boolean;
  review_only_reason: string;
  warnings: string[];
};
export type MemorySweepProposalResponse = {
  class_id: string;
  subject: string;
  queues: Record<string, MemorySweepCandidate[]>;
  warnings: string[];
};
export type MemoryCandidateStatus =
  | "proposed"
  | "approved"
  | "applied"
  | "rejected"
  | "snoozed"
  | "deleted"
  | "expired";
export type MemorySweepDecision = {
  card_id?: string;
  action: "apply" | "reject" | "snooze" | "delete" | "already_covered";
  target: string;
  section: string;
  content: string;
  operation?:
    | "add"
    | "adjust"
    | "already_covered"
    | "needs_decision"
    | "reject_low_signal";
  replaces_content?: string;
  candidate_ids: string[];
  rejection_reason?: string | null;
};
export type MemorySweepApplyResponse = {
  class_id: string;
  applied_wiki_paths: string[];
  updated_candidate_ids: string[];
  skipped: string[];
  warnings: string[];
};
export type MemoryProposalResponse = {
  class_id: string;
  pages: Record<string, string>;
  source_paths: string[];
  stale_report: string[];
  warnings: string[];
};
export type CommitIngestResponse = {
  raw_diary_path: string;
  applied_wiki_paths: string[];
  log_entry_id: string;
  lesson_date: string;
  title: string;
  class_memory_proposal?: MemoryProposalResponse | null;
};
export type MemoryCompactResponse = {
  class_id: string;
  applied_wiki_paths: string[];
  log_entry_id: string;
  source_paths: string[];
  stale_report: string[];
  warnings: string[];
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

/** Backend restarted or session expired — in-memory store no longer has this id. */
export function isUnknownSessionError(err: unknown): boolean {
  return (
    err instanceof Error &&
    /API 404:.*Unknown session:/i.test(err.message)
  );
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${getApiBase()}${path}`, {
      ...init,
      cache: "no-store",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
    });
  } catch {
    throw new Error(
      `Cannot reach API at ${getApiBase()}. Start the backend (docker compose up, or ./scripts/restart-dev.ps1 -NoNewWindow).`,
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

async function apiStreamPost(path: string, body: object, signal?: AbortSignal): Promise<Response> {
  let res: Response;
  try {
    res = await fetch(`${getApiBase()}${path}`, {
      method: "POST",
      cache: "no-store",
      credentials: "include",
      signal,
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error(
      `Cannot reach API at ${getApiBase()}. Start the backend (docker compose up, or ./scripts/restart-dev.ps1 -NoNewWindow).`,
    );
  }
  if (!res.ok) {
    const text = await res.text();
    let message = text || res.statusText;
    try {
      const parsed = JSON.parse(text) as {
        error?: { message?: string };
        detail?: string;
      };
      message = parsed.error?.message ?? parsed.detail ?? message;
    } catch {
      /* use raw text */
    }
    throw new Error(`API ${res.status}: ${message}`);
  }
  return res;
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
  betaLogin: (inviteCode: string) =>
    api<BetaIdentity>("/api/beta/login", {
      method: "POST",
      body: JSON.stringify({ invite_code: inviteCode }),
    }),
  betaLogout: () => api<{ status: string }>("/api/beta/logout", { method: "POST" }),
  betaMe: () => api<BetaIdentity>("/api/beta/me"),
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
  startIngestSession: (classId: string, hint?: IngestStartHint) =>
    api<IngestSession>(`/api/classes/${classId}/ingest/sessions`, {
      method: "POST",
      body: hint ? JSON.stringify(hint) : undefined,
    }),
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
  ingestChatStream: (
    classId: string,
    sessionId: string,
    message: string,
    diaryMarkdown?: string,
    attachments?: ChatAttachment[],
    signal?: AbortSignal,
  ) =>
    apiStreamPost(
      `/api/classes/${classId}/ingest/sessions/${sessionId}/chat/stream`,
      {
        message,
        diary_markdown: diaryMarkdown ?? null,
        attachments: attachments ?? [],
      },
      signal,
    ),
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
  getWikiFile: (classId: string, wikiPath: string) =>
    api<{ wiki_path: string; markdown: string }>(
      `/api/classes/${classId}/wiki/file?path=${encodeURIComponent(wikiPath)}`,
    ),
  ingestCommit: (
    classId: string,
    sessionId: string,
    diaryMarkdown: string,
    approvedUpdates: ApprovedWikiUpdate[],
  ) =>
    api<CommitIngestResponse>(
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
  planChatStream: (
    classId: string,
    sessionId: string,
    message: string,
    planMarkdown?: string,
    attachments?: ChatAttachment[],
    signal?: AbortSignal,
  ) =>
    apiStreamPost(
      `/api/classes/${classId}/plan/sessions/${sessionId}/chat/stream`,
      {
        message,
        plan_markdown: planMarkdown ?? null,
        attachments: attachments ?? [],
      },
      signal,
    ),
  planGetDraft: (classId: string, sessionId: string) =>
    api<PlanDraft>(`/api/classes/${classId}/plan/sessions/${sessionId}/draft`),
  planTrace: (classId: string, sessionId: string) =>
    api<PlanTraceResponse>(`/api/classes/${classId}/plan/sessions/${sessionId}/trace`),
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
  memoryProfilePropose: (
    classId: string,
    finalLessonMarkdown: string,
    sessionState?: Record<string, unknown> | null,
    lessonPlanningState?: Record<string, unknown> | null,
    memoryCandidates?: MemoryCandidate[],
  ) =>
    api<ProfileProposalResponse>(`/api/classes/${classId}/memory/profile/propose`, {
      method: "POST",
      body: JSON.stringify({
        final_lesson_markdown: finalLessonMarkdown,
        session_state: sessionState ?? null,
        lesson_planning_state: lessonPlanningState ?? null,
        memory_candidates: memoryCandidates ?? [],
      }),
    }),
  memoryApply: (classId: string, items: MemoryApplyItem[]) =>
    api<MemoryApplyResponse>(`/api/classes/${classId}/memory/apply`, {
      method: "POST",
      body: JSON.stringify({ items }),
    }),
  memorySweepPropose: (classId: string, options?: { queue?: string }) => {
    const search = options?.queue
      ? `?queue=${encodeURIComponent(options.queue)}`
      : "";
    return api<MemorySweepProposalResponse>(
      `/api/classes/${classId}/memory/sweep/propose${search}`,
      {
        method: "POST",
      },
    );
  },
  memoryCandidateStatus: (
    classId: string,
    candidateId: string,
    status: MemoryCandidateStatus,
    rejectionReason?: string,
  ) =>
    api<{ candidate_id: string; status: string }>(
      `/api/classes/${classId}/memory/candidates/${candidateId}/status`,
      {
        method: "POST",
        body: JSON.stringify({
          status,
          rejection_reason: rejectionReason ?? null,
        }),
      },
    ),
  memorySweepApply: (
    classId: string,
    decisions: MemorySweepDecision[],
    reviewBatchId?: string,
  ) =>
    api<MemorySweepApplyResponse>(`/api/classes/${classId}/memory/sweep/apply`, {
      method: "POST",
      body: JSON.stringify({
        decisions,
        review_batch_id: reviewBatchId ?? null,
      }),
    }),
  memoryCompactApply: (
    classId: string,
    pages: Record<string, string>,
    sourcePaths: string[] = [],
  ) =>
    api<MemoryCompactResponse>(`/api/classes/${classId}/memory/compact/apply`, {
      method: "POST",
      body: JSON.stringify({ pages, source_paths: sourcePaths }),
    }),
};
