import "server-only";

import fs from "node:fs/promises";
import path from "node:path";
import { DEFAULT_LOCALE } from "./registry";

const contentRoot = path.join(process.cwd(), "src", "content", "docs");

async function resolveMarkdownPath(slug: string, locale = DEFAULT_LOCALE) {
  const localized = path.join(contentRoot, locale, `${slug}.md`);
  try {
    await fs.access(localized);
    return localized;
  } catch {
    return path.join(contentRoot, `${slug}.md`);
  }
}

export async function readDocMarkdown(slug: string, locale = DEFAULT_LOCALE) {
  const filePath = await resolveMarkdownPath(slug, locale);
  return fs.readFile(filePath, "utf8");
}
