"use client";

import { MarkdownEditorPanel } from "@/components/klassenpilot/markdown-editor-panel";

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
  return (
    <MarkdownEditorPanel
      label={label}
      markdown={markdown}
      onChange={onChange}
      readOnly={readOnly}
      className="min-h-[320px]"
      emptyPreviewFallback="_Nothing yet._"
    />
  );
}
