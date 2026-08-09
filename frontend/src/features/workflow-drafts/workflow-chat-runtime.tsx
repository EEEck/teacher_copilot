"use client";

import { useCallback, useMemo, useRef } from "react";
import {
  useExternalStoreRuntime,
  type AppendMessage,
  type AttachmentAdapter,
  type ThreadMessageLike,
} from "@assistant-ui/react";

import { truncateThreadBeforeEdit } from "./thread-messages";
import {
  selectThreadMessages,
  useWorkflowDraftStore,
} from "./workflow-draft-store";

export type UpdateWorkflowThread = (
  update: (messages: ThreadMessageLike[]) => ThreadMessageLike[],
) => void;

export function useWorkflowChatRuntime({
  draftId,
  isRunning,
  onNew,
  onCancel,
  attachmentAdapter,
}: {
  draftId: string;
  isRunning: boolean;
  onNew: (message: AppendMessage, updateThread: UpdateWorkflowThread) => Promise<void>;
  /** Abort the in-flight SSE turn (Composer stop button). */
  onCancel?: () => Promise<void>;
  /** When set, enables composer + / drag-drop attachments (assistant-ui adapters). */
  attachmentAdapter?: AttachmentAdapter;
}) {
  // Stable fallback reference — an inline `?? []` here allocates per render
  // and loops useSyncExternalStore forever when the key is missing (Bug A).
  const messages = useWorkflowDraftStore(selectThreadMessages(draftId));
  const setThreadMessages = useWorkflowDraftStore((state) => state.setThreadMessages);
  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  const updateThread = useCallback(
    (update: (current: ThreadMessageLike[]) => ThreadMessageLike[]) => {
      setThreadMessages(draftId, update(messagesRef.current));
    },
    [draftId, setThreadMessages],
  );

  const onEdit = useCallback(
    async (message: AppendMessage) => {
      const truncated = truncateThreadBeforeEdit(
        messagesRef.current,
        message.parentId ?? null,
      );
      messagesRef.current = truncated;
      setThreadMessages(draftId, truncated);
      await onNew(message, updateThread);
    },
    [draftId, onNew, setThreadMessages, updateThread],
  );

  const adapter = useMemo(
    () => ({
      messages,
      isRunning,
      convertMessage: (message: ThreadMessageLike) => message,
      setMessages: (nextMessages: readonly ThreadMessageLike[]) =>
        setThreadMessages(draftId, [...nextMessages]),
      onNew: (message: AppendMessage) => onNew(message, updateThread),
      onEdit,
      onCancel,
      adapters: attachmentAdapter
        ? { attachments: attachmentAdapter }
        : undefined,
    }),
    [
      attachmentAdapter,
      draftId,
      isRunning,
      messages,
      onCancel,
      onEdit,
      onNew,
      setThreadMessages,
      updateThread,
    ],
  );

  return useExternalStoreRuntime(adapter);
}
