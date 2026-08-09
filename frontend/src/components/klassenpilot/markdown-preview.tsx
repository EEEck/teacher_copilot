"use client";

import "@assistant-ui/react-markdown/styles/dot.css";

import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { assistantUiMarkdownComponents } from "@/components/assistant-ui/markdown-components";
import {
  resolveMaterialAssetSrc,
  type MaterialAssetContext,
} from "@/lib/material-asset-urls";
import {
  resolveWikiMarkdownHref,
  wikiViewerHref,
} from "@/lib/wiki-viewer-links";

type MarkdownPreviewProps = {
  markdown: string;
  /** When set with currentWikiPath, wiki-relative links open in the inspector. */
  classId?: string;
  currentWikiPath?: string;
  /** Plan-session OCR cutouts: rewrite `assets/img-*` to the materials API. */
  materialAssets?: MaterialAssetContext | null;
};

export function MarkdownPreview({
  markdown,
  classId,
  currentWikiPath,
  materialAssets,
}: MarkdownPreviewProps) {
  // Local overrides (img asset rewrite / wiki links) sit outside the registry typings.
  const components: Record<string, unknown> = {
    ...assistantUiMarkdownComponents,
  };
  if (materialAssets) {
    components.img = (props: React.ComponentProps<"img">) => {
      const { src, alt, ...rest } = props;
      const resolved = resolveMaterialAssetSrc(
        typeof src === "string" ? src : undefined,
        materialAssets,
      );
      return (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={resolved} alt={alt ?? ""} className="max-w-full h-auto" {...rest} />
      );
    };
  }
  if (classId && currentWikiPath) {
    components.a = ({ href, children, className, ...props }: React.ComponentProps<"a">) => {
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
    };
  }

  return (
    <div className="aui-md max-w-full overflow-hidden wrap-break-word text-foreground">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={components as typeof assistantUiMarkdownComponents}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
