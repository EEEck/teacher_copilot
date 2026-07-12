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

const createWorkflowDraftState = (
  set: WorkflowDraftStore["setState"],
): WorkflowDraftState => ({
  draftsById: {},
  threadMessagesByDraftId: {},
  upsert: (snapshot) => {
    set((state) => ({
      draftsById: { ...state.draftsById, [snapshot.draftId]: snapshot },
      threadMessagesByDraftId: {
        ...state.threadMessagesByDraftId,
        [snapshot.draftId]: snapshot.messages.map(
          (message, index): ThreadMessageLike => ({
            id: `persisted-${index}`,
            role: message.role as ThreadMessageLike["role"],
            content: message.content,
          }),
        ),
      },
    }));
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
