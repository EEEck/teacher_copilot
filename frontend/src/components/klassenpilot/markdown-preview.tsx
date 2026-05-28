"use client";

import "@assistant-ui/react-markdown/styles/dot.css";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { assistantUiMarkdownComponents } from "@/components/assistant-ui/markdown-components";

export function MarkdownPreview({ markdown }: { markdown: string }) {
  return (
    <div className="aui-md text-foreground">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={assistantUiMarkdownComponents}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
