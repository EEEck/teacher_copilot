import type { ArtifactMode } from "@/components/assistant-ui/artifact-runtime-config";

type PendingTurnStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;

const INDEX_KEY = "kp:turn-pending:index";

export type PendingChatTurn = {
  key: string;
  mode: ArtifactMode;
  classId: string;
  sessionId: string;
  draftId?: string;
};

export type PendingDraftStatus = {
  turn_in_progress?: boolean;
  latest_turn_complete?: boolean;
};

export function isPendingDraftComplete(status: PendingDraftStatus): boolean {
  return status.latest_turn_complete === true && status.turn_in_progress !== true;
}

export function pendingTurnKey(
  draftId: string | undefined,
  sessionId: string,
): string {
  return `kp:turn-pending:${draftId || sessionId}`;
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
  turn: Omit<PendingChatTurn, "key">,
): string {
  const key = pendingTurnKey(turn.draftId, turn.sessionId);
  const next: PendingChatTurn = { ...turn, key };
  const existing = listPendingChatTurns(storage).filter((item) => item.key !== key);
  storage.setItem(key, "1");
  storage.setItem(INDEX_KEY, JSON.stringify([...existing, next]));
  return key;
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

function isPendingChatTurn(value: unknown): value is PendingChatTurn {
  if (!value || typeof value !== "object") return false;
  const item = value as PendingChatTurn;
  return (
    typeof item.key === "string" &&
    (item.mode === "ingest" || item.mode === "plan") &&
    typeof item.classId === "string" &&
    typeof item.sessionId === "string" &&
    (item.draftId === undefined || typeof item.draftId === "string")
  );
}
