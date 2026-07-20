/**
 * Runner-lite chat-turn scenarios (design §A.1.9) — these drive the REAL
 * turn runner + store singleton with controllable fake SSE streams, so the
 * leave/return, hard-refresh, Stop, and failure paths are exercised end to
 * end (no simulated flag flips). 3 workflows × the scenario matrix.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ThreadMessageLike } from "@assistant-ui/react";

const toastSpy = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast: toastSpy }));

import type {
  ArtifactMode,
  ChatStreamChunk,
} from "@/components/assistant-ui/artifact-runtime-config";
import { shouldShowResumedTurnStatus } from "@/components/assistant-ui/thread";
import { CHAT_ERROR_REPLY } from "@/features/workflow-drafts/chat-errors";
import {
  cancelTurn,
  hasLiveRunner,
  runTurn,
  type RunTurnArgs,
} from "@/features/workflow-drafts/turn-runner";
import {
  useWorkflowDraftStore,
  type WorkflowDraftSnapshot,
} from "@/features/workflow-drafts/workflow-draft-store";
import { workflowTurnActivity } from "@/features/workflow-drafts/workflow-turn-activity";

const MODES: ArtifactMode[] = ["plan", "ingest", "discuss"];

function baseSnapshot(
  mode: ArtifactMode,
  overrides: Partial<WorkflowDraftSnapshot> = {},
): WorkflowDraftSnapshot {
  return {
    mode,
    classId: "chemie_9b_2026_27",
    draftId: `${mode}-draft`,
    sessionId: `${mode}-session`,
    messages: [],
    artifactMarkdown: mode === "discuss" ? "" : "# Draft",
    artifactRevision: 1,
    artifactHash: "hash-1",
    turnInProgress: false,
    latestTurnComplete: true,
    ...overrides,
  };
}

/** Controllable fake SSE stream: the test pushes chunks/errors/end. */
function controlledStream() {
  type Item =
    | { chunk: ChatStreamChunk }
    | { error: unknown }
    | { end: true };
  const queue: Item[] = [];
  let notify: (() => void) | null = null;
  const push = (item: Item) => {
    queue.push(item);
    notify?.();
  };
  async function* stream(args: {
    signal?: AbortSignal;
  }): AsyncGenerator<ChatStreamChunk> {
    for (;;) {
      while (queue.length === 0) {
        await new Promise<void>((resolve, reject) => {
          notify = resolve;
          args.signal?.addEventListener(
            "abort",
            () => reject(new DOMException("Aborted", "AbortError")),
            { once: true },
          );
        });
        notify = null;
      }
      if (args.signal?.aborted) {
        throw new DOMException("Aborted", "AbortError");
      }
      const item = queue.shift()!;
      if ("error" in item) throw item.error;
      if ("end" in item) return;
      yield item.chunk;
    }
  }
  return { stream, push };
}

const flush = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

const RICH_PARTS = [
  { type: "reasoning" as const, text: "Working through the request..." },
  { type: "tool_call" as const, tool: "search_wiki", args_preview: "{}" },
];

function progress(parts = RICH_PARTS): ChatStreamChunk {
  return { kind: "progress", content: parts as never };
}

function final(mode: ArtifactMode): ChatStreamChunk {
  return {
    kind: "final",
    content: [],
    result: {
      reply: `Final ${mode} reply.`,
      artifactMarkdown: "# Updated",
      artifactRevision: 2,
      artifactHash: "hash-2",
    },
  };
}

function startTurn(mode: ArtifactMode) {
  const draftId = `${mode}-draft`;
  useWorkflowDraftStore.getState().upsert(baseSnapshot(mode));
  const { stream, push } = controlledStream();
  const args: RunTurnArgs = {
    draftId,
    mode,
    classId: "chemie_9b_2026_27",
    userText: "Please draft the next step.",
    userContent: "Please draft the next step.",
    placeholderContent: [{ type: "reasoning", text: "Starting..." }],
    currentMarkdown: "# Draft",
    chatStream: stream as never,
  };
  const done = runTurn(args);
  return { draftId, push, done };
}

/** Mirrors the provider's store→UI mapping (design §A.1.7). */
function observe(draftId: string) {
  const state = useWorkflowDraftStore.getState();
  const turn = state.turnByDraftId[draftId];
  const snap = state.draftsById[draftId];
  const localStreamActive = turn?.phase === "streaming";
  const backendTurnInProgress =
    turn?.phase === "awaiting_backend" ||
    (turn == null && snap?.turnInProgress === true);
  const activity = workflowTurnActivity({ localStreamActive, backendTurnInProgress });
  return {
    stopButton: activity.runtimeIsRunning,
    stillWorking: shouldShowResumedTurnStatus(
      backendTurnInProgress,
      localStreamActive,
    ),
  };
}

function thread(draftId: string): ThreadMessageLike[] {
  return useWorkflowDraftStore.getState().threadMessagesByDraftId[draftId] ?? [];
}

function lastAssistantText(messages: ThreadMessageLike[]): string | null {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i];
    if (message.role !== "assistant") continue;
    if (typeof message.content === "string") return message.content;
    if (!Array.isArray(message.content)) return null;
    const text = message.content
      .filter(
        (part): part is { type: "text"; text: string } =>
          part.type === "text" &&
          typeof (part as { text?: unknown }).text === "string",
      )
      .map((part) => part.text)
      .join("\n")
      .trim();
    return text || null;
  }
  return null;
}

function hasRichParts(messages: ThreadMessageLike[]): boolean {
  return messages.some(
    (message) =>
      Array.isArray(message.content) &&
      message.content.some((part) => part.type !== "text"),
  );
}

beforeEach(() => {
  toastSpy.success.mockClear();
  toastSpy.error.mockClear();
  useWorkflowDraftStore.setState({
    draftsById: {},
    threadMessagesByDraftId: {},
    turnByDraftId: {},
    notifiedTurns: {},
    mountedDraftId: null,
  });
});

describe.each(MODES)("chat turn scenarios — %s", (mode) => {
  it("stay on page: live stream, then final reply; no Still-working", async () => {
    const { draftId, push, done } = startTurn(mode);
    await flush();

    push({ chunk: progress() });
    await flush();
    expect(observe(draftId).stopButton).toBe(true);
    expect(observe(draftId).stillWorking).toBe(false);
    expect(hasRichParts(thread(draftId))).toBe(true);

    push({ chunk: final(mode) });
    push({ end: true });
    await done;

    expect(observe(draftId)).toEqual({ stopButton: false, stillWorking: false });
    expect(lastAssistantText(thread(draftId))).toBe(`Final ${mode} reply.`);
    const snap = useWorkflowDraftStore.getState().draftsById[draftId];
    expect(snap.artifactMarkdown).toBe("# Updated");
    expect(snap.turnInProgress).toBe(false);
    expect(snap.latestTurnComplete).toBe(true);
  });

  it("leave mid-turn: the runner keeps streaming and the final lands without any upsert", async () => {
    const { draftId, push, done } = startTurn(mode);
    await flush();
    push({ chunk: progress() });
    await flush();
    const partsAtLeave = thread(draftId);

    // "Leave the page": nothing happens to the runner (P3) — no abort, no
    // upsert. The stream keeps advancing into the store.
    push({
      chunk: progress([
        ...RICH_PARTS,
        { type: "reasoning" as const, text: "More thinking after leave" },
      ]),
    });
    await flush();
    expect(thread(draftId)).not.toBe(partsAtLeave);
    expect(hasLiveRunner(draftId)).toBe(true);

    push({ chunk: final(mode) });
    push({ end: true });
    await done;

    expect(lastAssistantText(thread(draftId))).toBe(`Final ${mode} reply.`);
    expect(observe(draftId)).toEqual({ stopButton: false, stillWorking: false });

    // Later notifier upsert (marker consume) must not flatten the settled thread.
    const richBefore = thread(draftId);
    useWorkflowDraftStore.getState().upsert(
      baseSnapshot(mode, {
        messages: [
          { role: "user", content: "Please draft the next step." },
          { role: "assistant", content: `Final ${mode} reply.` },
        ],
        artifactRevision: 2,
        artifactHash: "hash-2",
      }),
    );
    expect(thread(draftId)).toBe(richBefore);
  });

  it("hard refresh mid-turn: plain messages + Still-working, poll completes it", () => {
    const draftId = `${mode}-draft`;
    // Fresh store (beforeEach) — bootstrap sees a running turn.
    useWorkflowDraftStore.getState().upsert(
      baseSnapshot(mode, {
        messages: [{ role: "user", content: "Please draft the next step." }],
        turnInProgress: true,
        latestTurnComplete: false,
      }),
    );
    expect(observe(draftId)).toEqual({ stopButton: false, stillWorking: true });
    expect(hasRichParts(thread(draftId))).toBe(false);

    // Recovery poll / notifier upserts the completed draft.
    useWorkflowDraftStore.getState().upsert(
      baseSnapshot(mode, {
        messages: [
          { role: "user", content: "Please draft the next step." },
          { role: "assistant", content: `Recovered ${mode} reply.` },
        ],
        artifactRevision: 3,
      }),
    );
    expect(observe(draftId)).toEqual({ stopButton: false, stillWorking: false });
    expect(lastAssistantText(thread(draftId))).toBe(`Recovered ${mode} reply.`);
  });

  it("Stop button: abort → Still-working → completed draft merges the reply into rich parts", async () => {
    const { draftId, push, done } = startTurn(mode);
    await flush();
    push({ chunk: progress() });
    await flush();

    cancelTurn(draftId);
    await done;

    expect(observe(draftId)).toEqual({ stopButton: false, stillWorking: true });
    expect(hasRichParts(thread(draftId))).toBe(true);
    expect(lastAssistantText(thread(draftId))).toBeNull();

    // Backend finishes; recovery poll / notifier upserts the completed draft.
    useWorkflowDraftStore.getState().upsert(
      baseSnapshot(mode, {
        messages: [
          { role: "user", content: "Please draft the next step." },
          { role: "assistant", content: `Recovered ${mode} reply.` },
        ],
        artifactRevision: 3,
      }),
    );
    expect(observe(draftId)).toEqual({ stopButton: false, stillWorking: false });
    const merged = thread(draftId);
    expect(hasRichParts(merged)).toBe(true);
    expect(lastAssistantText(merged)).toBe(`Recovered ${mode} reply.`);
  });

  it("dropped stream after content: awaiting backend, not failed (invariant I3)", async () => {
    const { draftId, push, done } = startTurn(mode);
    await flush();
    push({ chunk: progress() });
    await flush();

    push({ error: new TypeError("network error") });
    await done;

    // The backend may still finish; the notifier's poll resolves it.
    expect(observe(draftId)).toEqual({ stopButton: false, stillWorking: true });
    expect(useWorkflowDraftStore.getState().turnByDraftId[draftId].phase).toBe(
      "awaiting_backend",
    );
  });

  it("failure before any content: error reply, turn settled", async () => {
    const { draftId, push, done } = startTurn(mode);
    await flush();

    push({ error: new Error("API 500: boom") });
    await done;

    expect(observe(draftId)).toEqual({ stopButton: false, stillWorking: false });
    expect(lastAssistantText(thread(draftId))).toBe(CHAT_ERROR_REPLY);
    expect(useWorkflowDraftStore.getState().turnByDraftId[draftId].phase).toBe(
      "settled",
    );
  });

  it("completion toast fires once off-page, never for the chat on screen", async () => {
    const draftId = `${mode}-draft`;
    const store = useWorkflowDraftStore.getState();

    // On screen: the teacher is watching, so nothing to announce.
    store.setMountedDraftId(draftId);
    const onScreen = startTurn(mode);
    await flush();
    onScreen.push({ chunk: final(mode) });
    onScreen.push({ end: true });
    await onScreen.done;
    expect(toastSpy.success).not.toHaveBeenCalled();

    // Off page: announce once, and the notifier can't double-toast it.
    useWorkflowDraftStore.setState({
      draftsById: {},
      threadMessagesByDraftId: {},
      turnByDraftId: {},
      notifiedTurns: {},
      mountedDraftId: null,
    });
    const offPage = startTurn(mode);
    await flush();
    offPage.push({ chunk: final(mode) });
    offPage.push({ end: true });
    await offPage.done;

    expect(toastSpy.success).toHaveBeenCalledTimes(1);
    // artifactRevision 2 comes from the final chunk.
    expect(
      useWorkflowDraftStore.getState().markTurnNotified(draftId, 2),
    ).toBe(false);
  });

  it("duplicate send while streaming is a no-op (one turn per draft)", async () => {
    const { draftId, push, done } = startTurn(mode);
    await flush();
    const userMessages = () =>
      thread(draftId).filter((message) => message.role === "user").length;
    expect(userMessages()).toBe(1);

    await runTurn({
      draftId,
      mode,
      classId: "chemie_9b_2026_27",
      userText: "duplicate",
      userContent: "duplicate",
      placeholderContent: [],
      currentMarkdown: "# Draft",
      chatStream: (async function* () {
        yield final(mode);
      }) as never,
    });
    expect(userMessages()).toBe(1);

    push({ chunk: final(mode) });
    push({ end: true });
    await done;
  });

  it("discard mid-turn: cancel + remove; late stream events cannot resurrect the draft (I5)", async () => {
    const { draftId, push, done } = startTurn(mode);
    await flush();
    push({ chunk: progress() });
    await flush();

    // Page discard flow: cancelTurn + remove.
    cancelTurn(draftId);
    useWorkflowDraftStore.getState().remove(draftId);
    push({ chunk: final(mode) });
    push({ end: true });
    await done;

    const state = useWorkflowDraftStore.getState();
    expect(state.draftsById[draftId]).toBeUndefined();
    expect(state.threadMessagesByDraftId[draftId]).toBeUndefined();
    expect(state.turnByDraftId[draftId]).toBeUndefined();
  });
});
