"use client";

import { useCallback, useMemo, useRef } from "react";
import {
  useExternalStoreRuntime,
  type AppendMessage,
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
}: {
  draftId: string;
  isRunning: boolean;
  onNew: (message: AppendMessage, updateThread: UpdateWorkflowThread) => Promise<void>;
  /** Abort the in-flight SSE turn (Composer stop button). */
  onCancel?: () => Promise<void>;
}) {
  const messages = useWorkflowDraftStore(
    (state) => selectThreadMessages(state, draftId),
  );
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
    }),
    [
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
