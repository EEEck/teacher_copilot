import type {
  MemoryCandidate,
  WikiUpdateProposal,
} from "@/lib/api";

export type PendingMemoryReview = {
  version: 2;
  savedAt: number;
  classId: string;
  routeKey: string;
  draftId: string;
  sourceArtifactRevision: number;
  sourceArtifactHash: string;
  diaryMarkdown: string;
  proposals: WikiUpdateProposal[];
  memoryCandidates: MemoryCandidate[];
  approvedByPath: Record<string, boolean>;
  contentByPath: Record<string, string>;
  selectedPath: string | null;
  editingWiki: boolean;
};

const MAX_REVIEW_AGE_MS = 24 * 60 * 60 * 1000;

export function pendingMemoryReviewKey(classId: string, routeKey: string): string {
  return `kp:pending-memory-review:${classId}:${encodeURIComponent(routeKey)}`;
}

export function savePendingMemoryReview(
  storage: Pick<Storage, "setItem">,
  review: Omit<PendingMemoryReview, "version" | "savedAt">,
  now = Date.now(),
) {
  const value: PendingMemoryReview = {
    ...review,
    version: 2,
    savedAt: now,
  };
  storage.setItem(
    pendingMemoryReviewKey(review.classId, review.routeKey),
    JSON.stringify(value),
  );
}

export function loadPendingMemoryReview(
  storage: Pick<Storage, "getItem">,
  classId: string,
  routeKey: string,
  now = Date.now(),
): PendingMemoryReview | null {
  const raw = storage.getItem(pendingMemoryReviewKey(classId, routeKey));
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<PendingMemoryReview>;
    if (parsed.version !== 2) return null;
    if (parsed.classId !== classId || parsed.routeKey !== routeKey) return null;
    if (typeof parsed.draftId !== "string") return null;
    if (typeof parsed.sourceArtifactRevision !== "number") return null;
    if (typeof parsed.sourceArtifactHash !== "string") return null;
    if (typeof parsed.savedAt !== "number" || now - parsed.savedAt > MAX_REVIEW_AGE_MS) {
      return null;
    }
    if (typeof parsed.diaryMarkdown !== "string") return null;
    if (!Array.isArray(parsed.proposals)) return null;
    if (!Array.isArray(parsed.memoryCandidates)) return null;
    if (!isStringBooleanRecord(parsed.approvedByPath)) return null;
    if (!isStringStringRecord(parsed.contentByPath)) return null;
    if (parsed.selectedPath !== null && typeof parsed.selectedPath !== "string") return null;
    if (typeof parsed.editingWiki !== "boolean") return null;
    return parsed as PendingMemoryReview;
  } catch {
    return null;
  }
}

export function clearPendingMemoryReview(
  storage: Pick<Storage, "removeItem">,
  classId: string,
  routeKey: string,
) {
  storage.removeItem(pendingMemoryReviewKey(classId, routeKey));
}

function isStringBooleanRecord(value: unknown): value is Record<string, boolean> {
  return (
    !!value &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    Object.values(value).every((v) => typeof v === "boolean")
  );
}

function isStringStringRecord(value: unknown): value is Record<string, string> {
  return (
    !!value &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    Object.values(value).every((v) => typeof v === "string")
  );
}
