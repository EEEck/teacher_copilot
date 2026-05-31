"use client";

import { MarkdownEditorPanel } from "@/components/klassenpilot/markdown-editor-panel";
import { Button } from "@/components/ui/button";
import { shortWikiPath } from "@/lib/markdown-diff";

export function WikiProposalEditor({
  wikiPath,
  markdown,
  onChange,
  onBackToDiary,
}: {
  wikiPath: string;
  markdown: string;
  onChange: (value: string) => void;
  onBackToDiary: () => void;
}) {
  return (
    <div className="flex h-full min-h-0 flex-col gap-2">
      <div className="flex shrink-0 justify-end">
        <Button type="button" variant="ghost" size="sm" className="h-7 text-xs" onClick={onBackToDiary}>
          Back to diary
        </Button>
      </div>
      <div className="min-h-0 flex-1">
        <MarkdownEditorPanel
          label={shortWikiPath(wikiPath)}
          markdown={markdown}
          onChange={onChange}
          placeholder="(empty)"
          className="h-full"
        />
      </div>
    </div>
  );
}
