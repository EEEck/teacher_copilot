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
  memory_draft_id?: string | null;
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
export type DraftMetadata = {
  draft_id: string;
  artifact_revision: number;
  artifact_hash: string;
};
export type IngestStartHint = {
  lesson_date?: string;
  lesson_title?: string;
  intent?: "log_new_results" | "update_missing_results" | "correct_existing_results";
  target_kind?: "new_lesson" | "planned_lesson" | "taught_lesson";
  source?: "teacher_explicit" | "timeline_hint" | "agent_inferred";
};
export type IngestSession = {
  session_id: string;
  draft_id: string;
  artifact_revision: number;
  artifact_hash: string;
  turn_in_progress?: boolean;
  latest_turn_complete?: boolean;
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
  draft_id: string;
  artifact_revision: number;
  artifact_hash: string;
  turn_in_progress?: boolean;
  latest_turn_complete?: boolean;
  messages?: ChatMessage[];
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
  draft_id: string;
  artifact_revision: number;
  artifact_hash: string;
  completeness: CompletenessChecklist;
  ready_to_propose: boolean;
  last_change_summary?: string;
  memory_state?: Record<string, unknown> | null;
  memory_candidates?: MemoryCandidate[];
};
export type PlanSession = {
  session_id: string;
  draft_id: string;
  artifact_revision: number;
  artifact_hash: string;
  turn_in_progress?: boolean;
  latest_turn_complete?: boolean;
  class_id: string;
  status: string;
  messages: ChatMessage[];
  opening_message: string;
};
export type PlanDraft = {
  draft_id: string;
  artifact_revision: number;
  artifact_hash: string;
  turn_in_progress?: boolean;
  latest_turn_complete?: boolean;
  messages?: ChatMessage[];
  plan_markdown: string;
};
export type PlanChatResponse = {
  reply: string;
  plan_markdown: string;
  draft_id: string;
  artifact_revision: number;
  artifact_hash: string;
  ready_to_save: boolean;
  phase?: string | null;
  last_change_summary?: string;
  session_state?: Record<string, unknown> | null;
  lesson_planning_state?: Record<string, unknown> | null;
  memory_candidates?: MemoryCandidate[];
};
/**
 * One job the backend is running right now (GET /api/workflow/active).
 * Fields not relevant to a kind come back as "" rather than absent.
 */
export type ActiveWorkItem = {
  kind: "draft_turn" | "memory_sweep";
  class_id: string;
  /** draft_turn: "ingest" | "plan" | "discuss". */
  mode: string;
  draft_id: string;
  session_id: string;
  lesson_date: string;
  lesson_title: string;
  /** memory_sweep only. */
  review_id: string;
  updated_at: string;
};
export type ActiveWorkResponse = { items: ActiveWorkItem[] };
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
  speech_act?: string;
  fast_lane?: boolean;
  occasion_key?: string;
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
export type WriteVerificationBlockedResponse = {
  code: "write_verification_blocked";
  action: "plan_save" | "ingest_propose" | "ingest_commit";
  artifact_fingerprint: string;
  executive_state: Record<string, unknown>;
  message: string;
};

export class WriteVerificationBlockedError extends Error {
  readonly status = 409;

  constructor(readonly payload: WriteVerificationBlockedResponse) {
    super(payload.message);
    this.name = "WriteVerificationBlockedError";
  }
}
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
  candidate_ids?: string[];
};
export type MemoryApplyResponse = {
  class_id: string;
  applied_wiki_paths: string[];
  skipped: string[];
  warnings: string[];
  updated_candidate_ids: string[];
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
  occasion_count?: number;
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
export type MemorySweepReviewStatus =
  | "generating"
  | "ready"
  | "stale"
  | "applying"
  | "completed"
  | "discarded"
  | "failed"
  | "none";
export type MemorySweepReviewResponse = {
  review_id: string;
  class_id: string;
  status: MemorySweepReviewStatus;
  source_fingerprint: string;
  generated_at?: string | null;
  updated_at?: string | null;
  completed_at?: string | null;
  is_stale: boolean;
  stale_reasons: string[];
  has_teacher_edits: boolean;
  queues: Record<string, MemorySweepCandidate[]>;
  decisions: MemorySweepDecision[];
  warnings: string[];
  error: string;
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
export type WikiPageSummary = {
  kind: string;
  id: string;
  path: string;
};

export type WikiPagesResponse = {
  class_id: string;
  pages: WikiPageSummary[];
};

export type ClassBriefAction = {
  label: string;
  href: string;
  rationale?: string;
};

export type ClassBrief = {
  class_id: string;
  summary: string;
  recommended_action: ClassBriefAction;
  reasons: string[];
  watch_items: string[];
  source_paths: string[];
  generated_at: string;
  cached: boolean;
};

export type DiscussSession = {
  session_id: string;
  draft_id: string;
  artifact_revision: number;
  artifact_hash: string;
  turn_in_progress: boolean;
  latest_turn_complete: boolean;
  class_id: string;
  status: string;
  messages: ChatMessage[];
  opening_message: string;
};

export type DiscussDraft = DraftMetadata & {
  turn_in_progress?: boolean;
  latest_turn_complete?: boolean;
  messages?: ChatMessage[];
  /** Discuss has no saveable markdown artifact; always empty when present. */
  artifact_markdown?: string;
};

export type DiscussChatResponse = {
  reply: string;
  draft_id: string;
  artifact_revision: number;
  artifact_hash: string;
  discussion_state: Record<string, unknown>;
  evidence_briefs: Record<string, unknown>[];
  memory_candidates: MemoryCandidate[];
  source_paths: string[];
  suggested_actions: ClassBriefAction[];
  executive_state?: Record<string, unknown> | null;
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
        code?: string;
        action?: WriteVerificationBlockedResponse["action"];
        artifact_fingerprint?: string;
        executive_state?: Record<string, unknown>;
        message?: string;
        error?: { message?: string };
        detail?: string;
      };
      if (res.status === 409 && body.code === "write_verification_blocked") {
        throw new WriteVerificationBlockedError({
          code: "write_verification_blocked",
          action: body.action ?? "plan_save",
          artifact_fingerprint: body.artifact_fingerprint ?? "",
          executive_state: body.executive_state ?? {},
          message: body.message ?? "I didn't save this yet; one detail needs your call.",
        });
      }
      // Typed envelope { error: { message } }, with fallback to legacy { detail }.
      message = body.error?.message ?? body.detail ?? message;
    } catch (err) {
      if (err instanceof WriteVerificationBlockedError) {
        throw err;
      }
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

export const client = {
  betaLogin: (inviteCode: string) =>
    api<BetaIdentity>("/api/beta/login", {
      method: "POST",
      body: JSON.stringify({ invite_code: inviteCode }),
    }),
  betaLogout: () => api<{ status: string }>("/api/beta/logout", { method: "POST" }),
  betaMe: () => api<BetaIdentity>("/api/beta/me"),
  getClasses: () => api<{ classes: ClassSummary[] }>("/api/classes"),
  getTimeline: (classId: string) =>
    api<ClassTimeline>(`/api/classes/${classId}/timeline`),
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
  listWikiPages: (classId: string, kind?: string) =>
    api<WikiPagesResponse>(
      `/api/classes/${classId}/wiki/pages${kind ? `?kind=${encodeURIComponent(kind)}` : ""}`,
    ),
  getClassBrief: (classId: string) =>
    api<ClassBrief>(`/api/classes/${classId}/brief`),
  refreshClassBrief: (classId: string) =>
    api<ClassBrief>(`/api/classes/${classId}/brief/refresh`, { method: "POST" }),
  startDiscussionSession: (classId: string) =>
    api<DiscussSession>(`/api/classes/${classId}/discussion/sessions`, {
      method: "POST",
    }),
  discussionGetDraft: (classId: string, sessionId: string) =>
    api<DiscussDraft>(
      `/api/classes/${classId}/discussion/sessions/${sessionId}/draft`,
    ),
  discussionChatStream: (
    classId: string,
    sessionId: string,
    message: string,
    attachments?: ChatAttachment[],
    signal?: AbortSignal,
  ) =>
    apiStreamPost(
      `/api/classes/${classId}/discussion/sessions/${sessionId}/chat/stream`,
      {
        message,
        attachments: attachments ?? [],
      },
      signal,
    ),
  ingestCommit: (
    classId: string,
    sessionId: string,
    diaryMarkdown: string,
    approvedUpdates: ApprovedWikiUpdate[],
    metadata?: {
      draftId?: string;
      expectedArtifactRevision?: number;
      expectedArtifactHash?: string;
      sourceArtifactRevision?: number;
      sourceArtifactHash?: string;
    },
  ) =>
    api<CommitIngestResponse>(
      `/api/classes/${classId}/ingest/commit`,
      {
        method: "POST",
        body: JSON.stringify({
          session_id: sessionId,
          diary_markdown: diaryMarkdown,
          approved_updates: approvedUpdates,
          draft_id: metadata?.draftId ?? null,
          expected_artifact_revision: metadata?.expectedArtifactRevision ?? null,
          expected_artifact_hash: metadata?.expectedArtifactHash ?? null,
          source_artifact_revision: metadata?.sourceArtifactRevision ?? null,
          source_artifact_hash: metadata?.sourceArtifactHash ?? null,
        }),
      },
    ),
  discardWorkflowDraft: (classId: string, draftId: string) =>
    api<{ draft_id: string; status: string }>(
      `/api/classes/${classId}/workflow-drafts/${draftId}/discard`,
      { method: "POST" },
    ),
  startPlanSession: (classId: string) =>
    api<PlanSession>(`/api/classes/${classId}/plan/sessions`, { method: "POST" }),
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
    metadata?: {
      draftId?: string;
      expectedArtifactRevision?: number;
      expectedArtifactHash?: string;
    },
  ) =>
    api<SavePlanResponse>(`/api/classes/${classId}/plan/save`, {
      method: "POST",
      body: JSON.stringify({
        session_id: sessionId,
        lesson_date: lessonDate,
        plan_markdown: planMarkdown,
        draft_id: metadata?.draftId ?? null,
        expected_artifact_revision: metadata?.expectedArtifactRevision ?? null,
        expected_artifact_hash: metadata?.expectedArtifactHash ?? null,
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
  getMemorySweepReview: (classId: string) =>
    api<MemorySweepReviewResponse>(
      `/api/classes/${classId}/memory/sweep/review`,
    ),
  /** Everything the backend is running right now, across all classes. */
  getActiveWork: () => api<ActiveWorkResponse>(`/api/workflow/active`),
  openMemorySweepReview: (
    classId: string,
    options?: { refresh?: boolean; keepStale?: boolean },
  ) =>
    api<MemorySweepReviewResponse>(
      `/api/classes/${classId}/memory/sweep/review`,
      {
        method: "POST",
        body: JSON.stringify({
          refresh: Boolean(options?.refresh),
          keep_stale: Boolean(options?.keepStale),
        }),
      },
    ),
  patchMemorySweepReview: (
    classId: string,
    reviewId: string,
    decisions: MemorySweepDecision[],
  ) =>
    api<MemorySweepReviewResponse>(
      `/api/classes/${classId}/memory/sweep/review/${reviewId}`,
      {
        method: "PATCH",
        body: JSON.stringify({ decisions }),
      },
    ),
  applyMemorySweepReview: (classId: string, reviewId: string) =>
    api<MemorySweepApplyResponse>(
      `/api/classes/${classId}/memory/sweep/review/${reviewId}/apply`,
      { method: "POST" },
    ),
  discardMemorySweepReview: (classId: string, reviewId: string) =>
    api<MemorySweepReviewResponse>(
      `/api/classes/${classId}/memory/sweep/review/${reviewId}/discard`,
      { method: "POST" },
    ),
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
