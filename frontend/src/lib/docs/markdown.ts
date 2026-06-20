import type { DocsCalloutType } from "@/components/docs/docs-callout";

const CALLOUT_TYPES = new Set<DocsCalloutType>([
  "note",
  "tip",
  "warning",
  "important",
  "blueprint",
]);

export type DocsMarkdownBlock =
  | { kind: "markdown"; content: string }
  | { kind: "callout"; calloutType: DocsCalloutType; content: string };

export function normalizeMarkdownNewlines(markdown: string): string {
  return markdown.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
}

function parseCalloutType(raw: string): DocsCalloutType {
  const type = raw.toLowerCase();
  return CALLOUT_TYPES.has(type as DocsCalloutType) ? (type as DocsCalloutType) : "note";
}

function unquoteCalloutBody(raw: string): string {
  return raw
    .split("\n")
    .map((line) => line.replace(/^>\s?/, ""))
    .join("\n")
    .trim();
}

/**
 * Extract GitHub-style alert blockquotes (`> [!type]`) before react-markdown runs.
 * Blockquote parsing merges lines unpredictably; splitting source text is reliable.
 */
export function splitDocsMarkdown(markdown: string): DocsMarkdownBlock[] {
  const source = normalizeMarkdownNewlines(markdown);
  const calloutStart = /^> \[!(\w+)\]\n(?:> \n)?/gm;

  const blocks: DocsMarkdownBlock[] = [];
  let cursor = 0;

  for (const match of source.matchAll(calloutStart)) {
    const start = match.index ?? 0;
    if (start > cursor) {
      blocks.push({ kind: "markdown", content: source.slice(cursor, start) });
    }

    const calloutType = parseCalloutType(match[1]);
    const bodyStart = start + match[0].length;
    let bodyEnd = bodyStart;

    while (bodyEnd < source.length) {
      const lineEnd = source.indexOf("\n", bodyEnd);
      const line = lineEnd === -1 ? source.slice(bodyEnd) : source.slice(bodyEnd, lineEnd);
      if (!line.startsWith(">")) break;
      bodyEnd = lineEnd === -1 ? source.length : lineEnd + 1;
    }

    blocks.push({
      kind: "callout",
      calloutType,
      content: unquoteCalloutBody(source.slice(bodyStart, bodyEnd)),
    });

    cursor = bodyEnd;
  }

  if (cursor < source.length) {
    blocks.push({ kind: "markdown", content: source.slice(cursor) });
  }

  if (blocks.length === 0) {
    blocks.push({ kind: "markdown", content: source });
  }

  return blocks;
}
