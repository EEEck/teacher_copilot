import type {
  ArtifactChatResult,
  ArtifactSessionConfig,
} from "@/components/assistant-ui/artifact-session-runtime";
import {
  client,
  isUnknownSessionError,
  type ChatMessage,
  type CompletenessChecklist,
} from "@/lib/api";
import { readSseJsonStream, StreamPartsAccumulator, type StreamPart } from "@/lib/sse-chat";
import type { SessionAttachment } from "@/lib/session-attachments";

export type ArtifactMode = "ingest" | "plan";

export type ChatStreamChunk =
  | { kind: "progress"; content: StreamPart[] }
  | { kind: "final"; content: StreamPart[]; result: ArtifactChatResult };

/**
 * Builds the per-mode runtime config consumed by ArtifactSessionRuntimeProvider.
 */
async function withSessionRecovery<T>(
  getSessionId: () => string,
  onSessionLost: ((markdown: string) => Promise<void>) | undefined,
  markdown: string,
  run: (sessionId: string) => Promise<T>,
): Promise<T> {
  try {
    return await run(getSessionId());
  } catch (err) {
    if (!onSessionLost || !isUnknownSessionError(err)) throw err;
    await onSessionLost(markdown);
    return await run(getSessionId());
  }
}

export function createArtifactRuntimeConfig(args: {
  mode: ArtifactMode;
  classId: string;
  sessionId: string;
  draftId?: string;
  artifactRevision?: number;
  artifactHash?: string;
  turnInProgress?: boolean;
  latestTurnComplete?: boolean;
  lessonDate?: string;
  lessonTitle?: string;
  initialMessages?: ChatMessage[];
  getSessionId?: () => string;
  onSessionLost?: (preserveMarkdown: string) => Promise<void>;
  initialMarkdown: string;
  initialCompleteness?: CompletenessChecklist | null;
  initialMemoryState?: Record<string, unknown> | null;
  onCompletenessChange?: (checklist: CompletenessChecklist) => void;
}): ArtifactSessionConfig {
  const {
    mode,
    classId,
    sessionId,
    draftId = "",
    artifactRevision = 0,
    artifactHash = "",
    turnInProgress = false,
    latestTurnComplete = true,
    lessonDate = "",
    lessonTitle = "",
    initialMessages,
    getSessionId = () => sessionId,
    onSessionLost,
    initialMarkdown,
    initialCompleteness = null,
    initialMemoryState = null,
    onCompletenessChange,
  } = args;

  async function* chatStream({
    message,
    currentMarkdown,
    attachments,
    signal,
  }: {
    message: string;
    currentMarkdown: string;
    attachments?: SessionAttachment[];
    signal?: AbortSignal;
  }): AsyncGenerator<ChatStreamChunk> {
    const res = await withSessionRecovery(
      getSessionId,
      onSessionLost,
      currentMarkdown,
      (sid) =>
        mode === "ingest"
          ? client.ingestChatStream(
              classId,
              sid,
              message,
              currentMarkdown,
              attachments,
              signal,
            )
          : client.planChatStream(
              classId,
              sid,
              message,
              currentMarkdown,
              attachments,
              signal,
            ),
    );

    const acc = new StreamPartsAccumulator();
    for await (const event of readSseJsonStream(res)) {
      if (event.type === "error") {
        throw new Error(event.message);
      }
      if (event.type === "final") {
        const content = acc.parts(event.reply);
        yield {
          kind: "final",
          content,
          result: {
            reply: event.reply,
            artifactMarkdown: event.artifact_markdown,
            draftId: event.draft_id ?? undefined,
            artifactRevision: event.artifact_revision ?? undefined,
            artifactHash: event.artifact_hash ?? undefined,
            readyToSave: event.ready,
            completeness: event.completeness ?? null,
            lastChangeSummary: event.last_change_summary ?? null,
            memoryCandidates: event.memory_candidates ?? undefined,
            memoryState: event.memory_state ?? null,
          },
        };
        return;
      }
      acc.apply(event);
      yield { kind: "progress", content: acc.parts() };
    }
    throw new Error("Stream ended without a final event");
  }

  if (mode === "ingest") {
    return {
      mode,
      classId,
      sessionId,
      draftId,
      artifactRevision,
      artifactHash,
      turnInProgress,
      latestTurnComplete,
      lessonDate,
      lessonTitle,
      initialMessages,
      initialMarkdown,
      initialCompleteness,
      initialMemoryState,
      onCompletenessChange,
      chatStream,
      patchDraft: async (markdown: string) => {
        const draft = await withSessionRecovery(getSessionId, onSessionLost, markdown, (sid) =>
          client.ingestUpdateDraft(classId, sid, markdown),
        );
        const ready = draft.completeness.items.every((i) => !i.required || i.complete);
        return {
          completeness: draft.completeness,
          readyToSave: ready,
          draftId: draft.draft_id,
          artifactRevision: draft.artifact_revision,
          artifactHash: draft.artifact_hash,
        };
      },
    };
  }

  return {
    mode,
    classId,
    sessionId,
    draftId,
    artifactRevision,
    artifactHash,
    turnInProgress,
    latestTurnComplete,
    lessonDate,
    lessonTitle,
    initialMessages,
    initialMarkdown,
    chatStream,
    patchDraft: async (markdown: string) => {
      const draft = await withSessionRecovery(getSessionId, onSessionLost, markdown, (sid) =>
        client.planUpdateDraft(classId, sid, markdown),
      );
      return {
        draftId: draft.draft_id,
        artifactRevision: draft.artifact_revision,
        artifactHash: draft.artifact_hash,
      };
    },
  };
}
