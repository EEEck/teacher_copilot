# A2 Task 3 — Canonical Network Models

> Promoted from `.superpowers/sdd/2026-08-18-course-network-foundation/task-3-brief.md` on 2026-08-22. Completed; retained as the task-level contract.

## Goal

Define the backend-only, class-owned course-network model contract used by
storage, reviewed seeds, and adoption. It must remain independent of React
Flow and introduce no UI, API route, durable class write, or model call.

## Required public contract

- `CurriculumRouteRef(subject, grade, branch)` belongs to
  `course_network.models`. It validates the normalized Chemie 8/9 NTG route
  but does not import A1's service-local `CurriculumRoute`.
- `CurriculumReference(source_id, section_id)` and
  `MaterialSectionReference(material_id, section_id, page_start, page_end)`;
  page bounds are positive and ordered.
- `CanvasPosition(x, y)`.
- `LearningBlock`: stable ID, title, optional description and learning goal,
  curriculum/material references, origin (`curriculum|teacher|material`), and
  status (`proposed|adopted|retired`). Material-origin blocks require a
  material reference.
- `NetworkEdge`: stable ID, known source/target nodes, and only
  `builds_on|related_to` relationships.
- `MaterialMapping`: material/section/node link with one of
  `explains|practices|assesses|extends`, optional 0–1 confidence, teacher note,
  and `agent|teacher` origin.
- `CourseNetworkDocument`: schema version 1, class ID, route, revision,
  nodes, edges, material mappings, positions, and timestamp.
- `canonical_network_json(document)`: deterministic JSON with Unicode retained
  and stable formatting.

## Invariants and boundaries

- IDs are stable, slug-like, and unique per node/edge/mapping kind.
- Edges reference real endpoints; self-edges and duplicate semantic edges are
  rejected. Mappings reference real nodes and their material/section/node/
  relation tuple is unique.
- Positions reference real nodes only.
- Canonical durable documents reject `proposed` nodes. A deliberately explicit
  draft/seed construction path can permit them. Retired nodes remain valid for
  historical lesson references.
- Models make no chemistry-plausibility judgement.
- No cross-class ownership, export/import, competency node type, graph DB,
  material ingestion, question bank, or React Flow dependency belongs here.

## Verification and completion record

The original task required failing invariant tests before implementation for
duplicate nodes, invalid/self edges, duplicate mappings, material-origin
validity, seed-vs-canonical proposed status, invalid page/position bounds, and
deterministic JSON. It completed with the model test suite, scoped Ruff/format,
and `git diff --check`; subsequent review closed finite-coordinate validation.
