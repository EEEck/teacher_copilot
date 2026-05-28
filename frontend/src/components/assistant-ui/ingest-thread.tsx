"use client";

import { Thread } from "@/components/assistant-ui/thread";
import { useIngestRuntime } from "@/components/assistant-ui/ingest-runtime-provider";
import { DiaryChecklist } from "@/components/klassenpilot/diary-checklist";

function IngestWelcomeChecklist() {
  const { completeness } = useIngestRuntime();
  return <DiaryChecklist checklist={completeness} inline />;
}

export function IngestThread() {
  return <Thread welcomeExtra={<IngestWelcomeChecklist />} />;
}
