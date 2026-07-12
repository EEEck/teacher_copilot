# Frontend Components

Components are split by responsibility.

## Folders

- `ui/` - low-level shadcn-style primitives. Keep domain logic out.
- `layout/` - app shell and page headers.
- `assistant-ui/` - chat/thread/streaming UI, assistant-ui integration, and
  shared artifact runtime state such as completeness, last change summary, and
  memory target state. Plan/Update Memory message ownership comes from
  `features/workflow-drafts/` via `useExternalStoreRuntime`.
- `klassenpilot/` - product components for class timelines, artifact panels,
  review flows, proposed memory updates, Memory Sweep brief, pending-job UI
  (`pending-turn-notifier.tsx`, `running-tasks-box.tsx`), and workflow-specific
  layouts.

## Conventions

- Put KlassenPilot-specific behavior in `klassenpilot/`.
- Put cross-route draft store/runtime ownership in `../features/`, not here.
- Keep shared chat presentation in `assistant-ui/`.
- Timeline/detail components may construct memory-entry links, but visible
  target/phase status should come from backend `memory_state`.
- Review surfaces should stay brief-first: use `review/review-brief.tsx` and
  `memory-sweep-brief.tsx` before exposing detailed diffs/cards. Memory Sweep
  view mode uses `SegmentedToggle` Simple / Detailed.
- Prefer existing `ui/` primitives before adding new visual components.
