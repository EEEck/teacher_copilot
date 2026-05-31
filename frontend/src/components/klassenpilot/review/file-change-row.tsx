"use client";

import { Check, FileText, X } from "lucide-react";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import {
  Item,
  ItemActions,
  ItemContent,
  ItemMedia,
  ItemTitle,
} from "@/components/ui/item";
import { diffLineStats, shortWikiPath } from "@/lib/markdown-diff";
import { cn } from "@/lib/utils";
import type { FileChange } from "./types";

export function FileChangeRow({
  item,
  selected,
  onSelect,
  onSetApproved,
}: {
  item: FileChange;
  selected: boolean;
  onSelect: () => void;
  onSetApproved: (approved: boolean) => void;
}) {
  const stats = diffLineStats(item.before, item.after);

  return (
    <Item
      variant={selected ? "muted" : "default"}
      size="xs"
      className={cn("cursor-pointer rounded-none border-0", selected && "bg-muted")}
      onClick={onSelect}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect();
        }
      }}
    >
      <ItemMedia variant="icon">
        <FileText className="text-primary" />
      </ItemMedia>
      <ItemContent>
        <ItemTitle className="font-mono text-xs font-normal" title={item.path}>
          {shortWikiPath(item.path)}
        </ItemTitle>
      </ItemContent>
      <span className="shrink-0 font-mono text-xs text-muted-foreground">
        {stats.added > 0 && <span className="text-primary">+{stats.added}</span>}
        {stats.removed > 0 && (
          <span className={stats.added > 0 ? " ml-1 text-destructive" : "text-destructive"}>
            −{stats.removed}
          </span>
        )}
        {stats.added === 0 && stats.removed === 0 && (
          <span className="text-muted-foreground">±0</span>
        )}
      </span>
      <ItemActions>
        <div className="flex items-center" onClick={(e) => e.stopPropagation()}>
          <TooltipIconButton
            tooltip="Reject this file"
            variant="ghost"
            className={cn(!item.approved && "text-destructive")}
            disabled={item.required && item.approved}
            onClick={() => onSetApproved(false)}
          >
            <X className="size-4" />
          </TooltipIconButton>
          <TooltipIconButton
            tooltip="Keep this file"
            variant="ghost"
            className={cn(item.approved && "text-primary")}
            onClick={() => onSetApproved(true)}
          >
            <Check className="size-4" />
          </TooltipIconButton>
        </div>
      </ItemActions>
    </Item>
  );
}
