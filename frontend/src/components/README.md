# Frontend Components

Components are split by responsibility.

## Folders

- `ui/` - low-level shadcn-style primitives. Keep domain logic out.
- `layout/` - app shell and page headers.
- `assistant-ui/` - chat/thread/streaming UI and assistant-ui integration.
- `klassenpilot/` - product components for class timelines, artifact panels,
  review flows, memory updates, and workflow-specific layouts.

## Conventions

- Put KlassenPilot-specific behavior in `klassenpilot/`.
- Keep shared chat runtime behavior in `assistant-ui/`.
- Prefer existing `ui/` primitives before adding new visual components.
