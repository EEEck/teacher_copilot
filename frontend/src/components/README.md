# Frontend Components

Components are split by responsibility.

## Folders

- `ui/` - low-level shadcn-style primitives. Keep domain logic out.
- `layout/` - app shell and page headers.
- `assistant-ui/` - chat/thread/streaming UI, assistant-ui integration, and
  shared artifact runtime state such as completeness, last change summary, and
  memory target state.
- `klassenpilot/` - product components for class timelines, artifact panels,
  review flows, memory updates, and workflow-specific layouts.

## Conventions

- Put KlassenPilot-specific behavior in `klassenpilot/`.
- Keep shared chat runtime behavior in `assistant-ui/`.
- Timeline/detail components may construct memory-entry links, but visible
  target/phase status should come from backend `memory_state`.
- Prefer existing `ui/` primitives before adding new visual components.
