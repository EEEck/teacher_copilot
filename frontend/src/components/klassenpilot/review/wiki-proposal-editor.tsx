"use client";

import { MarkdownEditorPanel } from "@/components/klassenpilot/markdown-editor-panel";
import { shortWikiPath } from "@/lib/markdown-diff";

export function WikiProposalEditor({
  wikiPath,
  markdown,
  onChange,
}: {
  wikiPath: string;
  markdown: string;
  onChange: (value: string) => void;
}) {
  return (
    <MarkdownEditorPanel
      label={shortWikiPath(wikiPath)}
      markdown={markdown}
      onChange={onChange}
      placeholder="(empty)"
      className="h-full"
    />
  );
}
