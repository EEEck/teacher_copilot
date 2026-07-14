/** Helpers for opening class wiki files in the read-only inspector. */

export function wikiViewerHref(classId: string, wikiPath: string): string {
  return `/classes/${classId}/wiki/view?path=${encodeURIComponent(wikiPath)}`;
}

/** Normalize known path drift (e.g. retired memory/course_state twin). */
export function normalizeClassWikiPath(classId: string, path: string): string {
  const rel = path.trim().replace(/\\/g, "/").replace(/^\/+/, "");
  const wrongCourseState = `wiki/classes/${classId}/memory/course_state.md`;
  if (rel === wrongCourseState || rel.endsWith("/memory/course_state.md")) {
    return `wiki/classes/${classId}/course_state.md`;
  }
  return rel;
}

/**
 * Resolve a markdown href into a wiki-root-relative path for the inspector.
 * Absolute http(s)/mailto/# links return null (leave as normal links).
 */
export function resolveWikiMarkdownHref(
  classId: string,
  href: string | undefined,
  currentWikiPath: string,
): string | null {
  if (!href) return null;
  const raw = href.trim();
  if (!raw || raw.startsWith("#")) return null;
  if (/^(https?:|mailto:|tel:)/i.test(raw)) return null;
  if (raw.startsWith("/classes/")) return null;

  let target = raw.replace(/\\/g, "/");
  if (target.startsWith("/")) {
    target = target.replace(/^\/+/, "");
  } else if (!target.startsWith("wiki/") && !target.startsWith("raw/")) {
    const current = currentWikiPath.replace(/\\/g, "/").replace(/^\/+/, "");
    const slash = current.lastIndexOf("/");
    const baseDir = slash >= 0 ? current.slice(0, slash) : "";
    target = baseDir ? `${baseDir}/${target}` : target;
  }

  // Collapse ./ and redundant segments without allowing .. escapes outside wiki.
  const parts: string[] = [];
  for (const part of target.split("/")) {
    if (!part || part === ".") continue;
    if (part === "..") {
      if (parts.length === 0) return null;
      parts.pop();
      continue;
    }
    parts.push(part);
  }
  return normalizeClassWikiPath(classId, parts.join("/"));
}
