/**
 * The Running box unions two sources: what the backend says it is running
 * (poll) and what this tab is running right now (store). These tests pin the
 * merge rules, since a wrong union either hides live work or shows ghosts.
 */
import { describe, expect, it } from "vitest";

import type { ActiveWorkItem } from "@/lib/api";
import { runningJobHref, runningJobsFromActiveWork } from "@/lib/running-jobs";

function activeDraft(overrides: Partial<ActiveWorkItem> = {}): ActiveWorkItem {
  return {
    kind: "draft_turn",
    class_id: "chemie_9b_2026_27",
    mode: "plan",
    draft_id: "plan-draft",
    session_id: "plan-session",
    lesson_date: "",
    lesson_title: "",
    review_id: "",
    updated_at: "2026-07-16T10:00:00Z",
    ...overrides,
  };
}

const live = (id: string) => (draftId: string) => draftId === id;
const noneLive = () => false;

describe("runningJobsFromActiveWork", () => {
  it("shows backend work this tab knows nothing about", () => {
    const jobs = runningJobsFromActiveWork([activeDraft()], {}, {}, noneLive);
    expect(jobs).toEqual([
      { key: "plan-draft", mode: "plan", classId: "chemie_9b_2026_27" },
    ]);
  });

  it("shows a just-sent local turn before the first poll sees it", () => {
    const jobs = runningJobsFromActiveWork(
      [],
      {
        "plan-draft": {
          phase: "streaming",
          mode: "plan",
          classId: "chemie_9b_2026_27",
          lessonDate: "2026-09-01",
        },
      },
      {},
      live("plan-draft"),
    );
    expect(jobs).toHaveLength(1);
    expect(jobs[0].lessonDate).toBe("2026-09-01");
  });

  it("lists a draft once, with the local label winning over the poll's", () => {
    const jobs = runningJobsFromActiveWork(
      [activeDraft()],
      {
        "plan-draft": {
          phase: "streaming",
          mode: "plan",
          classId: "chemie_9b_2026_27",
          lessonTitle: "Alkane",
        },
      },
      {},
      live("plan-draft"),
    );
    expect(jobs).toHaveLength(1);
    expect(jobs[0].lessonTitle).toBe("Alkane");
  });

  it("keeps awaiting_backend visible with no live runner, drops settled turns", () => {
    const turns = {
      "plan-draft": {
        phase: "awaiting_backend",
        mode: "plan" as const,
        classId: "chemie_9b_2026_27",
      },
      "ingest-draft": {
        phase: "settled",
        mode: "ingest" as const,
        classId: "chemie_9b_2026_27",
      },
    };
    const jobs = runningJobsFromActiveWork([], turns, {}, noneLive);
    expect(jobs.map((job) => job.key)).toEqual(["plan-draft"]);
  });

  it("drops a streaming record whose runner is gone (stale after refresh)", () => {
    const jobs = runningJobsFromActiveWork(
      [],
      {
        "plan-draft": {
          phase: "streaming",
          mode: "plan",
          classId: "chemie_9b_2026_27",
        },
      },
      {},
      noneLive,
    );
    expect(jobs).toEqual([]);
  });

  it("shows concurrent drafts and sweeps side by side", () => {
    const jobs = runningJobsFromActiveWork(
      [
        activeDraft(),
        activeDraft({ draft_id: "ingest-draft", mode: "ingest" }),
        activeDraft({
          kind: "memory_sweep",
          class_id: "bio_10a",
          mode: "",
          draft_id: "",
          review_id: "review-7",
        }),
      ],
      {},
      {},
      noneLive,
    );
    expect(jobs.map((job) => job.key)).toEqual([
      "plan-draft",
      "ingest-draft",
      "sweep:bio_10a",
    ]);
  });

  it("falls back to the draft row's class when the turn record lacks one", () => {
    const jobs = runningJobsFromActiveWork(
      [],
      {
        "plan-draft": {
          phase: "awaiting_backend",
          mode: "plan",
          classId: "",
        },
      },
      { "plan-draft": { classId: "bio_10a", mode: "plan" } },
      noneLive,
    );
    expect(jobs[0].classId).toBe("bio_10a");
  });
});

describe("runningJobHref", () => {
  it("routes each mode to where its work is visible", () => {
    const job = { key: "k", classId: "bio_10a" };
    expect(runningJobHref({ ...job, mode: "plan" })).toBe("/classes/bio_10a/plan");
    expect(runningJobHref({ ...job, mode: "ingest" })).toBe(
      "/classes/bio_10a/memory",
    );
    expect(runningJobHref({ ...job, mode: "memory_sweep" })).toBe(
      "/classes/bio_10a/memory-sweep",
    );
    // Discuss has no page of its own — it lives in a dock on class home.
    expect(runningJobHref({ ...job, mode: "discuss" })).toBe(
      "/classes/bio_10a?discuss=open",
    );
  });
});
