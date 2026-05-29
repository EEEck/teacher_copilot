"use client";

import { useMemo, type ReactNode } from "react";
import { ArtifactSessionRuntimeProvider } from "@/components/assistant-ui/artifact-session-runtime";
import { client } from "@/lib/api";

export function PlanRuntimeProvider({
  classId,
  sessionId,
  initialPlanMarkdown,
  children,
}: {
  classId: string;
  sessionId: string;
  initialPlanMarkdown: string;
  children: ReactNode;
}) {
  const config = useMemo(
    () => ({
      classId,
      sessionId,
      initialMarkdown: initialPlanMarkdown,
      chat: async ({
        message,
        currentMarkdown,
        attachments,
      }: {
        message: string;
        currentMarkdown: string;
        attachments?: { filename: string; content: string }[];
      }) => {
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
    }),
    [classId, sessionId, initialPlanMarkdown],
  );

  return (
    <ArtifactSessionRuntimeProvider config={config}>{children}</ArtifactSessionRuntimeProvider>
  );
}
