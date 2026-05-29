"use client";

import { useMemo, type ReactNode } from "react";
import {
  ArtifactSessionRuntimeProvider,
  useArtifactSession,
} from "@/components/assistant-ui/artifact-session-runtime";
import { client, type CompletenessChecklist } from "@/lib/api";

export function useIngestRuntime() {
  const ctx = useArtifactSession();
  return {
    ...ctx,
    diaryMarkdown: ctx.artifactMarkdown,
    setDiaryMarkdown: ctx.setArtifactMarkdown,
    readyToPropose: ctx.readyToSave,
  };
}

export function IngestRuntimeProvider({
  classId,
  sessionId,
  initialDiaryMarkdown,
  initialCompleteness,
  onCompletenessChange,
  children,
}: {
  classId: string;
  sessionId: string;
  initialDiaryMarkdown: string;
  initialCompleteness: CompletenessChecklist | null;
  onCompletenessChange?: (checklist: CompletenessChecklist) => void;
  children: ReactNode;
}) {
  const config = useMemo(
    () => ({
      classId,
      sessionId,
      initialMarkdown: initialDiaryMarkdown,
      initialCompleteness,
      onCompletenessChange,
      chat: async ({
        message,
        currentMarkdown,
        attachments,
      }: {
        message: string;
        currentMarkdown: string;
        attachments?: { filename: string; content: string }[];
      }) => {
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
    }),
    [classId, sessionId, initialDiaryMarkdown, initialCompleteness, onCompletenessChange],
  );

  return (
    <ArtifactSessionRuntimeProvider config={config}>{children}</ArtifactSessionRuntimeProvider>
  );
}
