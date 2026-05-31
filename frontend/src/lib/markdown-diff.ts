import { diffLines } from "diff";

export type DiffLineKind = "added" | "removed" | "unchanged";

export type DiffLine = {
  kind: DiffLineKind;
  text: string;
};

export function computeMarkdownDiff(before: string, after: string): DiffLine[] {
  const parts = diffLines(before || "", after || "");
  const lines: DiffLine[] = [];
  for (const part of parts) {
    const kind: DiffLineKind = part.added ? "added" : part.removed ? "removed" : "unchanged";
    const chunk = part.value.endsWith("\n") ? part.value.slice(0, -1) : part.value;
    if (chunk === "" && part.value === "\n") {
      lines.push({ kind, text: "" });
      continue;
    }
    const split = chunk.split("\n");
    for (let i = 0; i < split.length; i++) {
      lines.push({ kind, text: split[i] ?? "" });
    }
  }
  return lines;
}

export function diffLineStats(before: string, after: string): { added: number; removed: number } {
  let added = 0;
  let removed = 0;
  for (const line of computeMarkdownDiff(before, after)) {
    if (line.kind === "added") added += 1;
    if (line.kind === "removed") removed += 1;
  }
  return { added, removed };
}

export function shortWikiPath(path: string): string {
  const parts = path.replace(/\\/g, "/").split("/");
  if (parts.length >= 2) return parts.slice(-2).join("/");
  return parts[parts.length - 1] ?? path;
}
