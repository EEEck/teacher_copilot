"use client";

import { useEffect, useRef } from "react";
import { toast } from "sonner";

import { client } from "@/lib/api";
import { chatCompletionToastLabel } from "@/lib/chat-run-feedback";
import {
  clearPendingChatTurn,
  isPendingDraftComplete,
  listPendingChatTurns,
  type PendingChatTurn,
} from "@/lib/pending-chat-turns";

export function PendingTurnNotifier() {
  const inFlightRef = useRef(false);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const checkPendingTurns = async () => {
      if (inFlightRef.current) return;
      if (isArtifactWorkflowRoute(window.location.pathname)) return;
      const pending = listPendingChatTurns(window.sessionStorage);
      if (pending.length === 0) return;

      inFlightRef.current = true;
      try {
        await Promise.all(pending.map(checkOnePendingTurn));
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

    window.addEventListener("focus", handleFocus);
    document.addEventListener("visibilitychange", handleVisibility);
    void checkPendingTurns();

    return () => {
      window.clearInterval(interval);
      window.removeEventListener("focus", handleFocus);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, []);

  return null;
}

function isArtifactWorkflowRoute(pathname: string): boolean {
  return /^\/classes\/[^/]+\/(?:plan|memory)(?:\/|$)/.test(pathname);
}

async function checkOnePendingTurn(turn: PendingChatTurn): Promise<void> {
  try {
    const draft =
      turn.mode === "plan"
        ? await client.planGetDraft(turn.classId, turn.sessionId)
        : await client.ingestGetDraft(turn.classId, turn.sessionId);
    if (!isPendingDraftComplete(draft)) return;
    clearPendingChatTurn(window.sessionStorage, turn.key);
    toast.success(chatCompletionToastLabel(turn.mode));
  } catch {
    // Keep the marker. A transient API miss should not hide a future completion.
  }
}
