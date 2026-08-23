# A3 Task 8 — Read-Only Course Workspace

> Promoted from `.superpowers/sdd/2026-08-18-course-network-foundation/task-8-brief.md` on 2026-08-22. Completed; retained as the task-level contract.

## Goal

Build `/classes/{classId}/course`, the teacher-facing read-only course-network
workspace. Before adoption it guides seed review and adoption; after adoption
it inspects the class's canonical network. Graph editing is explicitly deferred
to Epic B.

## Composition and transport

The page dynamically imports the canvas with SSR disabled. Domain components
include the workspace, canvas, custom learning-block node, inspector,
searchable outline, and adoption screen. Task 7 feature-local types are the
transport source of truth; the client exposes network/draft/review/adopt
operations without duplicate types.

## Required user flow

- Desktop: canvas plus a 360px inspector.
- Narrow view: searchable outline plus the same inspector; it deliberately
  avoids forcing precision graph interaction in a small window.
- Nodes show title, truncated learning goal, origin badge, semantic connection
  handles, explicit accessible name, and keyboard selection.
- The header communicates `Network`; future `Materials` is disabled rather
  than linking to an unimplemented route.
- A selected block shows goal, description, class-authorized curriculum
  evidence, and relationships. Relationship and outline selection keep canvas
  emphasis coherent.
- Before adoption, open/resume the seed draft, show counts/sources/outline and
  review findings, then enable adoption only after an exact passing review.
  Discard leaves the legacy framework in place.

## Boundaries

Reuse the fixed design system and shared loading/error/review patterns. Do not
add graph editing, persisted React Flow state, material library, planner
changes, or hidden direct writes. Network data remains immutable view input.

## Completion record

Final review closed source-link, stale adoption, materials-404, and narrow-view
clarity findings. Browser testing exposed a React Flow controlled-selection
feedback loop; the final fix lets React Flow own visual selection and passes a
presentation-only emphasis flag for external selections. Source evidence resets
on node switch. Actual renderer/workspace tests, the full frontend suite, type
checking, and live browser acceptance passed. Task 9 remains the next A3 task.
