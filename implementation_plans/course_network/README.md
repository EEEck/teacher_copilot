# Course Network Delivery Handoff

**Updated:** 2026-09-05

**Branch:** `codex/class-course-network-design`

**Purpose:** a tracked handoff and shipping entry point for the class-owned course-network
program. The active shipping scope and implementation plan are linked below.
Original detailed plans remain in
[`docs/superpowers/plans/`](../../docs/superpowers/plans/); ephemeral review and
test evidence remains ignored under `.superpowers/sdd/`.

## Source documents

Documents 01–03 are promoted copies of the original planning documents.
Documents 04–05 define the implemented core workflow. Document 08 is the active
plan for the teacher-owned release work; its implementation is now present on
the feature branch. Document 09 records the fresh-workspace browser checks,
restoration rehearsal and remaining deployment gates.
Documents 06–07 record implementation and synthetic acceptance evidence, not
acceptance of fresh-teacher onboarding or a hosted release.

- [01 — approved product design](01_product_design.md)
- [02 — delivery program, Epic A–D](02_delivery_program.md)
- [03 — detailed A1–A3 foundation implementation plan](03_foundation_implementation.md)
- [04 — optimized end-to-end shipping scope](04_shipping_scope.md)
- [05 — optimized implementation plan](05_shipping_implementation.md)
- [06 — implementation and validation record](06_shipping_validation.md)
- [07 — realistic browser acceptance](07_browser_acceptance.md)
- [08 — teacher-owned release gaps and finishing plan](08_teacher_owned_release_plan.md)
- [09 — teacher-owned release acceptance](09_teacher_owned_release_acceptance.md)
- [Closed-beta operator runbook](../../docs/course_release_runbook.md)
- [Teacher guide — use and review the map](../../docs/course_graph_guide.md)
- [Current handoff and historical verified progress](README.md)

## Product boundary

The MVP is a **class-owned** Chemie 8/9 NTG course network. It has one
teacher-facing node type, `Lernbaustein`, and `builds_on` / `related_to`
relationships. The class wiki owns the canonical graph at
`course_network/network.json`; `overview.md` is regenerated for inspection and
retrieval. React Flow is only a view layer.

The implementation now includes reviewed concept changes, standalone chapter
imports and mappings, automatic planning context, and saved lesson references.
Deterministic/live API validation is recorded in 06; realistic browser acceptance
and the integration fix found during it are recorded in 07.
Question extraction, cross-class reuse, and graph databases remain excluded.

## Current progress

| Slice | Status | What is now available |
| --- | --- | --- |
| A1 — class provisioning | Complete and verified | A teacher can create a deterministic Chemie 8/9 NTG class. Provisioning creates the expected class wiki shell, rejects duplicates with the canonical error envelope, and does not call an LLM or external service. |
| A2 — network/adoption API | Complete and verified | Class-owned canonical network models, reviewed Chemie 8/9 seeds, exact-revision review/adoption, atomic JSON + overview/index publication, and legacy-framework fallback are implemented. |
| A3 Task 7 — canvas adapter | Complete and reviewed | `@xyflow/react` renders an immutable API view model. Canonical graph data never uses React Flow JSON; missing positions receive deterministic fallback coordinates. |
| A3 Task 8 — workspace | Complete and reviewed | `/classes/{classId}/course` loads an adopted graph or guides seed review/adoption. It provides a desktop canvas, narrow-screen searchable outline, node inspector, relationship navigation, and class-authorized curriculum-source evidence. |
| A3 Task 9 | Browser verified | Class home has the Course action. Materials opens the standalone chapter workspace. |
| Reviewed materials and changes | Implemented; live API and browser verified | PDF extraction, stable editable sections, exact document approval, generated mappings/concepts, exact map review/publication and recovery. |
| Planning integration | Implemented; live API and browser verified | Existing planning automatically receives bounded map/material context; plan save records explicit concept/material citations, including exact formatted concept IDs. |
| Teacher-owned release | Implemented; local validation in 09 | Demo retained plus optional empty workspace; own-class onboarding, saved-PDF normalization, archive/restore, teacher corrections, durable generation, honest lesson links and two-account isolation. 838 backend / 252 frontend tests pass; production build passes. Hosted deployment remains a separate gate. |

## Historical A3 browser evidence (before this change)

The earlier foundation workspace was intentionally read-only.

- On a wide view, the teacher can pan/zoom/fit the network and select a node.
  The inspector shows its learning goal, description, curriculum evidence, and
  graph relationships.
- On a narrow view, the app deliberately substitutes a searchable outline plus
  the same inspector rather than forcing an imprecise graph canvas into a small
  window.
- Selecting a related node updates the inspector and canvas emphasis. Opening a
  curriculum source reveals the exact class-authorized source section and its
  provenance; switching nodes clears the prior source panel.
- At that stage `Materials` was disabled. The current implementation enables it;
  the new route has rendered tests and browser acceptance recorded in 07.

The React Flow selection bug found in browser testing is fixed: React Flow owns
its own selected state, while the workspace passes only a presentation flag for
inspector/outline-driven selection. The former feedback loop (`selected` node
props plus `onSelectionChange`) is not used.

Historical Task 8 evidence: actual React Flow renderer and workspace tests passed
10/10; full frontend suite passed 49 files / 223 tests; TypeScript typecheck
and diff checks passed. A live browser check selected `Katalyse`, opened its
curriculum evidence, followed `Builds on Aktivierungsenergie`, confirmed the
new inspector content and canvas emphasis, and confirmed old source evidence
was cleared. Final Task 8 re-review: PASS, no findings.

## Active release plan — 2026-09-05

Read [08 — teacher-owned release plan](08_teacher_owned_release_plan.md).
The core upload → map → plan → results loop is implemented and has synthetic
browser evidence. The next gate is an invited teacher starting with an empty
workspace, creating their own class and completing that loop with their own
materials without developer assistance.

The remaining work is clean workspace provisioning, coherent material discovery
across both upload paths, complete teacher correction controls, relevant planning
context and lesson navigation, and fresh-account recovery/isolation acceptance.
Keep Chemistry 8/9 NTG as the recommended initial boundary; broader subject
support remains a scope decision. No graph redesign or new hosting platform is
required by this plan.

Code checkpoint: `d3e5638` is pushed; follow-up `fa184d3` is committed locally
but its additional push is pending explicit approval after automatic review.
Neither checkpoint alone establishes a merged or deployed release.

## Implemented core shipping scope — 2026-09-04

The next release is the connected course-knowledge workflow: curriculum map,
standalone course-material upload, reviewed section-to-concept mappings,
automatic use in ordinary lesson planning, and saved plan/result references.
The map serves both teacher inspection and source-grounded agent retrieval.
A standalone graph-generation chat or viewer is not the release goal.

Read [04 — shipping scope](04_shipping_scope.md) and
[05 — implementation plan](05_shipping_implementation.md) for core design and
implementation detail. These superseded
the old sequential B → C → D execution order for the first end-to-end release.
The original documents remain design references and historical evidence.

1. Close the foundation: Course entry, relationship semantics, source-scope
   labels, and fresh acceptance of the existing adoption/viewer implementation.
2. Add the small reviewed graph-change boundary required by corrections and
   enrichment, using forms and proposal rows.
3. Add standalone chapter-sized material imports with stable section references.
4. Add the backend-owned curriculum-generation/material-enrichment procedure.
5. Connect document review, mapping review, and source/material inspection.
6. Add bounded graph/material retrieval to the existing lesson planner.
7. Persist lesson references and evidence-grounded result associations.
8. Run the full upload → map → plan → results → next-plan acceptance scenario.

The core work above is implemented; see 06–07 for evidence and limitations.
Document 08 identifies gaps found in the subsequent teacher-owned release review.

## Original program reference

The original Epic B–D plans retain useful technical detail. Use only the parts
selected by the optimized plan; a complete canvas editor and whole-book
structure editor are deferred. Material mappings, automatic planning retrieval,
and saved lesson references remain required for the first release.

| Epic | Scope | Do not pull forward |
| --- | --- | --- |
| B — reviewed graph editing | Stage manual/agent-assisted operations, validate and review them, then atomically approve/reject. | Direct canvas writes or hidden agent edits. |
| C — durable materials and mappings | Upload textbook/teacher material outside lesson planning, review extraction, promote it, and approve mappings to learning blocks. | Lesson-scoped OCR promotion as the only library workflow. |
| D — planner and lesson integration | Automatically retrieve the relevant network/material neighbourhood for weekly planning; save plan and lesson-result references. | Asking teachers to tag every plan manually or changing planning chat’s read-only write boundary. |

## Local development handoff

Latest browser acceptance used the worktree-scoped stack below. It was not
restarted or re-tested during the 2026-09-05 documentation review:

- Worktree: `C:/Users/matth/.codex/worktrees/849f/teacher_agent_v2`
- Frontend: `http://localhost:3313`
- Backend health: `http://localhost:8588/api/health`
- Compose project: `kp_course_e2e_849f`
- Mutable test wiki: `.worktree-stack/course-e2e/wiki/`

The latest acceptance uses synthetic Chemie 9b data in that ignored sandbox.
Do not alter `backend/teacher_wiki/` unless a task explicitly
changes the baseline fixture. The supported command for a clean isolated stack
is `./scripts/worktree-stack.cmd up --fresh-wiki`; add `--beta --fresh-beta-data`
only for beta/HITL coverage.

### Default local test profile

Use this profile for normal development and course-network HITL checks. It is
local-only and must stay in the ignored `backend/.env`, never in Git:

```dotenv
APP_ENV=development
MODEL_PROFILE=economy
BETA_ENABLED=false
MISTRAL_OCR_MODEL=mistral-ocr-latest
MISTRAL_API_KEY=<local Mistral API key>
```

Start an isolated local wiki with the explicit economy profile and **without**
beta data:

```powershell
.\scripts\worktree-stack.cmd up --fresh-wiki --model-profile economy
```

Do not add `--beta` or `--fresh-beta-data` for this default path. The helper
prints the worktree-specific frontend and backend ports; use those URLs rather
than assuming another worktree's stack is serving this branch. Beta remains an
intentional, separate acceptance mode.

`MISTRAL_API_KEY` enables the product's live PDF OCR path. Obtain or rotate it
in the Mistral workspace/API-key console, then paste it only into the local
`backend/.env`. Do not paste it into a chat, a plan, a test fixture, or a
committed `.env` file. `RUN_LIVE_MISTRAL_OCR=1` is needed only for the opt-in
live pytest cases; it is not a default development setting.

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
