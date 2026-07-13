import { create } from "zustand";
import { createStore, type StoreApi } from "zustand/vanilla";
import type { ThreadMessageLike } from "@assistant-ui/react";

import type { ArtifactMode } from "@/components/assistant-ui/artifact-runtime-config";
import type { ChatMessage, CompletenessChecklist } from "@/lib/api";

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
  /** Ingest checklist from draft fetch / background completion. */
  completeness?: CompletenessChecklist | null;
  /** Ingest memory runtime payload from draft fetch. */
  memoryState?: Record<string, unknown> | null;
};

type WorkflowDraftState = {
  draftsById: Record<string, WorkflowDraftSnapshot>;
  threadMessagesByDraftId: Record<string, ThreadMessageLike[]>;
  upsert: (snapshot: WorkflowDraftSnapshot) => void;
  setThreadMessages: (draftId: string, messages: ThreadMessageLike[]) => void;
  remove: (draftId: string) => void;
};

type WorkflowDraftStore = StoreApi<WorkflowDraftState>;

function threadHasRichParts(messages: ThreadMessageLike[]): boolean {
  return messages.some((message) => Array.isArray(message.content));
}

function lastAssistantLacksText(messages: ThreadMessageLike[]): boolean {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i];
    if (message.role !== "assistant") continue;
    if (typeof message.content === "string") return !message.content.trim();
    if (!Array.isArray(message.content)) return true;
    return !message.content.some(
      (part) =>
        part.type === "text" &&
        typeof (part as { text?: unknown }).text === "string" &&
        String((part as { text: string }).text).trim().length > 0,
    );
  }
  return false;
}

function lastSnapshotAssistantReply(messages: ChatMessage[]): string {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    if (messages[i].role === "assistant" && messages[i].content.trim()) {
      return messages[i].content;
    }
  }
  return "";
}

/**
 * Keep streamed reasoning/tools, but attach the persisted final reply text when
 * leave/return aborted the SSE before the final event arrived.
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

function messagesFromSnapshot(
  messages: ChatMessage[],
): ThreadMessageLike[] {
  return messages.map(
    (message, index): ThreadMessageLike => ({
      id: `persisted-${index}`,
      role: message.role as ThreadMessageLike["role"],
      content: message.content,
    }),
  );
}

/**
 * Decide whether to keep the in-memory thread instead of replacing it with a
 * plain persisted snapshot. Always update draftsById (turn flags / artifact).
 */
export function shouldKeepLiveThread(
  previous: ThreadMessageLike[],
  snapshotMessages: ChatMessage[],
  opts?: { turnInProgress?: boolean },
): boolean {
  if (previous.length === 0) return false;
  // Stale/empty fetch must not wipe a live stream.
  if (snapshotMessages.length === 0) return true;
  // While the backend turn is still open, never replace rich streamed parts
  // with a plain draft snapshot (leave/return / notifier polls).
  if (opts?.turnInProgress && threadHasRichParts(previous)) return true;
  // Keep streamed reasoning/tool parts when the snapshot is only plain strings
  // of similar length (typical same-tab completion upsert).
  return (
    threadHasRichParts(previous) &&
    snapshotMessages.length <= previous.length
  );
}

const createWorkflowDraftState = (
  set: WorkflowDraftStore["setState"],
): WorkflowDraftState => ({
  draftsById: {},
  threadMessagesByDraftId: {},
  upsert: (snapshot) => {
    set((state) => {
      const previous = state.threadMessagesByDraftId[snapshot.draftId] ?? [];
      let nextThread = shouldKeepLiveThread(previous, snapshot.messages, {
        turnInProgress: snapshot.turnInProgress,
      })
        ? previous
        : messagesFromSnapshot(snapshot.messages);
      // Leave/return often keeps reasoning/tools but never received the final
      // SSE text. When the draft completes, merge the persisted reply in.
      if (
        nextThread === previous &&
        !snapshot.turnInProgress &&
        snapshot.latestTurnComplete &&
        lastAssistantLacksText(previous)
      ) {
        nextThread = mergeFinalReplyIntoThread(previous, snapshot.messages);
      }
      return {
        draftsById: { ...state.draftsById, [snapshot.draftId]: snapshot },
        threadMessagesByDraftId: {
          ...state.threadMessagesByDraftId,
          [snapshot.draftId]: nextThread,
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
  remove: (draftId) => {
    set((state) => {
      const { [draftId]: _removed, ...draftsById } = state.draftsById;
      const { [draftId]: _thread, ...threadMessagesByDraftId } =
        state.threadMessagesByDraftId;
      return { draftsById, threadMessagesByDraftId };
    });
  },
});

export function createWorkflowDraftStore(): WorkflowDraftStore {
  return createStore(createWorkflowDraftState);
}

export const useWorkflowDraftStore = create<WorkflowDraftState>(
  createWorkflowDraftState,
);
