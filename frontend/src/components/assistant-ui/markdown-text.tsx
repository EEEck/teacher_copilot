"use client";

import "@assistant-ui/react-markdown/styles/dot.css";

import { MarkdownTextPrimitive } from "@assistant-ui/react-markdown";
import remarkGfm from "remark-gfm";
import { memo } from "react";

import { assistantUiMarkdownComponents } from "@/components/assistant-ui/markdown-components";

const MarkdownTextImpl = () => {
  return (
    <MarkdownTextPrimitive
      remarkPlugins={[remarkGfm]}
      className="aui-md"
      components={assistantUiMarkdownComponents}
    />
  );
};

export const MarkdownText = memo(MarkdownTextImpl);
