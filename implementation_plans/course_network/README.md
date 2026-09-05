# Course Network Delivery Handoff

**Updated:** 2026-09-04

**Branch:** `cursor/5c01f259` (continues `codex/class-course-network-design`)

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
- Adopted HITL graph: [`fixtures/chemie_8a_2026_27/`](fixtures/chemie_8a_2026_27/)

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
| A3 Task 8 — workspace | Complete, with 2026-09-04 HITL layout follow-up | `/classes/{classId}/course` loads an adopted graph or guides seed review/adoption. It provides a canvas from `sm` (640px), a narrower-than-`sm` searchable outline, node inspector, relationship navigation, and class-authorized curriculum-source evidence. The page scrolls; connection cards are the last inspector section. |
| A3 Task 9 | Next — not started | Add the single `Course` action on class home, reconcile frontend/product/backlog docs, then close Epic A through the full acceptance gate. |

## A3 browser behavior verified

The current course workspace is intentionally read-only.

- On a wide view, the teacher can pan/zoom/fit the network and select a node.
  The inspector shows its learning goal, description, curriculum evidence, and
  graph relationships. For a selected block, **Connections** is the last
  inspector section; there is no hidden panel under those cards.
- From `sm` (640px) the canvas stays visible. Below `sm` the app substitutes a
  searchable outline plus the same inspector.
- Selecting a related node updates the inspector and canvas emphasis. Opening a
  curriculum source reveals the exact class-authorized source section and its
  provenance; switching nodes clears the prior source panel.
- `Materials` is visibly disabled as “Coming soon”; the future route is not
  linked and therefore cannot produce a 404.

### HITL layout follow-up (2026-09-04)

Verified in a ~667×710 Cursor browser pane on adopted Chemie 8a:

- Flush `main` and the course workspace allow page scroll so the inspector is
  not clipped at the window edge.
- Graph handles stay in layout at every canvas breakpoint. A previous
  `display: none` rule below 768px collapsed every React Flow edge to a point.
- Fit-view reruns on canvas resize; wheel over the graph does not steal page
  scroll (`zoomOnScroll={false}`, `preventScrolling={false}`).

This follow-up does **not** close Task 9 or Epic A. Known leftovers from the
same HITL pass:

- There is still no class-home `Course` button; the workspace is URL-only.
- Seed review can return `revise` with notes only, which disables both Review
  and Adopt and leaves the teacher with Discard. Chemie 8a in the local
  sandbox was operator-accepted; that is not a product fix.
- Browse class files still does not show `course_network/overview.md`
  (`kind: course_network` is omitted from the wiki viewer).
- Full `.\scripts\test.ps1` and the fresh-sandbox Epic A HITL gate have not
  been rerun after this layout follow-up. Focused course-network Vitest files
  in the frontend container passed.

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

## Agent continuation — how to set this up

Start here if you are a later agent on `cursor/5c01f259`. Do not invent a
second stack on the main repo ports. This worktree is isolated.

### 1. Read this handoff, then the next task

1. This file (status, leftovers, fixture graph).
2. [`03_foundation_implementation.md`](03_foundation_implementation.md) Task 9
   only, unless the teacher asked for Epic B.
3. [`AGENTS.md`](../../AGENTS.md) and [`frontend/DESIGN.md`](../../frontend/DESIGN.md)
   before UI work.

### 2. Local secrets (never commit)

`backend/.env` is gitignored. If it is missing, copy it from the main checkout
or another trusted local worktree, then keep this profile (keys stay local):

```dotenv
APP_ENV=development
MODEL_PROFILE=economy
BETA_ENABLED=false
MISTRAL_OCR_MODEL=mistral-ocr-latest
MISTRAL_API_KEY=<local Mistral API key>
```

This worktree has no `backend/.venv`. Use the frontend/backend containers from
the stack helper, or the host venv at `C:\Users\matth\teacher_agent_v2\backend\.venv`
for pytest only.

### 3. Start the worktree stack

Preserve an existing sandbox (this worktree already has adopted Chemie 8a):

```powershell
.\scripts\worktree-stack.cmd up --wiki sandbox --app-env development --model-profile economy
```

`--fresh-wiki` wipes the sandbox back to tracked `backend/teacher_wiki/` (Chemie
9b only, **no adopted graph**). After a fresh wiki, install the fixture:

```powershell
Copy-Item -Recurse -Force `
  implementation_plans\course_network\fixtures\chemie_8a_2026_27 `
  backend\teacher_wiki_sandbox\wiki\classes\chemie_8a_2026_27
```

Then restart or wait for the backend to see the class. Do not add `--beta` or
`--fresh-beta-data` unless you are running the Epic A HITL gate.

The helper prints `FRONTEND_URL` and `API_HEALTH_URL`. This worktree’s last
known ports:

- Frontend: `http://localhost:3228`
- Backend health: `http://localhost:8830/api/health`
- Compose project: `kp_9bv6_54edd4`

Confirm with `docker compose -p kp_9bv6_54edd4 ps` rather than assuming those
ports if another stack is running.

### 4. Open the adopted graph

There is still **no Course button** on class home. Use the URL:

- Adopted graph (continue here): `http://localhost:3228/classes/chemie_8a_2026_27/course`
- Seed / no-network class: `http://localhost:3228/classes/chemie_9b_2026_27/course`

The adopted Chemie 8 NTG graph is 12 Lernbausteine / 12 `builds_on` edges,
revision 1, in
[`fixtures/chemie_8a_2026_27/course_network/network.json`](fixtures/chemie_8a_2026_27/course_network/network.json).
It is **not** copied into tracked `backend/teacher_wiki/` because API tests
create `chemie_8a_2026_27` on a 9b-only seed wiki.

### 5. What not to do

- Do not commit `backend/.env` or `backend/teacher_wiki_sandbox/`.
- Do not treat Epic A as shipped. Task 9 + `.\scripts\test.ps1` + fresh-sandbox
  HITL are still open.
- Do not start Epic B graph editing until that gate is green, unless the
  teacher explicitly asks to skip it.
- Seed review can still return `revise` with notes only and trap Adopt. Do not
  “fix” that by editing SQLite unless the teacher asks for another operator
  override.

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

- Frontend: `http://localhost:3228`
- Backend health: `http://localhost:8830/api/health`
- Compose project: `kp_9bv6_54edd4`
- Mutable test wiki: `backend/teacher_wiki_sandbox/`

The live sandbox copy of Chemie 8a stays untracked under
`backend/teacher_wiki_sandbox/`. The same adopted class (graph included) is
tracked as
[`fixtures/chemie_8a_2026_27/`](fixtures/chemie_8a_2026_27/). Do not copy that
class into `backend/teacher_wiki/`; provisioning tests create
`chemie_8a_2026_27` against the 9b-only seed. The supported command for a clean
isolated stack is `./scripts/worktree-stack.cmd up --fresh-wiki`, then install
the fixture (see Agent continuation). Add `--beta --fresh-beta-data` only for
beta/HITL coverage.

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
- A3 HITL layout follow-up (narrow-pane edges + page scroll): `2a1deec`.
- Adopted Chemie 8a graph fixture + agent continuation setup: this follow-up
  commit on `cursor/5c01f259`.

Before completing A3, make the final Epic A verification report explicit about
the exact commits tested and whether the sandbox wiki changed. Do not treat
this handoff document as evidence that A3 or Epic A has merged or shipped.
