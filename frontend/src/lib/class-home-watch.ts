/** Build the brief Watch list: misconceptions first, then brief watch items. */

const MAX_WATCH = 3;

export function classHomeWatchItems(
  misconceptions: string[] | undefined,
  briefWatch: string[] | undefined,
  limit = MAX_WATCH,
): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of [...(misconceptions ?? []), ...(briefWatch ?? [])]) {
    const item = raw.trim();
    if (!item) continue;
    const key = item.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(item);
    if (out.length >= limit) break;
  }
  return out;
}
