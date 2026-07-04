# Frontend Source Map

This folder contains the Next.js app and shared UI code.

## App Router

- `app/page.tsx` - landing/class selection.
- `app/classes/[classId]/page.tsx` - class home.
- `app/classes/[classId]/memory/page.tsx` - update-memory artifact session;
  accepts optional lesson/date query hints from timeline/detail actions.
- `app/classes/[classId]/lessons/[lessonDate]/page.tsx` - lesson detail.
- `app/classes/[classId]/plan/page.tsx` - create lesson plan workflow.
- `app/classes/[classId]/wiki/view/page.tsx` - wiki file viewer.
- `app/docs/` - in-app beta docs landing and markdown-backed article pages.

## Component Layers

- `components/ui/` - generic primitives. Keep these domain-free.
- `components/layout/` - page/app chrome.
- `components/assistant-ui/` - chat runtime, thread UI, tool display, streaming
  event handling; adapted from
  [`assistant-ui/assistant-ui`](https://github.com/assistant-ui/assistant-ui).
  See `components/assistant-ui/README.md` for provenance and update notes.
- `components/klassenpilot/` - domain-specific workflow components.

## Library Code

- `lib/api.ts` - typed HTTP client helpers.
- `lib/sse-chat.ts` - SSE parser/runtime helpers, with `sse-chat.test.ts`.
- `lib/session-attachments.ts` - upload/session attachment utilities.
- `lib/markdown-diff.ts` - review diff helpers.
- `lib/diary-utils.ts` - diary-specific helpers.
- `content/docs/en/` - teacher-facing markdown docs (English; add `de/` for German later).

## Boundaries

- API shape changes should be reflected in `lib/api.ts` and backend
  `app/schemas/api.py`.
- Memory Sweep UI/API changes should also update
  `../../docs/mem_v2/frontend.md`.
- Keep assistant-ui integration reusable across ingest/plan workflows.
- When adding richer inline chat artifacts later, first inspect upstream
  assistant-ui patterns and adapt them behind KlassenPilot's artifact/review
  contracts instead of baking product behavior into vendor-style primitives.
- Keep typed memory hint construction in page/domain code, not low-level UI
  primitives. The backend remains the source of truth for whether a hinted
  lesson target is confirmed.
- Keep product-specific behavior in `components/klassenpilot/`, not low-level
  `components/ui/`.
