# Workflow Draft Frontend Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the workflow chat's local-runtime remount and duplicated completion polling with one backend-backed frontend draft store and one global operation notifier, while preserving current Plan and Update Memory behavior.

**Architecture:** The backend remains the authoritative source for draft messages, artifact text, runtime state, revision/hash, and active turns. A Zustand store mirrors backend draft snapshots by `draft_id`; assistant-ui's `useExternalStoreRuntime` renders that store and sends turns through the existing backend stream transport. A single app-level operation notifier polls only drafts with a locally initiated background turn and emits one completion toast.

**Tech Stack:** Next.js 15, React 19, TypeScript, Zustand 5, `@assistant-ui/react` 0.14.7, Sonner, Vitest.

## Global Constraints

- Preserve existing Plan and Update Memory routes, backend API contracts, review/hash guards, artifact editor behavior, and assistant-ui presentation components.
- Do not add `ThreadHistoryAdapter`; backend `WorkflowDraft` persistence is the only durable message-write path.
- Do not upgrade assistant-ui or copy its runtime internals in this refactor. UI primitives may be copied separately from a version-compatible registry update.
- The frontend store is a cache and operation coordinator only; it never authorizes wiki writes or replaces backend state.
- One component owns background completion polling and notifications.
- Memory Sweep remains a separate review workflow; only shared notification primitives may be adopted later.
- Do not commit before the user has smoke-tested the refactor.

---

### Task 1: Characterize Workflow Draft Behavior

**Files:**
- Create: `frontend/src/features/workflow-drafts/workflow-draft-store.test.ts`
- Modify: `frontend/src/lib/pending-chat-turns.test.ts`

**Interfaces:**
- Produces a test contract for draft snapshot updates, one completion claim, and unknown-session cleanup.

- [ ] Write failing tests for replacing a draft snapshot when the backend returns a later message list and for claiming a completed local operation exactly once.
- [ ] Run the focused Vitest files and confirm failures describe missing store behavior.
- [ ] Implement only the pure operation and snapshot-store helpers needed by the tests.
- [ ] Run the focused Vitest files and confirm they pass.

### Task 2: Add a Backend-Backed Workflow Draft Store

**Files:**
- Create: `frontend/src/features/workflow-drafts/workflow-draft-store.ts`
- Create: `frontend/src/features/workflow-drafts/workflow-draft-transport.ts`
- Test: `frontend/src/features/workflow-drafts/workflow-draft-store.test.ts`

**Interfaces:**
- Consumes the existing plan/ingest draft API functions.
- Produces `useWorkflowDraftStore`, `refreshDraft`, `startBackgroundTurn`, and `claimCompletedOperation`.

- [ ] Write failing tests for mode-specific refresh selection and immutable snapshot replacement.
- [ ] Run those tests and confirm the store/transport exports are absent.
- [ ] Implement the small Zustand store and transport normalization without changing route UI.
- [ ] Run tests and typecheck.

### Task 3: Move Assistant-UI Chat to the External Store Runtime

**Files:**
- Create: `frontend/src/features/workflow-drafts/workflow-chat-runtime.tsx`
- Modify: `frontend/src/components/assistant-ui/artifact-session-runtime.tsx`
- Modify: `frontend/src/components/klassenpilot/artifact-session-page.tsx`
- Delete: `frontend/src/lib/workflow-thread-snapshot.ts`
- Delete: `frontend/src/lib/workflow-thread-snapshot.test.ts`

**Interfaces:**
- Consumes a workflow draft snapshot and store actions.
- Produces the existing `useArtifactSession` context and live assistant-ui reasoning/tool-call rendering.

- [ ] Write a failing runtime/store test showing a completed backend snapshot updates visible messages without a remount key.
- [ ] Run the test and confirm it fails under the LocalRuntime key workaround.
- [ ] Replace only the message runtime ownership with `useExternalStoreRuntime`; preserve the existing editor context, stream-part conversion, session recovery, and artifact patch behavior.
- [ ] Remove the synthetic durable thread key and verify the Plan and Update Memory pages use the store-backed runtime.
- [ ] Run focused tests, typecheck, and a manual mounted-stream smoke test.

### Task 4: Centralize Background Completion Notifications

**Files:**
- Modify: `frontend/src/components/klassenpilot/pending-turn-notifier.tsx`
- Modify: `frontend/src/components/klassenpilot/artifact-session-page.tsx`
- Modify: `frontend/src/components/assistant-ui/artifact-session-runtime.tsx`
- Modify: `frontend/src/lib/pending-chat-turns.ts`
- Test: `frontend/src/lib/pending-chat-turns.test.ts`

**Interfaces:**
- `PendingTurnNotifier` is the only polling/toast owner.
- Route pages may render in-progress state from the draft store but never poll or toast completion.

- [ ] Write a failing test proving a completed marker is claimed once even if the route and app shell observe it.
- [ ] Run it and confirm it fails if two consumers toast/claim independently.
- [ ] Move all completion claims and toast emission into the global notifier; remove per-page polling and duplicate marker writes.
- [ ] Run focused tests and typecheck.

### Task 5: Regression Coverage and Smoke Verification

**Files:**
- Modify: relevant Vitest tests only when coverage gaps remain.
- Modify: `docs/agent_contracts.md` if the frontend runtime ownership statement changes.

- [ ] Run the frontend workflow draft, pending-turn, and memory-sweep status tests.
- [ ] Run `npm.cmd run typecheck` from `frontend`.
- [ ] Smoke test Plan and Update Memory: stay mounted for live reasoning/tool calls; navigate away during a turn; return before and after completion; verify one notification and the persisted artifact.
- [ ] Verify Memory Sweep still restores its persisted review and displays stale reasons.
- [ ] Run `git diff --check`; report all changed files without committing.
