# Port streaming D1–D4 onto chemistry tip (controlled file-by-file)

**Date:** 2026-07-20  
**Base:** `cloud/mvp-k12-quality` @ `4c29965` (Bavaria chemistry + MemV4 + k12 quality)  
**Reference tip:** `origin/claude/frontend-streaming-regression-ed1d2e` @ `7c04f8c`  
**Branch:** `cloud/port-streaming-d1-d4`  
**Method:** Controlled file-by-file port. Do **not** merge/rebase the entire streaming branch.

## Non-goals

- No blind merge of the streaming branch
- No H2 plan target-date, mock dashboard dates, or plan-review memory-copy commits
- No M3 live replay
- No WebSocket cancel
- No UI redesign beyond Running box / notifier wiring

## Architecture to preserve

| Track | Contract |
|---|---|
| **D1** | Module-level `turn-runner.ts` owns SSE. React only dispatches `runTurn` / `cancelTurn`. Unmount must **not** abort the backend turn. |
| **D2** | Zustand store is the sole client mirror. Pure `upsert(phase, snapshot)` reducer. Stable empty-thread identity (no `?? []`). |
| **D3** | Phases only: `streaming \| awaiting_backend \| settled`. Delete `workflow-turn-state.ts` (+ test). |
| **D4** | `GET /api/workflow/active` replaces `pending-chat-turns` sessionStorage markers. `PendingTurnNotifier` polls it. `running-jobs.ts` unions poll + local runners. |

Also: preserve HEAD timeout/error intent (`terminalStreamError` / settle-with-error from chemistry tip) inside the new runner path. Keep all MemV4/beta routes in `routes.py`; add `/workflow/active` **additively**.

## Path corrections on this tip

- SSE currently in: `frontend/src/components/assistant-ui/artifact-session-runtime.tsx` (not under `workflow-drafts/`)
- Markers: `frontend/src/lib/pending-chat-turns.ts` (+ test)
- Turn state: `frontend/src/features/workflow-drafts/workflow-turn-state.ts` (+ test)
- Reference on streaming tip: `turn-runner.ts`, `chat-errors.ts`, store rewrite, `running-jobs.ts`, backend active endpoint

## Task order (commit after each track when green)

### Task 1 — Backend D4

Port from tip `6b238ef` / `7c04f8c`:

- `list_in_progress` on `workflow_drafts`
- `list_generating` on `memory_sweep_reviews`
- Schemas `ActiveWorkItem` / `ActiveWorkResponse`
- `GET /api/workflow/active` in `routes.py` (additive; preserve MemV4/beta)
- `backend/tests/test_api_workflow_active.py` (cross-class, idle excluded, terminal excluded, empty)

Run pytest for that file. Commit.

### Task 2 — Store D2+D3

Port tip workflow-draft-store (+ tests). Keep one stable empty-thread selector. Delete `workflow-turn-state.ts` + test once no importers. Run vitest for store tests. Commit.

### Task 3 — Runner D1

Add `turn-runner.ts` + `chat-errors.ts` from tip. Thin `artifact-session-runtime` to `runTurn` / `cancelTurn`; Stop → `cancelTurn`. Map terminal/abort: Stop/drop → `awaiting_backend`; true terminal failure → settle with error. Adapt `chat-turn-scenarios.test.ts`. Run related vitest. Commit.

### Task 4 — Markers out

Add `getActiveWork()` to `api.ts`; `running-jobs.ts` + tests. Rewrite pending-turn-notifier to poll `/api/workflow/active` (~3s when visible+focused); `markTurnNotified` exactly-once; suppress toast for mounted draft. Wire `running-tasks-box`; remove all `pending-chat-turns` imports; delete `pending-chat-turns*`. Run tsc + vitest for touched areas. Commit.

### Task 5 — Docs + verify

Update `frontend/ARCHITECTURE.md` (Running jobs + Chat turn lifecycle). One-sentence note in `docs/agent_contracts.md` if appropriate. Full:

```bash
cd frontend && npx tsc --noEmit && npx vitest run
cd backend && .venv/bin/python -m pytest tests/test_api_workflow_active.py
```

Commit docs if needed. Push with `-u`. Prefer push + report branch name over opening a PR.
