"use client";

import { ArtifactDraftPanel } from "@/components/klassenpilot/artifact-draft-panel";

export function DiaryDraftPanel() {
  return (
    <ArtifactDraftPanel
      title="Lesson diary"
      placeholder="Your lesson summary will appear here as you chat, or type directly…"
    />
  );
}
