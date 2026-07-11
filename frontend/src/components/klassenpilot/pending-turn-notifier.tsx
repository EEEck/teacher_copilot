"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { RunningTasksBox } from "@/components/klassenpilot/running-tasks-box";
import { client, isUnknownSessionError } from "@/lib/api";
import {
  chatCompletionToastLabel,
  chatFailureToastLabel,
} from "@/lib/chat-run-feedback";
import { fetchedDraftToSnapshot } from "@/features/workflow-drafts/workflow-draft-transport";
import { useWorkflowDraftStore } from "@/features/workflow-drafts/workflow-draft-store";
import {
  clearPendingChatTurn,
  consumeCompletedPendingChatTurn,
  dismissRunningTasksBox,
  isPendingDraftComplete,
  isPendingMemorySweepComplete,
  isRunningTasksBoxDismissed,
  listPendingChatTurns,
  type PendingChatTurn,
} from "@/lib/pending-chat-turns";

export function PendingTurnNotifier() {
  const inFlightRef = useRef(false);
  const [pending, setPending] = useState<PendingChatTurn[]>([]);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const syncPending = () => {
      const next = listPendingChatTurns(window.sessionStorage);
      setPending(next);
      setDismissed(isRunningTasksBoxDismissed(window.sessionStorage, next));
    };

    const checkPendingTurns = async () => {
      if (inFlightRef.current) return;
      const current = listPendingChatTurns(window.sessionStorage);
      setPending(current);
      setDismissed(isRunningTasksBoxDismissed(window.sessionStorage, current));
      if (current.length === 0) return;

      inFlightRef.current = true;
      try {
        await Promise.all(current.map(checkOnePendingTurn));
        syncPending();
      } finally {
        inFlightRef.current = false;
      }
    };

    const interval = window.setInterval(() => {
      void checkPendingTurns();
    }, 2000);

    const handleFocus = () => {
      void checkPendingTurns();
    };
    const handleVisibility = () => {
      if (document.visibilityState === "visible") void checkPendingTurns();
    };
    const handleStorage = () => {
      syncPending();
    };

    window.addEventListener("focus", handleFocus);
    document.addEventListener("visibilitychange", handleVisibility);
    window.addEventListener("storage", handleStorage);
    void checkPendingTurns();

    // Same-tab marker writes do not fire the storage event; poll the index lightly.
    const localSync = window.setInterval(syncPending, 1000);

    return () => {
      window.clearInterval(interval);
      window.clearInterval(localSync);
      window.removeEventListener("focus", handleFocus);
      document.removeEventListener("visibilitychange", handleVisibility);
      window.removeEventListener("storage", handleStorage);
    };
  }, []);

  const visible = pending.length > 0 && !dismissed;

  return (
    <>
      {visible ? (
        <RunningTasksBox
          turns={pending}
          onDismiss={() => {
            if (typeof window === "undefined") return;
            dismissRunningTasksBox(window.sessionStorage, pending);
            setDismissed(true);
          }}
        />
      ) : null}
    </>
  );
}

async function checkOnePendingTurn(turn: PendingChatTurn): Promise<void> {
  try {
    if (turn.mode === "memory_sweep") {
      const review = await client.getMemorySweepReview(turn.classId);
      if (!isPendingMemorySweepComplete(review)) return;
      if (consumeCompletedPendingChatTurn(window.sessionStorage, turn.key)) {
        if (review.status === "failed") {
          toast.error(chatFailureToastLabel({ mode: "memory_sweep" }));
        } else {
          toast.success(chatCompletionToastLabel({ mode: "memory_sweep" }));
        }
      }
      return;
    }

    const draft =
      turn.mode === "plan"
        ? await client.planGetDraft(turn.classId, turn.sessionId)
        : await client.ingestGetDraft(turn.classId, turn.sessionId);
    if (!isPendingDraftComplete(draft)) return;
    useWorkflowDraftStore
      .getState()
      .upsert(fetchedDraftToSnapshot(turn.mode, turn.classId, turn.sessionId, draft));
    if (consumeCompletedPendingChatTurn(window.sessionStorage, turn.key)) {
      toast.success(
        chatCompletionToastLabel({
          mode: turn.mode,
          lessonDate: turn.lessonDate,
          lessonTitle: turn.lessonTitle,
        }),
      );
    }
  } catch (error) {
    if (isUnknownSessionError(error)) {
      clearPendingChatTurn(window.sessionStorage, turn.key);
    }
    // Keep transient API failures so a later check can still notify the teacher.
  }
}
