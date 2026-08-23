# A2 Task 4 — Atomic Class-Network Storage and Compiled Overview

> Promoted from `.superpowers/sdd/2026-08-18-course-network-foundation/task-4-brief.md` on 2026-08-22. Completed; retained as the task-level contract.

## Goal

Persist an adopted `CourseNetworkDocument` as inspectable, class-owned wiki
data. Normal catalog/search/index paths expose the compiled Markdown overview,
never raw JSON. A class without an adopted network remains unchanged.

## Durable layout and store API

```text
wiki/classes/{class_id}/course_network/network.json
wiki/classes/{class_id}/course_network/overview.md
```

`WikiStore` exposes `load_course_network(class_id)` and
`write_course_network(class_id, document)`. Helpers centralize parsing,
canonical JSON, overview rendering, and class-page listing in the focused
course-network wiki module.

## Required behavior

- Resolve and validate the class before access; require a matching document
  class ID.
- Reject proposed nodes before a durable write. Adoption converts an accepted
  seed to adopted status.
- `network.json` is deterministic canonical JSON with one trailing newline.
- `overview.md` deterministically describes revision, route, adopted blocks,
  relationships, and inspectable curriculum references.
- The JSON/overview pair uses same-directory staging and atomic replacement.
  On a second-file failure, preserve the previous pair and leave no temporary
  file.
- Missing JSON returns `None`; invalid existing JSON raises a clear storage or
  domain error rather than hiding it.
- The compiled overview is indexed as `course_network` and appears in the wiki
  viewer/catalog and deterministic search corpus. Raw `network.json` is never
  treated as prose.

## Scope boundary

This is storage capability only: no React Flow, API route, seed, draft,
adoption action, LLM review, material ingestion, planner retrieval, lesson
tagging, or tracked baseline wiki mutation.

## Verification and completion record

The TDD coverage included missing-network behavior, adopted round trip,
canonical newline/stability, proposed/mismatched class rejection, overview
content, raw JSON exclusion, overview retrieval, and injected atomic-write
failure. Follow-up review hardened class ownership, temporary cleanup, viewer
kind metadata, and durable recovery.
