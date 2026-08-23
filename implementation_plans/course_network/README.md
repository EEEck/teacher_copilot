# Course Network Delivery Handoff

**Updated:** 2026-08-22

**Branch:** `codex/class-course-network-design`

**Purpose:** a concise, tracked handoff for the class-owned course-network
program. Detailed implementation plans remain in
[`docs/superpowers/plans/`](../../docs/superpowers/plans/); ephemeral review and
test evidence remains ignored under `.superpowers/sdd/`.

## Source documents

These are verbatim promoted copies of the original planning documents. The
source locations remain canonical while this branch is active; copies make the
complete handoff portable for future agents.

- [01 — approved product design](01_product_design.md)
- [02 — delivery program, Epic A–D](02_delivery_program.md)
- [03 — detailed A1–A3 foundation implementation plan](03_foundation_implementation.md)
- [04 — current handoff and verified progress](README.md)

## Product boundary

The MVP is a **class-owned** Chemie 8/9 NTG course network. It has one
teacher-facing node type, `Lernbaustein`, and `builds_on` / `related_to`
relationships. The class wiki owns the canonical graph at
`course_network/network.json`; `overview.md` is regenerated for inspection and
retrieval. React Flow is only a view layer.

This foundation does not add graph editing, a durable materials library,
question extraction, cross-class reuse, a graph database, or planner retrieval
yet. Those belong to the later Epic B–D plans.

## Current progress

| Slice | Status | What is now available |
| --- | --- | --- |
| A1 — class provisioning | Complete and verified | A teacher can create a deterministic Chemie 8/9 NTG class. Provisioning creates the expected class wiki shell, rejects duplicates with the canonical error envelope, and does not call an LLM or external service. |
| A2 — network/adoption API | Complete and verified | Class-owned canonical network models, reviewed Chemie 8/9 seeds, exact-revision review/adoption, atomic JSON + overview/index publication, and legacy-framework fallback are implemented. |
| A3 Task 7 — canvas adapter | Complete and reviewed | `@xyflow/react` renders an immutable API view model. Canonical graph data never uses React Flow JSON; missing positions receive deterministic fallback coordinates. |
| A3 Task 8 — workspace | Complete and reviewed | `/classes/{classId}/course` loads an adopted graph or guides seed review/adoption. It provides a desktop canvas, narrow-screen searchable outline, node inspector, relationship navigation, and class-authorized curriculum-source evidence. |
| A3 Task 9 | Next | Add the single `Course` action on class home, reconcile frontend/product/backlog docs, then close Epic A through the full acceptance gate. |

## Promoted execution plans

The following task briefs were promoted from the detailed `.superpowers` work
ledger so later agents can read their original scoped requirements without
depending on ignored files:

- [A2 Task 3 — canonical network models](execution/a2-task-3-canonical-models.md)
- [A2 Task 4 — atomic wiki storage](execution/a2-task-4-atomic-storage.md)
- [A2 Task 5 — Chemie 8/9 seeds](execution/a2-task-5-chemie-seeds.md)
- [A2 Task 6 — reviewed adoption API](execution/a2-task-6-adoption-api.md)
- [A3 Task 7 — React Flow adapter](execution/a3-task-7-canvas-adapter.md)
- [A3 Task 8 — read-only course workspace](execution/a3-task-8-workspace.md)

They describe completed work and its original boundaries; use the current code,
this handoff, and the main delivery plan as the authority for the next task.

## A3 browser behavior verified

The current course workspace is intentionally read-only.

- On a wide view, the teacher can pan/zoom/fit the network and select a node.
  The inspector shows its learning goal, description, curriculum evidence, and
  graph relationships.
- On a narrow view, the app deliberately substitutes a searchable outline plus
  the same inspector rather than forcing an imprecise graph canvas into a small
  window.
- Selecting a related node updates the inspector and canvas emphasis. Opening a
  curriculum source reveals the exact class-authorized source section and its
  provenance; switching nodes clears the prior source panel.
- `Materials` is visibly disabled as “Coming soon”; the future route is not
  linked and therefore cannot produce a 404.

The React Flow selection bug found in browser testing is fixed: React Flow owns
its own selected state, while the workspace passes only a presentation flag for
inspector/outline-driven selection. The former feedback loop (`selected` node
props plus `onSelectionChange`) is not used.

Fresh Task 8 evidence: actual React Flow renderer and workspace tests passed
10/10; full frontend suite passed 49 files / 223 tests; TypeScript typecheck
and diff checks passed. A live browser check selected `Katalyse`, opened its
curriculum evidence, followed `Builds on Aktivierungsenergie`, confirmed the
new inspector content and canvas emphasis, and confirmed old source evidence
was cleared. Final Task 8 re-review: PASS, no findings.

## Immediate next steps

1. Execute A3 Task 9 only: add one class-home `Course` action beside Browse
   class files; document the route, view-only canvas boundary, and narrow
   outline behavior. Do not add editing or materials UI in this task.
2. Run the full Epic A deterministic gate from the worktree:

   ```powershell
   .\scripts\test.ps1
   ```

3. Run a fresh-sandbox HITL test before Epic B. Start with
   `./scripts/worktree-stack.cmd up --beta --fresh-wiki --fresh-beta-data`,
   create Chemie 8a, confirm pre-adoption has no canonical network, review and
   adopt the seed, inspect desktop canvas/keyboard selection/narrow outline,
   and verify `course_network/overview.md` in Browse class files. Preserve the
   tracked baseline wiki and stop only the worktree-scoped Compose project when
   done.
4. Only after that acceptance is green, begin Epic B (reviewed graph editing)
   using `docs/superpowers/plans/2026-08-18-course-network-editing.md`.

## Later-program order

| Epic | Scope | Do not pull forward |
| --- | --- | --- |
| B — reviewed graph editing | Stage manual/agent-assisted operations, validate and review them, then atomically approve/reject. | Direct canvas writes or hidden agent edits. |
| C — durable materials and mappings | Upload textbook/teacher material outside lesson planning, review extraction, promote it, and approve mappings to learning blocks. | Lesson-scoped OCR promotion as the only library workflow. |
| D — planner and lesson integration | Automatically retrieve the relevant network/material neighbourhood for weekly planning; save plan and lesson-result references. | Asking teachers to tag every plan manually or changing planning chat’s read-only write boundary. |

## Local development handoff

The current local stack for browser work is worktree-scoped:

- Frontend: `http://localhost:3303`
- Backend health: `http://localhost:8578/api/health`
- Compose project: `kp_teacher_agent_v2_64977d`
- Mutable test wiki: `backend/teacher_wiki_sandbox/`

The user’s manually created/adopted Chemie 8a lives only in that sandbox and is
not tracked. Do not alter `backend/teacher_wiki/` unless a task explicitly
changes the baseline fixture. The supported command for a clean isolated stack
is `./scripts/worktree-stack.cmd up --fresh-wiki`; add `--beta --fresh-beta-data`
only for beta/HITL coverage.

## Evidence and commit landmarks

- A1 final verification: `57b9150` (with prior remediation `75d0c8e`).
- A2 final review remediation: `7a1f0aa`; fresh API acceptance recorded under
  `.superpowers/sdd/2026-08-18-course-network-foundation/a2-api-acceptance-report.md`.
- A3 adapter: `b11d9db`, corrected by `29ed293`.
- A3 workspace and review fixes: `b37a051`, `8202124`.
- A3 React Flow selection stabilization and coherence: `00b7c40`, `2d21263`.

Before completing A3, make the final Epic A verification report explicit about
the exact commits tested and whether the sandbox wiki changed. Do not treat
this handoff document as evidence that A3 or Epic A has merged or shipped.
