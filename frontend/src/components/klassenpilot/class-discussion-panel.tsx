"use client";

import { useCallback, useEffect, useState } from "react";

import { createArtifactRuntimeConfig } from "@/components/assistant-ui/artifact-runtime-config";
import { ArtifactSessionRuntimeProvider } from "@/components/assistant-ui/artifact-session-runtime";
import { DiscussThread } from "@/components/assistant-ui/discuss-thread";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { client, type ChatMessage } from "@/lib/api";
import { toWorkflowDraftSnapshot } from "@/features/workflow-drafts/workflow-draft-bootstrap";
import { useWorkflowDraftStore } from "@/features/workflow-drafts/workflow-draft-store";
import { workflowDraftRuntimeKey } from "@/features/workflow-drafts/workflow-draft-runtime-key";

type ClassDiscussionPanelProps = {
  classId: string;
};

type BootstrapState = {
  sessionId: string;
  draftId: string;
  artifactRevision: number;
  artifactHash: string;
  turnInProgress: boolean;
  latestTurnComplete: boolean;
  initialMessages: ChatMessage[];
};

export function ClassDiscussionPanel({ classId }: ClassDiscussionPanelProps) {
  const upsert = useWorkflowDraftStore((state) => state.upsert);
  const [boot, setBoot] = useState<BootstrapState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const bootstrap = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const session = await client.startDiscussionSession(classId);
      const draft = await client.discussionGetDraft(classId, session.session_id);
      const snapshot = toWorkflowDraftSnapshot("discuss", classId, {
        sessionId: session.session_id,
        draftId: draft.draft_id || session.draft_id,
        artifactRevision: draft.artifact_revision || session.artifact_revision,
        artifactHash: draft.artifact_hash || session.artifact_hash,
        turnInProgress: draft.turn_in_progress ?? session.turn_in_progress,
        latestTurnComplete:
          draft.latest_turn_complete ?? session.latest_turn_complete,
        initialMessages: draft.messages?.length ? draft.messages : session.messages,
        initialMarkdown: "",
      });
      if (!snapshot) {
        throw new Error("Discussion draft missing id");
      }
      upsert(snapshot);
      setBoot({
        sessionId: session.session_id,
        draftId: snapshot.draftId,
        artifactRevision: snapshot.artifactRevision,
        artifactHash: snapshot.artifactHash,
        turnInProgress: snapshot.turnInProgress,
        latestTurnComplete: snapshot.latestTurnComplete,
        initialMessages: snapshot.messages,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start discussion");
      setBoot(null);
    } finally {
      setLoading(false);
    }
  }, [classId, upsert]);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  if (loading) {
    return <p className="text-sm text-muted-foreground">Starting discussion…</p>;
  }

  if (error || !boot) {
    return (
      <Alert className="border-destructive/30 bg-[var(--error-bg)] text-destructive">
        <AlertDescription>{error ?? "Discussion unavailable."}</AlertDescription>
      </Alert>
    );
  }

  const config = createArtifactRuntimeConfig({
    mode: "discuss",
    classId,
    sessionId: boot.sessionId,
    draftId: boot.draftId,
    artifactRevision: boot.artifactRevision,
    artifactHash: boot.artifactHash,
    turnInProgress: boot.turnInProgress,
    latestTurnComplete: boot.latestTurnComplete,
    initialMessages: boot.initialMessages,
    initialMarkdown: "",
  });

  return (
    <div className="min-h-[420px] overflow-hidden rounded-lg border border-border">
      <ArtifactSessionRuntimeProvider
        key={workflowDraftRuntimeKey(boot.draftId, boot.sessionId)}
        config={config}
      >
        <DiscussThread />
      </ArtifactSessionRuntimeProvider>
    </div>
  );
}
