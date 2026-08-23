# A3 Task 7 — React Flow and Pure API-to-Canvas Adapter

> Promoted from `.superpowers/sdd/2026-08-18-course-network-foundation/task-7-brief.md` on 2026-08-22. Completed; retained as the task-level contract.

## Goal

Install the only approved graph dependency and create a pure deterministic
adapter from the Course Network API record to React Flow nodes and edges. This
is view-only infrastructure, not a course page or a persistence format.

## Dependency and interface

The only runtime dependency is `@xyflow/react@^12.11.3`. No xyflow repository
clone is required. React Flow JSON is never persisted; canonical data remains
the backend `network.json` record.

`toReactFlowModel(network)` preserves domain IDs, stores each full
`LearningBlock` under `data.learningBlock`, maps relationship labels/styles,
and never mutates the API object. Missing positions receive finite,
deterministic layout: topological layers for `builds_on` and a stable final grid
for cyclic or unconnected blocks.

## Scope and verification

This task adds no page, API transport, backend change, class-home entry,
editing, materials UI, or persistent React Flow state. The original test plan
covers stable IDs, full data coverage, finite deterministic positions, and
input immutability. Review later corrected CSS token colors and clarified type
ownership; the adapter is complete.
