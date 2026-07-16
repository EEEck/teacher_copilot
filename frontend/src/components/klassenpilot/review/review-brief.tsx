"use client";

import {
  ChevronDownIcon,
  LoaderCircleIcon,
  MinusIcon,
  PencilLineIcon,
  PlusIcon,
  SquarePenIcon,
  Undo2Icon,
} from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { briefFromChanges, briefLessonDate, type BriefEntry } from "@/lib/review-brief";
import { FileChangeReviewPanel } from "./file-change-review-panel";
import { MarkdownLineDiff } from "./markdown-line-diff";
import { ReviewChrome } from "./review-chrome";
import type { FileChange } from "./types";

const SECTION_TITLES: Record<BriefEntry["category"], string> = {
  new: "New",
  updated: "Updated",
  removed: "Rewritten",
};

const SECTION_ORDER: BriefEntry["category"][] = ["new", "updated", "removed"];

const CATEGORY_ICONS: Record<BriefEntry["category"], typeof PlusIcon> = {
  new: PlusIcon,
  updated: PencilLineIcon,
  removed: MinusIcon,
};

function BriefItemRow({
  entry,
  item,
  expanded,
  disabled,
  onToggleView,
  onSetApproved,
  onEdit,
}: {
  entry: BriefEntry;
  item: FileChange | undefined;
  expanded: boolean;
  disabled?: boolean;
  onToggleView: () => void;
  onSetApproved: (approved: boolean) => void;
  onEdit?: () => void;
}) {
  const Icon = CATEGORY_ICONS[entry.category];
  return (
    <li
      className={
        "rounded-md border border-transparent px-2 py-1.5 " +
        (entry.approved ? "" : "opacity-55")
      }
    >
      <div className="flex items-center gap-2">
        <Icon className="size-3.5 shrink-0 text-muted-foreground" />
        <button
          type="button"
          onClick={onToggleView}
          className="min-w-0 flex-1 truncate text-left text-sm hover:underline"
          title="Show what changes"
        >
          <span className={entry.approved ? "font-medium" : "font-medium line-through"}>
            {entry.label}
          </span>
          {entry.summary && (
            <span className="ml-2 font-normal text-muted-foreground">{entry.summary}</span>
          )}
        </button>
        <div className="flex shrink-0 items-center gap-1 text-xs">
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground"
            onClick={onToggleView}
            disabled={disabled}
          >
            {expanded ? "hide" : "view"}
          </button>
          {entry.approved ? (
            <button
              type="button"
              className="text-muted-foreground hover:text-destructive disabled:opacity-40"
              onClick={() => onSetApproved(false)}
              disabled={disabled || entry.required}
              title={
                entry.required
                  ? "The lesson results are required to save memory"
                  : "Don't save this change"
              }
            >
              skip
            </button>
          ) : (
            <button
              type="button"
              className="inline-flex items-center gap-0.5 text-primary hover:underline"
              onClick={() => onSetApproved(true)}
              disabled={disabled}
              title="Save this change again"
            >
              <Undo2Icon className="size-3" /> undo
            </button>
          )}
        </div>
      </div>
      {expanded && item && (
        <div className="mt-2 space-y-2 pl-5">
          <MarkdownLineDiff
            path={item.path}
            before={item.before}
            after={item.after}
            className="max-h-56"
          />
          {onEdit && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={onEdit}
              disabled={disabled}
            >
              <SquarePenIcon className="size-3" /> Edit this text
            </Button>
          )}
        </div>
      )}
    </li>
  );
}

/**
 * Teacher-first review surface: a plain-language brief of what gets saved,
 * grouped into New / Updated / Removed, with one-click save, per-item skip,
 * inline detail on demand, and the full technical file list behind a
 * collapsible. Approval state and the commit path are owned by the caller
 * (useFileChangeReview) — this is a presentation layer only.
 */
export function ReviewBrief({
  items,
  selectedPath,
  title = "Save lesson memory",
  onSelectPath,
  onSetApproved,
  onUndoAll,
  onKeepAll,
  onSave,
  saving,
  actionsDisabled,
  saveDisabled,
}: {
  items: FileChange[];
  selectedPath: string | null;
  title?: string;
  /** When provided, expanded items offer "Edit this text" via this callback. */
  onSelectPath?: (path: string) => void;
  onSetApproved: (path: string, approved: boolean) => void;
  onUndoAll: () => void;
  onKeepAll: () => void;
  onSave: () => void;
  saving?: boolean;
  actionsDisabled?: boolean;
  saveDisabled?: boolean;
}) {
  const entries = useMemo(() => briefFromChanges(items), [items]);
  const lessonDate = useMemo(() => briefLessonDate(items), [items]);
  const [expandedPath, setExpandedPath] = useState<string | null>(null);

  const itemsByPath = useMemo(
    () => Object.fromEntries(items.map((i) => [i.path, i])),
    [items],
  );
  const approvedCount = entries.filter((e) => e.approved).length;

  const setEntryApproved = (entry: BriefEntry, approved: boolean) => {
    for (const path of entry.paths) onSetApproved(path, approved);
  };

  return (
    <ReviewChrome>
      <div className="flex items-center justify-between gap-2 border-b border-border/60 px-3 py-2">
        <div className="min-w-0 text-sm font-medium">
          {title}
          {lessonDate ? ` — ${lessonDate}` : ""}
          <span className="ml-2 font-normal text-muted-foreground">
            {approvedCount} of {entries.length} changes selected
          </span>
        </div>
        <div className="flex shrink-0 items-center gap-2 text-xs">
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground"
            onClick={onUndoAll}
            disabled={actionsDisabled}
          >
            Cancel
          </button>
          <Button
            type="button"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={onSave}
            disabled={saving || saveDisabled}
          >
            {saving ? (
              <>
                <LoaderCircleIcon className="animate-spin" />
                Saving…
              </>
            ) : (
              `Save ${approvedCount === entries.length ? "all" : "selected"} (${approvedCount})`
            )}
          </Button>
        </div>
      </div>

      <div className="space-y-3 px-3 py-2">
        {SECTION_ORDER.map((category) => {
          const sectionEntries = entries.filter((e) => e.category === category);
          if (sectionEntries.length === 0) return null;
          return (
            <div key={category}>
              <div className="mb-0.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                {SECTION_TITLES[category]}
              </div>
              <ul>
                {sectionEntries.map((entry) => (
                  <BriefItemRow
                    key={entry.path}
                    entry={entry}
                    item={itemsByPath[entry.path]}
                    expanded={expandedPath === entry.path}
                    disabled={actionsDisabled}
                    onToggleView={() =>
                      setExpandedPath((prev) => (prev === entry.path ? null : entry.path))
                    }
                    onSetApproved={(approved) => setEntryApproved(entry, approved)}
                    onEdit={onSelectPath ? () => onSelectPath(entry.path) : undefined}
                  />
                ))}
              </ul>
            </div>
          );
        })}
      </div>

      <Collapsible>
        <CollapsibleTrigger className="flex w-full items-center gap-1 border-t border-border/60 px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground [&[data-state=open]>svg]:rotate-180">
          <ChevronDownIcon className="size-3.5 transition-transform" />
          Show technical details (file list &amp; line diffs)
        </CollapsibleTrigger>
        <CollapsibleContent className="px-2 pb-2">
          <FileChangeReviewPanel
            items={items}
            selectedPath={selectedPath}
            onSelectPath={onSelectPath ?? (() => {})}
            onSetApproved={onSetApproved}
            onUndoAll={onUndoAll}
            onKeepAll={onKeepAll}
            onSave={onSave}
            saving={saving}
            actionsDisabled={actionsDisabled}
            saveDisabled={saveDisabled}
            saveLabel="Save selected files"
          />
        </CollapsibleContent>
      </Collapsible>
    </ReviewChrome>
  );
}
