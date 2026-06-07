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

## Folder Map

- `src/app/` - Next.js App Router pages and route-specific UI.
- `src/components/assistant-ui/` - shared assistant-ui primitives and chat
  runtime integration.
- `src/components/klassenpilot/` - product/domain components for timelines,
  artifact panels, review flows, and proposed memory updates.
- `src/components/ui/` - shadcn-style low-level UI primitives.
- `src/components/layout/` - app shell and page headers.
- `src/lib/` - API client, SSE parsing, markdown diff/session utilities, and
  tests.
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
