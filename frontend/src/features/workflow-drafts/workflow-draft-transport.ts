import type { ArtifactMode } from "@/components/assistant-ui/artifact-runtime-config";
import type { DiscussDraft, IngestDraft, PlanDraft } from "@/lib/api";

import type { WorkflowDraftSnapshot } from "./workflow-draft-store";

export function fetchedDraftToSnapshot(
  mode: ArtifactMode,
  classId: string,
  sessionId: string,
  draft: IngestDraft | PlanDraft | DiscussDraft,
): WorkflowDraftSnapshot {
  const artifactMarkdown =
    mode === "ingest"
      ? (draft as IngestDraft).diary_markdown
      : mode === "plan"
        ? (draft as PlanDraft).plan_markdown
        : ((draft as DiscussDraft).artifact_markdown ?? "");
  const ingest = mode === "ingest" ? (draft as IngestDraft) : null;
  return {
    mode,
    classId,
    sessionId,
    draftId: draft.draft_id,
    messages: draft.messages ?? [],
    artifactMarkdown,
    artifactRevision: draft.artifact_revision,
    artifactHash: draft.artifact_hash,
    turnInProgress: draft.turn_in_progress ?? false,
    latestTurnComplete: draft.latest_turn_complete ?? true,
    completeness: ingest?.completeness ?? null,
    memoryState: ingest?.memory_state ?? null,
  };
}
