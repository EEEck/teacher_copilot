# Teacher-owned course release implementation plan

> For agentic workers: use `superpowers:executing-plans` to implement this plan task by task. This is the remaining release work; do not rebuild the completed feature in 05.

**Date:** 2026-09-05
**Status:** Implementation present on the feature branch; local acceptance is recorded in [09](09_teacher_owned_release_acceptance.md). Hosted deployment remains a separate gate.
**Goal:** An invited teacher can explore the seeded demo, create their own class, bring their own PDFs, review its concept map, and complete the plan → approved results → next-plan loop without developer assistance.
**Architecture:** Keep the class wiki, stable concept/material identifiers, existing proposal/review/publication services, and ordinary planning workflow. Close onboarding and integration gaps around those services. Keep the existing single-process deployment model.
**Tech stack:** FastAPI/Pydantic, filesystem wiki and SQLite workflow drafts, OpenAI Agents SDK, Mistral OCR, Next.js/React, existing design system and React Flow, Docker/Railway configuration.
**Spec:** [04 shipping scope](04_shipping_scope.md), [product vision](../../docs/product_vision.md), [agent contracts](../../docs/agent_contracts.md), and the teacher-owned workflow requested in this review.

## Scope and constraints

- Recommended release boundary: teachers' own **Chemie 8/9 NTG classes**, Gymnasium Bayern. The subject/grade expansion question is still open. This plan does not promise arbitrary subjects.
- User update: retain the seeded demo by default for the closed beta. Teachers can also create their own class, which starts with no taught lessons. Optional empty provisioning copies only reviewed shared assets and initializes fresh memory; it never inherits demo classes, materials, preferences or workflow state.
- Invite provisioning is sufficient for this private release; self-service signup is not required.
- PDFs remain chapter-sized: existing 40 MB / 30 selected-page limits. Clearly explain supported formats and limits in the upload flow.
- Planning chat remains read-only with respect to durable wiki memory. Plan save may promote its materials; extraction and graph changes retain their explicit review/approval boundaries.
- `builds_on` means source depends on target. The map describes content relationships, never automatically established teaching coverage or mastery.
- Reuse shared UI controls. Keep the canvas read-only; corrections belong in bounded proposal forms.
- No graph database, graph chat, general agent orchestration, automatic mastery tracking, whole-book editor, cross-class sharing, or hosting migration.
- Never clean or replace existing teacher workspaces as an onboarding migration.

If other subjects are required, first add an explicit materials-led route that does not claim official curriculum coverage. That affects `class_provisioning.py`, `course_network/models.py`, `seeds.py`, `prompts.py`, generation/context contracts and onboarding, not just the subject dropdown. Treat this as a separate scope decision before execution.

## Review findings and evidence limits

The core map → material → planning loop exists. [07](07_browser_acceptance.md) records a live synthetic chemistry browser journey, including saved results and the next plan. That test used an existing sandbox class; later chemistry corrections also used a backend harness. It does **not** establish that a fresh teacher can finish unaided.

| Finding | Code evidence | Release consequence |
| --- | --- | --- |
| Own-class creation exists but is restricted to Chemie 8/9 NTG; school year defaults to `2026_27` | `backend/app/services/class_provisioning.py`; `frontend/src/components/klassenpilot/create-class-card.tsx` | Keep supported scope explicit and make onboarding work for a real new class. |
| Beta provisioning copies the seed wiki except `workflow` | `backend/app/services/beta.py:provision_tester` | Retain this demo mode as requested; add explicit empty provisioning and make own-class creation available alongside the demo. |
| Course library requires an approved `material.json`; ordinary plan-save promotion does not create that manifest | `backend/app/course_materials/store.py`; `backend/app/services/materials_scratch.py:promote_scratch_material` | A PDF saved through planning is durable but not automatically a course-library chapter. Unify discovery without bypassing extraction approval. |
| Teacher UI only edits part of the graph proposal; correction generation is not exposed | `frontend/src/components/klassenpilot/course/course-material-library.tsx`; `frontend/src/features/course-network/material-api.ts` | Completing a content review can still need developer intervention. |
| Imports have no complete teacher-facing discard/archive/duplicate recovery path | `backend/app/course_materials/import_service.py`; course material UI/routes | Wrong uploads and abandoned imports need a small, reversible recovery path. |
| Planner ignores query tokens shorter than four characters and falls back to the first three ranked IDs when there is no match | `backend/app/course_network/planning.py` | Short topics and “continue next lesson” can receive arbitrary map context. |
| Saved concept references exist, but the concept inspector does not show linked lessons | `backend/app/course_network/lesson_refs.py`; `learning-block-inspector.tsx` | Finish the promised navigation from map to actual planning/results evidence. |
| OCR task tracking is process-local; generation is request-bound; review failures are not uniformly translated into retryable outcomes | `backend/app/api/course_material_routes.py`; `DocumentReviewer`; `OpenAICourseNetworkReviewer` | Verify leave/reopen/restart and prevent duplicate work; retain one backend process. |
| Deployment documents disagree | `docs/pm_hub.md` describes future AWS hosting; `product_backlog.md` reports Railway beta; `deploy/railway/` exists | Verify actual hosted configuration and reconcile docs, rather than building another platform. |

Checkpoint: `d3e5638` is pushed; `fa184d3` is local and adds retryable generation failures plus factual proposal summaries. The latter push was blocked by automatic approval review pending approval of that additional payload. No new push is part of this planning change.

Previously recorded validation includes 231 frontend tests, typecheck, focused course backend checks and synthetic browser acceptance. Two known baseline backend failures were excluded from the broader run. These are historical results, not a fresh full release test.

## Delivery order

Each task should be a separately reviewable change with focused tests. Write the named regression cases first, observe the relevant failure, then implement and verify the behavior. Update agent contracts in the same change when write or context behavior changes.

### 1. Keep the beta demo and finish own-class onboarding

**Modify:** `backend/app/services/beta.py`, `beta_cli.py`, `class_provisioning.py`, `backend/app/api/routes.py`, `frontend/src/components/klassenpilot/create-class-card.tsx`, `frontend/src/app/page.tsx`.
**Create:** `backend/app/services/workspace_template.py`; `frontend/src/components/klassenpilot/create-class-card.rendered.test.ts`.
**Existing tests:** `backend/tests/test_beta_auth_telemetry.py`, `test_class_provisioning.py`, `test_api_class_provisioning.py`.

- [x] Add `initialize_teacher_workspace(seed_root: Path, destination: Path, *, mode: Literal["empty", "demo"] = "empty") -> None` in `workspace_template.py`. Explicitly copy reviewed shared subject/framework assets; initialize an empty class index and fresh global memory files using the existing wiki schema. Publish a completed staged directory; leave an existing destination unchanged. Do not copy personal files and then delete a blacklist.
- [x] Route new beta provisioning through that function. Add CLI `--workspace-mode empty|demo`, default `demo` for this closed beta. Preserve existing workspaces on re-provision.
- [x] Test a deliberately contaminated seed containing a fake teacher preference, demo lesson, uploaded PDF and workflow database: none appears in empty mode, reviewed chemistry routes still load, and re-provision leaves a teacher-created sentinel lesson intact.
- [x] Let the teacher confirm class label and school year, with defaults derived from current configuration/date rather than a fixed year. Keep the roster optional. Render actionable duplicate/unsupported-route errors.
- [x] After class creation, show the existing Course and Materials actions with a short next step: review the curriculum map and add a chapter. A blank class must honestly show no taught lessons.
- [x] Verify rendered form submission and a fresh beta login → create class → course route. No direct database/wiki seeding may substitute for this acceptance path.

**Deliverable:** An invited teacher can explore the demo and create a supported own class whose teaching history is empty. An explicitly empty workspace contains no demo classes.

### 2. Make both upload paths lead to one usable materials library

**Modify:** `backend/app/services/materials_scratch.py`, `backend/app/teacher_agent/wiki/materials.py`, `backend/app/course_materials/{models,store,import_service,sections}.py`, `backend/app/api/course_material_routes.py`, `frontend/src/components/klassenpilot/course/course-material-library.tsx`, `frontend/src/features/course-network/{material-api,material-types}.ts`.
**Tests:** `backend/tests/test_materials_plan_api.py`, `test_api_course_materials.py`, `test_course_material_import.py`, `test_course_material_sections.py`; `course-material-library.rendered.test.ts`.

- [x] Add a library listing state for legacy/plan-saved materials that lack an approved course manifest: “Saved with a lesson — review for course map.” Keep the current material ID and source asset. Unsaved scratch uploads must remain absent.
- [x] Add an explicit “Review for course map” action that opens a normal course-material import draft from the already saved OCR package, preserving source/page provenance and assigning stable section IDs. Reuse OCR output; do not charge for another OCR run simply to normalize the package. Approval publishes the manifest; graph changes still require their separate approval.
- [x] Make publication reject conflicting reuse of the material ID and preserve old lesson citations. Test repeated normalization/approval for idempotency, and verify the existing plan-only upload path still works without a map.
- [x] Expose discard for unfinished imports using the existing draft lifecycle. Add a duplicate warning keyed by source content **and selected pages**; offer the existing material instead of silently importing again. Different selected chapters in the same PDF remain valid.
- [x] Add reversible archive/unarchive for approved materials. Proposed API: `PATCH /classes/{class_id}/course/materials/{material_id}/archive` with `{ "archived": true|false }`. Store archive state separately from the approved content manifest. Exclude archived content from new automatic retrieval and enrichment; preserve source access for historical citations and show archived mappings honestly.
- [x] Add editable page bounds for extraction sections, validated against the selected source pages. Preserve stable IDs when correcting text/titles/bounds; any edit invalidates review. Show the actual PDF pages beside correction controls.

**Contract checks:** Before plan save, no library item. After plan save, an unreviewed saved item. After explicit section approval, a mappable item with the same material ID. After archive, old lesson source links still resolve but new plans do not automatically receive that material.

**Deliverable:** Teachers can find their saved materials, recover from the wrong upload, and connect either upload path to the map without re-uploading the document.

### 3. Let teachers finish a chemistry review themselves

**Modify:** `frontend/src/components/klassenpilot/course/course-material-library.tsx`, `course-network-adoption.tsx`, `frontend/src/features/course-network/material-api.ts`, `backend/app/course_materials/import_service.py`, `backend/app/course_network/review.py`, `backend/app/api/course_material_routes.py`.
**Create:** `frontend/src/components/klassenpilot/course/course-change-editor.tsx` and its rendered test; keep proposal controls separate from the material library page.
**Tests:** `backend/tests/test_course_network_review.py`, `test_course_network_edits.py`, `test_api_course_materials.py`; existing rendered library tests.

- [x] Expose the backend's existing `purpose: "correction"` generation path as “Suggest a correction,” with a bounded teacher request. Use the existing typed proposal and exact-revision approval flow.
- [x] Add proposal controls for concept title, description and learning goal, and relationship endpoints/type. Display concept names and “requires / related to” wording; retain canonical IDs underneath. Continue supporting material mapping target/relation/note edits.
- [x] When a teacher rejects a proposed new concept, explain dependent proposed edges/mappings and remove or explicitly resolve those proposal rows before saving. Never silently change the adopted graph.
- [x] Test correcting a learning goal and reversing a mistaken prerequisite, saving, invalidating the old review, re-reviewing and approving. The summary must describe the edited operations, not stale model prose.
- [x] Extend bounded malformed-output/timeout handling to document and graph reviewers. A failed review leaves the exact proposal intact, does not confer approval, and shows retry. A successful retry reviews the same current revision.
- [x] Run the chemistry review in the browser: check particle-model accuracy, prerequisite direction, concept granularity, source support and partial curriculum coverage. Apply at least one teacher correction using UI controls only.

**Deliverable:** A teacher can inspect, explain and fix a proposal without a developer sending a PUT request or editing JSON.

### 4. Finish map-to-lesson use and evidence navigation

**Modify:** `backend/app/course_network/planning.py`, `lesson_refs.py`, relevant course-network API response/route definitions, `frontend/src/components/klassenpilot/course/learning-block-inspector.tsx`, course frontend types/API client.
**Tests:** `backend/tests/test_course_planning_context.py`, `test_course_lesson_refs.py`, `test_course_network_api.py`; rendered workspace tests.

- [x] Keep deterministic bounded retrieval, but recognize meaningful short topic tokens and prefer the current request, then explicit runtime/current-unit evidence for continuation requests. If neither identifies a topic, return an honest compact map overview/available topics rather than treating the first three IDs as relevant evidence.
- [x] Add regression cases for two unrelated approved chapters, a short query token, a continuation request, no match, no graph, and archived materials. Only authorized class material may be returned.
- [x] Budget context by complete evidence sections rather than truncating the final string. Record only the nodes/material sections actually injected in `runtime.course_context`. Keep detailed evidence available through existing tools.
- [x] Add read-only lesson associations to the concept inspector using existing `course_refs.json` and approved results. Distinguish “Referenced in plan” from “Approved lesson results”; link to the normal lesson detail. A saved plan alone must never label a concept taught or mastered.
- [x] Verify normal planning automatically uses the relevant new chapter without selecting map nodes or re-uploading PDFs. Save, record approved results, then verify the next plan uses the actual reported outcome and unfinished work.

**Deliverable:** The map is useful both as a teacher's content overview and as navigation for source-grounded planning, with visible links back to lesson evidence.

### 5. Verify recovery, workspace isolation and the existing hosted deployment

**Modify as findings require:** `backend/app/api/course_material_routes.py`, existing course services and `backend/app/services/workflow_drafts.py`; `deploy/railway/backend/{Dockerfile,railway.toml}` only if configuration needs correction.
**Tests:** `backend/tests/test_course_publication_races.py`, `test_api_course_materials.py`, `test_beta_auth_telemetry.py`.
**Create:** `backend/tests/test_course_beta_isolation.py` and `docs/course_release_runbook.md`.

- [x] Record a course generation reservation in the existing durable draft store before the model call, scoped to workspace/class/purpose and input revision/hash. Reuse or reject an identical active request. Persist completion/failure; do not add a new general job system.
- [x] Make leave/reopen show a pending operation and let interrupted work retry from saved input. Exercise two tabs, browser reload, failed OCR, malformed review, backend restart and stale publication. No duplicate approved chapter or network revision may result.
- [x] Extend existing beta isolation tests to course routes: two accounts with the same class ID; draft/status/source-PDF/section/map reads and writes must resolve only within the authenticated workspace. Repeat with identical material/draft identifiers in fixtures. Existing generic beta tests alone are insufficient evidence for new routes.
- [ ] Inspect actual hosted settings before deployment. Repository Railway configuration already specifies one replica and one uvicorn process; preserve that assumption. Verify persistent beta volume, cookie/session behavior, frontend API routing and source-PDF access after restart.
- [x] Document and rehearse backup/restore of wiki files plus associated workflow/identity databases in a disposable workspace. Record restoration of an approved map, material source, saved lesson and pending draft. Verify model/OCR secrets are configured without printing their values.
- [x] Reconcile the existing material-processing disclosure and beta operator trace/access/retention guidance with these uploads. Do not introduce a new broad compliance system or an unrelated infrastructure migration.

**Deliverable:** The existing private deployment can host separate teachers and recover their course workflow without silently losing or mixing data.

### 6. Run the release acceptance and reconcile the handoff

**Modify:** `docs/pm_hub.md`, `implementation_plans/product_backlog.md`, `docs/course_graph_guide.md`, `docs/agent_contracts.md`, `docs/memory_hierarchy.md`, `frontend/ARCHITECTURE.md`, this directory's README and validation record where applicable.
**Create:** `implementation_plans/course_network/09_teacher_owned_release_acceptance.md` during execution to record actual results.

- [x] Establish the local implementation checkpoint including the pending `fa184d3` follow-up. The commit containing the acceptance record captures the tested source; migration assumptions and rollback checkpoint are documented in the runbook.
- [ ] Integrate and push the release candidate once the outstanding push authorization is resolved; do not conflate committed, pushed, merged and deployed.
- [x] Run focused tests for each task, then the broader deterministic suite and frontend tests/typecheck/production build. Diagnose the two previously excluded baseline tests: `test_memory_sweep_review_api_explains_new_candidates_that_make_a_draft_stale` and `test_proposal_sends_singletons_to_the_second_judge[asyncio]`. Fix them or document an explicitly reviewed quarantine with ownership; report any non-green release suite honestly.
- [x] Run the fresh-teacher browser scenario in an isolated beta stack using synthetic material. Record observed outcomes, normal teacher corrections, deterministic-only coverage and browser limitations in the acceptance record.
- [ ] Smoke-test the release candidate on the existing hosting target. Local evidence does not substitute for hosted validation.
- [x] Replace obsolete “implementation not started” claims with implementation/verification/deployment distinctions. Reconcile Railway versus AWS documentation. Update the teacher guide to match actual correction, upload and recovery controls.
- [ ] Pilot with a teacher creating their own class and material set. Ship this bounded release when the acceptance gates pass; capture additional subject support and advanced graph features separately.

Suggested deterministic commands from the feature worktree (no paid model calls):

```powershell
# Backend: run the task-specific test files above using this interpreter.
.\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_class_provisioning.py backend/tests/test_beta_auth_telemetry.py backend/tests/test_api_course_materials.py backend/tests/test_course_planning_context.py backend/tests/test_course_lesson_refs.py
.\scripts\test.ps1
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
```

## Fresh-teacher browser release gate

1. Provision a **new demo beta account**. Log in through the browser, set teacher preferences, and create a Chemie 8 class with no roster required. The demo remains available; the new class has no prior lessons. Also verify an explicitly empty account has no demo classes.
2. Adopt/review its supported partial curriculum map. Upload a teacher-authored chapter on chemical reactions and a second, different chapter through ordinary planning. Save that plan and discover its PDF in the course library; convert it through section review without re-uploading.
3. Include a scanned/formula/table page and noncontiguous page selection in the test material. Inspect original pages; correct one section boundary or transcription error; verify changes invalidate review. Cover unsupported/oversized input, duplicate upload, discard and archive recovery.
4. Generate mappings, correct a learning goal or prerequisite, reject one suggested change, re-review and approve. Reload; verify the intended concepts, edges and material links persist and source pages resolve.
5. Ask for a lesson on the first chapter without attaching it again. Check the plan uses that chapter's evidence, not the unrelated chapter or demo memory. Save through the normal approval flow.
6. Record an actual simulated outcome and an unfinished activity through Update Memory; inspect and approve the proposal. Request the next lesson without repeating those facts. Verify appropriate recall and no invented mastery.
7. From the map, follow the saved plan/result links. From the lesson, open its source PDF. Archive a material and verify historical citations still open while it disappears from new automatic retrieval.
8. Leave/reopen during OCR/generation, retry a controlled failure, and restart the backend. Repeat a request in two tabs. Confirm recoverable state and no duplicate publication.
9. Log in as a second teacher with an identically named class. Verify neither teacher can read or mutate the other's map, materials, drafts or source assets. Smoke-test the existing Chemie 9 flow for compatibility.

Pass only when steps 1–9 use product UI for teacher actions, persisted data matches the displayed result, no developer repair is needed, and the tested build is identified. API/file inspection may verify outcomes but may not substitute for teacher controls.

## Suggested first change

Start with Task 1. It creates the environment in which the remaining work can be tested honestly. Keep the graph architecture and existing planning loop; the work is to finish their connections and make the teacher journey self-sufficient.
