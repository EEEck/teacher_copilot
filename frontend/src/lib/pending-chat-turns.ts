import type { ArtifactMode } from "@/components/assistant-ui/artifact-runtime-config";

type PendingTurnStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;

const INDEX_KEY = "kp:turn-pending:index";
const DISMISS_KEY = "kp:running-tasks:dismissed";

export type PendingJobMode = ArtifactMode | "memory_sweep";

export type PendingChatTurn = {
  key: string;
  mode: PendingJobMode;
  classId: string;
  sessionId: string;
  draftId?: string;
  lessonDate?: string;
  lessonTitle?: string;
  resumeHref?: string;
  /**
   * True once the notifier (or live stream) has observed this turn running.
   * Required before treating idle+complete as *this* turn finishing — otherwise
   * a marker set before the stream starts races the still-idle previous state.
   */
  seenInProgress?: boolean;
  /** Persisted draft message count at mark time; growth implies a real turn landed. */
  baselineMessageCount?: number;
};

export type PendingDraftStatus = {
  turn_in_progress?: boolean;
  latest_turn_complete?: boolean;
};

export type PendingMemorySweepStatus = {
  status?: string;
};

export function isPendingDraftComplete(status: PendingDraftStatus): boolean {
  return status.latest_turn_complete === true && status.turn_in_progress !== true;
}

/**
 * A pending plan/ingest marker may be written before the backend begins the turn.
 * Only notify after we have seen in-progress, or after persisted messages grew
 * past the baseline captured at mark time (fast turns that skip the in-progress poll).
 */
export function shouldNotifyPendingDraftComplete(
  status: PendingDraftStatus,
  turn: Pick<PendingChatTurn, "seenInProgress" | "baselineMessageCount">,
  draftMessageCount = 0,
): boolean {
  if (!isPendingDraftComplete(status)) return false;
  if (turn.seenInProgress) return true;
  if (
    turn.baselineMessageCount !== undefined &&
    draftMessageCount > turn.baselineMessageCount
  ) {
    return true;
  }
  return false;
}

/** Memory Sweep generation is done when the review is no longer generating. */
export function isPendingMemorySweepComplete(
  status: PendingMemorySweepStatus,
): boolean {
  return status.status !== undefined && status.status !== "generating";
}

export function pendingTurnKey(
  draftId: string | undefined,
  sessionId: string,
): string {
  return `kp:turn-pending:${draftId || sessionId}`;
}

/** One pending Memory Sweep job per class. */
export function pendingMemorySweepKey(classId: string): string {
  return `kp:turn-pending:sweep:${classId}`;
}

export function pendingTurnWorkflowHref(turn: PendingChatTurn): string {
  if (turn.mode === "memory_sweep") {
    const base = `/classes/${turn.classId}/memory-sweep`;
    if (turn.resumeHref === base || turn.resumeHref?.startsWith(`${base}?`)) {
      return turn.resumeHref;
    }
    return base;
  }
  if (turn.mode === "discuss") {
    // Always land on class home with the discuss dock forced open
    // (covers closed / minimized and cross-page return).
    return `/classes/${turn.classId}?discuss=open`;
  }
  const base =
    turn.mode === "plan"
      ? `/classes/${turn.classId}/plan`
      : `/classes/${turn.classId}/memory`;
  if (
    turn.resumeHref === base ||
    turn.resumeHref?.startsWith(`${base}?`)
  ) {
    return turn.resumeHref;
  }
  return base;
}

/**
 * True when this pending turn was started on the current page (same path+search).
 * Used with the live-stream registry: background tabs still toast + hydrate.
 */
export function isPendingTurnOnCurrentPage(
  turn: Pick<PendingChatTurn, "resumeHref">,
  currentPathWithSearch: string,
): boolean {
  if (!turn.resumeHref) return false;
  return turn.resumeHref === currentPathWithSearch;
}

export function listPendingChatTurns(storage: PendingTurnStorage): PendingChatTurn[] {
  const raw = storage.getItem(INDEX_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isPendingChatTurn);
  } catch {
    return [];
  }
}

export function markPendingChatTurn(
  storage: PendingTurnStorage,
  turn: Omit<PendingChatTurn, "key" | "seenInProgress">,
): string {
  const key =
    turn.mode === "memory_sweep"
      ? pendingMemorySweepKey(turn.classId)
      : pendingTurnKey(turn.draftId, turn.sessionId);
  const next: PendingChatTurn = {
    ...turn,
    key,
    seenInProgress: false,
    baselineMessageCount: turn.baselineMessageCount ?? 0,
  };
  const existing = listPendingChatTurns(storage).filter((item) => item.key !== key);
  storage.setItem(key, "1");
  storage.setItem(INDEX_KEY, JSON.stringify([...existing, next]));
  return key;
}

/** Record that this pending turn was observed running on the backend. */
export function markPendingTurnSeenInProgress(
  storage: PendingTurnStorage,
  key: string,
): void {
  const turns = listPendingChatTurns(storage);
  let changed = false;
  const next = turns.map((turn) => {
    if (turn.key !== key || turn.seenInProgress) return turn;
    changed = true;
    return { ...turn, seenInProgress: true };
  });
  if (!changed) return;
  storage.setItem(INDEX_KEY, JSON.stringify(next));
}

export function markPendingMemorySweep(
  storage: PendingTurnStorage,
  {
    classId,
    reviewId,
  }: {
    classId: string;
    reviewId: string;
  },
): string {
  return markPendingChatTurn(storage, {
    mode: "memory_sweep",
    classId,
    sessionId: reviewId,
    draftId: reviewId,
    resumeHref: `/classes/${classId}/memory-sweep`,
  });
}

export function clearPendingMemorySweep(
  storage: PendingTurnStorage,
  classId: string,
): void {
  clearPendingChatTurn(storage, pendingMemorySweepKey(classId));
}

export function clearPendingChatTurn(
  storage: PendingTurnStorage,
  key: string,
): void {
  storage.removeItem(key);
  const remaining = listPendingChatTurns(storage).filter((item) => item.key !== key);
  if (remaining.length > 0) {
    storage.setItem(INDEX_KEY, JSON.stringify(remaining));
  } else {
    storage.removeItem(INDEX_KEY);
  }
}

/**
 * Returns true only for the first UI surface that observes this completion.
 * The active chat and app-wide notifier may race, but only one should toast.
 */
export function consumeCompletedPendingChatTurn(
  storage: PendingTurnStorage,
  key: string,
): boolean {
  if (!storage.getItem(key)) return false;
  clearPendingChatTurn(storage, key);
  return true;
}

/** Stable fingerprint of the current pending-turn key set for dismiss UI. */
export function pendingTurnDismissFingerprint(turns: PendingChatTurn[]): string {
  return turns
    .map((turn) => turn.key)
    .sort()
    .join("|");
}

export function isRunningTasksBoxDismissed(
  storage: PendingTurnStorage,
  turns: PendingChatTurn[],
): boolean {
  if (turns.length === 0) return true;
  return storage.getItem(DISMISS_KEY) === pendingTurnDismissFingerprint(turns);
}

export function dismissRunningTasksBox(
  storage: PendingTurnStorage,
  turns: PendingChatTurn[],
): void {
  if (turns.length === 0) {
    storage.removeItem(DISMISS_KEY);
    return;
  }
  storage.setItem(DISMISS_KEY, pendingTurnDismissFingerprint(turns));
}

function isOptionalString(value: unknown): value is string | undefined {
  return value === undefined || typeof value === "string";
}

function isPendingChatTurn(value: unknown): value is PendingChatTurn {
  if (!value || typeof value !== "object") return false;
  const item = value as PendingChatTurn;
  return (
    typeof item.key === "string" &&
    (item.mode === "ingest" ||
      item.mode === "plan" ||
      item.mode === "discuss" ||
      item.mode === "memory_sweep") &&
    typeof item.classId === "string" &&
    typeof item.sessionId === "string" &&
    (item.draftId === undefined || typeof item.draftId === "string") &&
    (item.seenInProgress === undefined || typeof item.seenInProgress === "boolean") &&
    (item.baselineMessageCount === undefined ||
      typeof item.baselineMessageCount === "number") &&
    isOptionalString(item.lessonDate) &&
    isOptionalString(item.lessonTitle) &&
    isOptionalString(item.resumeHref)
  );
}
