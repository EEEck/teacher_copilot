# Frontend Architecture

How KlassenPilot’s frontend is layered, and how to reuse chat/workflow pieces
without copy-paste. Pair with [`DESIGN.md`](DESIGN.md) (tokens/visual rules) and
[`src/components/assistant-ui/README.md`](src/components/assistant-ui/README.md)
(assistant-ui provenance).

## Mental model (NumPy-style)

Prefer **import + inject** over forking:

- Shared engines live in `features/workflow-drafts/` and `components/assistant-ui/`.
- Product shells (plan page, memory page, discuss dock) only supply **mode**,
  bootstrap, and chrome.
- Do **not** invent a second message list, SSE parser, or pending-turn system
  for a new workflow.

```text
app/pages  →  klassenpilot shells  →  assistant-ui Thread
                      ↓
            features/workflow-drafts (zustand + turn state)
                      ↓
            lib/ (API client, SSE, pending jobs)
                      ↓
            components/ui (design-system primitives)
```

## Layer map

| Layer | Path | Put here | Do not put here |
|---|---|---|---|
| Routes | `src/app/` | Page composition, URL params | Business logic, SSE |
| Domain UI | `src/components/klassenpilot/` | Timeline, dock, review, pending box | Raw Thread primitives |
| Chat UI | `src/components/assistant-ui/` | Thread, markdown, reasoning (registry) | Mode-specific bootstrap |
| Workflow feature | `src/features/workflow-drafts/` | Draft store, turn state, chat runtime adapter | Page layout |
| Lib | `src/lib/` | API, SSE, running-jobs, wiki links | React trees |
| Primitives | `src/components/ui/` | Button, Card, Input (design system) | Product copy |

## Zustand vs assistant-ui

- **`useWorkflowDraftStore`** is the session source of truth for:
  - draft metadata (`turnInProgress`, revision/hash, artifact markdown)
  - rich in-memory thread messages (`threadMessagesByDraftId`)
- **`useExternalStoreRuntime`** (`workflow-chat-runtime.tsx`) adapts that store
  into assistant-ui. Do not reintroduce `useLocalRuntime` remount keys as sync.
- Persisted API messages are still plain `{ role, content: string }`. Rich
  reasoning/tool parts are **client-session** overlays (MVP hybrid). Hard
  refresh will not restore Reasoning UI; turn flags + plain reply still resume.

## Chat turn lifecycle (runner-lite)

Design: the streaming port plan shipped; its design/build notes live in Git
history. This document is the current runner-lite reference.

- SSE owner: [`turn-runner.ts`](src/features/workflow-drafts/turn-runner.ts) —
  a module-level runner outside React. Navigation never touches a running
  turn; only the composer Stop button aborts the client stream.
- Turn phases live on the store (`turnByDraftId`):
  `streaming` → (`settled` | `awaiting_backend` → `settled`).
  `awaiting_backend` = Stop or a dropped connection while the backend may
  still finish; the store's snapshot reducer (`upsert`) merges the final
  reply when the completed draft arrives.
- Every backend snapshot (bootstrap, notifier poll) goes through
  `upsert`; thread handling is decided purely from (phase, snapshot) — see the
  reducer table in `workflow-draft-store.ts`.

Expected product behavior (all of plan / ingest / discuss):

1. On page while streaming: show reasoning + tool calls.
2. Leave and return in the same browser session: the runner keeps streaming —
   rich parts continue advancing; if the client stream ended (Stop/drop), show
   **Still working on your response…** until the reducer merges the reply.
3. When the turn finishes: spinner clears; reply visible.

UI mapping: [`workflow-turn-activity.ts`](src/features/workflow-drafts/workflow-turn-activity.ts)
→ Thread `isRunning` vs resumed spinner, fed from the store phase.

Intent dispatcher: [`artifact-session-runtime.tsx`](src/components/assistant-ui/artifact-session-runtime.tsx)
(`onNew` → `runTurn`, `onCancel` → `cancelTurn`; owns the page-local artifact
editor). Shells must not clear `turnInProgress` ad hoc.

**MVP non-goal:** backend persistence/replay of reasoning/tool traces (hard
refresh resumes with plain reply + turn flags).

## How to add a chat mode

1. Add mode to `ArtifactMode` in `artifact-runtime-config.ts` and wire stream/API.
2. Register backend `ArtifactSpec` / routes (contracts in `docs/agent_contracts.md`).
3. Thin `*Thread` welcome wrapper over shared `Thread` (see `plan-thread.tsx`,
   `discuss-thread.tsx`).
4. Shell: either `ArtifactSessionPage` + workspace (artifact workflows) or a
   chrome-only dock (`discuss-dock.tsx`) with a fixed-height Thread parent.
5. Ensure `running-jobs.ts` accepts the mode and `runningJobHref` returns the
   right resume URL.
6. **Never** fork Thread or invent a textarea chat.

## Shells

| Shell | Use |
|---|---|
| `ArtifactSessionPage` + `ArtifactSessionWorkspace` | Plan / Update Memory (dual-pane) |
| `DiscussDock` | Class-home helper (fixed viewport, min/expand/close, no artifact pane) |

Discuss dock is **chrome only**; chat behavior is the shared runtime + Thread.

## Class home dashboard

[`class-home-client.tsx`](src/app/classes/[classId]/class-home-client.tsx) is a light
dashboard, not a second product surface. Layout is three titled sections
(`ClassHomeSection`):

1. **Classroom dashboard** — brief hero + At a glance / Upcoming / My notes.
   Page title formats `chemie_9b_2026_27` → **Chemie 9b** with subtitle
   `2026/27 · STEM track` (or Language track). At a glance keeps 2×2 with a
   shortened unit label and larger metric type. Brief merges **Watch**
   (misconceptions first, then brief watch items; max 3). Upcoming shows an
   honest empty state ("No key dates yet") until a real dates source exists
   (assessment calendar is a later backlog item); notes are localStorage
   (`kp:class-notes:{classId}` via `class-home-notes.ts`) — browser-local only.
2. **Actions** — dismissible `StickyNote` + compact equal-width row
   (`inline-grid` + `auto-cols-[1fr]`, sized to the widest label; `size="lg"`).
   Core order: Plan, Update memory, Discuss (`variant="soft"`) with wow-tone
   hover copy (`CLASS_HOME_HOVER`); Sharpen assistant + Browse class files
   use `outline`. Sharpen (Memory Sweep route) shows a quiet “Draft saved…”
   subtitle when useful, an attention chip for generating/stale/failed, and a
   due chip after 5 days / never applied, resetting also on empty all-caught-up
   reviews (`memory-sweep-review-status.ts`).
3. **Lesson timeline** — larger section title with hover explanation; timeline
   card below. Toolbar row: Jump to month (left) + centered **+ plan next lesson**
   (links to `/plan`). One status chip per entry from
   `timeline-status-tone.ts` / `timeline-status-badges.ts`:
   - **Done** (dark green) — `taught` / results exist
   - **Upcoming** (black) — `planned`, date after today
   - **Add results** (amber) — `planned`, date today or past
   Row CTAs use matching button variants via `timelineMemoryAction`
   (`attention` / `inverse` / `outline`).

Discuss dock stays page chrome (FAB). App chrome: header hamburger opens Docs +
Settings (`/settings` is a placeholder). Do not add a feature kanban or
wiki-backed todos here without an explicit product decision.

## Running jobs

The backend is the source of truth for what is running — the client keeps no
sessionStorage turn markers. `PendingTurnNotifier` polls `GET /api/workflow/active`
(draft turns across all classes + generating memory sweeps) every 3s while the
tab is visible and focused.

- Notifier: `pending-turn-notifier.tsx`. When a job leaves the active list it
  fetches that draft once, `upsert`s it, and toasts — unless the draft is the
  one on screen (`mountedDraftId`). `markTurnNotified(draftId, revision)` makes
  the toast fire exactly once even if two polls race.
- Union: `src/lib/running-jobs.ts` merges poll items with this tab's live
  runners, so a turn shows the instant it is sent and a short turn that starts
  and finishes between polls is still visible. Local labels win (they carry the
  resolved lesson date/title).
- Running box: `running-tasks-box.tsx` (bottom-left); discuss FAB is bottom-right.

## In-thread workflow activity and review layout

Non-message workflow activity belongs in the same transcript flow as the
teacher conversation. `ThreadActivity` composes shared activity chrome around
Plan verification, Plan save (`ReviewBrief`), and Update Memory's save-review
brief; it is not a second chat window and must not introduce an independent
scroll region. Plan save must not use the workspace `reviewFileList` slot —
that path is reserved for legacy layout only; Plan matches Memory by mounting
`ReviewBrief` as in-chat activity.

Memory Sweep’s Simple brief (`lib/sweep-brief.ts`) groups cards as: Explicitly
requested, New memory, Changed (old → new), Already covered / not worth keeping,
and a separate last bucket **Student summary updates** — not mixed into Changed.

`ArtifactSessionWorkspace` keeps a selected review diff pinned above that
transcript. The diff owns 70% of the left workspace and scrolls internally;
the remaining 30% is the normal Thread/composer viewport. This applies to any
selected review file, not only `lesson_results.md`.

The backend `WorkflowDraft` remains the source of truth for artifact/review
state. The frontend's activity card explains current work but never authorizes
a write or substitutes for a final draft/revision refresh.

## Testing chat turns

Deterministic Vitest (no OpenAI / browser). The scenarios drive the REAL
runner + store with controllable fake SSE streams — **3 workflows × 8
scenarios** (stay, leave-mid-turn, hard refresh, Stop, dropped stream,
fail-before-content, duplicate send, discard-mid-turn). Key cases:

| Case | Meaning | Expected observations |
|---|---|---|
| **Stay on page** | Live SSE until final | Stop button while streaming; no “Still working…”; final reply visible; spinner off |
| **Leave mid-turn** | Runner keeps streaming (no abort) | Thread keeps advancing after unmount; final lands without any upsert; later flat upserts can't flatten the settled thread |
| **Stop / dropped stream** | Client stream ends; backend finishes | “Still working…”; reducer merges the reply into rich parts; spinner off |

Workflows: `plan`, `ingest` (Update Memory), `discuss`.

Primary suite:

```powershell
cd frontend
npx vitest run src/features/workflow-drafts/chat-turn-scenarios.test.ts
```

Related unit coverage:

| File | Covers |
|---|---|
| [`chat-turn-scenarios.test.ts`](src/features/workflow-drafts/chat-turn-scenarios.test.ts) | Runner-driven scenario observations (matrix above) |
| [`workflow-turn-activity.test.ts`](src/features/workflow-drafts/workflow-turn-activity.test.ts) | Stop vs Still-working mapping |
| [`workflow-draft-store.test.ts`](src/features/workflow-drafts/workflow-draft-store.test.ts) | Snapshot reducer rows, turn actions, meta preservation, selector stability |
| [`running-jobs.test.ts`](src/lib/running-jobs.test.ts) | Running-box union (poll ∪ local turns) + resume hrefs |
| [`thread-background-status.test.ts`](src/components/assistant-ui/thread-background-status.test.ts) | Still-working banner copy |

Broader frontend check:

```powershell
cd frontend
npx tsc --noEmit
npx vitest run
```

HITL against Docker is optional for real-model confidence; the Vitest matrix is the
regression gate for the two cases.

For a full fresh-sandbox beta acceptance pass, use the browser/trace/ledger
scenario design in
[`docs/superpowers/specs/2026-07-20-browser-workflow-runbook-design.md`](../docs/superpowers/specs/2026-07-20-browser-workflow-runbook-design.md).

Incident write-up (races, stuck Still-working, fixes):  
[`docs/chat_message_issue.md`](../docs/chat_message_issue.md).

## Design system

See [`DESIGN.md`](DESIGN.md). Prefer `components/ui/` and shared klassenpilot
controls; semantic tokens only; one solid primary CTA per action group.
