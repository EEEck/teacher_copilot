# Assistant UI Provenance

This folder contains KlassenPilot's local chat UI shell. It is adapted from the
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
- Keep KlassenPilot-specific session, artifact, safety, and SSE behavior in the
  local runtime integration files and backend stream policy.
- Raw reasoning/tool panels are for development diagnostics. In production the
  backend stream policy strips raw reasoning text, tool args, and tool outputs
  before these components receive events.
- When updating from assistant-ui, diff carefully and preserve local artifact
  behavior.
