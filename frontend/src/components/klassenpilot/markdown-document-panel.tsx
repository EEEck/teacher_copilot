"use client";

import { useState } from "react";

import { MarkdownPreview } from "@/components/klassenpilot/markdown-preview";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

type ViewMode = "edit" | "preview";

export function MarkdownDocumentPanel({
  markdown,
  onChange,
  label,
  readOnly = false,
}: {
  markdown: string;
  onChange?: (value: string) => void;
  label: string;
  readOnly?: boolean;
}) {
  const [viewMode, setViewMode] = useState<ViewMode>("preview");

  return (
    <div className="flex h-full min-h-[320px] flex-col gap-2">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">{label}</p>
        {!readOnly && (
          <div className="flex rounded-md border border-border p-0.5">
            <button
              type="button"
              className={cn(
                "rounded px-2 py-0.5 text-xs",
                viewMode === "preview"
                  ? "bg-muted font-medium text-foreground"
                  : "text-muted-foreground",
              )}
              onClick={() => setViewMode("preview")}
            >
              Preview
            </button>
            <button
              type="button"
              className={cn(
                "rounded px-2 py-0.5 text-xs",
                viewMode === "edit"
                  ? "bg-muted font-medium text-foreground"
                  : "text-muted-foreground",
              )}
              onClick={() => setViewMode("edit")}
            >
              Edit
            </button>
          </div>
        )}
      </div>
      {readOnly || viewMode === "preview" ? (
        <div className="min-h-0 flex-1 overflow-y-auto rounded-md border bg-background p-3">
          <MarkdownPreview markdown={markdown || "_Nothing yet._"} />
        </div>
      ) : (
        <Textarea
          className="min-h-0 flex-1 resize-none font-mono text-sm"
          value={markdown}
          onChange={(e) => onChange?.(e.target.value)}
          aria-label={label}
        />
      )}
    </div>
  );
}
