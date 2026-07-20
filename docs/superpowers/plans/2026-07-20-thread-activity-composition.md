# Thread Activity Composition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show Update Memory's existing wiki-change review inside the scrollable assistant-ui chat viewport, using the same reusable non-message activity composition as Plan verification.

**Architecture:** `ThreadActivity` is a presentation-only assistant-ui component. It provides the consistent runtime-activity boundary; its children retain their existing data, actions, and ownership. `IngestThread` receives the existing `ReviewBrief` from the page and mounts it through `Thread.activity`. The left-side draft/diff remains owned by `ArtifactSessionWorkspace`.

**Tech Stack:** React 19, TypeScript, assistant-ui, existing `ReviewBrief`, Vitest source/render tests.

## Global Constraints

- No backend, API, persistence, or write-contract changes.
- Do not create a synthetic assistant message or a second chat history.
- Keep the existing review controls, editable left-side diff, and teacher approval behavior unchanged.
- Use semantic design-system tokens and shared components.

---

### Task 1: Add the shared chat-activity composition

**Files:**
- Create: `frontend/src/components/assistant-ui/thread-activity.tsx`
- Test: `frontend/src/components/assistant-ui/thread-activity.test.ts`

- [x] Write a rendering test that asserts the wrapper exposes a stable activity marker and renders its child.
- [x] Run `npm test -- src/components/assistant-ui/thread-activity.test.ts` and observe failure because the component does not exist.
- [x] Implement `ThreadActivity({ children })` as a presentation-only wrapper using compact spacing and a `data-slot="thread-activity"` marker.
- [x] Re-run the focused test and confirm it passes.

### Task 2: Compose Plan and Update Memory activities

**Files:**
- Modify: `frontend/src/components/assistant-ui/plan-thread.tsx`
- Modify: `frontend/src/components/assistant-ui/ingest-thread.tsx`
- Modify: `frontend/src/app/classes/[classId]/memory/page.tsx`
- Test: `frontend/src/components/assistant-ui/thread.contract.test.ts`

- [x] Confirm the existing thread contract keeps its one activity slot after runtime messages.
- [x] Pass `PlanVerificationPanel` through `ThreadActivity` in `PlanThread`.
- [x] Add an optional `activity` prop to `IngestThread` and pass it to `Thread` through `ThreadActivity`.
- [x] Move only the existing `ReviewBrief` composition from `reviewFileList` to the `IngestThread` activity prop; retain `reviewDiff` unchanged.
- [x] Run the focused frontend tests and `npm run typecheck`.

### Task 3: Validate the live interaction

**Files:** no additional files

- [ ] Use the local beta stack to prepare wiki updates from an Update Memory draft.
- [ ] Confirm the review appears after chat messages in the scrollable viewport, not as a message and not beneath the workspace.
- [ ] Confirm View/Edit still opens the left-side diff/editor and Save/Cancel behavior is unchanged.
