import type { MemoryCandidate } from "@/lib/api";

/** Stable de-dupe for post-save / propose memory candidate lists. */
export function dedupeMemoryCandidates(
  candidates: MemoryCandidate[],
): MemoryCandidate[] {
  const seen = new Set<string>();
  const out: MemoryCandidate[] = [];
  for (const c of candidates) {
    const key = `${c.target}::${c.section ?? ""}::${c.candidate_update.trim().toLowerCase()}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(c);
  }
  return out;
}
