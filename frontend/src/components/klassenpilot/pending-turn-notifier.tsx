"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import type { ArtifactMode } from "@/components/assistant-ui/artifact-runtime-config";
import { RunningTasksBox } from "@/components/klassenpilot/running-tasks-box";
import { client, isUnknownSessionError, type ActiveWorkItem } from "@/lib/api";
import {
  chatCompletionToastLabel,
  chatFailureToastLabel,
} from "@/lib/chat-run-feedback";
import { fetchedDraftToSnapshot } from "@/features/workflow-drafts/workflow-draft-transport";
import { hasLiveRunner } from "@/features/workflow-drafts/turn-runner";
import { useWorkflowDraftStore } from "@/features/workflow-drafts/workflow-draft-store";
import { runningJobsFromActiveWork } from "@/lib/running-jobs";

const POLL_MS = 3000;

/**
 * App-wide "what is running" surface (design: audit §A.1, M2).
 *
 * Asks the backend what it is running (`GET /api/workflow/active`) instead of
 * keeping sessionStorage markers. Two jobs:
 *  - render the Running-tasks box (poll items ∪ this tab's live runners);
 *  - when a job stops running, hydrate its draft and toast once.
 *
 * All draft hydration goes through the store's snapshot reducer, so a turn
 * streaming in this tab is never disturbed by a poll.
 */
export function PendingTurnNotifier() {
  const inFlightRef = useRef(false);
  const previousRef = useRef<ActiveWorkItem[]>([]);
  const [active, setActive] = useState<ActiveWorkItem[]>([]);
  const [dismissedKeys, setDismissedKeys] = useState<string[]>([]);

  // This tab's own turns: instant (no poll lag) and covers short turns that
  // start and finish between two polls.
  const localTurns = useWorkflowDraftStore((s) => s.turnByDraftId);
  const drafts = useWorkflowDraftStore((s) => s.draftsById);

  const resolveStopped = useCallback(async (item: ActiveWorkItem) => {
    if (item.kind === "memory_sweep") {
      try {
        const review = await client.getMemorySweepReview(item.class_id);
        if (review.status === "generating") return;
        // Key on review_id, not class: each generation is a new review, and a
        // regenerated sweep must be able to toast again.
        if (
          !useWorkflowDraftStore
            .getState()
            .markTurnNotified(`sweep:${item.review_id}`, 0)
        ) {
          return;
        }
        if (review.status === "failed") {
          toast.error(chatFailureToastLabel({ mode: "memory_sweep" }));
        } else {
          toast.success(chatCompletionToastLabel({ mode: "memory_sweep" }));
        }
      } catch {
        // Transient: a later poll can still notify.
      }
      return;
    }

    // A draft turn stopped running. Hydrate it (the reducer decides what that
    // means for the thread) and toast unless this chat is on screen.
    try {
      const mode = item.mode as ArtifactMode;
      const draft =
        mode === "plan"
          ? await client.planGetDraft(item.class_id, item.session_id)
          : mode === "discuss"
            ? await client.discussionGetDraft(item.class_id, item.session_id)
            : await client.ingestGetDraft(item.class_id, item.session_id);
      const snapshot = fetchedDraftToSnapshot(
        mode,
        item.class_id,
        item.session_id,
        draft,
      );
      const store = useWorkflowDraftStore.getState();
      store.upsert(snapshot);

      if (store.mountedDraftId === snapshot.draftId) return;
      if (!store.markTurnNotified(snapshot.draftId, snapshot.artifactRevision)) {
        return;
      }
      const failed = snapshot.latestTurnComplete === false;
      const label = {
        mode,
        lessonDate: item.lesson_date || undefined,
        lessonTitle: item.lesson_title || undefined,
      };
      if (failed) toast.error(chatFailureToastLabel(label));
      else toast.success(chatCompletionToastLabel(label));
    } catch (error) {
      if (!isUnknownSessionError(error)) {
        // Transient: a later poll can still notify.
      }
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    let cancelled = false;

    const poll = async () => {
      if (inFlightRef.current) return;
      inFlightRef.current = true;
      try {
        const items = (await client.getActiveWork()).items;
        if (cancelled) return;
        const stopped = previousRef.current.filter(
          (prev) => !items.some((item) => sameJob(prev, item)),
        );
        previousRef.current = items;
        setActive(items);
        await Promise.all(stopped.map(resolveStopped));
      } catch {
        // Keep the last known state; try again next tick.
      } finally {
        inFlightRef.current = false;
      }
    };

    const interval = window.setInterval(() => {
      if (document.visibilityState === "visible") void poll();
    }, POLL_MS);
    const onVisible = () => {
      if (document.visibilityState === "visible") void poll();
    };
    window.addEventListener("focus", onVisible);
    document.addEventListener("visibilitychange", onVisible);
    void poll();

    return () => {
      cancelled = true;
      window.clearInterval(interval);
      window.removeEventListener("focus", onVisible);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [resolveStopped]);

  // Stop / dropped stream: the client stream ended but the backend may still
  // be finishing. The poll resolves it when the job leaves the active list.
  const jobs = runningJobsFromActiveWork(active, localTurns, drafts, hasLiveRunner);
  const visible = jobs.filter((job) => !dismissedKeys.includes(job.key));

  return visible.length > 0 ? (
    <RunningTasksBox
      jobs={visible}
      onDismiss={() => setDismissedKeys(jobs.map((job) => job.key))}
    />
  ) : null;
}

function sameJob(a: ActiveWorkItem, b: ActiveWorkItem): boolean {
  return a.kind === "memory_sweep"
    ? b.kind === "memory_sweep" && a.class_id === b.class_id
    : b.kind === "draft_turn" && a.draft_id === b.draft_id;
}
