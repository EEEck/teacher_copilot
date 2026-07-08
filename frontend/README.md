# KlassenPilot Frontend

Next.js frontend for teacher workflows. The UI is intentionally a practical
tool shell rather than a marketing site: class selection, class memory, lesson
timeline, update-memory chat, and create-plan chat.

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
- The memory page displays the backend `memory_state` target/phase summary
  above the shared artifact workspace.
- The memory review surface starts with a teacher-first brief of what will be
  saved, with detailed file diffs still available behind the review panel.
- Pending memory reviews are stored in session storage so a prepared review can
  survive route refresh while staying non-authoritative; backend commit remains
  the only durable write.
- Memory save guards prevent double-commit behavior while chat/save work is in
  flight or after the review has already committed.
- The Memory Sweep page uses a brief-first inbox: explicit asks are pinned,
  new/changed/already-covered signals are grouped, and detailed cards remain
  available per row.

## Assistant UI provenance

The chat surface is built on [`assistant-ui/assistant-ui`](https://github.com/assistant-ui/assistant-ui)
via `@assistant-ui/react`, `@assistant-ui/react-markdown`, and locally adapted
shadcn-style components under `src/components/assistant-ui/`.

Treat that folder as an adapted upstream component layer: useful for thread UI,
streaming chat affordances, attachments, markdown rendering, tool panels, and
future inline chat artifacts. Keep KlassenPilot-specific artifact state,
review/apply behavior, stream sanitization, and backend contracts outside the
vendor-style components so upstream patterns can still be borrowed later.

## Folder Map

- `src/app/` - Next.js App Router pages and route-specific UI.
- `src/components/assistant-ui/` - shared assistant-ui primitives and chat
  runtime integration; see its README for provenance and update notes.
- `src/components/klassenpilot/` - product/domain components for timelines,
  artifact panels, review flows, proposed memory updates, and the Memory Sweep
  brief.
- `src/components/ui/` - shadcn-style low-level UI primitives.
- `src/components/layout/` - app shell and page headers.
- `src/lib/` - API client, SSE parsing, markdown diff/session utilities,
  review/sweep brief builders, pending memory review storage, save guards, and
  tests.
- `src/content/docs/en/` - markdown content rendered into in-app teacher docs (`de/` locale later).
- `src/hooks/` - shared React hooks.
- `DESIGN.md` - frontend design notes.

## Tests

```powershell
cd frontend
npm run typecheck
npm run test
```

## Related Docs

- `src/README.md`
- `../README.md`
- `../docs/product_vision.md`
