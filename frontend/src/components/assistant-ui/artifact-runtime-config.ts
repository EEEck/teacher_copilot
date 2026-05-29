import type { ArtifactSessionConfig } from "@/components/assistant-ui/artifact-session-runtime";
import { client, type CompletenessChecklist } from "@/lib/api";

export type ArtifactMode = "ingest" | "plan";

/**
 * Builds the per-mode runtime config consumed by ArtifactSessionRuntimeProvider.
 * Replaces the old PlanRuntimeProvider / IngestRuntimeProvider wrappers — adding
 * a new artifact mode means adding a branch here, not a new provider component.
 */
export function createArtifactRuntimeConfig(args: {
  mode: ArtifactMode;
  classId: string;
  sessionId: string;
  initialMarkdown: string;
  initialCompleteness?: CompletenessChecklist | null;
  onCompletenessChange?: (checklist: CompletenessChecklist) => void;
}): ArtifactSessionConfig {
  const {
    mode,
    classId,
    sessionId,
    initialMarkdown,
    initialCompleteness = null,
    onCompletenessChange,
  } = args;

  if (mode === "ingest") {
    return {
      classId,
      sessionId,
      initialMarkdown,
      initialCompleteness,
      onCompletenessChange,
      chat: async ({ message, currentMarkdown, attachments }) => {
        const res = await client.ingestChat(
          classId,
          sessionId,
          message,
          currentMarkdown,
          attachments,
        );
        return {
          reply: res.reply,
          artifactMarkdown: res.diary_markdown,
          completeness: res.completeness,
          readyToSave: res.ready_to_propose,
        };
      },
      patchDraft: async (markdown: string) => {
        const draft = await client.ingestUpdateDraft(classId, sessionId, markdown);
        const ready = draft.completeness.items.every((i) => !i.required || i.complete);
        return { completeness: draft.completeness, readyToSave: ready };
      },
    };
  }

  return {
    classId,
    sessionId,
    initialMarkdown,
    chat: async ({ message, currentMarkdown, attachments }) => {
      const res = await client.planChat(
        classId,
        sessionId,
        message,
        currentMarkdown,
        attachments,
      );
      return {
        reply: res.reply,
        artifactMarkdown: res.plan_markdown,
        readyToSave: res.ready_to_save,
      };
    },
    patchDraft: async (markdown: string) => {
      await client.planUpdateDraft(classId, sessionId, markdown);
      return {};
    },
  };
}
