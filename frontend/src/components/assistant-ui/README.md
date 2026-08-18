# Assistant UI Provenance

This folder contains KlassenPilot's local chat UI shell. It is adapted from
[`assistant-ui/assistant-ui`](https://github.com/assistant-ui/assistant-ui), the
assistant-ui React/shadcn-style component registry, then customized for the
KlassenPilot artifact sessions.

Local evidence:

- `frontend/package.json` depends on `@assistant-ui/react` and
  `@assistant-ui/react-markdown`.
- `frontend/components.json` registers the assistant-ui shadcn registry alias:
  `@assistant-ui: https://r.assistant-ui.com/{name}.json`.
- `frontend/DESIGN.md` documents the update command:
  `npx assistant-ui add thread -o -p src/components/assistant-ui`.
- The component files use assistant-ui primitives and `aui-*` class naming.

Maintenance notes:

- Treat these files as adapted/vendor-style UI components, not as product
  behavior contracts.
- Plan, Update Memory, and Discuss class state all own messages via
  `src/features/workflow-drafts/` and render through
  `useExternalStoreRuntime`. Do not reintroduce `useLocalRuntime` remount keys
  as the sync strategy.
- Discuss on class home is chrome-only (`discuss-dock.tsx`); it must reuse the
  same runtime + `Thread` stack. See `frontend/ARCHITECTURE.md` for turn
  lifecycle and how to add a mode.
- Attachments: follow
  [assistant-ui File Attachments](https://www.assistant-ui.com/docs/guides/attachments).
  Plan PDFs OCR via `lib/workflow-attachment-adapters.ts`; Textbook/Personal sits
  beside composer `+` (`composer-attachment-controls.tsx`). PDF only. The attach
  dialog closes on pick; the composer tile shows Reading → check/fail; Send is
  gated until OCR finishes.
- For future inline chat artifacts, message actions, or richer tool/result
  displays, inspect upstream assistant-ui examples first and adapt the smallest
  useful pattern locally.
- Keep KlassenPilot-specific session, artifact, safety, and SSE behavior in the
  local runtime integration files, the workflow-draft feature module, and
  backend stream policy.
- Raw reasoning/tool panels are for development diagnostics. In production the
  backend stream policy strips raw reasoning text, tool args, and tool outputs
  before these components receive events.
- When updating from assistant-ui, diff carefully and preserve local artifact
  behavior.
