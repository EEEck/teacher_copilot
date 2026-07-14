import { create } from "zustand";
import { createStore, type StoreApi } from "zustand/vanilla";
import type { ThreadMessageLike } from "@assistant-ui/react";

import type { ArtifactMode } from "@/components/assistant-ui/artifact-runtime-config";
import type {
  ChatMessage,
  CompletenessChecklist,
  MemoryCandidate,
} from "@/lib/api";

import { CHAT_ERROR_REPLY } from "./chat-errors";
import { newThreadMessageId, replaceLastAssistantContent } from "./thread-messages";
import { flagsForPhase } from "./workflow-turn-state";

export type WorkflowDraftSnapshot = {
  mode: ArtifactMode;
  classId: string;
  draftId: string;
  sessionId: string;
  messages: ChatMessage[];
  artifactMarkdown: string;
  artifactRevision: number;
  artifactHash: string;
  turnInProgress: boolean;
  latestTurnComplete: boolean;
  /** Ingest checklist from draft fetch / turn completion. */
  completeness?: CompletenessChecklist | null;
  /** Ingest memory runtime payload from draft fetch / turn completion. */
  memoryState?: Record<string, unknown> | null;
  /** Final-turn meta (previously mirrored in provider state). */
  readyToSave?: boolean;
  lastChangeSummary?: string | null;
  memoryCandidates?: MemoryCandidate[];
};

/**
 * Turn ownership for one draft in THIS JS context (design:
 * docs/beta_readiness_audit_2026-07-13.md §A.1.3).
 *
 * - `streaming`: a runner is consuming SSE for this draft.
 * - `awaiting_backend`: the client stream ended without a final event (Stop
 *   button or dropped connection); the backend may still finish the turn.
 * - `settled`: this context knows the turn's outcome; the local thread is
 *   authoritative until discard/refresh (documented limitation: a second
 *   tab/device appending to the same draft is not reflected until refresh).
 */
export type TurnPhase = "streaming" | "awaiting_backend" | "settled";

export type TurnRecord = {
  phase: TurnPhase;
  startedAt: number;
  /** pending-chat-turns marker key; cleared by the runner on hard failure. */
  pendingKey?: string;
};

/** Final-turn payload written by the runner on the final SSE event. */
export type TurnFinalPatch = {
  /** Final assistant thread content (stream parts, or plain reply text). */
  content: ThreadMessageLike["content"];
  /** Plain-text mirror appended to snapshot.messages. */
  reply: string;
  userText: string;
  artifactMarkdown: string;
  artifactRevision?: number;
  artifactHash?: string;
  completeness?: CompletenessChecklist | null;
  readyToSave?: boolean;
  lastChangeSummary?: string | null;
  memoryState?: Record<string, unknown> | null;
  memoryCandidates?: MemoryCandidate[];
};

/** Partial snapshot merge for PATCH-draft responses (no messages/flags). */
export type DraftMetadataPatch = {
  draftId?: string;
  /** Teacher-edited markdown just PATCHed — keeps the mirror in step so the
   * store→editor sync effect cannot revert the editor to a stale value. */
  artifactMarkdown?: string;
  artifactRevision?: number;
  artifactHash?: string;
  completeness?: CompletenessChecklist | null;
  readyToSave?: boolean;
};

type WorkflowDraftState = {
  draftsById: Record<string, WorkflowDraftSnapshot>;
  threadMessagesByDraftId: Record<string, ThreadMessageLike[]>;
  turnByDraftId: Record<string, TurnRecord>;
  /** Snapshot reducer — the only entry point for backend snapshots. */
  upsert: (snapshot: WorkflowDraftSnapshot) => void;
  /** Merge PATCH-draft metadata into an existing snapshot (no thread/flags). */
  applyDraftPatch: (draftId: string, patch: DraftMetadataPatch) => void;
  setThreadMessages: (draftId: string, messages: ThreadMessageLike[]) => void;
  /** Runner-facing turn lifecycle (all no-ops when the draft was removed). */
  beginTurn: (
    draftId: string,
    args: {
      userContent: ThreadMessageLike["content"];
      placeholderContent: ThreadMessageLike["content"];
      pendingKey?: string;
    },
  ) => void;
  applyTurnProgress: (
    draftId: string,
    content: ThreadMessageLike["content"],
  ) => void;
  completeTurn: (draftId: string, patch: TurnFinalPatch) => void;
  markAwaitingBackend: (draftId: string) => void;
  failTurn: (draftId: string, friendlyMessage: string) => void;
  remove: (draftId: string) => void;
};

type WorkflowDraftStore = StoreApi<WorkflowDraftState>;

/** Stable fallback so selectors never allocate per render (invariant I6). */
export const EMPTY_THREAD: ThreadMessageLike[] = [];

export const selectThreadMessages =
  (draftId: string) =>
  (state: Pick<WorkflowDraftState, "threadMessagesByDraftId">) =>
    state.threadMessagesByDraftId[draftId] ?? EMPTY_THREAD;

function lastSnapshotAssistantReply(messages: ChatMessage[]): string {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    if (messages[i].role === "assistant" && messages[i].content.trim()) {
      return messages[i].content;
    }
  }
  return "";
}

/**
 * Attach the persisted final reply text to the last assistant message without
 * dropping streamed reasoning/tool parts. Used only for the
 * `awaiting_backend` reducer rows (Stop button / dropped connection).
 */
export function mergeFinalReplyIntoThread(
  previous: ThreadMessageLike[],
  snapshotMessages: ChatMessage[],
): ThreadMessageLike[] {
  const reply = lastSnapshotAssistantReply(snapshotMessages);
  if (!reply) return previous;

  const next = [...previous];
  for (let i = next.length - 1; i >= 0; i -= 1) {
    if (next[i].role !== "assistant") continue;
    const content = next[i].content;
    if (!Array.isArray(content)) {
      next[i] = { ...next[i], content: reply };
      return next;
    }
    const parts = [...content];
    const textIndex = parts.findIndex((part) => part.type === "text");
    if (textIndex >= 0) {
      parts[textIndex] = { type: "text", text: reply };
    } else {
      parts.push({ type: "text", text: reply });
    }
    next[i] = { ...next[i], content: parts };
    return next;
  }
  return previous;
}

function messagesFromSnapshot(messages: ChatMessage[]): ThreadMessageLike[] {
  return messages.map(
    (message, index): ThreadMessageLike => ({
      id: `persisted-${index}`,
      role: message.role as ThreadMessageLike["role"],
      content: message.content,
    }),
  );
}

function snapshotSaysComplete(snapshot: WorkflowDraftSnapshot): boolean {
  return !snapshot.turnInProgress && snapshot.latestTurnComplete;
}

function snapshotSaysInterrupted(snapshot: WorkflowDraftSnapshot): boolean {
  return !snapshot.turnInProgress && !snapshot.latestTurnComplete;
}

const createWorkflowDraftState = (
  set: WorkflowDraftStore["setState"],
): WorkflowDraftState => ({
  draftsById: {},
  threadMessagesByDraftId: {},
  turnByDraftId: {},

  /**
   * Snapshot reducer (design §A.1.4). Always refreshes draftsById; the thread
   * is decided purely from (turn record, snapshot):
   *
   * | record            | snapshot        | thread                     |
   * |-------------------|-----------------|----------------------------|
   * | none              | any             | replace (empty-fetch guard)|
   * | streaming         | any             | untouched                  |
   * | awaiting_backend  | in progress     | untouched                  |
   * | awaiting_backend  | complete        | merge final reply; settle  |
   * | awaiting_backend  | interrupted     | append error text; settle  |
   * | settled           | any             | untouched                  |
   */
  upsert: (snapshot) => {
    set((state) => {
      const key = snapshot.draftId;
      const previous = state.threadMessagesByDraftId[key] ?? [];
      const turn = state.turnByDraftId[key];

      let nextThread = previous;
      let nextTurn = turn;
      if (!turn) {
        // Stale/empty fetch must not wipe an existing thread.
        nextThread =
          snapshot.messages.length === 0 && previous.length > 0
            ? previous
            : messagesFromSnapshot(snapshot.messages);
      } else if (turn.phase === "awaiting_backend") {
        if (snapshotSaysComplete(snapshot)) {
          nextThread = mergeFinalReplyIntoThread(previous, snapshot.messages);
          nextTurn = { ...turn, phase: "settled" };
        } else if (snapshotSaysInterrupted(snapshot)) {
          nextThread = mergeFinalReplyIntoThread(previous, [
            { role: "assistant", content: CHAT_ERROR_REPLY },
          ]);
          nextTurn = { ...turn, phase: "settled" };
        }
        // still in progress → untouched
      }
      // streaming / settled → untouched

      return {
        draftsById: { ...state.draftsById, [key]: snapshot },
        threadMessagesByDraftId: {
          ...state.threadMessagesByDraftId,
          [key]: nextThread,
        },
        turnByDraftId:
          nextTurn === turn
            ? state.turnByDraftId
            : { ...state.turnByDraftId, [key]: nextTurn as TurnRecord },
      };
    });
  },

  applyDraftPatch: (draftId, patch) => {
    set((state) => {
      const existing = state.draftsById[draftId];
      if (!existing) return state;
      return {
        draftsById: {
          ...state.draftsById,
          [draftId]: {
            ...existing,
            ...(patch.artifactMarkdown !== undefined
              ? { artifactMarkdown: patch.artifactMarkdown }
              : null),
            ...(patch.artifactRevision !== undefined
              ? { artifactRevision: patch.artifactRevision }
              : null),
            ...(patch.artifactHash !== undefined
              ? { artifactHash: patch.artifactHash }
              : null),
            ...(patch.completeness !== undefined
              ? { completeness: patch.completeness }
              : null),
            ...(patch.readyToSave !== undefined
              ? { readyToSave: patch.readyToSave }
              : null),
          },
        },
      };
    });
  },

  setThreadMessages: (draftId, messages) => {
    set((state) => ({
      threadMessagesByDraftId: {
        ...state.threadMessagesByDraftId,
        [draftId]: messages,
      },
    }));
  },

  beginTurn: (draftId, { userContent, placeholderContent, pendingKey }) => {
    set((state) => {
      const existing = state.draftsById[draftId];
      if (!existing) return state; // I5: removed draft → no-op
      const flags = flagsForPhase("streaming");
      const previous = state.threadMessagesByDraftId[draftId] ?? [];
      return {
        draftsById: {
          ...state.draftsById,
          [draftId]: {
            ...existing,
            turnInProgress: flags.turnInProgress,
            latestTurnComplete: flags.latestTurnComplete,
          },
        },
        threadMessagesByDraftId: {
          ...state.threadMessagesByDraftId,
          [draftId]: [
            ...previous,
            {
              id: newThreadMessageId("user"),
              role: "user",
              content: userContent,
            },
            {
              id: newThreadMessageId("assistant"),
              role: "assistant",
              content: placeholderContent,
            },
          ],
        },
        turnByDraftId: {
          ...state.turnByDraftId,
          [draftId]: { phase: "streaming", startedAt: Date.now(), pendingKey },
        },
      };
    });
  },

  applyTurnProgress: (draftId, content) => {
    set((state) => {
      if (!state.draftsById[draftId]) return state;
      if (state.turnByDraftId[draftId]?.phase !== "streaming") return state;
      const previous = state.threadMessagesByDraftId[draftId] ?? [];
      return {
        threadMessagesByDraftId: {
          ...state.threadMessagesByDraftId,
          [draftId]: replaceLastAssistantContent(previous, content),
        },
      };
    });
  },

  completeTurn: (draftId, patch) => {
    set((state) => {
      const existing = state.draftsById[draftId];
      if (!existing) return state;
      const flags = flagsForPhase("complete");
      const previous = state.threadMessagesByDraftId[draftId] ?? [];
      const turn = state.turnByDraftId[draftId];
      return {
        draftsById: {
          ...state.draftsById,
          [draftId]: {
            ...existing,
            messages: [
              ...existing.messages,
              { role: "user", content: patch.userText },
              { role: "assistant", content: patch.reply },
            ],
            artifactMarkdown: patch.artifactMarkdown,
            artifactRevision: patch.artifactRevision ?? existing.artifactRevision,
            artifactHash: patch.artifactHash ?? existing.artifactHash,
            turnInProgress: flags.turnInProgress,
            latestTurnComplete: flags.latestTurnComplete,
            ...(patch.completeness !== undefined
              ? { completeness: patch.completeness }
              : null),
            ...(patch.readyToSave !== undefined
              ? { readyToSave: patch.readyToSave }
              : null),
            ...(patch.lastChangeSummary !== undefined
              ? { lastChangeSummary: patch.lastChangeSummary }
              : null),
            ...(patch.memoryState !== undefined
              ? { memoryState: patch.memoryState }
              : null),
            ...(patch.memoryCandidates !== undefined
              ? { memoryCandidates: patch.memoryCandidates }
              : null),
          },
        },
        threadMessagesByDraftId: {
          ...state.threadMessagesByDraftId,
          [draftId]: replaceLastAssistantContent(previous, patch.content),
        },
        turnByDraftId: {
          ...state.turnByDraftId,
          [draftId]: {
            phase: "settled",
            startedAt: turn?.startedAt ?? Date.now(),
            pendingKey: turn?.pendingKey,
          },
        },
      };
    });
  },

  markAwaitingBackend: (draftId) => {
    set((state) => {
      const existing = state.draftsById[draftId];
      const turn = state.turnByDraftId[draftId];
      if (!existing || !turn) return state;
      const flags = flagsForPhase("backend_running");
      return {
        draftsById: {
          ...state.draftsById,
          [draftId]: {
            ...existing,
            turnInProgress: flags.turnInProgress,
            latestTurnComplete: flags.latestTurnComplete,
          },
        },
        turnByDraftId: {
          ...state.turnByDraftId,
          [draftId]: { ...turn, phase: "awaiting_backend" },
        },
      };
    });
  },

  failTurn: (draftId, friendlyMessage) => {
    set((state) => {
      const existing = state.draftsById[draftId];
      if (!existing) return state;
      const flags = flagsForPhase("failed");
      const previous = state.threadMessagesByDraftId[draftId] ?? [];
      const turn = state.turnByDraftId[draftId];
      return {
        draftsById: {
          ...state.draftsById,
          [draftId]: {
            ...existing,
            turnInProgress: flags.turnInProgress,
            latestTurnComplete: flags.latestTurnComplete,
          },
        },
        threadMessagesByDraftId: {
          ...state.threadMessagesByDraftId,
          [draftId]: replaceLastAssistantContent(previous, [
            { type: "text", text: friendlyMessage },
          ]),
        },
        turnByDraftId: {
          ...state.turnByDraftId,
          [draftId]: {
            phase: "settled",
            startedAt: turn?.startedAt ?? Date.now(),
            pendingKey: turn?.pendingKey,
          },
        },
      };
    });
  },

  remove: (draftId) => {
    set((state) => {
      const { [draftId]: _removed, ...draftsById } = state.draftsById;
      const { [draftId]: _thread, ...threadMessagesByDraftId } =
        state.threadMessagesByDraftId;
      const { [draftId]: _turn, ...turnByDraftId } = state.turnByDraftId;
      return { draftsById, threadMessagesByDraftId, turnByDraftId };
    });
  },
});

export function createWorkflowDraftStore(): WorkflowDraftStore {
  return createStore(createWorkflowDraftState);
}

export const useWorkflowDraftStore = create<WorkflowDraftState>(
  createWorkflowDraftState,
);
