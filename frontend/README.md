# KlassenPilot Frontend

Next.js frontend for teacher workflows. The UI is intentionally a practical
tool shell rather than a marketing site: class selection, class memory, lesson
timeline, update-memory chat, create-plan chat (optional PDF class materials),
and Memory Sweep review.

## Run

```powershell
cd frontend
npm install
npm run dev
```

The app expects `NEXT_PUBLIC_API_BASE_URL` in `.env.local` or falls back to the
local backend URL used by the repo scripts.

Raw reasoning/tool panels are a backend-controlled diagnostic surface. The
frontend renders the SSE events it receives; backend `APP_ENV=production`
strips streamed reasoning text, tool args, and tool outputs before they reach
the browser.

## Workflow Notes

- The top-level **Update memory** action starts a generic free-agent session.
- Lesson timeline and lesson-detail actions pass a typed start hint in the
  memory URL (`lessonDate`, `lessonTitle`, `intent`, `targetKind`). The backend
  decides whether that target is confirmed; unknown dates still require
  confirmation.
- Plan and Update Memory chat are backend-owned **workflow drafts**. The
  frontend mirrors them in `src/features/workflow-drafts/` (Zustand cache +
  assistant-ui `useExternalStoreRuntime`). Navigating away does not cancel an
  accepted model turn; reopening resumes the same draft.
- Durable background work (chat turns and Memory Sweep generation) is reported
  by `GET /api/workflow/active` and mirrored via `lib/running-jobs.ts`. One
  app-level `PendingTurnNotifier` polls those jobs, shows the bottom-left
  Running box, and emits a single completion toast.
- The memory page displays the backend `memory_state` target/phase summary
  above the shared artifact workspace.
- The memory review surface starts with a teacher-first brief of what will be
  saved, with detailed file diffs still available behind the review panel.
- Pending memory reviews may still use session storage as a visual cache so a
  prepared review can survive route refresh; backend commit remains the only
  durable write, and draft revision/hash guards reject stale saves.
- Memory save guards prevent double-commit behavior while chat/save work is in
  flight or after the review has already committed.
- Plan verification is revision-bound: deterministic checks appear immediately
  and a short background review may add advisory notes. Only a completed
  severe-safety hold blocks a save; the frontend never rewrites the teacher's
  Markdown from that report.
- Update Memory's integrity pack is backend-owned. It can block a confirmed
  date mismatch or malformed/unknown/name-style student label, but it does not
  edit the diary for the teacher.
- Plan verification and Save lesson memory review appear as shared in-thread
  workflow activities. The selected review diff is pinned above the transcript;
  it does not replace the chat viewport.
- Memory Sweep opens a backend-owned saved review (`/memory/sweep/review`).
  Simple view is the default triage list; **Simple / Detailed** switches to the
  full card layout. Class-home shows “Stale draft” only when teacher edits are
  at risk; unedited fingerprint drift stays “Draft saved …”.

## Assistant UI provenance

The chat surface is built on [`assistant-ui/assistant-ui`](https://github.com/assistant-ui/assistant-ui)
via `@assistant-ui/react`, `@assistant-ui/react-markdown`, and locally adapted
shadcn-style components under `src/components/assistant-ui/`.

Treat that folder as an adapted upstream component layer: useful for thread UI,
streaming chat affordances, attachments, markdown rendering, tool panels, and
future inline chat artifacts. Keep KlassenPilot-specific artifact state,
workflow-draft ownership, review/apply behavior, stream sanitization, and
backend contracts outside the vendor-style components so upstream patterns can
still be borrowed later.

## Folder Map

- `src/app/` - Next.js App Router pages and route-specific UI.
- `src/features/` - cross-route feature modules (workflow draft store/runtime).
- `src/components/assistant-ui/` - shared assistant-ui primitives and chat
  runtime integration; see its README for provenance and update notes.
- `src/components/klassenpilot/` - product/domain components for timelines,
  artifact panels, review flows, pending-job UI, and the Memory Sweep brief.
- `src/components/ui/` - shadcn-style low-level UI primitives
  (`SegmentedToggle`, `Button`, …).
- `src/components/layout/` - app shell and page headers.
- `src/lib/` - API client, SSE parsing, pending-job markers, review/sweep brief
  builders, save guards, and tests.
- `src/content/docs/en/` - markdown content rendered into in-app teacher docs
  (`de/` locale later).
- `src/hooks/` - shared React hooks.
- `DESIGN.md` - frontend design notes.

## Tests

```powershell
cd frontend
npm run typecheck
npm run test
```

Focused suites for the draft/job work:

```powershell
npx vitest run src/features/workflow-drafts src/lib/running-jobs.test.ts src/lib/memory-sweep-review-status.test.ts
```

For fresh beta-browser acceptance rather than a unit-test run, follow the
sanitized browser workflow manifests described in
[`../docs/superpowers/specs/2026-07-20-browser-workflow-runbook-design.md`](../docs/superpowers/specs/2026-07-20-browser-workflow-runbook-design.md).

## Related Docs

- `src/README.md`
- `src/features/README.md`
- `DESIGN.md`
- `../README.md`
- `../docs/agent_contracts.md` (Workflow Draft Persistence + Memory Sweep)
- `../docs/product_vision.md`
