import type { ArtifactMode } from "@/components/assistant-ui/artifact-runtime-config";
import type { ChatMessage } from "@/lib/api";

import type { WorkflowDraftSnapshot } from "./workflow-draft-store";

export type WorkflowDraftBootstrap = {
  sessionId: string;
  draftId?: string;
  artifactRevision?: number;
  artifactHash?: string;
  turnInProgress?: boolean;
  latestTurnComplete?: boolean;
  initialMessages?: ChatMessage[];
  initialMarkdown: string;
};

export function toWorkflowDraftSnapshot(
  mode: ArtifactMode,
  classId: string,
  bootstrap: WorkflowDraftBootstrap,
): WorkflowDraftSnapshot | null {
  if (!bootstrap.draftId) return null;
  return {
    mode,
    classId,
    draftId: bootstrap.draftId,
    sessionId: bootstrap.sessionId,
    messages: bootstrap.initialMessages ?? [],
    artifactMarkdown: bootstrap.initialMarkdown,
    artifactRevision: bootstrap.artifactRevision ?? 0,
    artifactHash: bootstrap.artifactHash ?? "",
    turnInProgress: bootstrap.turnInProgress ?? false,
    latestTurnComplete: bootstrap.latestTurnComplete ?? true,
  };
}
