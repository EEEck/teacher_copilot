# Background Turn And Timeline Drafts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make resumed background turns visibly active and expose active Update Memory drafts in the lesson timeline.

**Architecture:** Durable workflow state remains backend-owned. The shared chat
thread renders backend progress, while the timeline API overlays matching active
ingest drafts from the central WorkflowDraft store.

**Tech Stack:** FastAPI, SQLite, Next.js, React, assistant-ui, pytest, Vitest.

## Global Constraints

- Apply chat feedback to Lesson Plan and Update Memory.
- Keep Memory Sweep out of scope.
- Do not persist raw reasoning or tool-call SSE events.
- Keep timeline navigation compatible with existing open-or-resume identity.

---

### Task 1: Active Timeline Draft Metadata

**Files:**
- Modify: `backend/app/services/workflow_drafts.py`
- Modify: `backend/app/schemas/api.py`
- Modify: `backend/app/api/routes.py`
- Modify: `backend/tests/test_workflow_drafts.py`

- [ ] Add failing tests for active ingest draft listing and timeline overlay.
- [ ] Implement the store query and optional `memory_draft_id`.
- [ ] Run focused backend tests.

### Task 2: Timeline Action States

**Files:**
- Create: `frontend/src/lib/timeline-memory-action.ts`
- Create: `frontend/src/lib/timeline-memory-action.test.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/components/klassenpilot/lesson-timeline.tsx`

- [ ] Add failing tests for Add, Edit, and Correct labels.
- [ ] Implement the pure action resolver and consume it in the timeline.
- [ ] Run focused frontend tests and typecheck.

### Task 3: Shared Background Turn Indicator

**Files:**
- Modify: `frontend/src/components/assistant-ui/thread.tsx`
- Modify: `frontend/src/components/assistant-ui/plan-thread.tsx`
- Modify: `frontend/src/components/assistant-ui/ingest-thread.tsx`

- [ ] Pass backend `turnInProgress` from both workflow wrappers.
- [ ] Render one shared spinner for local or resumed backend work.
- [ ] Run frontend tests and typecheck.

### Task 4: Regression Verification

**Files:**
- Verify only.

- [ ] Run focused workflow draft and timeline tests.
- [ ] Run the full deterministic repository suite.
