"use client";

import { Undo2, Redo2 } from "lucide-react";
import { useState } from "react";
import { useIngestRuntime } from "@/components/assistant-ui/ingest-runtime-provider";
import { MarkdownPreview } from "@/components/klassenpilot/markdown-preview";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

type ViewMode = "edit" | "preview";

export function DiaryDraftPanel() {
  const {
    diaryMarkdown,
    setDiaryMarkdown,
    isUpdating,
    syncStatus,
    undo,
    redo,
    canUndo,
    canRedo,
  } = useIngestRuntime();

  const [viewMode, setViewMode] = useState<ViewMode>("preview");

  return (
    <div className="flex h-full flex-col gap-2">
      <div className="flex shrink-0 items-center justify-between">
        <p className="text-sm font-medium">Lesson diary</p>
        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-8"
            onClick={undo}
            disabled={!canUndo}
            aria-label="Undo"
          >
            <Undo2 className="size-4" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-8"
            onClick={redo}
            disabled={!canRedo}
            aria-label="Redo"
          >
            <Redo2 className="size-4" />
          </Button>
          <div className="ml-1 flex rounded-md border border-border p-0.5">
            <button
              type="button"
              className={cn(
                "rounded px-2 py-0.5 text-xs",
                viewMode === "preview" ? "bg-muted font-medium text-foreground" : "text-muted-foreground",
              )}
              onClick={() => setViewMode("preview")}
            >
              Preview
            </button>
            <button
              type="button"
              className={cn(
                "rounded px-2 py-0.5 text-xs",
                viewMode === "edit" ? "bg-muted font-medium text-foreground" : "text-muted-foreground",
              )}
              onClick={() => setViewMode("edit")}
            >
              Edit
            </button>
          </div>
        </div>
      </div>

      {isUpdating && (
        <p className="shrink-0 text-xs text-muted-foreground">Updating draft from chat…</p>
      )}
      {!isUpdating && syncStatus === "saving" && (
        <p className="shrink-0 text-xs text-muted-foreground">Saving…</p>
      )}

      {viewMode === "edit" ? (
        <Textarea
          className="min-h-0 flex-1 resize-none font-mono text-sm"
          value={diaryMarkdown}
          onChange={(e) => setDiaryMarkdown(e.target.value, "manual")}
          placeholder="Your lesson summary will appear here as you chat, or type directly…"
          aria-label="Lesson diary markdown"
        />
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto rounded-md border bg-background p-3">
          <MarkdownPreview markdown={diaryMarkdown} />
        </div>
      )}
    </div>
  );
}
