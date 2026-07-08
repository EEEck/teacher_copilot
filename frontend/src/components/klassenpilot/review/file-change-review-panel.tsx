"use client";

import { ChevronDownIcon } from "lucide-react";
import { useMemo } from "react";

import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ItemGroup } from "@/components/ui/item";
import { FileChangeRow } from "./file-change-row";
import { ReviewChrome } from "./review-chrome";
import type { FileChange } from "./types";

export function FileChangeReviewPanel({
  items,
  selectedPath,
  onSelectPath,
  onSetApproved,
  onUndoAll,
  onKeepAll,
  onSave,
  saving,
  actionsDisabled,
  saveDisabled,
  saveLabel = "Save changes",
  defaultOpen = true,
}: {
  items: FileChange[];
  selectedPath: string | null;
  onSelectPath: (path: string) => void;
  onSetApproved: (path: string, approved: boolean) => void;
  onUndoAll: () => void;
  onKeepAll: () => void;
  onSave: () => void;
  saving?: boolean;
  actionsDisabled?: boolean;
  saveDisabled?: boolean;
  saveLabel?: string;
  defaultOpen?: boolean;
}) {
  const approvedCount = useMemo(() => items.filter((i) => i.approved).length, [items]);

  return (
    <ReviewChrome>
      <Collapsible defaultOpen={defaultOpen}>
        <div className="flex items-center justify-between gap-2 border-b border-border/60 px-3 py-2">
          <CollapsibleTrigger className="flex min-w-0 flex-1 items-center gap-1 text-sm font-medium text-foreground [&[data-state=open]>svg]:rotate-180">
            <ChevronDownIcon className="size-4 shrink-0 text-muted-foreground transition-transform" />
            <span>
              {items.length} {items.length === 1 ? "file" : "files"}
            </span>
            <span className="font-normal text-muted-foreground">· {approvedCount} to save</span>
          </CollapsibleTrigger>
          <div className="flex shrink-0 items-center gap-2 text-xs">
            <button
              type="button"
              className="text-muted-foreground hover:text-foreground"
              onClick={onUndoAll}
              disabled={actionsDisabled}
            >
              Undo all
            </button>
            <button
              type="button"
              className="text-muted-foreground hover:text-foreground"
              onClick={onKeepAll}
              disabled={actionsDisabled}
            >
              Keep all
            </button>
            <Button
              type="button"
              variant="default"
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={onSave}
              disabled={saving || saveDisabled}
            >
              {saving ? "Saving…" : saveLabel}
            </Button>
          </div>
        </div>
        <CollapsibleContent>
          <ItemGroup className="max-h-48 gap-0 overflow-auto py-0">
            {items.map((item) => (
              <FileChangeRow
                key={item.path}
                item={item}
                selected={selectedPath === item.path}
                onSelect={() => onSelectPath(item.path)}
                onSetApproved={(approved) => onSetApproved(item.path, approved)}
              />
            ))}
          </ItemGroup>
        </CollapsibleContent>
      </Collapsible>
    </ReviewChrome>
  );
}
