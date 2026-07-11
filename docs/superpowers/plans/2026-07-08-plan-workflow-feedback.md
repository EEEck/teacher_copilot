# Plan Workflow Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct plan discard/save progress feedback and GPT-5.4 reasoning compatibility.

**Architecture:** Keep operation state local to the plan workflow while reusing the
existing shared review button for final-save progress. Normalize model compatibility
at the single backend boundary that builds `ModelSettings`.

**Tech Stack:** FastAPI/Python, OpenAI Agents SDK, Next.js/React, Vitest.

## Global Constraints

- Do not change wiki write approval contracts.
- Do not add dependencies.
- Preserve configured model-profile routing.

---

### Task 1: GPT-5.4 Reasoning Compatibility

**Files:**
- Modify: `backend/app/teacher_agent/agent.py`
- Test: `backend/tests/test_model_profile.py`

**Interfaces:**
- Consumes: model identifier and configured reasoning effort.
- Produces: `chat_model_settings(reasoning_effort, model=...)`.

- [ ] Add tests proving GPT-5.4 models map `minimal` to `none` while other
  models and efforts remain unchanged.
- [ ] Run the focused test and confirm the new assertion fails.
- [ ] Add model-aware normalization at `chat_model_settings`.
- [ ] Pass each agent builder's model identifier into that boundary.
- [ ] Run the focused backend test and confirm it passes.

### Task 2: Plan Operation Feedback

**Files:**
- Modify: `frontend/src/app/classes/[classId]/plan/page.tsx`
- Modify: `frontend/src/components/klassenpilot/review/review-brief.tsx`
- Test: `frontend/src/components/klassenpilot/review/review-brief.test.tsx`

**Interfaces:**
- Consumes: `saving?: boolean` on `ReviewBrief`.
- Produces: a disabled save button with spinner while saving.

- [ ] Add a rendering test for the disabled save button and spinner.
- [ ] Run the focused test and confirm it fails.
- [ ] Replace the plan footer's shared loading boolean with explicit operation state.
- [ ] Keep final save pending until navigation or restore it only on failure.
- [ ] Add the spinner to the shared review save button.
- [ ] Run the focused frontend test and typecheck.

### Task 3: Regression Verification

**Files:**
- Verify only.

**Interfaces:**
- Consumes: completed backend and frontend changes.
- Produces: test evidence.

- [ ] Run the focused backend workflow/model tests.
- [ ] Run the focused frontend tests.
- [ ] Run frontend type checking.
- [ ] Verify discard and save states in the running app when browser control is available.
