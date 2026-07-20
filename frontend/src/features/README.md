# Frontend Features

Product feature modules that own durable UI state across routes. Prefer this
layer when a workflow needs a shared store, bootstrap, or transport that is
larger than a single page helper in `lib/`.

## Current Modules

### `workflow-drafts/`

Backend-backed Plan and Update Memory chat.

| File | Role |
|------|------|
| `workflow-draft-store.ts` | Zustand cache of draft snapshots by `draft_id` |
| `workflow-draft-bootstrap.ts` | Open/resume draft on page entry |
| `workflow-draft-transport.ts` | Stream turns into the store / backend |
| `workflow-chat-runtime.tsx` | assistant-ui `useExternalStoreRuntime` bridge |
| `thread-messages.ts` | Message mapping, edit truncate + rerun |
| `workflow-turn-activity.ts` | Live turn / tool activity helpers |
| `workflow-draft-runtime-key.ts` | Stable runtime identity helpers |

Rules:

- The store is a cache and operation coordinator only. The backend
  `WorkflowDraft` remains authoritative for messages, artifact text, revision,
  and active turns.
- Do not remount the chat runtime to force sync; refresh from backend revision
  instead.
- Background-turn completion toasts stay in
  `components/klassenpilot/pending-turn-notifier.tsx`, which claims a
  `lib/running-jobs.ts` marker once.

Memory Sweep is **not** an assistant-ui draft. It uses the same pending-job
lane (`mode: "memory_sweep"`) but resumes a backend-owned review session via
`/memory/sweep/review`.

## Conventions

- Keep feature modules focused on one workflow family.
- Put presentational domain UI in `components/klassenpilot/`.
- Put small pure helpers/tests in `lib/` when they are shared beyond one
  feature.
- Keep contracts aligned with `../../../docs/agent_contracts.md`
  (Workflow Draft Persistence + Memory Sweep).
