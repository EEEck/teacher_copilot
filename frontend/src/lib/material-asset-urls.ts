/**
 * Resolve markdown image srcs like `assets/img-0.jpeg` to the plan materials API.
 * With a single session material, bare `assets/…` paths are enough (materials skill).
 */

export type MaterialAssetContext = {
  classId: string;
  sessionId: string;
  /** Prefer first / only session material for bare assets/ paths. */
  materialIds: string[];
};

function apiBase(): string {
  if (typeof window === "undefined") {
    return (
      process.env.INTERNAL_API_BASE_URL ??
      process.env.NEXT_PUBLIC_API_BASE_URL ??
      "http://localhost:8010"
    );
  }
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8010";
}

/** Extract `assets/<file>` from a markdown image src (relative or absolute path tail). */
export function parseMaterialAssetFilename(src: string | undefined): string | null {
  if (!src) return null;
  const cleaned = src.trim().split("?")[0]?.split("#")[0] ?? "";
  const match = cleaned.match(/(?:^|\/)assets\/([^/]+)$/i);
  if (!match?.[1]) return null;
  const name = match[1];
  if (!/\.(jpe?g|png|webp|gif)$/i.test(name)) return null;
  if (name.includes("..")) return null;
  return name;
}

export function materialAssetUrl(
  ctx: MaterialAssetContext,
  filename: string,
  materialId?: string,
): string {
  const id = materialId || ctx.materialIds[0];
  if (!id) return filename;
  const base = apiBase().replace(/\/$/, "");
  return (
    `${base}/api/classes/${encodeURIComponent(ctx.classId)}` +
    `/plan/sessions/${encodeURIComponent(ctx.sessionId)}` +
    `/materials/${encodeURIComponent(id)}` +
    `/assets/${encodeURIComponent(filename)}`
  );
}

export function resolveMaterialAssetSrc(
  src: string | undefined,
  ctx: MaterialAssetContext | null | undefined,
): string | undefined {
  if (!src || !ctx?.classId || !ctx.sessionId || ctx.materialIds.length === 0) {
    return src;
  }
  const filename = parseMaterialAssetFilename(src);
  if (!filename) return src;
  // Absolute API URLs already pointing at materials assets — leave alone.
  if (/\/plan\/sessions\/[^/]+\/materials\/[^/]+\/assets\//i.test(src)) {
    return src;
  }
  return materialAssetUrl(ctx, filename);
}
