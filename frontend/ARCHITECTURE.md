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
| Lib | `src/lib/` | API, SSE, pending-chat-turns, wiki links | React trees |
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

## Chat turn lifecycle (shared)

Module: [`workflow-turn-state.ts`](src/features/workflow-drafts/workflow-turn-state.ts)

Phases: `idle` → `streaming` → (`backend_running` | `complete` | `failed`)

Expected product behavior (all of plan / ingest / discuss):

1. On page while streaming: show reasoning + tool calls.
2. Leave and return in the same browser session while backend still running:
   keep already-streamed rich parts; show **Still working on your response…**.
3. When final arrives: spinner clears; reply visible.

UI mapping: [`workflow-turn-activity.ts`](src/features/workflow-drafts/workflow-turn-activity.ts)
→ Thread `isRunning` vs resumed spinner.

Runtime owner: [`artifact-session-runtime.tsx`](src/components/assistant-ui/artifact-session-runtime.tsx)
(`onNew` + SSE). Shells must not clear `turnInProgress` ad hoc.

**MVP non-goal:** backend persistence/replay of reasoning/tool traces.

## How to add a chat mode

1. Add mode to `ArtifactMode` in `artifact-runtime-config.ts` and wire stream/API.
2. Register backend `ArtifactSpec` / routes (contracts in `docs/agent_contracts.md`).
3. Thin `*Thread` welcome wrapper over shared `Thread` (see `plan-thread.tsx`,
   `discuss-thread.tsx`).
4. Shell: either `ArtifactSessionPage` + workspace (artifact workflows) or a
   chrome-only dock (`discuss-dock.tsx`) with a fixed-height Thread parent.
5. Ensure `pending-chat-turns` accepts the mode and `pendingTurnWorkflowHref`
   returns the right resume URL.
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
   (misconceptions first, then brief watch items; max 3). Upcoming uses mock
   dates (`class-home-mock-dates.ts`); notes are localStorage
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

## Pending jobs

- Markers: `src/lib/pending-chat-turns.ts` (includes `discuss`).
- Notifier: `PendingTurnNotifier` polls drafts and upserts the draft store.
- Running box: `running-tasks-box.tsx` (bottom-left); discuss FAB is bottom-right.

## Testing chat turns

Deterministic Vitest (no OpenAI / browser). The matrix is **3 workflows × 2 cases**:

| Case | Meaning | Expected observations |
|---|---|---|
| **1 — Stay on page** | Live SSE until final | Stop button while streaming; no “Still working…”; final reply visible; spinner off |
| **2 — Leave mid-turn** | Abort/unmount SSE; backend finishes | Rich reasoning/tools kept; “Still working…”; notifier upsert merges final reply; spinner off |

Workflows: `plan`, `ingest` (Update Memory), `discuss`.

Primary suite:

```powershell
cd frontend
npx vitest run src/features/workflow-drafts/chat-turn-scenarios.test.ts
```

Related unit coverage:

| File | Covers |
|---|---|
| [`chat-turn-scenarios.test.ts`](src/features/workflow-drafts/chat-turn-scenarios.test.ts) | 6 scenario observations (matrix above) |
| [`workflow-turn-state.test.ts`](src/features/workflow-drafts/workflow-turn-state.test.ts) | Phase → flags (streaming / backend_running / complete) |
| [`workflow-turn-activity.test.ts`](src/features/workflow-drafts/workflow-turn-activity.test.ts) | Stop vs Still-working mapping |
| [`workflow-draft-store.test.ts`](src/features/workflow-drafts/workflow-draft-store.test.ts) | Keep rich thread; merge final reply after leave/return |
| [`pending-chat-turns.test.ts`](src/lib/pending-chat-turns.test.ts) | Pending markers + discuss resume href |
| [`thread-background-status.test.ts`](src/components/assistant-ui/thread-background-status.test.ts) | Still-working banner copy |

Broader frontend check:

```powershell
cd frontend
npx tsc --noEmit
npx vitest run
```

HITL against Docker is optional for real-model confidence; the Vitest matrix is the
regression gate for the two cases.

Incident write-up (races, stuck Still-working, fixes):  
[`docs/chat_message_issue.md`](../docs/chat_message_issue.md).

## Design system

See [`DESIGN.md`](DESIGN.md). Prefer `components/ui/` and shared klassenpilot
controls; semantic tokens only; one solid primary CTA per action group.
