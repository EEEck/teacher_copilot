"use client";

import { useArtifactSession } from "@/components/assistant-ui/artifact-session-runtime";
import { MarkdownEditorPanel } from "@/components/klassenpilot/markdown-editor-panel";

export function ArtifactDraftPanel({
  title,
  placeholder,
  emptyPreviewFallback,
  updatingLabel = "Updating draft from chat…",
}: {
  title: string;
  placeholder: string;
  emptyPreviewFallback?: string;
  updatingLabel?: string;
}) {
  const {
    artifactMarkdown,
    setArtifactMarkdown,
    isUpdating,
    syncStatus,
    undo,
    redo,
    canUndo,
    canRedo,
  } = useArtifactSession();

  return (
    <MarkdownEditorPanel
      label={title}
      markdown={artifactMarkdown}
      onChange={(value) => setArtifactMarkdown(value, "manual")}
      placeholder={placeholder}
      emptyPreviewFallback={emptyPreviewFallback}
      isUpdating={isUpdating}
      updatingLabel={updatingLabel}
      syncStatus={syncStatus}
      showUndoRedo
      onUndo={undo}
      onRedo={redo}
      canUndo={canUndo}
      canRedo={canRedo}
    />
  );
}
