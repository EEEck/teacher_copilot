# Class Course Network Delivery Program

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a class-owned Chemie 8/9 NTG course network, durable materials library, reviewed graph maintenance, and automatic lesson-planning integration as a sequence of independently reviewable releases.

**Architecture:** Store one canonical, versioned course-network document inside each class wiki and compile a Markdown overview for inspection and LLM retrieval. Use existing durable workflow drafts, exact-revision write gates, OCR packaging, evidence briefs, and review UI as foundations; React Flow renders an API view model and never becomes the persistence format.

**Tech Stack:** FastAPI, Pydantic 2, stdlib JSON/file operations, OpenAI Agents SDK, Mistral OCR, Next.js 15, React 19, TypeScript 5.7, Zustand 5, `@xyflow/react` 12.11.x, Tailwind, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-08-17-class-course-network-design.md`

## Delivery status — 2026-08-22

This is an in-progress branch status, not a claim that the feature has merged
or shipped. The durable agent handoff is
[`implementation_plans/course_network/README.md`](../../../implementation_plans/course_network/README.md).

- **A1 — complete and verified:** deterministic Chemie 8/9 NTG class
  provisioning, including fresh-sandbox API and browser acceptance.
- **A2 — complete and verified:** canonical class-owned network, reviewed
  Chemie 8/9 seed adoption, atomic persistence, index/overview compilation,
  and API acceptance.
- **A3 Tasks 7–8 — complete and reviewed:** read-only React Flow workspace,
  outline fallback, inspector, adoption surface, and class-authorized
  curriculum-source evidence. The desktop graph interaction was live-browser
  tested after the React Flow selection fix.
- **A3 Task 9 and the Epic A final gate remain:** add the class-home Course
  entry and documentation, then run the full Epic A deterministic and fresh
  HITL acceptance before starting Epic B.

## Global Constraints

- The network is class-owned in the MVP; cross-class inheritance, export, and import are excluded.
- One teacher-facing node type is used: `Lernbaustein`.
- Planning chat is read-only; canonical network/material writes require explicit teacher approval.
- Questions and exercises remain inside material content; no question bank or OCR question extraction is added.
- A future structured question feature must version a fixed rubric with every question revision.
- React Flow is a replaceable canvas layer; its full JSON format is never canonical backend data.
- Reuse the fixed frontend design system and existing review/error/running-work components.
- No graph database, vector database, additional backend dependency, or automatic layout dependency is introduced.
- New frontend runtime dependency: `@xyflow/react` pinned through the lockfile from `^12.11.3`.
- Chemie 8 NTG ships first; Chemie 9 NTG follows through the same route-driven contracts.
- Legacy `teaching_framework_adjustments.md` remains a fallback until a class adopts a course network.
- Every API/schema change updates `contracts/openapi.yaml` in the same PR.
- Every behavior change updates its durable product/agent/wiki/frontend documentation in the same PR.

---

## Delivery Shape

The approved design contains four sequential subsystems. Implement them through
four linked plans so each produces useful, testable software and can be stopped
or reprioritized without leaving a half-integrated platform.

| Epic | Detailed plan | Product increment |
|---|---|---|
| A. Foundation and adoption | `docs/superpowers/plans/2026-08-18-course-network-foundation.md` | Create Chemie 8/9 classes, adopt a reviewed seed, inspect the network in a read-only React Flow workspace |
| B. Reviewed graph editing | `docs/superpowers/plans/2026-08-18-course-network-editing.md` | Stage manual/agent-assisted graph operations, validate, LLM-review, approve, and commit atomically |
| C. Durable materials and mappings | `docs/superpowers/plans/2026-08-18-course-materials-and-mapping.md` | Upload outside lessons, review extraction, promote packages, and approve material-to-node mappings |
| D. Planner and lesson integration | `docs/superpowers/plans/2026-08-18-course-network-planner-integration.md` | Retrieve network neighbourhoods automatically, save plan tags, associate lesson results, and migrate legacy framework behavior |

## Architectural Decisions Locked for Planning

### Canonical class-wiki files

```text
wiki/classes/{class_id}/
  course_network/
    network.json        # canonical nodes, edges, mappings, positions, revision
    overview.md         # deterministic compiled view; rebuildable
  materials/
    textbooks/{material_id}/
      material.json     # approved identity + section hierarchy
      document.agent.md
      summary.md
      provenance.json
      page_structure.json
      assets/*
    personal/{material_id}/
      ...               # same package; teacher-facing label is Teacher material
  lessons/{date}/
    lesson_plan.md
    lesson_results.md
    materials.json      # existing material-id compatibility file
    course_refs.json    # planned/taught/revisit node references
```

`network.json` is the only graph source of truth and is replaced atomically.
`overview.md` is regenerated after a successful canonical write and can be
repaired from JSON. Material packages remain separate canonical sources.

### Structured draft reuse

Extend `WorkflowDraftStore` with structured-artifact helpers while preserving
the existing SQLite column and plan/ingest behavior:

```python
def open_structured_draft(
    self,
    identity: WorkflowDraftIdentity,
    *,
    default_status: str,
    artifact: BaseModel | dict[str, Any],
    runtime_json: dict[str, Any] | None = None,
) -> OpenWorkflowDraftResult: ...

def save_structured_draft(
    self,
    draft_id: str,
    *,
    status: str,
    artifact: BaseModel | dict[str, Any],
    runtime_json: dict[str, Any] | None = None,
    executive_json: dict[str, Any] | None = None,
) -> WorkflowDraftRow: ...
```

The helpers serialize stable, sorted JSON into the existing artifact field and
therefore inherit revision/hash, active-review snapshot, workspace isolation,
discard, and terminal-state behavior. Do not register course-network or
material-import pages as assistant-ui chat modes.

### Shared review pipeline

Reuse these existing layers:

- `artifact_fingerprint`, `ExecutiveRuntime`, `apply_write_verification`, and
  `evaluate_write_gate` for exact-artifact safety;
- `WorkflowDraftStore.mark_review_snapshot` and
  `validate_review_snapshot` for stale-draft protection;
- `ReviewChrome`, `WorkflowActionNeededCard`, buttons, fields, and semantic
  tokens in the frontend.

Add course-specific layers:

- typed operation validation for graph integrity and material references;
- a bounded no-tools chemistry/curriculum reviewer that returns report rows and
  `ExecutivePatch` findings;
- an operation review panel rather than pretending graph operations are
  Markdown file diffs.

### Frontend routes

```text
/classes/{classId}/course
  Network canvas, outline fallback, node inspector, adoption/edit review

/classes/{classId}/course/materials
  Durable textbook and teacher-material library

/classes/{classId}/course/materials/import/{draftId}
  Extraction review followed by network-mapping review
```

Class home adds one `Course` action. The course workspace owns tabs/links for
Network and Materials, keeping the existing class-home action row from growing
into a second navigation system.

### Frontend composition

```text
app routes
  -> components/klassenpilot/course/*       # page composition and domain UI
  -> features/course-network/*              # draft reducer, API/view adapters
  -> lib/api.ts                              # transport types and calls
  -> components/ui + components/klassenpilot/review
  -> @xyflow/react                           # canvas interaction only
```

Desktop shows canvas plus a fixed inspector. Narrow screens default to a
searchable Lernbaustein outline and inspector; they do not force precision edge
editing on a phone.

### New libraries

Only `@xyflow/react` is added. Seed positions and teacher-saved positions avoid
an auto-layout dependency. A deterministic layered layout helper handles nodes
without positions. Do not add ELK, Dagre, a graph database, or a second state
manager during the MVP.

## Reuse and Refactor Matrix

| Need | Reuse | Focused change |
|---|---|---|
| Class creation | Claude branch `claude/class-generator-setup-wizard-70c68b` | Port only deterministic Chemie 8/9 provisioning and UI; exclude unrelated source crawl/Physics expansion |
| Revision/hash drafts | `WorkflowDraftStore` | Add stable JSON helpers and generic running-state methods |
| Exact write gate | `executive_verification.py` | Add course-specific report translation; do not weaken existing gates |
| LLM checking | `AgentRunner` structured one-shot pattern and Plan verification | Add no-tools `review_course_network`; do not reuse the generic prompt unchanged |
| Wiki facade | `WikiStore` delegation pattern | Add focused `course_network.py`; keep `store.py` thin |
| OCR | `materials_ocr*`, `materials_scratch.py` | Move upload validation/promotion policy out of `PlanService`; keep Mistral runtime |
| Material retrieval | `wiki/materials.py` | Add durable library enumeration independent of lesson links |
| Planner evidence | `PlanRuntime`, evidence briefs, raw refs | Add bounded network orientation and read tools |
| Review UI | `review-chrome`, workflow error components | Add typed operation rows and report card; do not force graph edits into file diffs |
| Background status | `WorkflowDraftStore`, `/workflow/active`, Running box | Add `course_network` and `course_material` labels/hrefs; poll final draft snapshots without registering assistant-ui modes |
| Design system | shared UI and KlassenPilot components | Build custom React Flow nodes from semantic tokens; no copied Tailwind islands |

## Epic and PR Map

### Epic A — Foundation and adoption

- **PR A1:** Port deterministic Chemie class creation from the Claude branch.
- **PR A2:** Add network schema, JSON store, Chemie 8/9 seeds, adoption draft,
  deterministic/LLM review, API, index/search integration, and compatibility
  fallback.
- **PR A3:** Add `@xyflow/react`, read-only course workspace, outline fallback,
  node inspector, adoption review, and class-home entry.

Exit: a teacher can create Chemie 8a, review/adopt the seed, and inspect the
canonical graph. No editing or course material upload is enabled yet.

### Epic B — Reviewed graph editing

- **PR B1:** Add typed operations, deterministic validation, exact draft
  review/commit, audit log entries, and course-specific LLM judgement.
- **PR B2:** Add canvas/inspector edit mode, agent-assist request, operation
  review, findings UI, stale-revision recovery, and keyboard/mobile coverage.

Exit: a teacher can safely maintain the graph independently of lesson planning.

### Epic C — Durable materials and mappings

- **PR C1:** Extract shared OCR package policy; add import drafts, background
  OCR status, and material identity/section schemas.
- **PR C2:** Add canonical materials library, extraction-review pages,
  structure edits, asset preview, exact review, search, and approved promotion.
- **PR C3:** Add mapping/enrichment proposal agent, typed missing-node/edge
  operations, validation, operation review, atomic network commit, and
  mapped-material inspector UI.

Exit: a teacher can prepare a quarter's textbook/teacher materials and connect
approved sections to the graph outside lesson planning.

### Epic D — Planner and lesson integration

- **PR D1:** Add deterministic network search/neighbourhood tools, context-pack
  tracing, and automatic PlanRuntime node references.
- **PR D2:** Persist `course_refs.json`, associate approved lesson results with
  taught/revisit nodes without a new teacher step, link consulted materials,
  and preserve legacy framework fallback.
- **PR D3:** Complete fallback routing, Chemie 8/9 evals, product docs, wiki
  docs, frontend docs, browser acceptance runbook, and full deterministic
  regression.

Exit: weekly planning automatically uses the graph and materials, while the
teacher-facing Plan and Update Memory flows retain their current cadence.

## Product Documentation Map

| Document | Change owner |
|---|---|
| `docs/pm_hub.md` | A1 records class setup; A3 records course workspace; C2 records year-start library; D3 closes roadmap gaps |
| `docs/product_vision.md` | A3 adds build/use cadence; D3 confirms integrated weekly loop |
| `implementation_plans/product_backlog.md` | Every merged PR marks its slice and removes superseded framework/library wording |
| `docs/agent_architecture.md` | B1 documents graph review; C3 mapping evidence; D1 retrieval/context |
| `docs/agent_contracts.md` | A2 adoption writes; B1 edit writes; C1/C3 material writes; D1/D2 planner/result contracts |
| `docs/memory_hierarchy.md` | A2 canonical network; C1 material manifest; D2 course references and legacy fallback |
| `backend/teacher_wiki/AGENTS.md` | A2/C1/D2 wiki paths and approval rules |
| `frontend/ARCHITECTURE.md` | A3 route/component layering; B2 draft/edit lifecycle; C2 import workflow |
| `frontend/DESIGN.md` | A3 canvas tokens; B2 operation review; C2 extraction review patterns |
| `contracts/openapi.yaml` | Updated in every API PR |

## Release Gates

Each PR runs its focused tests plus:

```powershell
cd backend
.\.venv\Scripts\python -m pytest tests\test_api_stream.py tests\test_api_workflow_active.py tests\test_wiki_store.py

cd ..\frontend
npm run typecheck
npm run test
```

Each epic closes with the repository-wide deterministic suite:

```powershell
.\scripts\test.ps1
```

No live OpenAI call is required for CI. Agent proposal/review behavior receives
stub/golden contract tests; one opt-in live eval is added per LLM feature. Run a
fresh worktree sandbox for HITL acceptance only after deterministic checks pass.

## Execution Order

- [ ] **Step 1: Complete Epic A using the foundation plan**

Read and execute `docs/superpowers/plans/2026-08-18-course-network-foundation.md`.

- [ ] **Step 2: Run the Epic A acceptance gate**

Run `./scripts/test.ps1`, then use
`./scripts/worktree-stack.cmd up --beta --fresh-beta-data` to create Chemie 8a,
adopt its seed, and inspect the canvas.

- [ ] **Step 3: Complete Epic B using the editing plan**

Read and execute `docs/superpowers/plans/2026-08-18-course-network-editing.md`.

- [ ] **Step 4: Run the Epic B acceptance gate**

Verify manual add/edit/connect/delete, agent-assisted edits, rejection,
blocking findings, stale revision, narrow-screen outline, and atomic commit.

- [ ] **Step 5: Complete Epic C using the materials plan**

Read and execute
`docs/superpowers/plans/2026-08-18-course-materials-and-mapping.md`.

- [ ] **Step 6: Run the Epic C acceptance gate**

Upload a multi-chapter PDF in a fresh beta sandbox, correct its hierarchy,
promote it, review mappings, and confirm the original plan-only PDF path still
works.

- [ ] **Step 7: Complete Epic D using the integration plan**

Read and execute
`docs/superpowers/plans/2026-08-18-course-network-planner-integration.md`.

- [ ] **Step 8: Run final acceptance and documentation reconciliation**

Run `./scripts/test.ps1`, the new offline graph-aware planning goldens, one
opt-in live planning eval, and the browser runbook. Confirm every documentation
row above describes shipped behavior rather than planned behavior.
