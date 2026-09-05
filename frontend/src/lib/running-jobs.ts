import type { ArtifactMode } from "@/components/assistant-ui/artifact-runtime-config";
import type { ActiveWorkItem } from "@/lib/api";

export type RunningJobMode = ArtifactMode | "memory_sweep" | "course_material";

export type RunningJob = {
  /** Stable identity for React keys and dismissal. */
  key: string;
  mode: RunningJobMode;
  classId: string;
  lessonDate?: string;
  lessonTitle?: string;
};

/** Where clicking a running job should take the teacher. */
export function runningJobHref(job: RunningJob): string {
  if (job.mode === "course_material") return `/classes/${job.classId}/course/materials`;
  if (job.mode === "memory_sweep") return `/classes/${job.classId}/memory-sweep`;
  // Discuss lives in a dock on class home; force it open on arrival.
  if (job.mode === "discuss") return `/classes/${job.classId}?discuss=open`;
  return job.mode === "plan"
    ? `/classes/${job.classId}/plan`
    : `/classes/${job.classId}/memory`;
}

function jobFromActiveWork(item: ActiveWorkItem): RunningJob {
  if (item.kind === "memory_sweep") {
    return { key: `sweep:${item.class_id}`, mode: "memory_sweep", classId: item.class_id };
  }
  return {
    key: item.draft_id,
    mode: item.mode as ArtifactMode,
    classId: item.class_id,
    lessonDate: item.lesson_date || undefined,
    lessonTitle: item.lesson_title || undefined,
  };
}

/**
 * What to show in the Running box: everything the backend says is running,
 * plus this tab's live runners.
 *
 * The local half matters twice: a turn is visible the instant it is sent
 * (before the first poll sees it), and a short turn that starts and finishes
 * between two polls is still shown while it runs. Local records also carry
 * richer labels (resolved lesson date/title) than a draft row does.
 */
export function runningJobsFromActiveWork(
  active: ActiveWorkItem[],
  localTurns: Record<
    string,
    { phase: string; mode: ArtifactMode; classId: string; lessonDate?: string; lessonTitle?: string }
  >,
  drafts: Record<string, { classId: string; mode: ArtifactMode }>,
  isLive: (draftId: string) => boolean,
): RunningJob[] {
  const jobs = active.map(jobFromActiveWork);
  const seen = new Set(jobs.map((job) => job.key));

  for (const [draftId, turn] of Object.entries(localTurns)) {
    const running = turn.phase === "streaming" || turn.phase === "awaiting_backend";
    if (!running) continue;
    // `streaming` implies a live runner; `awaiting_backend` has none but the
    // backend may still be working, so keep showing it until a poll resolves it.
    if (turn.phase === "streaming" && !isLive(draftId)) continue;
    const existing = jobs.findIndex((job) => job.key === draftId);
    const local: RunningJob = {
      key: draftId,
      mode: turn.mode,
      classId: turn.classId || drafts[draftId]?.classId || "",
      lessonDate: turn.lessonDate,
      lessonTitle: turn.lessonTitle,
    };
    // Local labels win: the backend draft row may not carry a resolved target.
    if (existing >= 0) jobs[existing] = local;
    else if (!seen.has(draftId)) jobs.push(local);
  }
  return jobs;
}
