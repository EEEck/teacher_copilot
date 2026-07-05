import { describe, expect, it } from "vitest";

import {
  clearPendingMemoryReview,
  loadPendingMemoryReview,
  pendingMemoryReviewKey,
  savePendingMemoryReview,
  type PendingMemoryReview,
} from "./pending-memory-review";

class MemoryStorage {
  private readonly items = new Map<string, string>();

  getItem(key: string) {
    return this.items.get(key) ?? null;
  }

  setItem(key: string, value: string) {
    this.items.set(key, value);
  }

  removeItem(key: string) {
    this.items.delete(key);
  }
}

const review: Omit<PendingMemoryReview, "version" | "savedAt"> = {
  classId: "chemie_9b_2026_27",
  routeKey: "/classes/chemie_9b_2026_27/memory?lessonDate=2026-07-04",
  diaryMarkdown: "# Lesson results\n\nStudent note.",
  proposals: [
    {
      wiki_path: "classes/chemie_9b_2026_27/lessons/2026-07-04/lesson_results.md",
      current_content: "",
      proposed_content: "# Lesson results\n",
      rationale: "Save lesson results.",
    },
  ],
  memoryCandidates: [],
  approvedByPath: {
    "classes/chemie_9b_2026_27/lessons/2026-07-04/lesson_results.md": true,
  },
  contentByPath: {
    "classes/chemie_9b_2026_27/lessons/2026-07-04/lesson_results.md":
      "# Lesson results\nEdited.",
  },
  selectedPath: "classes/chemie_9b_2026_27/lessons/2026-07-04/lesson_results.md",
  editingWiki: true,
};

describe("pending memory review storage", () => {
  it("round trips a pending review for the same class and route", () => {
    const storage = new MemoryStorage();

    savePendingMemoryReview(storage, review, 1_000);

    expect(
      loadPendingMemoryReview(storage, review.classId, review.routeKey, 1_500),
    ).toMatchObject({
      ...review,
      version: 1,
      savedAt: 1_000,
    });
  });

  it("does not restore stale reviews", () => {
    const storage = new MemoryStorage();

    savePendingMemoryReview(storage, review, 1_000);

    expect(
      loadPendingMemoryReview(
        storage,
        review.classId,
        review.routeKey,
        1_000 + 24 * 60 * 60 * 1000 + 1,
      ),
    ).toBeNull();
  });

  it("clears a pending review", () => {
    const storage = new MemoryStorage();
    savePendingMemoryReview(storage, review, 1_000);

    clearPendingMemoryReview(storage, review.classId, review.routeKey);

    expect(
      storage.getItem(pendingMemoryReviewKey(review.classId, review.routeKey)),
    ).toBeNull();
  });
});
