# Frontend Source Map

This folder contains the Next.js app and shared UI code.

## App Router

- `app/page.tsx` - landing/class selection.
- `app/classes/[classId]/page.tsx` - class home.
- `app/classes/[classId]/memory/page.tsx` - memory overview.
- `app/classes/[classId]/lessons/[lessonDate]/page.tsx` - lesson detail.
- `app/classes/[classId]/plan/page.tsx` - create lesson plan workflow.
- `app/classes/[classId]/wiki/view/page.tsx` - wiki file viewer.

## Component Layers

- `components/ui/` - generic primitives. Keep these domain-free.
- `components/layout/` - page/app chrome.
- `components/assistant-ui/` - chat runtime, thread UI, tool display, streaming
  event handling.
- `components/klassenpilot/` - domain-specific workflow components.

## Library Code

- `lib/api.ts` - typed HTTP client helpers.
- `lib/sse-chat.ts` - SSE parser/runtime helpers, with `sse-chat.test.ts`.
- `lib/session-attachments.ts` - upload/session attachment utilities.
- `lib/markdown-diff.ts` - review diff helpers.
- `lib/diary-utils.ts` - diary-specific helpers.

## Boundaries

- API shape changes should be reflected in `lib/api.ts` and backend
  `app/schemas/api.py`.
- Keep assistant-ui integration reusable across ingest/plan workflows.
- Keep product-specific behavior in `components/klassenpilot/`, not low-level
  `components/ui/`.
