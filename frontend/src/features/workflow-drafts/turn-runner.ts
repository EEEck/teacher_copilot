"use client";

/**
 * Module-level chat turn runner (design:
 * docs/beta_readiness_audit_2026-07-13.md §A.1.6).
 *
 * Owns the SSE consumption loop outside React so navigation never interrupts
 * a turn (P3): only the Stop button (`cancelTurn`) or process death do. All
 * thread/flag writes go through the workflow draft store; ambiguous stream
 * ends resolve to a phase and are settled against backend truth by the
 * store's snapshot reducer — never by inspecting thread content (P2).
 */

import { toast } from "sonner";
import type { ThreadMessageLike } from "@assistant-ui/react";

import type { ChatStreamChunk, ArtifactMode } from "@/components/assistant-ui/artifact-runtime-config";
import { chatFailureToastLabel } from "@/lib/chat-run-feedback";
import {
  clearPendingChatTurn,
  isPendingTurnOnCurrentPage,
  listPendingChatTurns,
  type PendingTurnStorage,
} from "@/lib/pending-chat-turns";
import type { SessionAttachment } from "@/lib/session-attachments";
import { streamPartsToRunContent } from "@/lib/sse-chat";

import { CHAT_ERROR_REPLY, friendlyChatError } from "./chat-errors";
import { isPlaceholderAssistantContent } from "./thread-messages";
import { useWorkflowDraftStore } from "./workflow-draft-store";
import { resolveClientStreamEnd } from "./workflow-turn-state";

export type ChatStreamFn = (args: {
  message: string;
  currentMarkdown: string;
  attachments?: SessionAttachment[];
  signal?: AbortSignal;
}) => AsyncGenerator<ChatStreamChunk>;

/** One in-flight turn per draft; controllers are not render state. */
const controllers = new Map<string, AbortController>();

export function hasLiveRunner(draftId: string): boolean {
  return controllers.has(draftId);
}

/** Stop button: abort the client stream. The backend turn keeps running. */
export function cancelTurn(draftId: string): void {
  controllers.get(draftId)?.abort();
}

export type RunTurnArgs = {
  draftId: string;
  mode: ArtifactMode;
  lessonDate?: string;
  lessonTitle?: string;
  /** pending-chat-turns marker key written by the page before calling. */
  pendingKey?: string;
  /** Marker storage; defaults to window.sessionStorage (injectable in tests). */
  pendingStorage?: PendingTurnStorage;
  userText: string;
  userContent: ThreadMessageLike["content"];
  placeholderContent: ThreadMessageLike["content"];
  attachments?: SessionAttachment[];
  currentMarkdown: string;
  chatStream: ChatStreamFn;
};

export async function runTurn(args: RunTurnArgs): Promise<void> {
  if (controllers.has(args.draftId)) return;
  const ctl = new AbortController();
  controllers.set(args.draftId, ctl);

  const store = () => useWorkflowDraftStore.getState();
  store().beginTurn(args.draftId, {
    userContent: args.userContent,
    placeholderContent: args.placeholderContent,
    pendingKey: args.pendingKey,
  });

  let gotFinal = false;
  let streamedContent = false;
  try {
    for await (const chunk of args.chatStream({
      message: args.userText,
      currentMarkdown: args.currentMarkdown,
      attachments: args.attachments,
      signal: ctl.signal,
    })) {
      if (chunk.kind === "progress") {
        if (chunk.content.length > 0) {
          const runContent = streamPartsToRunContent(chunk.content) ?? [];
          if (!isPlaceholderAssistantContent(runContent)) {
            streamedContent = true;
          }
          store().applyTurnProgress(args.draftId, runContent);
        }
        continue;
      }
      gotFinal = true;
      const content =
        chunk.content.length > 0
          ? (streamPartsToRunContent(chunk.content) ?? [])
          : [{ type: "text" as const, text: chunk.result.reply }];
      store().completeTurn(args.draftId, {
        content,
        reply: chunk.result.reply,
        userText: args.userText,
        artifactMarkdown: chunk.result.artifactMarkdown,
        artifactRevision: chunk.result.artifactRevision,
        artifactHash: chunk.result.artifactHash,
        completeness: chunk.result.completeness,
        readyToSave: chunk.result.readyToSave,
        lastChangeSummary: chunk.result.lastChangeSummary,
        memoryState: chunk.result.memoryState,
        memoryCandidates: chunk.result.memoryCandidates,
      });
    }
    if (!gotFinal) settleWithoutFinal(args, ctl, undefined, streamedContent);
  } catch (err) {
    if (!gotFinal) settleWithoutFinal(args, ctl, err, streamedContent);
    // gotFinal + late transport noise → already settled, ignore.
  } finally {
    controllers.delete(args.draftId);
  }
}

/**
 * The client stream ended without a final event. Same classification as the
 * old resolveClientStreamEnd, now confined here: an explicit Stop or a
 * mid-stream drop means the backend may still finish (awaiting_backend, the
 * reducer merges the reply later); nothing streamed means the turn never
 * started (failed).
 */
function settleWithoutFinal(
  args: RunTurnArgs,
  ctl: AbortController,
  err: unknown,
  streamedContent: boolean,
): void {
  const store = useWorkflowDraftStore.getState();
  const phase = ctl.signal.aborted
    ? "backend_running"
    : resolveClientStreamEnd({ gotFinal: false, hadStreamedContent: streamedContent });
  if (phase === "backend_running") {
    store.markAwaitingBackend(args.draftId);
    return;
  }
  store.failTurn(
    args.draftId,
    err === undefined ? CHAT_ERROR_REPLY : friendlyChatError(err),
  );
  notifyTurnFailed(args);
}

/**
 * Hard failure: clear the pending marker (no false completion toast) and,
 * when the teacher is not looking at this chat, tell them it failed
 * (design decision Q5, 2026-07-14).
 */
function notifyTurnFailed(args: RunTurnArgs): void {
  const storage =
    args.pendingStorage ??
    (typeof window === "undefined" ? undefined : window.sessionStorage);
  if (!storage || !args.pendingKey) return;
  const marker = listPendingChatTurns(storage).find(
    (turn) => turn.key === args.pendingKey,
  );
  clearPendingChatTurn(storage, args.pendingKey);
  if (typeof window === "undefined") return;
  const onCurrentPage = marker
    ? isPendingTurnOnCurrentPage(
        marker,
        `${window.location.pathname}${window.location.search}`,
      )
    : true;
  if (!onCurrentPage) {
    toast.error(
      chatFailureToastLabel({
        mode: args.mode,
        lessonDate: args.lessonDate,
        lessonTitle: args.lessonTitle,
      }),
    );
  }
}
