# Frontend Source Map

This folder contains the Next.js app and shared UI code.

## App Router

- `app/page.tsx` - landing/class selection.
- `app/classes/[classId]/page.tsx` - class home (includes Memory Sweep draft
  badge from `GET /memory/sweep/review`).
- `app/classes/[classId]/memory/page.tsx` - update-memory artifact session;
  accepts optional lesson/date query hints from timeline/detail actions and
  renders the teacher-first memory review before commit.
- `app/classes/[classId]/memory-sweep/page.tsx` - backend-owned Memory Sweep
  review session (open/resume, decisions, apply/discard/refresh).
- `app/classes/[classId]/lessons/[lessonDate]/page.tsx` - lesson detail.
- `app/classes/[classId]/plan/page.tsx` - create lesson plan workflow.
- `app/classes/[classId]/wiki/view/page.tsx` - wiki file viewer.
- `app/docs/` - in-app beta docs landing and markdown-backed article pages.

## Feature Modules

- `features/workflow-drafts/` - Zustand draft cache, bootstrap/transport, and
  assistant-ui `useExternalStoreRuntime` for Plan / Update Memory. See
  `features/README.md`.

## Component Layers

- `components/ui/` - generic primitives. Keep these domain-free.
- `components/layout/` - page/app chrome.
- `components/assistant-ui/` - chat runtime, thread UI, tool display, streaming
  event handling; adapted from
  [`assistant-ui/assistant-ui`](https://github.com/assistant-ui/assistant-ui).
  See `components/assistant-ui/README.md` for provenance and update notes.
- `components/klassenpilot/` - domain-specific workflow components, including
  proposed durable-memory updates, Memory Sweep brief, pending-turn notifier,
  running-tasks box, and wiki review panels.

## Library Code

- `lib/api.ts` - typed HTTP client helpers.
- `lib/sse-chat.ts` - SSE parser/runtime helpers, with `sse-chat.test.ts`.
- `lib/session-attachments.ts` - upload/session attachment utilities.
- `lib/workflow-attachment-adapters.ts` - Plan PDF OCR attach + Send gate.
- `lib/plan-material-arm.ts` / `lib/material-asset-urls.ts` - Textbook/Personal
  arm and classroom asset URLs in plan preview.
- `lib/markdown-diff.ts` - review diff helpers.
- `lib/diary-utils.ts` - diary-specific helpers.
- `lib/review-brief.ts` - groups proposed wiki file changes into a
  teacher-first save brief.
- `lib/sweep-brief.ts` - groups Memory Sweep candidates into New / Changed /
  Already-covered brief rows.
- `lib/running-jobs.ts` - poll ∪ local runners for durable background jobs
  (plan/ingest chat turns and Memory Sweep generation).
- `lib/chat-run-feedback.ts` - running-task and completion toast labels.
- `lib/memory-sweep-review-status.ts` - class-home badge + sweep loading copy.
- `lib/pending-memory-review.ts` - session-storage helper for non-durable
  prepared reviews.
- `lib/memory-save-guards.ts` - prevents save/double-save actions in invalid
  review states.
- `content/docs/en/` - teacher-facing markdown docs (English; add `de/` for
  German later).

## Boundaries

- API shape changes should be reflected in `lib/api.ts` and backend
  `app/schemas/api.py`.
- Memory Sweep UI/API changes should also update the active memory docs under
  `../../docs/mem_v4/` and `../../docs/agent_contracts.md`.
- Workflow draft ownership changes should update
  `../../docs/agent_contracts.md` (Workflow Draft Persistence Contract) and
  `features/README.md`.
- Keep assistant-ui integration reusable across ingest/plan workflows; put
  draft-store ownership in `features/workflow-drafts/`, not vendor-style
  thread primitives.
- When adding richer inline chat artifacts later, first inspect upstream
  assistant-ui patterns and adapt them behind KlassenPilot's artifact/review
  contracts instead of baking product behavior into vendor-style primitives.
- Keep typed memory hint construction in page/domain code, not low-level UI
  primitives. The backend remains the source of truth for whether a hinted
  lesson target is confirmed.
- Keep product-specific behavior in `components/klassenpilot/`, not low-level
  `components/ui/`.
