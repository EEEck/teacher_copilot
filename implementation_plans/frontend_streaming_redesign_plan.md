# Frontend Streaming Redesign Plan (M1–M3)

Status: draft for review — 2026-07-12.
Branch context: `claude/frontend-streaming-regression-ed1d2e` (executive-copilot
branch after the main merge). This plan builds on that branch's state, including
the `useWorkflowDraftStore.getState().remove(draftId)` discard behavior it added.

## Product Contract

Three behaviors, MVP scope:

1. **Live streaming in chat.** While a turn runs on the page that started it,
   reasoning deltas and tool calls stream into the thread as they happen.
2. **Leaving the page never loses the turn.** In-app navigation away keeps the
   turn streaming into client state; returning shows everything up to (and past)
   the point of interruption, plus a spinner while the backend turn runs. A hard
   reload degrades gracefully: persisted messages + spinner, completion arrives
   by poll (live re-streaming after reload is M3, parked).
3. **One small "Running tasks" surface** shows every in-flight job (plan turns,
   memory turns, Memory Sweep generation) across classes, with a completion
   toast when a job finishes off-page.

The backend already supports all three: turns run as service-owned asyncio tasks
(`_stream_tasks` in
[`artifact_session_service.py`](../backend/app/services/artifact_session_service.py)),
the HTTP SSE response is just one subscriber (`_stream_subscribers`), and drafts
persist messages/artifact/turn flags durably. This plan makes the frontend stop
fighting that architecture.

## Diagnosis: why the current construction is fragile

The same facts live in four places, synchronized by heuristics:

| # | Location | What it holds |
|---|----------|---------------|
| 1 | Backend workflow draft (SQLite) | durable truth: messages, artifact, revision/hash, `turn_in_progress`, `latest_turn_complete` |
| 2 | Zustand `useWorkflowDraftStore` | `draftsById` + `threadMessagesByDraftId` |
| 3 | Six mirrored `useState`s in `ArtifactSessionRuntimeProvider` (`activeSessionId`, `activeDraftId`, `activeArtifactRevision`, `activeArtifactHash`, `activeTurnInProgress`, `activeLatestTurnComplete`) | copies of #1/#2, synced both directions via two effects |
| 4 | sessionStorage pending-turn markers (`pending-chat-turns.ts`) | which turns are running, `seenInProgress`, `baselineMessageCount`, dismissal flags |

Every pairwise sync needs a guess:

- `shouldKeepLiveThread` (workflow-draft-store.ts) guesses whether a snapshot
  upsert would wipe live SSE parts by comparing message counts and detecting
  "rich parts".
- `shouldNotifyPendingDraftComplete` (pending-chat-turns.ts) guesses whether
  "idle + complete" means *this* turn finished, via the `seenInProgress` flag
  plus `baselineMessageCount` growth.
- `isPendingTurnOnCurrentPage` compares href strings to suppress toasts.
- `PendingTurnNotifier` polls the backend every 2 s **and** sessionStorage every
  1 s to keep #4 and the UI consistent.

The second structural flaw: **the turn runner lives inside a React callback**
(`onNew` in `artifact-session-runtime.tsx`). Component lifecycle — unmount,
error boundary, hard navigation — gets conflated with turn outcome.

### The two concrete bugs this produced (both reproduced in the browser)

**Bug A — infinite-render crash ("Maximum update depth exceeded").**
`useWorkflowChatRuntime` selects
`state.threadMessagesByDraftId[draftId] ?? []`
([workflow-chat-runtime.tsx:26-28](../frontend/src/features/workflow-drafts/workflow-chat-runtime.tsx)).
When the key is missing, `?? []` allocates a new array per render, and the
`useSyncExternalStore`-backed hook re-renders forever. The key goes missing
deterministically since this branch added `remove(draftId)` on discard; an error
boundary swallows the crash, so the symptom is "nothing appears when I submit".

**Bug B — abort treated as turn failure.** On a hard navigation mid-turn the
browser cancels the fetch; `onNew`'s catch block marks the turn failed and
clears the pending marker
([artifact-session-runtime.tsx:446-455](../frontend/src/components/assistant-ui/artifact-session-runtime.tsx)),
even though the backend turn keeps running and lands correctly. The completion
toast / Running-tasks entry silently never fires.

### What already works today and must be preserved

On **in-app navigation** away and back mid-turn, the current code keeps the
streamed reasoning/tool-call parts and continues streaming: the fetch is never
aborted (no signal passed), the detached `onNew` loop keeps writing to the
module-level store through a frozen ref, and `shouldKeepLiveThread` (usually)
protects the thread from the re-bootstrap snapshot. This UX is correct — the
redesign keeps it identically, but as the designed path instead of an accident.

### Why the redesign is more robust (failure-mode view)

| Failure mode in the old construction | Structural cause | What removes it |
|---|---|---|
| Thread wiped / kept wrongly on upsert | `shouldKeepLiveThread` guesses from message counts | Explicit `liveTurn` gate — one rule, no guessing |
| False/missing completion toasts | Markers written before the backend knows the turn; completion inferred via `seenInProgress` + `baselineMessageCount` | "Running" is a backend query; a missed poll self-heals next tick |
| Turn "fails" on navigation (Bug B) | SSE loop inside `onNew`; component lifecycle conflated with turn outcome | Runner is a plain function; only the stream itself can fail a turn |
| Infinite-render crash (Bug A) | Fresh `?? []` per render against `useSyncExternalStore` | Selector contract: stored reference or module constant, enforced by test |
| Stale UI after missed marker write/clear | sessionStorage as write-ahead bookkeeping — one missed write is permanent, silent | No client bookkeeping; derived UI state is recomputable from store + poll |
| Nav-survival fragile to refactoring | Worked by accident (no AbortSignal + frozen ref) | Same behavior is the runner's documented contract |

The maintainability asymmetry in one example — adding a new background job
type (e.g. report generation):

- **Old:** new sessionStorage marker key + completion heuristic + toast guard
  + storage-poll wiring + tests for the races between them.
- **New:** one `kind` value in `ActiveWorkItem` plus a toast/box label.
  Sidebar, polling, transition detection, and toast dedupe are shared.

The same asymmetry applies to new surfaces: anything that wants to show
running work (a class-home badge, a nav indicator) reads the store or the
active endpoint — it does not need to participate in a bookkeeping protocol.

## Critical Design Decisions (agreed 2026-07-12)

### 1. One client mirror: the store

The Zustand workflow-draft store becomes the only client-side copy of draft
state. The six mirrored `useState`s and both sync effects in
`ArtifactSessionRuntimeProvider` are deleted; everything reads store selectors.
Genuinely page-local UI state stays component-local: editor history/undo,
`syncStatus`, the `patchDraft` debounce.

### 2. Store keyed by `draft_id` only

`IngestService.start_session` and `PlanService.start_session` always pass a
`WorkflowDraftIdentity`, and `open_draft` creates or reopens the row before the
session is returned
([artifact_session_service.py:136-151](../backend/app/services/artifact_session_service.py)).
So `draft_id` exists at bootstrap and the frontend's
`activeDraftId || activeSessionId` dual-key fallback guards a state that does
not occur in production. It is deleted. `toWorkflowDraftSnapshot`'s
`if (!bootstrap.draftId) return null` guard becomes a thrown invariant (or a
logged no-op), not a silent skip that leaves the store unpopulated.

### 3. The turn runner is a plain service, not a component callback

`runTurn(...)` is a module-level async function that owns the SSE consumption
loop and writes to the store. Components call it and render the store. Unmount
no longer touches the stream (deliberately, not accidentally); an aborted HTTP
connection is not a turn failure.

### 4. An explicit `liveTurn` flag replaces `shouldKeepLiveThread`

While a runner owns a draft, snapshot upserts update draft metadata but never
touch the thread. No message counting, no rich-part detection.

### 5. "What's running" is a query, not a bookkeeping protocol

- Same JS context: the store's `liveTurn` entries (exact).
- After a reload: `GET /api/workflow/active` (M2) lists in-flight work across
  classes, including Memory Sweep generation.
- The whole sessionStorage marker system (`pending-chat-turns.ts`) is deleted
  in M2. sessionStorage keeps doing the one thing it is good at: unsent
  composer text (`kp:composer:{draftId}`).

### 6. Reload recovery is poll-only for MVP

After a hard reload mid-turn: persisted messages + spinner
(`turn_in_progress`), completion arrives via the M2 poll. This is exact parity
with today (reasoning parts are SSE-only and were never persisted). Live
re-attach is specced as M3 and parked.

## Target architecture

### Store shape (M1)

```ts
// frontend/src/features/workflow-drafts/workflow-draft-store.ts
type LiveTurn = {
  status: "streaming";      // M3 adds "attached"
  startedAt: number;
};

type WorkflowDraftEntry = {
  snapshot: WorkflowDraftSnapshot;   // backend mirror incl. completeness/memoryState
  thread: ThreadMessageLike[];       // render model for assistant-ui
  liveTurn: LiveTurn | null;
};

type WorkflowDraftState = {
  draftsById: Record<string, WorkflowDraftEntry>;
  mountedDraftId: string | null;     // set/cleared by the artifact page

  // Snapshot path (bootstrap, patchDraft response, notifier poll):
  upsertSnapshot(snapshot: WorkflowDraftSnapshot): void;
  //   - always replaces entry.snapshot
  //   - replaces entry.thread from snapshot.messages ONLY if liveTurn === null

  // Runner path:
  beginTurn(draftId, userContent, placeholderContent): void;  // appends msgs, sets liveTurn
  applyTurnProgress(draftId, content: ThreadMessageLike["content"]): void;
  completeTurn(draftId, final: ArtifactChatResult): void;     // final thread + snapshot meta, clears liveTurn
  failTurn(draftId, friendlyMessage: string): void;           // error text into last assistant msg, clears liveTurn

  // Page lifecycle:
  setMountedDraftId(draftId | null): void;
  remove(draftId): void;

  // Toast dedupe (used in M2; introduced in M1 for symmetry):
  markTurnNotified(draftId, artifactRevision): boolean;       // true = first observer
};
```

Selector rules (fixes Bug A structurally):

```ts
const EMPTY_THREAD: ThreadMessageLike[] = [];
const selectThread = (draftId: string) => (s: WorkflowDraftState) =>
  s.draftsById[draftId]?.thread ?? EMPTY_THREAD;
```

Every selector returns either a stored reference or a module-level constant —
never a fresh allocation.

### Turn runner (M1)

```ts
// frontend/src/features/workflow-drafts/turn-runner.ts
const activeRunners = new Set<string>();   // one turn per draft, N drafts concurrently

export async function runTurn(args: {
  draftId: string;
  message: string;
  currentMarkdown: string;
  attachments?: SessionAttachment[];
  chatStream: ChatStreamFn;   // the artifact-runtime-config generator;
                              // session recovery stays wrapped inside it
}): Promise<void> {
  if (activeRunners.has(args.draftId)) return;   // composer should prevent this anyway
  activeRunners.add(args.draftId);
  const store = useWorkflowDraftStore.getState();
  store.beginTurn(args.draftId, userContent(args), initialAssistantRunContent());
  let completed = false;
  try {
    for await (const chunk of args.chatStream({ ... })) {
      if (chunk.kind === "progress") {
        store.applyTurnProgress(args.draftId, streamPartsToRunContent(chunk.content));
        continue;
      }
      store.completeTurn(args.draftId, chunk.result);
      completed = true;
    }
    if (!completed) store.failTurn(args.draftId, CHAT_ERROR_REPLY);
  } catch (err) {
    if (!completed) store.failTurn(args.draftId, friendlyChatError(err));
  } finally {
    activeRunners.delete(args.draftId);
  }
}

export const hasLiveRunner = (draftId: string) => activeRunners.has(draftId);
```

Notes:

- **No AbortSignal is passed.** The fetch outliving the page is the feature
  (today's accidental behavior made deliberate). Bug B disappears: there is no
  unmount-coupled catch block left to misfire.
- `completeTurn` carries what the current `applyDraftMetadata` + `applyMeta` +
  `pushMarkdown` trio does, but writes it into the snapshot; the mounted page
  picks artifact markdown / completeness / memoryState up from the store via
  the existing revision/hash-keyed effect.
- Session recovery (`withSessionRecovery` / `onSessionLost`) stays inside the
  `chatStream` generator in `artifact-runtime-config.ts` — unchanged.

### Slimmed runtime provider (M1)

`ArtifactSessionRuntimeProvider` keeps: editor history/undo/redo, the
`patchDraft` debounce (now calling `upsertSnapshot` with the PATCH response),
`onCompletenessChange` (an effect watching store completeness), and the
assistant-ui adapter. It loses: the six mirrored states, both sync effects, the
in-component SSE loop, and all pending-marker writes except the transitional
ones noted in M1 scope below.

Turn activity mapping (existing `workflowTurnActivity` is kept, fed from the
store):

```ts
const entry = useWorkflowDraftStore((s) => s.draftsById[draftId]);
const activity = workflowTurnActivity({
  localStreamActive: entry?.liveTurn !== null,          // spinner + isRunning
  backendTurnInProgress: entry?.snapshot.turnInProgress // resumed-turn status
});
```

`localStreamActive` now survives in-app navigation because it lives in the
store, not in a component's `isUpdating` state.

### Scenario walkthroughs

**Same-page turn.** Composer submit → `onNew` calls `runTurn` → `beginTurn`
appends user + placeholder assistant → progress events replace the last
assistant content → `completeTurn` writes final reply, artifact markdown,
revision/hash, completeness → editor effect syncs the artifact panel. Identical
UX to today.

**In-app nav away and back mid-turn.** Page unmounts; runner keeps consuming
and writing to the store. Returning re-bootstraps → `upsertSnapshot` sees
`liveTurn !== null` → thread untouched, snapshot meta refreshed → the thread
renders with all parts up to now and continues streaming; spinner from
`liveTurn`. On completion the runner writes the final state; if the teacher is
elsewhere in the app, the completion toast fires (M2 path) because
`mountedDraftId !== draftId`.

**Hard reload mid-turn.** JS context dies (runner, store). Bootstrap fetches the
draft: persisted messages, `turn_in_progress: true` → `upsertSnapshot` with
`liveTurn === null` replaces the thread from the snapshot → spinner via
`backendTurnInProgress`. The M2 poll observes completion → final
`upsertSnapshot` (+ toast if off-page). Parity with today; M3 upgrades this.

**Discard.** `discardWorkflowDraft` + `remove(draftId)` → redirect →
fresh bootstrap → `upsertSnapshot` populates the new draft key **before** the
runtime mounts (`ArtifactSessionPage` already upserts inside `loadBootstrap`
before `setData`). Even if a key is ever missing, the `EMPTY_THREAD` constant
makes it safe (Bug A cannot recur).

## File structure

### New files

```
frontend/src/features/workflow-drafts/turn-runner.ts
frontend/src/features/workflow-drafts/turn-runner.test.ts
backend/app/api: GET /api/workflow/active handler (M2, in routes.py)
backend/tests/test_api_workflow_active.py (M2)
```

### Modified

```
frontend/src/features/workflow-drafts/workflow-draft-store.ts      (entry shape, actions, gate)
frontend/src/features/workflow-drafts/workflow-draft-store.test.ts (rewritten)
frontend/src/features/workflow-drafts/workflow-chat-runtime.tsx    (stable selectors, thread from entry)
frontend/src/features/workflow-drafts/workflow-draft-bootstrap.ts  (draftId invariant)
frontend/src/features/workflow-drafts/workflow-draft-transport.ts  (snapshot → entry)
frontend/src/components/assistant-ui/artifact-session-runtime.tsx  (slimmed; onNew → runTurn)
frontend/src/components/klassenpilot/artifact-session-page.tsx     (setMountedDraftId lifecycle)
frontend/src/components/klassenpilot/pending-turn-notifier.tsx     (M2: poll /api/workflow/active)
frontend/src/components/klassenpilot/running-tasks-box.tsx         (M2: new data source)
frontend/src/lib/api.ts                                            (M2: getActiveWork client fn)
backend/app/services/workflow_drafts.py                            (M2: list_active across classes)
backend/app/services (sweep review store)                          (M2: list generating reviews)
backend/app/schemas/api.py                                         (M2: ActiveWorkResponse)
```

### Deleted

```
frontend/src/lib/pending-chat-turns.ts        (M2 — whole marker system)
frontend/src/lib/pending-chat-turns.test.ts   (M2)
shouldKeepLiveThread + its tests               (M1)
the two sync effects + six mirrored states     (M1)
```

## M1 — store-first refactor + turn runner (one PR)

Fixes Bug A and Bug B structurally; streaming survives in-app navigation by
design. Branches off the current branch.

**Commit 1 — surgical hotfixes (branch goes green immediately):**
- `EMPTY_THREAD` module constant in `workflow-chat-runtime.tsx` (Bug A).
- Stop clearing the pending marker in `onNew`'s catch when the error is a
  fetch abort (Bug B) — transitional; the whole path is rewritten next.

**Commit 2+ — the refactor:**

1. Store: entry shape (`snapshot`/`thread`/`liveTurn`), the six actions, the
   `liveTurn` gate in `upsertSnapshot`, `mountedDraftId`, `markTurnNotified`.
   Delete `shouldKeepLiveThread`.
2. `turn-runner.ts` as specced above.
3. Slim `ArtifactSessionRuntimeProvider`: delete mirrored states + sync
   effects; context values become store selectors; `onNew` builds content and
   delegates to `runTurn`.
4. `artifact-session-page.tsx`: set/clear `mountedDraftId` on mount/unmount;
   keep the bootstrap-upsert-before-mount ordering.
5. Transitional marker behavior: `markPendingChatTurn` moves into
   `runTurn` (written when the turn starts); it is **only** cleared by
   `failTurn` on a real stream failure. `baselineMessageCount` capture is kept
   as-is so the existing notifier keeps working until M2 replaces it.

**Explicitly out of M1:** notifier changes, backend changes, marker deletion.

### M1 tests

- Store unit tests: upsert gate (live vs no live turn), begin/progress/
  complete/fail sequences, `remove` + re-upsert, selector reference stability
  (same input → same reference; missing key → `EMPTY_THREAD` identity).
- Runner tests with fake async generators: progress→final happy path; error
  mid-stream → `failTurn` once; generator ends without final → `failTurn`;
  second `runTurn` for the same draft is a no-op; runner completes after the
  "page" (subscriber) is gone.
- Regression tests named for the bugs: Bug A (missing key never allocates),
  Bug B (consumer abort does not fail the turn or clear the marker).
- `npx tsc --noEmit && npx vitest run` green; backend suite untouched.

## M2 — global active-work endpoint + notifier re-drive (one PR)

### Backend

`GET /api/workflow/active` → `ActiveWorkResponse`:

```python
class ActiveWorkItem(BaseModel):
    kind: Literal["draft_turn", "memory_sweep"]
    class_id: str
    mode: str = ""                  # "ingest" | "plan" for draft_turn
    draft_id: str = ""
    session_id: str = ""            # backend_session_id
    lesson_date: str = ""
    lesson_title: str = ""
    turn_in_progress: bool = False
    status: str = ""                # sweep review status for memory_sweep
    updated_at: str = ""

class ActiveWorkResponse(BaseModel):
    items: list[ActiveWorkItem]
```

Implementation:
- `WorkflowDraftStore.list_in_progress()` — same query as
  `list_active_for_class` without the class filter, plus
  `AND turn_in_progress = 1` (running turns only; idle active drafts are not
  "running tasks" — class home already surfaces those).
- Memory Sweep: list reviews with `status == "generating"` from the sweep
  review store (add a `list_generating()` if absent).
- Response is workspace-scoped exactly like every other route (beta auth
  middleware unchanged).

### Frontend

- `PendingTurnNotifier` rewrite: poll `GET /api/workflow/active` every ~3 s
  while the tab is visible, plus on focus/visibilitychange. Keep the previous
  poll result in memory; on a `draft_turn` item disappearing (or flipping to
  complete), fetch that draft once, `upsertSnapshot` (thread still gated by
  `liveTurn`), and toast if `markTurnNotified(draftId, revision)` returns true
  **and** `mountedDraftId !== draftId`. Sweep items toast on
  `generating → ready/failed` transitions using the existing labels.
- Runner-side completion toast: `completeTurn` also calls `markTurnNotified`
  and toasts when `mountedDraftId !== draftId` (covers the in-context off-page
  case without waiting for a poll tick). The shared dedupe makes runner/poll
  racing harmless.
- `RunningTasksBox` renders the union of live runners and poll items.
  Dismissal becomes in-memory store state (decided 2026-07-12): a reload
  re-shows the box while tasks still run. Rationale: dismissal is derived UI
  state and must be recomputable, not persisted bookkeeping that can go stale —
  the same principle that removes the marker system.
- Delete `pending-chat-turns.ts`, its tests, and every call site
  (`markPendingChatTurn`, `markPendingMemorySweep`, `seenInProgress`,
  `baselineMessageCount`, `isPendingTurnOnCurrentPage`,
  `consumeCompletedPendingChatTurn`, dismissal keys, the 1 s storage poll).

### M2 tests

- Backend: endpoint test over a tmp SQLite store — in-progress drafts across
  two classes + one generating sweep; terminal/idle drafts excluded.
- Frontend: extract transition detection + toast dedupe into pure functions;
  unit-test running→complete transitions, first-observer semantics, and
  mounted-draft suppression. Delete the heuristic tests with the heuristics.

## M3 — live re-attach after reload (parked)

Not scheduled; specced so it can be picked up without re-deriving context.

- `GET /api/classes/{class_id}/{mode}/sessions/{session_id}/chat/stream/attach`:
  if `session_id` has a task in `_stream_tasks`, `_subscribe_stream` and stream
  until the `None` sentinel — the existing pub/sub machinery, ~30 lines. If no
  task is running, return 204 immediately (client falls back to the draft
  fetch it already does).
- Optional replay: a per-session ring buffer (`deque[str]`, cap ~512 lines) of
  published SSE lines, replayed to new subscribers before the live tail — this
  restores the reasoning/tool parts emitted while the client was disconnected.
- Frontend: on bootstrap with `turn_in_progress: true` and
  `!hasLiveRunner(draftId)`, start an attach consumer that feeds
  `applyTurnProgress`/`completeTurn` with `liveTurn.status = "attached"`.

## Manual smoke checkpoints (browser, dev stack)

- **A — same-page streaming:** two-turn Update-memory chat; reasoning + tool
  parts render live; artifact panel updates on completion.
- **B — in-app nav mid-turn:** send, click to class home mid-stream, return via
  "Update memory": parts retained and still advancing, spinner correct, final
  reply + artifact land without a thread reset. No toast (mounted draft).
- **C — hard reload mid-turn:** F5 mid-stream: persisted messages + spinner;
  completion lands via poll; navigating to class home before completion yields
  exactly one toast.
- **D — discard regression (Bug A):** discard draft → fresh session → type and
  send immediately. No console errors, reply streams.
- **E — concurrency:** start a plan turn and a memory turn in two classes;
  Running-tasks box lists both; each completion toasts once with the right
  label.

## Explicit non-goals

- Persisting reasoning/tool-call parts server-side (M3 ring buffer is the
  chosen partial answer).
- Cross-tab state sharing (BroadcastChannel/SharedWorker). Each tab keeps its
  own store; the M2 poll gives background tabs eventual consistency.
- Replacing assistant-ui / `useExternalStoreRuntime`.
- Any change to backend turn execution, model routing, executive verification,
  or the draft persistence model.
- Changing the artifact editor's undo/history model or the `patchDraft`
  debounce contract.

## Open questions for review

1. **Endpoint naming/shape:** `GET /api/workflow/active` vs
   `/api/running-tasks`. Any preference for including idle-but-active drafts
   (currently excluded)?
2. **Dismissal semantics:** ~~open~~ **Resolved 2026-07-12**: in-memory only;
   box reappears after reload while tasks still run.
3. **M1 transitional markers:** plan keeps `pending-chat-turns.ts` functioning
   through M1 so the old notifier works between the two PRs. Confirm, or merge
   M1+M2 if the interim state isn't worth preserving.
4. **Toast on same-context off-page completion:** specced to fire immediately
   from the runner (not waiting for a poll tick). Confirm the UX.
