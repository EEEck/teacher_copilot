"use client";

import { Redo2, Undo2 } from "lucide-react";
import { useState, type ReactNode } from "react";

import { MarkdownPreview } from "@/components/klassenpilot/markdown-preview";
import { Button } from "@/components/ui/button";
import { SegmentedToggle } from "@/components/ui/segmented-toggle";
import { Textarea } from "@/components/ui/textarea";
import type { MaterialAssetContext } from "@/lib/material-asset-urls";
import { cn } from "@/lib/utils";

type ViewMode = "edit" | "preview" | (string & {});

export type MarkdownEditorExtraView = {
  value: string;
  label: string;
  content: ReactNode;
};

export type MarkdownEditorPanelProps = {
  label: string;
  markdown: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  /** Shown in preview when markdown is empty; omit for artifact drafts (empty preview). */
  emptyPreviewFallback?: string;
  readOnly?: boolean;
  className?: string;
  isUpdating?: boolean;
  updatingLabel?: string;
  syncStatus?: "idle" | "saving" | "error";
  showUndoRedo?: boolean;
  onUndo?: () => void;
  onRedo?: () => void;
  canUndo?: boolean;
  canRedo?: boolean;
  /** Optional dismiss control (e.g. close wiki proposal → lesson diary). */
  onDismiss?: () => void;
  dismissAriaLabel?: string;
  materialAssets?: MaterialAssetContext | null;
  extraViews?: MarkdownEditorExtraView[];
};

export function MarkdownEditorPanel({
  label,
  markdown,
  onChange,
  placeholder,
  emptyPreviewFallback,
  readOnly = false,
  className,
  isUpdating = false,
  updatingLabel = "Updating draft from chat…",
  syncStatus = "idle",
  showUndoRedo = false,
  onUndo,
  onRedo,
  canUndo = false,
  canRedo = false,
  onDismiss,
  dismissAriaLabel = "Dismiss",
  materialAssets,
  extraViews = [],
}: MarkdownEditorPanelProps) {
  const [viewMode, setViewMode] = useState<ViewMode>("preview");
  const editable = !readOnly && Boolean(onChange);
  const extra = extraViews.find((view) => view.value === viewMode);
  const showToggle = editable || extraViews.length > 0;

  const previewMarkdown =
    markdown.trim() !== ""
      ? markdown
      : (emptyPreviewFallback ?? "");

  return (
    <div
      className={cn(
        "flex h-full min-h-0 w-full min-w-0 flex-1 basis-0 flex-col gap-2 overflow-hidden",
        className,
      )}
    >
      <div className="flex shrink-0 items-center justify-between gap-2">
        <p className="min-w-0 flex-1 truncate text-sm font-medium">{label}</p>
        <div className="flex shrink-0 items-center gap-1">
          {showUndoRedo && (
            <>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-8"
                onClick={onUndo}
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
                onClick={onRedo}
                disabled={!canRedo}
                aria-label="Redo"
              >
                <Redo2 className="size-4" />
              </Button>
            </>
          )}
          {showToggle && (
            <SegmentedToggle
              className={showUndoRedo ? "ml-1" : undefined}
              value={viewMode}
              onValueChange={(v) => setViewMode(v as ViewMode)}
              size="sm"
              aria-label="View mode"
              options={[
                { value: "preview", label: "Preview" },
                ...(editable ? [{ value: "edit", label: "Edit" }] : []),
                ...extraViews.map((view) => ({
                  value: view.value,
                  label: view.label,
                })),
              ]}
            />
          )}
          {onDismiss && (
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label={dismissAriaLabel}
              className="shrink-0 text-base leading-none text-muted-foreground hover:text-foreground"
              onClick={onDismiss}
            >
              ×
            </Button>
          )}
        </div>
      </div>

      {isUpdating && (
        <p className="shrink-0 text-xs text-muted-foreground">{updatingLabel}</p>
      )}
      {!isUpdating && syncStatus === "saving" && (
        <p className="shrink-0 text-xs text-muted-foreground">Saving…</p>
      )}
      {!isUpdating && syncStatus === "error" && (
        <p className="shrink-0 text-xs text-destructive">
          Couldn&apos;t sync your edits — they&apos;re kept locally; keep typing or retry.
        </p>
      )}

      {extra ? (
        extra.content
      ) : editable && viewMode === "edit" ? (
        <Textarea
          className="min-h-0 w-full flex-1 basis-0 resize-none overflow-y-auto overscroll-contain [field-sizing:fixed] font-mono text-sm"
          value={markdown}
          onChange={(e) => onChange?.(e.target.value)}
          placeholder={placeholder}
          aria-label={`${label} markdown`}
        />
      ) : (
        <div className="min-h-0 max-h-full w-full min-w-0 flex-1 basis-0 overflow-y-auto overscroll-contain rounded-md border bg-background p-3">
          <MarkdownPreview
            markdown={previewMarkdown}
            materialAssets={materialAssets}
          />
        </div>
      )}
    </div>
  );
}
