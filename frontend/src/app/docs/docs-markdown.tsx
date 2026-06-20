import React from "react";
import Link from "next/link";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { DocsCallout } from "@/components/docs/docs-callout";
import { splitDocsMarkdown, normalizeMarkdownNewlines } from "@/lib/docs/markdown";
import { slugify } from "@/lib/docs/registry";

function childrenToText(children: React.ReactNode): string {
  if (typeof children === "string") return children;
  if (typeof children === "number") return String(children);
  if (Array.isArray(children)) return children.map(childrenToText).join("");
  if (React.isValidElement<{ children?: React.ReactNode }>(children)) {
    return childrenToText(children.props.children);
  }
  return "";
}

const proseComponents: Components = {
  h1: () => null,
  h2: ({ children }) => {
    const text = childrenToText(children);
    return (
      <h2
        id={slugify(text)}
        className="scroll-mt-24 border-t border-dashed border-primary/20 pt-8 text-2xl font-semibold tracking-tight first:border-t-0 first:pt-0"
      >
        {children}
      </h2>
    );
  },
  h3: ({ children }) => {
    const text = childrenToText(children);
    return (
      <h3
        id={slugify(text)}
        className="scroll-mt-24 pt-4 text-lg font-semibold tracking-tight"
      >
        {children}
      </h3>
    );
  },
  p: ({ children }) => <p className="leading-7 text-foreground">{children}</p>,
  ul: ({ children }) => (
    <ul className="ml-5 list-disc space-y-2 leading-7">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="ml-5 list-decimal space-y-2 leading-7">{children}</ol>
  ),
  li: ({ children }) => <li className="pl-1">{children}</li>,
  strong: ({ children }) => (
    <strong className="font-semibold text-foreground">{children}</strong>
  ),
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-primary/40 pl-4 italic text-muted-foreground">
      {children}
    </blockquote>
  ),
  a: ({ href, children }) => {
    const isInternal = href?.startsWith("/");
    if (isInternal && href) {
      return (
        <Link href={href} className="font-medium text-primary underline-offset-4 hover:underline">
          {children}
        </Link>
      );
    }
    return (
      <a
        href={href}
        className="font-medium text-primary underline-offset-4 hover:underline"
        target="_blank"
        rel="noopener noreferrer"
      >
        {children}
      </a>
    );
  },
  hr: () => <hr className="my-8 border-0 border-t border-dashed border-primary/20" />,
  code: ({ children }) => (
    <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[0.85em] text-foreground">
      {children}
    </code>
  ),
  table: ({ children }) => (
    <div className="my-6 overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="border-b border-border bg-muted/50">{children}</thead>,
  th: ({ children }) => (
    <th className="px-4 py-2.5 text-left font-semibold text-foreground">{children}</th>
  ),
  td: ({ children }) => (
    <td className="border-t border-border px-4 py-2.5 text-muted-foreground">{children}</td>
  ),
};

function MarkdownChunk({ markdown }: { markdown: string }) {
  const content = normalizeMarkdownNewlines(markdown).trim();
  if (!content) return null;

  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={proseComponents}>
      {content}
    </ReactMarkdown>
  );
}

export function DocsMarkdown({ markdown }: { markdown: string }) {
  const blocks = splitDocsMarkdown(markdown);

  return (
    <div className="docs-prose space-y-5 text-[0.98rem] [&>div>p:first-of-type]:text-[1.05rem] [&>div>p:first-of-type]:leading-8 [&>div>p:first-of-type]:text-muted-foreground">
      {blocks.map((block, index) => {
        if (block.kind === "callout") {
          return (
            <DocsCallout key={`callout-${index}`} type={block.calloutType}>
              <MarkdownChunk markdown={block.content} />
            </DocsCallout>
          );
        }

        return (
          <div key={`md-${index}`}>
            <MarkdownChunk markdown={block.content} />
          </div>
        );
      })}
    </div>
  );
}
