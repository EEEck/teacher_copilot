# KlassenPilot Beta-Readiness Audit — 2026-07-13

Branch: `claude/frontend-streaming-regression-ed1d2e` (executive-copilot branch
after merging `main` incl. the `feature/class-home-discussion` dashboard and the
`e53039e` chat-turn lifecycle fix).

Method: production mode (`APP_ENV=production`, `MODEL_PROFILE=production`,
strong model), sandbox copy of `teacher_wiki`, live browser run of all three
workflows with the mock ochem prompts, plus source review of the chat lifecycle,
class-home dashboard, design system, and backend stream/verification paths.

**Bottom line:** The agent quality is genuinely strong and beta-worthy — all
three workflows produced grounded, well-structured output, wrong-student-ID
handling works, and the executive-verification "advisory note" behavior fires
correctly. The risks are in the **frontend turn/hydration plumbing** and a set of
**content/polish bugs**, not in the agent. One intermittent class-home hang needs
a developer repro before beta.

---

## What works well (keep / do not regress)

- **Lesson planning** grounded in real class history. The ochem prompt triggered
  a 12-tool-call redox-history search; the plan cited the actual lesson dates
  (2026-05-14 … 2026-05-29), built the requested 15-min redox bridge, and
  produced board plan, quiz, activity, exit ticket, misconceptions, and
  post-lesson memory notes.
- **Wrong student ID handling — excellent.** Mock results included a non-roster
  `S-006`. The agent detected it, **held it back** from the draft (it was absent
  from "Student observations", which correctly kept only real S-014/S-021/S-033),
  and asked for confirmation instead of fabricating. The correction flow
  (`S-006 → S-046`) then applied cleanly. Matches the intended
  remove-confirm-never-fabricate policy.
- **Executive verification / advisory notes.** In Discuss, the agent flagged a
  real inconsistency unprompted: the snapshot claims "last lesson 2026-06-01" but
  no such lesson exists in the index (latest is 2026-05-29). Calm, correct,
  non-blocking — exactly the "verify continuously, interrupt selectively" intent.
- **Write-verification save flow** works: plan save opened the review UI, showed
  the correct target date (2026-09-28), and persisted to
  `lessons/2026-09-28/lesson_plan.md`.
- **Design system** is principled and consistent: a single token file
  (`globals.css`), documented palette/surfaces (`DESIGN.md`), semantic tokens,
  and one shared chat stack for plan/memory/discuss (no forked message lists).
- **Backend stream architecture is sound.** The model turn runs as a
  service-owned task; the HTTP SSE is only a subscriber, so navigating away or a
  dropped connection does not cancel the turn — it completes and writes the draft.
- **Typecheck + unit tests are green** (`tsc` clean; 18 chat-lifecycle tests pass).

---

## Findings by severity

### HIGH

**H1 — Intermittent class-home hang after chat turns.**

> 🟢 **Not reproducible after runner-lite (2026-07-14) — likely resolved.**
> Stress-tested on the runner-lite code: navigating to class home mid-turn,
> letting a turn complete while on class home (notifier/toast churn), and an
> aggressive rapid triple-bounce (memory↔home) during a live turn all render the
> dashboard cleanly ("At a glance" present, no `Loading class…` hang) across
> every attempt. H1 was a *client hydration failure* observed on the
> pre-runner-lite provider, which carried six mirrored `useState`s + two
> store-sync effects + an always-on recovery poll — exactly the render churn a
> hydration break stems from; runner-lite deleted all of it. Not a *guaranteed*
> fix (the original repro was non-deterministic/transient and cleared on
> restart), so keep it on a watch list and confirm once more against a
> production build, but it is no longer observable. This also removes the
> primary motivation for doing M2 (marker cleanup) *as an H1 fix* — M2 remains
> valuable as architectural cleanup, but there is no longer a bug driving it.

Original finding (pre-runner-lite):
After running the plan + memory workflows and navigating back to class home, the
dashboard got stuck on the `Loading class…` Suspense fallback (body = 28 chars).
It reproduced across a fresh browser tab and persisted through a page reload.
Key evidence and caveats:
- SSR HTML (40 KB) *did* contain the full dashboard shell ("At a glance",
  "Classroom dashboard", "Lesson timeline"), and all data endpoints returned 200
  quickly — so this is a **client-side hydration failure**, not a data-fetch hang.
- It did **not** reproduce from the durable wiki data: an identical class wiki
  (`diff -rq` shows zero class-file differences) in a clean workflow DB renders
  fine, and a planned future lesson (2026-09-28) renders fine on its own.
- A **backend restart cleared it**, pointing at transient in-memory/session state
  associated with the just-completed/active chat turn (the SSE churn below), not a
  deterministic data trigger.
- Action: reproduce with the Next.js error overlay expanded (the exact React
  error is in the dev overlay) and confirm against a production build
  (`next build && next start`). If it survives a prod build, it is a beta blocker;
  if it is a dev-HMR/overlay artifact, downgrade. I could not fully isolate it in
  the time available and do not want to assert a false root cause.

**H2 — Plan artifact "Target date" is wrong and persists to disk.**

> ✅ **RESOLVED 2026-07-14.** Two-part deterministic fix:
> (1) `empty_plan_template()` now emits `Target date: (set when saving)` instead
> of `date.today()` — no date is baked in at draft-creation time
> ([context_packs.py](../backend/app/teacher_agent/wiki/context_packs.py));
> (2) a new pure helper `normalize_plan_target_date(markdown, lesson_date)`
> ([parsing.py](../backend/app/teacher_agent/wiki/parsing.py), exposed on
> `WikiStore`) rewrites/inserts the heading at the save boundary. Wired into
> `PlanService.save` **before** `verify_artifact_for_write` (so the verifier
> sees the final artifact) and into the legacy `save_plan` path
> ([plan_service.py](../backend/app/services/plan_service.py)). 7 deterministic
> unit tests in `tests/test_plan_target_date.py` (replace stale date / replace
> placeholder / idempotent / insert-when-missing / no-op on empty date /
> template has no baked-in date / template→save composition). Offline suites
> (prompts, wiki tools/indexing, reference resolution, workflow drafts) stay
> green. **Test-infra note:** the pre-existing real-agent smoke tests
> (`test_api_plan::test_plan_full_flow`, `test_output_safety`,
> `test_api_stream`) fail in this worktree because they exercise the live agent
> rather than the stub (their openings/plans cite real seed data) — they fail
> identically with this fix stashed and with prod or dev `.env`, so they are not
> caused by H2; worth a separate look since they claim to run offline.

`empty_plan_template()` bakes in `date.today()`
([context_packs.py:746](../backend/app/teacher_agent/wiki/context_packs.py:746)):
`d = lesson_date or date.today().isoformat()`. The plan session starts before the
teacher picks the lesson date, and setting the date field afterward never
rewrites the artifact heading. Result: a plan saved under `lessons/2026-09-28/`
whose body reads `> Duration: 45 min | Target date: 2026-07-13`. Confirmed in the
persisted file. Fix: reconcile the heading with the chosen lesson date on
date-field change and/or at save. (Note: the ingest/results flow does this
correctly — it resolved 2026-09-28 from the message.)

**H3 — Chat turn lifecycle is functionally correct but architecturally fragile
("hacky", per `docs/chat_message_issue.md`).**

> ✅ **RESOLVED 2026-07-14 — runner-lite implemented, verified, and committed.**
> Commits `6aff82f` (audit + design) and `0c5744f` (implementation, 12 files,
> +1492/−858; `tsc` clean, 157 vitest green). The SSE loop moved out of React
> into a module-level turn runner
> ([turn-runner.ts](../frontend/src/features/workflow-drafts/turn-runner.ts));
> navigation no longer aborts a turn (only the Stop button does). The store gained
> a `turnByDraftId` phase map (`streaming`/`awaiting_backend`/`settled`) and a
> **single snapshot reducer** in `upsert` that decides thread handling purely from
> (phase, snapshot) — replacing the six content-guessing helpers below. The
> provider lost its six mirrored `useState`s, both sync effects, the unmount-abort,
> and the `finally` race-guard. Bug A (unstable selector → "Maximum update depth")
> fixed with a stable `EMPTY_THREAD`. Scenario tests rewritten to drive the **real
> runner + store** with controllable fake SSE streams (closes the "tests pass but
> browser breaks" gap). **All four acceptance criteria browser-verified** in dev +
> economy mode (see `implementation_plans/runner_lite_implementation_log.md` Step 6):
> (1) live reasoning + tool-call streaming; (2) leave-and-return keeps the thread /
> hard-refresh degrades to plain-text + spinner; (3) "Still working…" → final reply
> → spinner clears; (4) Running box + off-page completion toast. Bug A regression
> (discard → immediate send) confirmed clean.
>
> **What's still deferred (not blocking):** the sessionStorage marker system +
> `PendingTurnNotifier` remain — runner-lite demoted them to driving toasts only
> and the reducer makes their upserts unable to corrupt the thread. Fully removing
> that 4th source of truth (a global `GET /api/workflow/active` query) is **M2**;
> live re-stream after hard refresh (attach/replay) is **M3** (parked).

The original finding (below) is kept as the pre-fix record. The merged hybrid
worked — I saw it recover a stuck spinner after a mid-turn SSE reset — but it
sustained that correctness with a lot of moving parts that each new bug had added
to rather than removed:
- **Four sources of truth** for one turn: backend draft (SQLite), Zustand
  `threadMessagesByDraftId`, Zustand `draftsById` flags, and sessionStorage
  pending markers.
- **Six content-introspection/reconciliation helpers** in
  [workflow-draft-store.ts](../frontend/src/features/workflow-drafts/workflow-draft-store.ts)
  (`shouldKeepLiveThread`, `mergeFinalReplyIntoThread`, `lastAssistantLacksText`,
  `lastSnapshotAssistantReply`, `threadHasRichParts`, `messagesFromSnapshot`) plus
  a runtime `finally` race-guard ("never regress turnInProgress").
- **Three polling loops**: `PendingTurnNotifier` `/draft` poll (2 s) + its
  sessionStorage sync (1 s) + the runtime's own recovery `/draft` poll (2 s in
  [artifact-session-runtime.tsx:345](../frontend/src/components/assistant-ui/artifact-session-runtime.tsx:345)).
  The notifier and recovery poll overlap in the stuck-spinner case.
- The team's own `docs/chat_message_issue.md` §7 lists 7 still-open fragilities
  (notifier/toast-guard races, frozen boot flags, no browser E2E).
- **The unit tests pass but do not exercise this** — they lock the store/phase
  contract, not the SSE-reset / notifier / hydration integration where the real
  bugs (H1, and the stuck spinner) live. This is why "tests pass but the browser
  breaks."
- Recommendation: the store-first + turn-runner redesign in
  `implementation_plans/frontend_streaming_redesign_plan.md` (single `liveTurn`
  flag, one query endpoint, no sessionStorage bookkeeping) directly removes these
  classes of races. Worth doing before scaling beta.

### MEDIUM

**M1 — Mock data shown in the customer-facing dashboard.**
✅ **RESOLVED 2026-07-14** (commit `43a1949`). The "Upcoming" card now shows an
honest empty state ("No key dates yet") and the `class-home-mock-dates.ts`
module is deleted; no fake exam/excursion dates ship. A real source (assessment
calendar) is a later backlog item.

**M2 — Wrong workflow copy in the plan-save review.**
✅ **RESOLVED 2026-07-14** (commit `4f213d5`). The shared `ReviewBrief`
required-item tooltip no longer hard-codes "…required to save memory"; it uses
mode-agnostic copy ("This change is required and can't be skipped").

**M3 — SSE `ConnectionResetError` → stuck-spinner-until-poll.** On Windows dev the
SSE connection was reset mid-turn (asyncio proactor `WinError 10054`, benign log
noise). The backend turn completed correctly, but the UI showed
"Working through the request…" until a poll recovered it (several seconds). The
recovery works, but real deployments also reset SSE (proxies/timeouts), so the
recovery latency and the reliance on it are a beta UX consideration — see H3.

**M4 — Test suite gives false green.** See H3: green `tsc` + 18 passing lifecycle
tests coexist with real browser failures. Add at least one integration test that
simulates an SSE abort + notifier recovery, and ideally a Playwright pass over
the three workflows.

### LOW

**L1 — Timeline title mojibake — ❌ NOT A BUG (retracted 2026-07-14).** This was
a **false finding**: my own diagnostic harness, not the product. The em-dash is
correct UTF-8 end to end — verified: `lesson_plan.md` stores `E2 80 94`,
`read_text(encoding="utf-8")` + `extract_title` yield codepoint `U+2014`, the
HTTP response body carries `E2 80 94` (`Content-Type: application/json`), and the
browser's `fetch().json()` returns `U+2014` with no mojibake. The apparent
`â€"` came from inspecting the API with `curl … | python`, where Windows
`sys.stdin` defaults to cp1252 and mis-decoded the UTF-8 bytes. No code change.
(Lesson for future audits on Windows: pipe bytes, or force `PYTHONUTF8=1` /
`encoding="utf-8"`, before calling anything mojibake.)

**L2 — Seed-data phantom "last lesson".** Snapshot/course_state report
"Last taught: 2026-06-01", but no 2026-06-01 lesson exists (latest is
2026-05-29). Class home surfaces the phantom date; the agent correctly flagged it
(see positives). Clean up the seed wiki.

**L3 — Redundant polling + CORS preflight per poll.** Every `/draft` poll is an
`OPTIONS` + `GET` pair, and the notifier + runtime-recovery loops can both poll
the same draft. Minor overhead; folded into the H3 redesign.

---

## Workflow run log (evidence)

| Workflow | Result | Notes |
|---|---|---|
| Create lesson plan (ochem) | Pass (strong) | Grounded redox recap + full plan; bug H2 (target date). Saved to `lessons/2026-09-28/`. |
| Update memory (results w/ bad ID) | Pass (strong) | S-006 caught & held; correction to S-046 applied; recovered from SSE reset. |
| Discuss (class state) | Pass (strong) | Prioritized loops, named real students, advisory note caught the 2026-06-01 inconsistency. |

---

## Appendix A — Remediation plans for H1–H3 (added 2026-07-14)

Recommended order: **A.0 Bug-A hotfix (minutes) → A.3 H2 date fix (hours) →
A.1 H3 runner-lite (~1–1.5 days) → A.2 H1 repro protocol (gate before beta)**.

### A.0 — Prerequisite hotfix: the unstable selector (Bug A)

`useWorkflowChatRuntime` still selects
`state.threadMessagesByDraftId[draftId] ?? []`
([workflow-chat-runtime.tsx:29-31](../frontend/src/features/workflow-drafts/workflow-chat-runtime.tsx)).
A missing key allocates a fresh array every render → `useSyncExternalStore`
infinite loop → "Maximum update depth exceeded", swallowed by an error boundary.
Deterministically reachable after discard (`remove(draftId)`) on plan/memory
pages. Fix now regardless of everything else:

```ts
const EMPTY_THREAD: ThreadMessageLike[] = [];
const messages = useWorkflowDraftStore(
  (state) => state.threadMessagesByDraftId[draftId] ?? EMPTY_THREAD,
);
```

Plus one regression test asserting selector reference identity for a missing key.

### A.1 — H3 design: "runner-lite" (review draft v2, 2026-07-14)

Design only — implementation follows sign-off. This v2 supersedes the first
A.1 sketch after working the edge cases: two claims in v1 were wrong and are
corrected here (§A.1.4, §A.1.13). Deltas vs the original redesign plan
([implementation_plans/frontend_streaming_redesign_plan.md](../implementation_plans/frontend_streaming_redesign_plan.md))
are listed at the end.

**Acceptance criteria (agreed):**
1. Reasoning + tool calls stream live via SSE while the teacher is on the chat.
2. Leaving the page keeps what already streamed in the browser; losing the rich
   parts on a **hard refresh is acceptable**.
3. While the backend finishes, show the "Still working on your response…"
   status; when it finishes, the final reply appears and the spinner clears.
4. Completion toasts / Running-tasks box keep working as today.

#### A.1.1 Root cause, restated

The SSE loop lives inside the component (`onNew`) and the stream is *aborted on
unmount*. Every navigation therefore manufactures an ambiguous state — "stream
ended, no final event" — which needs `resolveClientStreamEnd` to guess the
phase, `mergeFinalReplyIntoThread` to patch the missing reply, a `finally`
race-guard against the notifier, and a recovery poll for when the guesses miss.
Each fix adds a reconciler because the architecture *creates* the state that
needs reconciling.

#### A.1.2 Design principles

- **P1 — One writer per fact.** Backend draft = durable truth. The turn runner
  is the only writer of a draft's thread while it owns it. `store.upsert` is
  the only entry point for backend snapshots, and its behavior is a pure
  function of (ownership state, snapshot) — the reducer table in §A.1.4.
  Components are readers plus user-intent dispatch (send / stop / edit /
  discard).
- **P2 — Ambiguity is resolved by asking the backend, never by inspecting
  thread content.** When the client cannot know the turn's fate (stream died),
  it polls the draft; it does not count messages or detect "rich parts".
- **P3 — The page is not the process.** Navigation changes nothing about a
  running turn. Only two things interrupt a client stream: the Stop button and
  process death (refresh/close). This is what deletes the unmount-abort and
  everything downstream of it.

#### A.1.3 State model

```ts
// Zustand store — reactive render state
type TurnPhase = "streaming" | "awaiting_backend" | "settled";
type TurnRecord = {
  phase: TurnPhase;
  startedAt: number;
  /** pending-chat-turns marker key; runner clears it only on hard failure */
  pendingKey?: string;
};

type WorkflowDraftState = {
  draftsById: Record<string, WorkflowDraftSnapshot>;   // + readyToSave, lastChangeSummary
  threadMessagesByDraftId: Record<string, ThreadMessageLike[]>;
  turnByDraftId: Record<string, TurnRecord>;           // NEW — ownership + phase
  // actions: §A.1.5
};

// turn-runner.ts module scope — NOT in the store
const controllers = new Map<string, AbortController>();
```

Decisions embedded here:
- **AbortControllers stay out of the store** (non-serializable, not render
  state); the store holds only the reactive `phase`. `hasLiveRunner(draftId)` =
  `controllers.has(draftId)`.
- The two existing maps keep their shape (minimal diff vs the original plan's
  merged-entry refactor). `WorkflowDraftSnapshot` gains the final-result meta
  the provider currently holds in `useState` (`readyToSave`,
  `lastChangeSummary`), so `applyMeta` mirroring can be deleted.
- Store keying is unchanged: `workflowDraftRuntimeKey(draftId, sessionId)` —
  `draft_id` exists at bootstrap for all three modes (verified; the discuss
  dock already throws if it's missing).

**Phase meanings and transitions:**

| Phase | Meaning | Set by | UI |
|---|---|---|---|
| *(no record)* | No turn ran in this JS context | — | snapshots hydrate the thread freely |
| `streaming` | Runner alive, SSE flowing | `beginTurn` (runner) | Stop button, live parts |
| `awaiting_backend` | Client stream ended without final, backend may still be working (Stop pressed, or connection dropped mid-stream) | runner catch/end | "Still working on your response…" |
| `settled` | This context knows the turn's outcome; thread is locally authoritative | `completeTurn` / `failTurn` (runner) or reducer resolution of `awaiting_backend` | idle |

```
(none) → streaming → settled                      (final SSE event arrived)
                   → awaiting_backend → settled   (Stop / stream drop; resolved by snapshot)
                   → settled (failed)             (stream error with nothing streamed)
settled → streaming                               (next send appends to the same thread)
any → (none)                                      (discard → remove())
```

**The `settled` rule (new in v2, the important correction):** a thread that a
runner has written in this JS context is *permanently* locally authoritative —
`settled` is not cleared when the turn ends. Rationale: chat threads are only
ever mutated by turns; a persisted snapshot can never be *richer* than what
this tab streamed, only flatter (plain text without reasoning/tool parts). v1's
"clear the flag on completion" was wrong: the pending marker is still alive
after a successful turn (the notifier consumes it later), so the notifier's
always-upsert would have replaced the just-streamed rich thread with the plain
persisted copy — exactly the bug class we are removing. With `settled`,
notifier/bootstrap upserts refresh flags and artifact but never the thread.
Hard refresh clears the store, so criterion 2's "hard refresh may lose rich
parts" falls out naturally.

> **Documented limitation (accepted 2026-07-14):** because a `settled` thread
> is locally authoritative, a tab left open on a draft will not show messages
> added to that same draft from *elsewhere* (a second tab or device) until it
> is refreshed. No product feature mutates chat threads server-side today, and
> the backend rejects overlapping turns per session, so this only affects the
> deliberate two-tabs-on-one-draft case. Any future feature that edits chat
> history server-side must invalidate the `settled` record.

#### A.1.4 The snapshot reducer (heart of the design)

Every snapshot ingestion — bootstrap, `PendingTurnNotifier`, recovery poll,
`patchDraft` response — goes through `upsert(snapshot)`, which always updates
`draftsById` and decides the thread purely from this table:

| `turnByDraftId[id]` | Snapshot says | Thread action | Phase after |
|---|---|---|---|
| *(none)* | anything | replace from `snapshot.messages` — **one guard**: never replace a non-empty thread with an empty snapshot (stale-fetch protection) | *(none)* |
| `streaming` | anything | untouched (runner owns it) | `streaming` |
| `awaiting_backend` | `turn_in_progress` | untouched | `awaiting_backend` |
| `awaiting_backend` | complete (`latest_turn_complete && !turn_in_progress`) | `mergeFinalReplyIntoThread(thread, snapshot.messages)` | `settled` |
| `awaiting_backend` | interrupted (`!latest_turn_complete && !turn_in_progress`) | append error text to last assistant message | `settled` |
| `settled` | anything | untouched | `settled` |

This one reducer replaces `shouldKeepLiveThread`, the scattered merge calls,
and the `finally` race-guard — and it is where the second v1 correction lives:

**`mergeFinalReplyIntoThread` survives, for exactly one row.** v1 claimed it
could be deleted because "the final always arrives in-context". That misses two
real paths where the client stream dies but the backend finishes: the Stop
button, and a dropped SSE connection (observed live during this audit — M3;
proxies/timeouts will do the same in production). In both, the thread has rich
parts but no final text, and the reply must be attached when the completed
snapshot arrives. The function is kept **only** as this reducer row — triggered
by an explicit phase, never by content guessing. (`lastAssistantLacksText`,
`lastSnapshotAssistantReply` as standalone gate logic, and
`threadHasRichParts` are still deleted.)

Because resolution lives in the reducer, it works from *any* snapshot source:
the recovery poll while the page is open, the notifier while it's not, or the
bootstrap upsert on the next visit. No path needs its own merge logic.

#### A.1.5 Store actions (runner-facing)

- `beginTurn(draftId, userContent, placeholderContent, pendingKey)` — appends
  user + placeholder assistant message to the thread, sets
  `{phase: "streaming", startedAt, pendingKey}`, sets snapshot flags to the
  `streaming` mapping from `flagsForPhase`.
- `applyTurnProgress(draftId, content)` — replaces the last assistant
  message's content (same `replaceLastAssistantContent` as today).
- `completeTurn(draftId, result: ArtifactChatResult)` — writes final reply
  content, artifact markdown/revision/hash, completeness, memoryState,
  readyToSave, lastChangeSummary into the snapshot; phase → `settled`; flags →
  `complete`. Leaves the pending marker for the notifier (unchanged toast
  behavior).
- `markAwaitingBackend(draftId)` — phase → `awaiting_backend`; flags →
  `backend_running`.
- `failTurn(draftId, friendlyMessage)` — writes/keeps error text per today's
  partial-content rules; phase → `settled`; flags → `failed`; **clears the
  pending marker** (the only runner-side marker clear).
- **Guard on all of the above:** no-op if the draft entry no longer exists
  (discard while a background turn is streaming calls `cancelTurn` + `remove`;
  a late runner event must not resurrect the draft).

#### A.1.6 Turn runner contract

`frontend/src/features/workflow-drafts/turn-runner.ts`:

```ts
export const hasLiveRunner = (id: string) => controllers.has(id);
export const cancelTurn = (id: string) => controllers.get(id)?.abort();

export async function runTurn(args: {
  draftId: string; message: string; currentMarkdown: string;
  attachments?: SessionAttachment[];
  chatStream: ChatStreamFn;   // session recovery stays wrapped inside (unchanged)
  pendingKey: string;         // page writes the marker; runner only fails it
}): Promise<void> {
  if (controllers.has(args.draftId)) return;       // one turn per draft
  const ctl = new AbortController();
  controllers.set(args.draftId, ctl);
  const s = useWorkflowDraftStore.getState();
  s.beginTurn(args.draftId, userContent, placeholder, args.pendingKey);
  let gotFinal = false, streamedContent = false;
  try {
    for await (const chunk of args.chatStream({ ...args, signal: ctl.signal })) {
      if (chunk.kind === "progress") {
        streamedContent ||= !isPlaceholderAssistantContent(chunk.content);
        s.applyTurnProgress(args.draftId, parts(chunk));
      } else { s.completeTurn(args.draftId, chunk.result); gotFinal = true; }
    }
    if (!gotFinal) s.failTurn(args.draftId, CHAT_ERROR_REPLY);
  } catch (err) {
    if (gotFinal) return;                              // late transport noise
    if (ctl.signal.aborted || streamedContent) {
      s.markAwaitingBackend(args.draftId);             // Stop, or mid-stream drop
    } else {
      s.failTurn(args.draftId, friendlyChatError(err)); // never started
    }
  } finally { controllers.delete(args.draftId); }
}
```

Note the stream-end classification (`gotFinal` / `aborted` /
`streamedContent`) is the *same logic* as today's `resolveClientStreamEnd` —
the design keeps that decision (it is genuinely necessary: a mid-stream drop is
indistinguishable from a backend still working) but confines it to the runner,
where it cannot race the notifier: it only ever produces a *phase*, and the
reducer resolves the phase against backend truth.

#### A.1.7 UI derivation

`workflowTurnActivity` is kept, fed from the store instead of component state:

```ts
const turn = useWorkflowDraftStore((s) => s.turnByDraftId[key]);   // stable refs
const snap = useWorkflowDraftStore((s) => s.draftsById[key]);
workflowTurnActivity({
  localStreamActive: turn?.phase === "streaming",
  backendTurnInProgress:
    turn?.phase === "awaiting_backend" ||
    (turn == null && snap?.turnInProgress === true),   // post-refresh case
});
```

- `runtimeIsRunning` (Stop button shown) ⇐ `streaming`.
- `showResumedTurnStatus` ("Still working on your response…") ⇐
  `awaiting_backend`, or refresh-with-turn-in-progress.
- The six mirrored `useState`s and both sync effects in
  `ArtifactSessionRuntimeProvider` are deleted; the discuss dock reads live
  flags from the store, which also fixes the frozen `boot.turnInProgress`
  problem (issue-doc §7.2). The provider keeps: editor history/undo,
  `patchDraft` debounce, `syncStatus`, session-recovery plumbing.
- `onEdit` / assistant-ui `setMessages` remain direct thread writes — they are
  user intent, allowed when no turn is `streaming` (composer is disabled while
  one is).

**Recovery poll** (kept, page-scoped, now condition-crisp): while the page is
mounted and `turn?.phase === "awaiting_backend"` **or** (`turn == null` &&
`snap.turnInProgress`), poll `fetchDraft` every 2 s and feed the result to
`upsert`. Off-page, the notifier's existing poll feeds the same reducer; on
next page mount, the bootstrap upsert does. Three entry points, one rule.

#### A.1.8 Deleted / kept / unchanged

| Component | Fate |
|---|---|
| Unmount-abort effect ([artifact-session-runtime.tsx:245-250](../frontend/src/components/assistant-ui/artifact-session-runtime.tsx)) | **deleted** — P3 |
| `finally` race-guard + flag writes (lines ~550-599) | **deleted** — reducer owns resolution |
| `resolveClientStreamEnd` (component-level) | **absorbed** into runner catch-classification |
| `shouldKeepLiveThread` + `threadHasRichParts` + count heuristics | **deleted** — reducer table |
| `mergeFinalReplyIntoThread` | **kept, one reducer row only** (Stop / stream-drop) |
| `lastAssistantLacksText`, `lastSnapshotAssistantReply` | deleted as gates (merge keeps its internal reply lookup) |
| Six mirrored `useState`s + 2 sync effects | **deleted** — store selectors |
| Recovery poll | **kept**, crisp condition (§A.1.7) |
| `pending-chat-turns.ts`, `PendingTurnNotifier`, toast heuristics, Running box | **untouched** (M2 deletes them; notifier's always-upsert now flows through the reducer and is harmless by construction) |
| `workflow-turn-state.ts` (`flagsForPhase`) | kept as the flag vocabulary |
| Stop button `onCancel` | kept → `cancelTurn(draftId)` |
| Session recovery (`withSessionRecovery` inside `chatStream`) | unchanged |
| Artifact editor / undo / `patchDraft` | unchanged |

#### A.1.9 Scenario walkthroughs

1. **Stay on page:** send → `beginTurn` → progress parts render → final →
   `completeTurn` (reply + artifact + flags) → `settled`. Notifier later
   consumes the marker; its upsert hits the `settled` row — thread untouched,
   toast suppressed on current page (existing logic).
2. **Leave mid-turn (in-app), return:** runner unaffected by unmount; parts
   keep streaming into the store. Return → bootstrap upsert hits `streaming`
   row (thread untouched) → thread renders mid-stream and continues. *Better
   than today* (today the parts freeze at the moment of leave).
3. **Leave mid-turn, stay away:** runner completes in background →
   `completeTurn`. Notifier sees complete draft, consumes marker, toasts
   ("Finished updating memory…"), its upsert hits `settled`. Running box entry
   clears. Unchanged UX.
4. **Hard refresh mid-turn:** store empty, no runner. Bootstrap upsert hits the
   *(none)* row → plain persisted messages (user message is persisted at turn
   start) + "Still working…" via `snap.turnInProgress`. Recovery poll →
   complete snapshot → *(none)* row again → thread replaced with full plain
   messages, spinner clears. Exactly criterion 3.
5. **Stop button:** `cancelTurn` → abort → `markAwaitingBackend` → "Still
   working…" (backend intentionally keeps running — unchanged semantics).
   Completed snapshot (poll or notifier) → merge row → reply attached to the
   rich thread → `settled`.
6. **SSE connection drops mid-turn** (observed live in this audit): runner
   catch, not aborted, `streamedContent` → `awaiting_backend` → same as (5).
   Today this path needs the notifier's stuck-spinner special case; here it is
   just a reducer row.
7. **Stream fails before anything arrives:** `failTurn` → error reply in
   thread, marker cleared (no false toast), flags `failed`, `settled`.
8. **Discard, then fresh session (Bug A scenario):** discard → `cancelTurn` +
   `remove` → new bootstrap upserts under the new draftId before the runtime
   mounts; selector fallback is the stable `EMPTY_THREAD` (A.0). Late events
   from a cancelled runner no-op (action guard).
9. **Two drafts in parallel** (plan + memory in two tabs/pages of one context):
   independent `TurnRecord`s and controllers; no shared state beyond the maps.

#### A.1.10 Invariants (each becomes a test)

- **I1** A snapshot upsert never modifies a thread whose `TurnRecord` exists
  (any phase) — except the two explicit `awaiting_backend` resolution rows.
- **I2** No permanent spinner: `streaming` implies a live controller (runner
  clears it in `finally`); `awaiting_backend` always has a poller (page poll,
  notifier, or next bootstrap) driving it to `settled`; refresh-case spinner is
  cleared by the *(none)* row on a complete snapshot.
- **I3** Only `cancelTurn` or process death interrupt a client stream.
- **I4** The pending marker is cleared exactly once: by `failTurn` or by the
  notifier's consume. (Today it can also be cleared by the unmount-abort path —
  that's the H-audit Bug B.)
- **I5** Store actions on a removed draft are no-ops.
- **I6** Selectors return stable references for missing keys (A.0).

#### A.1.11 Risks & mitigations

- **assistant-ui `ExternalStoreRuntime` interplay:** messages identity now
  changes only via store writes (fewer, batched) — should reduce re-render
  churn, but verify Stop-button enable/disable and composer state flips in the
  browser pass (checkpoint list below).
- **Discard racing a background turn:** covered by I5 + `cancelTurn` on
  discard; add a scenario test.
- **Multiple browser tabs:** unchanged vs today (per-tab stores and
  sessionStorage; backend serializes turns per session via `turn_in_progress`
  and the second tab's send gets the existing `turn_in_progress` SSE error).
- **React StrictMode double-invoke:** `runTurn`'s registry makes the second
  invocation a no-op by design.

#### A.1.12 Test design

- **Reducer unit tests:** one per row of the §A.1.4 table (6 rows + the
  empty-snapshot guard) — pure functions, no React.
- **Runner unit tests** with fake async generators: progress→final; final then
  transport error (late-noise row); error after content → `awaiting_backend`;
  error before content → `failTurn`; abort → `awaiting_backend`; duplicate
  `runTurn` no-op; events after `remove` no-op.
- **Scenario tests** (rework of the existing 6, still 3 modes × cases, plus
  new): leave-mid-turn now asserts the thread *keeps growing* after unmount and
  the final lands without any upsert; hard-refresh scenario (fresh store +
  in-progress snapshot → poll → plain thread + spinner clear); Stop scenario
  (abort → merge on complete). The old Case-2 tests that simulate
  abort-on-leave are retired with the behavior.
- **Regression tests:** Bug A selector identity (I6); marker single-clear (I4).
- **Browser pass (manual, against prod build):** scenarios 1, 2, 4, 5, 8 above
  + toast on scenario 3.

#### A.1.13 Corrections vs. v1 of this appendix, and deltas vs. the original plan

v1 corrections (both found while working the reducer table):
1. `liveTurn` must not clear on completion → the `settled` ownership rule;
   otherwise the notifier's post-completion upsert flattens the rich thread.
2. `mergeFinalReplyIntoThread` cannot be fully deleted → kept for the
   `awaiting_backend` resolution row (Stop button, dropped SSE).

Deltas vs. [implementation_plans/frontend_streaming_redesign_plan.md](../implementation_plans/frontend_streaming_redesign_plan.md):
- Store keeps its two-map shape + a new `turnByDraftId` map (the plan's
  merged-entry refactor is deferred — smaller diff, same invariants).
- Markers + notifier remain (M2 unchanged as follow-up: global
  `GET /api/workflow/active`, delete `pending-chat-turns.ts`).
- M3 (attach/replay after refresh) unchanged as a parked follow-up; nothing in
  runner-lite blocks it — the reducer's *(none)* row is exactly where an
  attach-fed live thread would plug in.
- Effort unchanged: ~1–1.5 focused days incl. tests + browser pass, after
  design sign-off.

#### A.1.14 Design questions — ALL RESOLVED 2026-07-14

1. **Stop button = "stop watching", not "cancel the job" — RESOLVED: keep for
   this milestone.** Server-side cancellation is important product behavior and
   is now a **v1.1 backlog item** ("Server-side chat turn cancellation" in
   [implementation_plans/product_backlog.md](../implementation_plans/product_backlog.md)).
2. **`settled` permanence — RESOLVED: accepted as documented limitation.**
   See the limitation callout in §A.1.3 (second tab/device won't see new
   messages on the same draft until refresh; server-side thread edits would
   need to invalidate `settled`).
3. **Merge vs. flatten on Stop/connection-drop — RESOLVED: merge.** Preserve
   the watched reasoning; costs nothing (function exists, either choice is one
   reducer row).
4. **Toast bookkeeping (`seenInProgress`/`baselineMessageCount`) — RESOLVED:
   keep only until M2.** M2 (backend "what's running" endpoint replacing
   sessionStorage markers) is the committed cleanup; do not extend the marker
   system's life beyond that.
5. **Background failure toast — RESOLVED: add it.** When a turn fails off-page,
   fire an error toast ("… didn't finish — open the draft to retry") alongside
   writing the error into the thread. In scope for the runner-lite
   implementation (lives in the runner's `failTurn` path).

#### A.1.15 Best-practice pattern review (2026-07-14)

Checked the design against current industry patterns for MVP chat streaming
with background continuation; conclusions and the one watch-item they add:

- **"Disconnect ≠ stop" is the established rule.** Resumable-streaming guides
  are explicit: *route/page cleanup is a disconnect, not a stop; only an
  explicit user action should call stop* — a client that aborts on navigation
  and treats it as failure is the anti-pattern. This is precisely P3 and the
  deletion of the unmount-abort. (Ably's resumable-LLM-streaming series; AI SDK
  resume docs.)
- **Generation decoupled from the HTTP request is the standard server shape.**
  LibreChat's `GenerationJobManager` and the AI SDK/`resumable-stream` pattern
  (job + stream survive client disconnects; clients re-attach) match our
  backend's service-owned `_stream_tasks` + subscriber queues. Our backend
  already implements the recommended architecture; runner-lite makes the client
  stop fighting it.
- **True stream resumption after refresh requires per-token persistence**
  (Redis/last-event-id replay) and is acknowledged as a cost/complexity
  trade-off — validating our decision to park it as M3 (attach + ring buffer)
  rather than build it into the MVP. Our poll-on-refresh is the accepted
  lightweight fallback.
- **assistant-ui `ExternalStoreRuntime` guidance** matches the store-first
  direction: host-owned message state, immutable array updates, stable
  selector references (their docs specifically recommend `useShallow`-style
  stable snapshots — our I6), and full handler wiring incl. `onCancel`.
  **Watch item for the browser pass:** upstream issue #2603 reports `isRunning`
  glitches on `ExternalStoreRuntime` when messages exist — explicitly verify
  Stop-button/typing-indicator behavior in scenarios 1 and 2.
- **Optimistic append + authoritative snapshot reconciliation** (our reducer)
  is the normal chat pattern; no source suggests content-introspection guards
  like the ones being deleted.

Sources: [AI SDK — Chatbot Resume Streams](https://ai-sdk.dev/docs/ai-sdk-ui/chatbot-resume-streams),
[Ably — resumable LLM streaming across reconnects](https://ably.com/blog/resumable-llm-streaming-session-recovery-across-reconnects),
[Ably — resume tokens & last-event IDs](https://ably.com/blog/resume-tokens-last-event-id-llm-streaming-reconnection),
[LibreChat — resumable streams](https://www.librechat.ai/docs/features/resumable_streams),
[LibreChat data flow](https://deepwiki.com/danny-avila/LibreChat/3.4-data-flow),
[assistant-ui — ExternalStoreRuntime](https://www.assistant-ui.com/docs/runtimes/custom/external-store),
[assistant-ui issue #2603](https://github.com/assistant-ui/assistant-ui/issues/2603),
[zknill — SSE token streams: resumable, cancellable, multi-device](https://zknill.io/posts/everyone-said-sse-token-streaming-was-easy/).

### A.2 — H1: class-home hang — repro & fix protocol

Facts assembled so far: SSR HTML complete; all data endpoints 200 in <40 ms; no
console errors; hang appeared while an ingest turn was in progress and
persisted after completion, across reloads **and a fresh tab**; identical wiki
data renders fine in isolation; cleared only when both dev servers restarted;
frontend log showed repeated Fast Refresh rebuilds without file edits. Verified:
the closed Discuss dock does **not** mount the chat runtime, so Bug A is not a
confirmed cause here (it remains a real crasher on plan/memory pages).

Protocol:
1. Land A.0 first (removes the one *known* infinite-loop crasher from the tree).
2. **Prod-build gate:** `next build && next start` against the same backend;
   script the trigger (start ingest turn → navigate to class home mid-turn →
   wait for completion → reload). If it never reproduces in a prod build,
   reclassify as dev-tooling annoyance (HMR/webpack chunk desync — consistent
   with the unexplained Fast Refresh churn) and drop from the beta-blocker list.
3. If it reproduces: capture the real error — `window.addEventListener('error'|
   'unhandledrejection')` logger injected at page top (the overlay's shadow DOM
   resisted scripted extraction), React DevTools ⚛ profiler for the suspended
   boundary, and the expanded dev-tools overlay.
4. Suspect list to check against the captured error, in order: `useSearchParams`
   /Suspense interplay in [page.tsx:15](../frontend/src/app/classes/%5BclassId%5D/page.tsx)
   + the `?discuss=open` `router.replace` effect; hydration mismatch from
   `new Date()` defaults in `timelineStatusTone`/`timelineMemoryAction` once a
   *planned* entry exists; `PendingTurnNotifier` upsert storm at turn completion
   re-rendering a subscribed component in a loop.
5. Exit criteria: named root cause + regression test, or documented
   dev-only classification with the prod-build evidence attached.

### A.3 — H2: plan "Target date" fix

Root cause chain: `empty_plan_template(store, lesson_date=None)` bakes
`date.today()` into the artifact header
([context_packs.py:745-749](../backend/app/teacher_agent/wiki/context_packs.py));
the plan session starts before a date exists; the date field is only used as
`SavePlanRequest.lesson_date` for the file location
([plan_service.py:206-251](../backend/app/services/plan_service.py)) — the
header line is never reconciled, so the wrong date persists into
`lessons/{date}/lesson_plan.md`.

Fix (deterministic, server-side):
1. Template honesty: `Target date: {lesson_date or "(set when saving)"}` — stop
   fabricating today's date at session start.
2. Normalization at the write boundary: in `PlanService.save`, right after
   `plan_markdown` is resolved from the validated draft row (~line 235) and
   **before** `verify_artifact_for_write` (so the verifier sees the final
   artifact), rewrite/insert the header's `Target date:` to the validated
   `lesson_date`. Small pure helper, e.g.
   `normalize_plan_target_date(markdown, lesson_date)` — replaces an existing
   `Target date: …` token in the blockquote line, inserts the line if missing,
   idempotent.
3. Apply the same helper in the legacy `save_plan(LessonPlan)` path
   ([plan_service.py:300-301](../backend/app/services/plan_service.py)).

Tests: unit (replaces wrong date; inserts when missing; idempotent; placeholder
handled); API test — save with `lesson_date=2026-09-28`, assert the persisted
file body contains `Target date: 2026-09-28` and not today. Frontend unchanged
(draft header self-corrects on save; live-editing the header pre-save is
optional polish, not part of this fix). Effort: ~1–2 hours.

## Environment changes made for this audit (revert before normal use)

In `backend/.env`: `WIKI_ROOT=teacher_wiki_sandbox` (was `teacher_wiki`),
`APP_ENV=production` (added), `BETA_ENABLED=false` (was `true`),
`CORS_ORIGINS=["http://localhost:3001"]`. Created `backend/teacher_wiki_sandbox/`
and `teacher_wiki_sandbox2/` (gitignored). Added `.claude/launch.json` (ports
8011/3001). No production wiki data was modified.
