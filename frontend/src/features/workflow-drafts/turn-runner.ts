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
import {
  chatCompletionToastLabel,
  chatFailureToastLabel,
} from "@/lib/chat-run-feedback";
import type { SessionAttachment } from "@/lib/session-attachments";
import { streamPartsToRunContent } from "@/lib/sse-chat";

import { CHAT_ERROR_REPLY, friendlyChatError } from "./chat-errors";
import { isPlaceholderAssistantContent } from "./thread-messages";
import { useWorkflowDraftStore } from "./workflow-draft-store";

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
  /** Toast/label context, carried on the store's turn record. */
  mode: ArtifactMode;
  classId: string;
  lessonDate?: string;
  lessonTitle?: string;
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
    mode: args.mode,
    classId: args.classId,
    lessonDate: args.lessonDate,
    lessonTitle: args.lessonTitle,
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
        artifactMarkdown: chunk.result.artifactMarkdown,
        artifactRevision: chunk.result.artifactRevision,
        artifactHash: chunk.result.artifactHash,
        completeness: chunk.result.completeness,
        readyToSave: chunk.result.readyToSave,
        lastChangeSummary: chunk.result.lastChangeSummary,
        memoryState: chunk.result.memoryState,
        memoryCandidates: chunk.result.memoryCandidates,
      });
      notifyTurnFinished(args, chunk.result.artifactRevision);
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
 * The client stream ended without a final event.
 *
 * Mapping (D1 + chemistry-tip error copy):
 * - Stop / AbortError → awaiting_backend (backend may still finish).
 * - Drop after content arrived → awaiting_backend (poll/reducer settles).
 * - True terminal failure with nothing streamed → settle with friendly error
 *   (preserves HEAD CHAT_ERROR_REPLY / friendlyChatError settle-with-error).
 */
function settleWithoutFinal(
  args: RunTurnArgs,
  ctl: AbortController,
  err: unknown,
  streamedContent: boolean,
): void {
  const store = useWorkflowDraftStore.getState();
  if (ctl.signal.aborted || streamedContent) {
    store.markAwaitingBackend(args.draftId);
    return;
  }
  store.failTurn(
    args.draftId,
    err === undefined ? CHAT_ERROR_REPLY : friendlyChatError(err),
  );
  notifyTurnFailed(args);
}

/** True when this chat is not the one on screen — i.e. worth a toast. */
function isOffScreen(draftId: string): boolean {
  return useWorkflowDraftStore.getState().mountedDraftId !== draftId;
}

/**
 * The turn finished in this context. Toast immediately when the teacher is
 * elsewhere (no need to wait for a notifier poll tick); the shared
 * markTurnNotified dedupe keeps the notifier from toasting it again.
 */
function notifyTurnFinished(args: RunTurnArgs, artifactRevision?: number): void {
  if (!isOffScreen(args.draftId)) return;
  const store = useWorkflowDraftStore.getState();
  const revision =
    artifactRevision ?? store.draftsById[args.draftId]?.artifactRevision ?? 0;
  if (!store.markTurnNotified(args.draftId, revision)) return;
  toast.success(
    chatCompletionToastLabel({
      mode: args.mode,
      lessonDate: args.lessonDate,
      lessonTitle: args.lessonTitle,
    }),
  );
}

/**
 * Hard failure: when the teacher is not looking at this chat, tell them it
 * failed (the error reply itself lands in the unwatched thread).
 */
function notifyTurnFailed(args: RunTurnArgs): void {
  if (!isOffScreen(args.draftId)) return;
  toast.error(
    chatFailureToastLabel({
      mode: args.mode,
      lessonDate: args.lessonDate,
      lessonTitle: args.lessonTitle,
    }),
  );
}
