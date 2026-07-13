"use client";

import "@assistant-ui/react-markdown/styles/dot.css";

import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { assistantUiMarkdownComponents } from "@/components/assistant-ui/markdown-components";
import {
  resolveWikiMarkdownHref,
  wikiViewerHref,
} from "@/lib/wiki-viewer-links";

type MarkdownPreviewProps = {
  markdown: string;
  /** When set with currentWikiPath, wiki-relative links open in the inspector. */
  classId?: string;
  currentWikiPath?: string;
};

export function MarkdownPreview({
  markdown,
  classId,
  currentWikiPath,
}: MarkdownPreviewProps) {
  const components =
    classId && currentWikiPath
      ? {
          ...assistantUiMarkdownComponents,
          a: ({ href, children, className, ...props }: React.ComponentProps<"a">) => {
            const wikiPath = resolveWikiMarkdownHref(
              classId,
              href,
              currentWikiPath,
            );
            if (wikiPath) {
              return (
                <Link
                  href={wikiViewerHref(classId, wikiPath)}
                  className={className ?? "text-primary underline"}
                >
                  {children}
                </Link>
              );
            }
            return (
              <a
                href={href}
                className={className}
                {...props}
                {...(href && /^(https?:)/i.test(href)
                  ? { target: "_blank", rel: "noreferrer" }
                  : {})}
              >
                {children}
              </a>
            );
          },
        }
      : assistantUiMarkdownComponents;

  return (
    <div className="aui-md max-w-full overflow-hidden wrap-break-word text-foreground">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
